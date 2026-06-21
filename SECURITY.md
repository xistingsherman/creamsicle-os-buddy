# Security Policy

## Scope

Creamsicle: OS Buddy writes directly to physical drives using raw Win32 API calls and `diskpart`. Security issues in this area are taken seriously.

Vulnerabilities in scope:
- Drive selection bypass (writing to a non-removable or system drive)
- Path traversal in file upload or image path handling
- Command injection via user-supplied fields (hostname, username, WiFi SSID, etc.)

## Reporting a Vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities.

Instead, report them privately by emailing the maintainer directly (see the email on the GitHub profile) or by using GitHub's private vulnerability reporting feature if enabled on this repository.

Include:
- A description of the vulnerability
- Steps to reproduce
- The potential impact
- Any suggested fix (optional)

You can expect an acknowledgement within 72 hours.
