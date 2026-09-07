# Security Policy & Vulnerability Disclosure

## 1. Supported Versions
Security updates are actively applied to the main development branch.

| Version | Supported |
| :--- | :--- |
| AlphaQuant Target Modular Architecture | Yes |
| AlphaQuant V8.2 Legacy | Maintenance Mode |
| SCALPER_HUNT | Deprecated |

---

## 2. Reporting a Vulnerability
If you discover a security vulnerability (such as an exposed API key, unhandled financial overflow, or authentication bypass), please do **NOT** open a public issue on GitHub.

Report the issue directly to the lead security maintainer at:
`security@alphaquant.internal` or via direct encrypted channel.

---

## 3. Mandatory Security Rules
1. **No Live Trading by Default**: All deployments must default to `USE_TESTNET=True` and `SIMULATION_MODE=True`.
2. **No Withdrawal Permissions**: API keys must strictly have withdrawal capabilities **disabled**.
3. **No Committing Secrets**: Never commit `.env`, `*.pem`, or plaintext passwords.
