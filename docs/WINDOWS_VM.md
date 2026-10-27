# Windows research VM

1. Create a dedicated updated Windows VM using your organization's approved hypervisor and a clean installation image. Take a clean snapshot.
2. Use a standard non-administrator research account. Administrator access should only be used for approved operating-system maintenance.
3. Disable shared host drives, clipboard integration and drag-and-drop where practical. Do not mount host credentials or personal folders. Do not import personal browser profiles or sign into unrelated accounts.
4. Keep Defender, firewall, Windows updates and browser sandboxing enabled. Restrict unnecessary inbound/outbound access according to your network policy. Never use a public tunnel for the dashboard.
5. Install Python from python.org, Git from its trusted distribution, and reviewed pinned dependencies. Use a project folder such as `C:\Research\product-opportunity-finder` with normal user write permissions. If Controlled Folder Access blocks a folder, choose an approved writable development location; do not disable protection.
6. Take a snapshot before installing new dependencies, downloading Chromium or enabling new connectors. Treat a virtual environment as dependency management, not a sandbox.
7. Set Google OAuth environment variables only inside the VM. Use the minimum account access required; revoke refresh tokens when the VM is retired. Environment and disk data are not encrypted by the application; use approved disk protection.
8. Start with demo/import mode. Review provider access terms before enabling any network connector. Avoid personal sessions and executable downloads. Optional browser contexts are ephemeral and have JavaScript disabled.
9. Back up research data separately while the app is stopped. Treat exported worksheets as untrusted and open them with Office protections enabled. Formula injection is mitigated, not a replacement for endpoint defenses.

Normal operation requires no administrator privileges. Initial Python/Git/VM installation may require your administrator according to local policy.
