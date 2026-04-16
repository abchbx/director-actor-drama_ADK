---
phase: 08
slug: dynamic-storm
status: verified
threats_open: 0
asvs_level: 1
created: 2026-04-13
---

# Phase 08 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| LLM Response → parse_llm_perspectives() | External LLM output parsed into structured data | JSON text → dict list (injection risk) |
| State Dict → dynamic_storm functions | Internal state passed to pure functions | state: dict (mutation risk) |
| trigger_storm → dynamic_storm | Sync→Async bridge for backward compatibility | ToolContext, focus_area (exception risk) |
| discover_perspectives_prompt → LLM | Full drama state assembled into prompt | All story data (information exposure) |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-08-01 | Tampering | parse_llm_perspectives() | mitigate | Graceful degradation: invalid JSON → empty list; non-dict items skipped; empty name/desc skipped; questions coerced to strings | closed |
| T-08-02 | Tampering | update_dynamic_storm_state() | mitigate | In-place mutation is by design (caller owns state); trigger_history trimmed to MAX_TRIGGER_HISTORY=10; missing fields auto-initialized | closed |
| T-08-03 | Denial of Service | parse_llm_perspectives() | accept | No size limit on parsed array; LLM could return extremely long list. Accept: downstream consumer (Director) handles large inputs; STORM design limits to 1-2 perspectives per trigger via prompt | closed |
| T-08-04 | Information Disclosure | discover_perspectives_prompt() | mitigate | Prompt includes full story state (perspectives, conflicts, actors, scenes, outline). This is by design — LLM needs context for quality output. Data stays within LLM API call, not persisted externally | closed |
| T-08-05 | Elevation of Privilege | trigger_storm backward compat | mitigate | Sync→Async bridge uses ThreadPoolExecutor fallback; DeprecationWarning on get_event_loop() is non-blocking; both paths catch RuntimeError | closed |
| T-08-06 | Spoofing | check_keyword_overlap() | mitigate | Overlap does NOT block generation — only warns. OVERLAP_THRESHOLD=0.6 prevents false positives from dominating | closed |
| T-08-07 | Repudiation | trigger_history | mitigate | Every trigger recorded with scene, type, focus_area, perspectives_found. History capped at MAX_TRIGGER_HISTORY for storage sanity | closed |

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-08-01 | T-08-03 | No hard size limit on LLM response parsing. Prompt instructs 1-2 perspectives; downstream handles larger lists. Low likelihood, low impact. | Security Audit | 2026-04-13 |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-04-13 | 7 | 7 | 0 | gsd-secure-phase |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-04-13
