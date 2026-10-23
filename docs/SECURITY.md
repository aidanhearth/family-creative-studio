# Local-use boundary

This project is a single-user local creative tool, not an Internet-facing multi-tenant service. Publishing its source does not deploy its web server.

- The server binds to loopback (or an explicitly selected Unix socket inside its state directory). Requests enforce local Host/Origin rules and a session token. These are not user authentication or tenant isolation.
- Render children use Linux network and PID namespaces, timeouts, output-log limits and process-group cancellation. Bubblewrap binds the host filesystem read/write under the current user's permissions. It is **not filesystem isolation**, and the rendering Chromium is started with `--no-sandbox` inside this boundary.
- Work with trusted inputs and a dedicated unprivileged account or an additional OS/container boundary when needed. Do not mount unrelated credentials into a shared or untrusted deployment. Do not run as root.
- Setup downloads pinned public source and locked packages over the network. Rendering disables selected upstream update/telemetry features and isolates subprocess networking. This does not constitute a full audit of every dependency.
- Keep `.state`, imported media, generated outputs, logs, `.env`, and local configuration outside Git. State contains private content and media.
- No paid model API is invoked by the current renderer. Images are imported or represented by prompts; generated draft speech uses local eSpeak NG. Models/voices from other products are not included.

For sensitive vulnerability reports, use the repository's private vulnerability reporting option if enabled. Do not post credentials or private project data in a public issue. If no private channel is configured, open a minimal issue requesting one without exploit-sensitive details.
