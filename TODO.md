# TODO

Security and code quality items identified during internal audit (March 2026).

---

## Security

### Medium

- [ ] **Add auth to `/events` SSE endpoint** — currently unauthenticated; anyone on the network can read the live security event stream. Add session cookie, API key header, or restrict to localhost only.

- [ ] **Async lock for `block_injections` toggle** — `settings.block_injections` is mutated without synchronization. Add `asyncio.Lock()` around reads/writes in `proxy.py` and `main.py`. Low probability of impact but worth fixing.

- [ ] **Generic domain filter error messages** — `check_domain()` returns `"domain 'x' is not in the whitelist"`, leaking filter mode to callers. Return a generic `"domain not allowed"` message; keep detail in server-side logs only.

- [ ] **Expand credential scanner patterns** — current patterns cover OpenAI, Anthropic, AWS, Google, GitHub, Slack, JWT. Missing:
  - SSH/PEM private keys (`-----BEGIN RSA/EC PRIVATE KEY-----`)
  - MongoDB connection strings (`mongodb+srv://user:pass@...`)
  - GCP service account JSON (`private_key_id`)
  - Consider entropy-based detection for unknown key formats

- [ ] **Unicode normalization before injection scanning** — regex patterns can be bypassed via zero-width spaces, homoglyphs, or newline insertion. Run `unicodedata.normalize('NFKC', text)` before scanning in `scanner.py`.

### Low

- [ ] **Rate limiting on sensitive endpoints** — `/events`, `/settings/block-injections`, and `/wizard/generate` have no rate limiting. Add `slowapi` or similar middleware for production deployments.

- [ ] **Restrict `/hardening` endpoint** — currently exposes whether Landlock/Seatbelt is active to any caller. Consider restricting to localhost or removing from public API.

- [ ] **Startup validation for domain filter** — if `AEGIS_DOMAIN_FILTER_MODE=whitelist` but `AEGIS_DOMAIN_WHITELIST` is empty, log a loud warning at startup so operators don't accidentally block all outbound traffic silently.

- [ ] **Document Docker socket mount in dev compose** — `docker-compose.dev.yml` mounts `/var/run/docker.sock` with no explanation. Add a comment noting it grants container-escape capability and is intentional for agent launching.

---

## Features

- [ ] **`install.sh`** — single `curl | bash` bootstrap that pulls images and opens the wizard in the browser. See `install.sh` for draft.

- [ ] **Agent Builder** — full in-UI agent creation flow for non-technical users. No Mako required. See `docs/agent-builder.md` for full spec.

- [ ] **Gemini proxy** — TLS termination for providers that don't support `ANTHROPIC_BASE_URL`-style override.

- [ ] **VPS deploy** — wizard generates SSH deploy commands for remote servers.
