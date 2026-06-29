# Security Policy

Hardflow is a Blender add-on (Python). It does not handle network requests,
credentials, or sensitive data, so the attack surface is small. Still, we take
any potential issue seriously — for example, a `.blend` asset library or decal
image that could cause Blender to execute unexpected code on load.

## Supported Versions

Only the latest released version receives fixes. Hardflow targets **Blender 4.2
LTS and newer**.

| Version | Supported |
|---------|-----------|
| 1.2.x   | ✅        |
| < 1.2   | ❌        |

## Reporting a Vulnerability

**Please do not open a public issue for security problems.**

Instead, report privately via either:

- GitHub's [private vulnerability reporting](https://github.com/ugulay/hardflow/security/advisories/new)
  (Security → Report a vulnerability), or
- Email **ugurgulay@gmail.com** with the subject line `Hardflow security`.

Please include:

- A description of the issue and its impact
- Steps to reproduce (a minimal `.blend` or asset folder if relevant)
- The Hardflow version and Blender version

You can expect an initial response within **7 days**. Once a fix is ready we will
release it and credit you in the release notes, unless you prefer to remain
anonymous.
