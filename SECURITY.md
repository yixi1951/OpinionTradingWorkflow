# Security Policy

## 支持的版本 / Supported Versions

This project is a personal research portfolio. Currently, only the latest
commit on the `main` branch receives security-related fixes.

| Version | Supported          |
| ------- | ------------------ |
| main    | :white_check_mark: |
| other   | :x:                |

## 报告漏洞 / Reporting a Vulnerability

If you discover a security vulnerability, please **do not** open a public issue.
Instead, send a private email to the repository owner or open a
[confidential issue](https://docs.github.com/en/issues/security-issue-templates)
via GitHub's security advisory feature.

We will acknowledge receipt within **48 hours** and provide an estimated
timeline for a fix. Critical vulnerabilities will be addressed as a priority.

## 安全注意事项 / Security Notes

- **API Keys / Tokens**: Store in environment variables, never commit to the repository.
- **WebSocket Credentials**: The `WS_GATEWAY_TOKEN` and `OPENCLAW_TOKEN` should be
  rotated regularly and scoped to the minimum required permissions.
- **Dependency Scanning**: Run `pip-audit` or Dependabot periodically to detect
  known vulnerabilities in dependencies.
- **Network Access**: The OpenClaw Gateway and WS Proxy should be bound to
  `127.0.0.1` in production to avoid exposing internal APIs to the network.
