# Security policy

Run under a standard Windows user in an isolated research VM. Keep Defender, firewall and browser sandboxing enabled. A Python virtual environment isolates dependencies, not hostile code. Keep research separate from personal browser profiles and sensitive files.

All external responses are untrusted. Product data never becomes executable Python, shell commands or AI instructions. UI inputs cannot launch commands. Network adapters accept allowlisted HTTPS endpoints only, check every resolved address, pin an approved public IP while preserving TLS hostname verification, reject all redirects, ignore environment proxies, impose timeouts and stop after bounded retries. Responses are capped at 5 MiB after decompression. Imports are 10 MiB/10,000 rows. Access denials/rate limits stop collection.

No secrets belong in CSV, URLs, source settings, logs, SQLite or Git. Google OAuth is read only from environment variables and transmitted only by the official client to Google's endpoints. Environment variables can still be inspected by a compromised same-user process. Rotate credentials by replacing/revoking tokens, restarting the application and checking access logs in Google Cloud. Do not enable HTTP/gRPC debug logging. Protect VM disks and backups.

Report vulnerabilities privately to the repository owner through an approved private channel or GitHub private vulnerability reporting if enabled. Do not post credentials, private datasets or exploit details in public issues. No response-time guarantee is established.

Known residual risks include browser/parser defects, malicious dependency updates, misleading merchant data, local account compromise, and incomplete heuristics for identity/demand. Defense in depth reduces risk; the application is not impossible to compromise. See docs/THREAT_MODEL.md.
