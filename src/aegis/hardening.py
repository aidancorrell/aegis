"""Kernel-level security hardening.

Linux:  Landlock (kernel 5.13+) — filesystem write restriction via syscall.
        Jails write access to workspace + /tmp at the kernel level.

macOS:  Seatbelt / sandbox_init — Apple's kernel sandbox (XNU Sandbox.framework).
        Applies "no-write-except-temporary" named profile: kernel-blocks all
        writes outside /tmp. Reads and network are unrestricted.
        Works because local dev workspace is already in /tmp.

Both platforms fall back gracefully if the kernel feature is unavailable.
"""

import ctypes
import ctypes.util
import logging
import os
import platform
import struct
from dataclasses import dataclass
from pathlib import Path

from .events import SecurityEvent, bus

logger = logging.getLogger(__name__)

_IS_LINUX = platform.system() == "Linux"
_IS_MACOS = platform.system() == "Darwin"
_MACHINE = platform.machine()

# Landlock syscall numbers — same on x86_64 and aarch64 (generic ABI, kernel 5.13+)
_NR_LANDLOCK_CREATE_RULESET = 444
_NR_LANDLOCK_ADD_RULE = 445
_NR_LANDLOCK_RESTRICT_SELF = 446

_PR_SET_NO_NEW_PRIVS = 38

# Landlock access-right bitmasks (ABI v1)
_FS_EXECUTE     = 1 << 0
_FS_WRITE_FILE  = 1 << 1
_FS_READ_FILE   = 1 << 2
_FS_READ_DIR    = 1 << 3
_FS_REMOVE_DIR  = 1 << 4
_FS_REMOVE_FILE = 1 << 5
_FS_MAKE_CHAR   = 1 << 6
_FS_MAKE_DIR    = 1 << 7
_FS_MAKE_REG    = 1 << 8
_FS_MAKE_SOCK   = 1 << 9
_FS_MAKE_FIFO   = 1 << 10
_FS_MAKE_BLOCK  = 1 << 11
_FS_MAKE_SYM    = 1 << 12

# All write-mutating operations (what we restrict to workspace+tmp only)
_ALL_WRITE = (
    _FS_WRITE_FILE | _FS_REMOVE_DIR | _FS_REMOVE_FILE |
    _FS_MAKE_CHAR | _FS_MAKE_DIR | _FS_MAKE_REG |
    _FS_MAKE_SOCK | _FS_MAKE_FIFO | _FS_MAKE_BLOCK | _FS_MAKE_SYM
)

_RULE_PATH_BENEATH = 1


# ctypes structures matching kernel ABI
class _RulesetAttr(ctypes.Structure):
    _fields_ = [("handled_access_fs", ctypes.c_uint64)]


class _PathBeneathAttr(ctypes.Structure):
    _pack_ = 1  # __attribute__((packed))
    _fields_ = [
        ("allowed_access", ctypes.c_uint64),
        ("parent_fd", ctypes.c_int32),
    ]


def _libc():
    return ctypes.CDLL(None, use_errno=True)


def _syscall(nr: int, *args) -> int:
    lib = _libc()
    fn = lib.syscall
    fn.restype = ctypes.c_long
    result = fn(ctypes.c_long(nr), *[ctypes.c_long(a) for a in args])
    if result == -1:
        errno = ctypes.get_errno()
        raise OSError(errno, os.strerror(errno))
    return result


def _prctl(option: int, arg2: int) -> None:
    lib = _libc()
    result = lib.prctl(ctypes.c_int(option), ctypes.c_ulong(arg2),
                       ctypes.c_ulong(0), ctypes.c_ulong(0), ctypes.c_ulong(0))
    if result == -1:
        errno = ctypes.get_errno()
        raise OSError(errno, os.strerror(errno))


def _landlock_create_ruleset(handled_access_fs: int) -> int:
    attr = _RulesetAttr(handled_access_fs=handled_access_fs)
    return _syscall(
        _NR_LANDLOCK_CREATE_RULESET,
        ctypes.addressof(attr),
        ctypes.sizeof(attr),
        0,
    )


def _landlock_add_rule(ruleset_fd: int, allowed_access: int, parent_fd: int) -> None:
    attr = _PathBeneathAttr(allowed_access=allowed_access, parent_fd=parent_fd)
    _syscall(
        _NR_LANDLOCK_ADD_RULE,
        ruleset_fd,
        _RULE_PATH_BENEATH,
        ctypes.addressof(attr),
        0,
    )


def _landlock_restrict_self(ruleset_fd: int) -> None:
    _syscall(_NR_LANDLOCK_RESTRICT_SELF, ruleset_fd, 0)


@dataclass
class HardeningStatus:
    landlock_active: bool = False
    landlock_reason: str = ""
    no_new_privs: bool = False
    seatbelt_active: bool = False
    seatbelt_reason: str = ""
    platform: str = ""


def _apply_seatbelt() -> tuple[bool, str]:
    """Apply macOS Seatbelt via sandbox_init(). Returns (success, reason)."""
    # "no-write-except-temporary": kernel-blocks all writes outside /tmp.
    # Reads and network are unrestricted — Python stdlib and API calls work fine.
    # Works for Aegis because the local workspace lives in /tmp.
    _PROFILE = b"no-write-except-temporary"

    try:
        lib = ctypes.CDLL("libsandbox.1.dylib", use_errno=True)
    except OSError:
        return False, "libsandbox.1.dylib not found"

    try:
        fn = lib.sandbox_init
        fn.argtypes = [ctypes.c_char_p, ctypes.c_uint64, ctypes.POINTER(ctypes.c_char_p)]
        fn.restype = ctypes.c_int

        _SANDBOX_NAMED = ctypes.c_uint64(1)
        error_buf = ctypes.c_char_p()
        result = fn(_PROFILE, _SANDBOX_NAMED, ctypes.byref(error_buf))

        if result == 0:
            return True, ""
        else:
            msg = error_buf.value.decode() if error_buf.value else "unknown error"
            try:
                lib.sandbox_free_error(error_buf)
            except Exception:
                pass
            return False, f"sandbox_init failed: {msg}"

    except Exception as e:
        return False, str(e)


def apply(workspace_path: str, audit_path: str) -> HardeningStatus:
    """Apply kernel hardening. Call once at startup before serving requests."""
    status = HardeningStatus(platform=platform.system())

    if _IS_MACOS:
        success, reason = _apply_seatbelt()
        status.seatbelt_active = success
        status.seatbelt_reason = reason
        if success:
            logger.info("Seatbelt active — writes kernel-jailed to /tmp (no-write-except-temporary)")
        else:
            logger.warning("Seatbelt: %s", reason)
        # Still try Landlock path below — will gracefully skip on non-Linux
        status.landlock_reason = f"unavailable on {platform.system()}"
        _emit(status)
        return status

    if not _IS_LINUX:
        status.landlock_reason = f"unavailable on {platform.system()}"
        _emit(status)
        return status

    if _MACHINE not in ("x86_64", "aarch64", "arm64"):
        status.landlock_reason = f"unsupported architecture: {_MACHINE}"
        _emit(status)
        return status

    try:
        # Require no_new_privs — prevents privilege escalation and is required for Landlock
        _prctl(_PR_SET_NO_NEW_PRIVS, 1)
        status.no_new_privs = True
        logger.info("Landlock: no_new_privs set")
    except OSError as e:
        status.landlock_reason = f"prctl failed: {e}"
        _emit(status)
        return status

    try:
        # Create ruleset: we handle all write operations
        ruleset_fd = _landlock_create_ruleset(_ALL_WRITE)
    except OSError as e:
        if e.errno == 95:  # EOPNOTSUPP
            status.landlock_reason = "kernel < 5.13 (upgrade to enable)"
        else:
            status.landlock_reason = f"create_ruleset failed: {e}"
        logger.warning("Landlock: %s", status.landlock_reason)
        _emit(status)
        return status

    try:
        # Allow writes only to: workspace, audit dir, /tmp
        allowed_paths = [workspace_path, audit_path, "/tmp"]
        for path_str in allowed_paths:
            path = Path(path_str)
            path.mkdir(parents=True, exist_ok=True)
            fd = os.open(str(path), os.O_PATH | os.O_DIRECTORY)
            try:
                _landlock_add_rule(ruleset_fd, _ALL_WRITE, fd)
            finally:
                os.close(fd)

        # Engage — from this point, writes outside allowed paths are kernel-blocked
        _landlock_restrict_self(ruleset_fd)
        os.close(ruleset_fd)

        status.landlock_active = True
        logger.info(
            "Landlock active — writes kernel-jailed to %s",
            ", ".join(allowed_paths),
        )

    except OSError as e:
        status.landlock_reason = f"rule application failed: {e}"
        logger.warning("Landlock: %s", status.landlock_reason)
        try:
            os.close(ruleset_fd)
        except Exception:
            pass

    _emit(status)
    return status


def _emit(status: HardeningStatus) -> None:
    kernel_active = status.landlock_active or status.seatbelt_active
    bus.emit(SecurityEvent(
        type="TOOL_CALL",
        severity="info" if kernel_active else "warn",
        data={
            "tool": "hardening",
            "landlock": "active" if status.landlock_active else f"inactive ({status.landlock_reason})",
            "seatbelt": "active" if status.seatbelt_active else f"inactive ({status.seatbelt_reason})",
            "no_new_privs": status.no_new_privs,
            "platform": status.platform,
        },
    ))


# Module-level status — set by apply(), read by dashboard endpoint
status: HardeningStatus = HardeningStatus()
