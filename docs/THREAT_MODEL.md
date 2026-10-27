# Threat model

Assets: host/VM integrity, OAuth credentials, research history, private repository, exported datasets. Trust boundaries: untrusted internet responses/imports → validation → immutable storage → calculations/UI/exports; environment OAuth → official Google client; local browser → localhost UI.

| Threat | Controls | Residual risk |
|---|---|---|
| SSRF/rebinding/metadata access | HTTPS allowlist, all DNS addresses public, IP-pinned connection, TLS SNI, redirects blocked, no env proxy | Network stack/TLS vulnerabilities; trusted API client's own behavior |
| Hostile page/browser exploit | Dedicated VM, ephemeral sandboxed browser, scrubbed child environment; static parsers disable JS, native profile restricts destinations/read operations and requests | Native site JavaScript/browser defects, asset allocation and VM escape risks; not a hard OS memory quota |
| Huge or malformed content | Byte/row limits, strict numeric/schema validation, safe JSON/HTML parsing, bounded collection | Python parser resource use inside capped documents; no hard OS memory quota |
| Credential leakage | Env-only OAuth, ignore rules, safe event fields, generic external errors, private repository, scan before commits | Same-user process compromise, debug logging enabled outside app, human mistakes |
| Malicious spreadsheet content | Prefix dangerous leading characters, remove illegal controls, exports held in memory, fixed download names | Office vulnerabilities, users removing escaping |
| Dependency compromise | Reputable packages, exact pins/hashes, review updates, pip-audit, SHA-pinned CI | Unknown vulnerabilities and compromised upstream releases |
| Financial/data deception | Provenance, stale/missing states, conservative matching, explicit assumptions and reviews | False merchant claims; incorrect human overrides |
| Local server exposure | Launcher and config bind 127.0.0.1, XSRF/CORS enabled, no tunnels | Local malicious users/processes; manually overriding server flags |
| Arbitrary execution/path traversal | No eval/exec/pickle/shell execution in app; fixed local directories; safe filename helper | Trusted installed dependencies inherently execute Python |

No external content is sent to an AI system. Future AI functionality must treat external content as data, keep OS/secrets/tools isolated, and require approval for consequential actions. No current business execution features exist.
