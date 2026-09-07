# Target Security Architecture & Hardening Guide

## 1. Zero-Trust Security Architecture

The target security architecture enforces strict separation of privileges, secure credential management, network isolation, and non-privileged daemon execution:

```mermaid
graph TD
    subgraph Host Isolation
        NON_ROOT[Non-Privileged System User: alphaquant]
        DOT_ENV[Sanitized .env File - Mode 0600]
        UFW_RULES[UFW Firewall - Allow 22, 443, 8080 from Whitelist Only]
    end
    
    subgraph Secret Injection
        DOT_ENV -->|Read on Boot| APP[Application Memory]
    end
    
    subgraph Access Boundaries
        APP -->|Read/Write Local Only| DB[(PostgreSQL 127.0.0.1)]
        APP -->|Read/Write Local Only| REDIS[(Redis 127.0.0.1)]
        APP -->|TLS 1.3 Outbound| BN[Binance Futures API]
        APP -->|TLS 1.3 Outbound| TG[Telegram API]
    end
```

---

## 2. Hardening Standards

1. **Non-Root Execution**: All systemd services must execute under a dedicated `alphaquant` system user with `NoNewPrivileges=true` and `ProtectSystem=strict`.
2. **Secrets Storage**:
   * API keys and database passwords must reside strictly in an untracked `.env` file with POSIX permissions `chmod 600 .env`.
   * The repository `.gitignore` must strictly prohibit committing `.env`, `*.pem`, `*.key`, or credentials.
3. **Network & Firewall**:
   * PostgreSQL (port 5432) and Redis (port 6379) must bind exclusively to `127.0.0.1` and reject external ingress.
   * Web Dashboard (port 8080) should be reverse-proxied via Nginx with HTTPS (Let's Encrypt SSL) and HTTP Basic Authentication.
