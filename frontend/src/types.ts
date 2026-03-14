export type Severity = 'info' | 'warn' | 'high' | 'critical'

export type EventType =
  | 'LLM_REQUEST'
  | 'LLM_RESPONSE'
  | 'TOOL_CALL'
  | 'TOOL_BLOCKED'
  | 'INJECTION_PROBE'
  | 'INJECTION_BLOCKED'
  | 'CREDENTIAL_LEAK'
  | 'RATE_LIMIT_HIT'
  | 'PING'

export interface SecurityEvent {
  type: EventType
  severity: Severity
  data: Record<string, unknown>
  timestamp: string
}

export interface Stats {
  counts: {
    total: number
    injection: number
    blocked: number
    tool_calls: number
  }
  block_injections: boolean
  hardening: {
    platform: string
    landlock_active: boolean
    landlock_reason: string
    seatbelt_active: boolean
    seatbelt_reason: string
    no_new_privs: boolean
  }
}
