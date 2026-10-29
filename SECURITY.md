# 🛡️ Comprehensive Security Audit & Threat Model

**Platform**: Technozion CTF Game Server (Jumanji Edition)  
**Date of Audit**: October 2026  
**Audit Scope**: Web Endpoints, Authentication, WebSocket PTY, Docker Sandboxing, State Persistence, and Network Boundaries.  
**Compliance Standard**: OWASP Top 10 (2021), CIS Docker Benchmarks, NIST SP 800-115.

---

## 1. Executive Summary

A comprehensive source code security assessment and architectural threat analysis was conducted across the Technozion CTF Game Server codebase. The platform features robust foundational controls—including POSIX pseudo-terminal allocation (`pty.openpty()`) with non-root container users, dynamic HMAC-based flag derivation, and multi-tier permission checking.

However, the audit identified **12 actionable security vulnerabilities** ranging from High to Low severity across authentication, reverse-proxy subnet enforcement, in-memory state lifecycles, and cryptographic secrets management. 

### Vulnerability Summary Matrix

| ID | Title | Severity | CVSS v3.1 | Status |
|---|---|---|---|---|
| **SEC-01** | Missing Brute-Force Rate Limiting on Admin Login (`/login`) | **HIGH** | 7.5 | Action Required |
| **SEC-02** | Plaintext Admin Password Storage & Comparison | **HIGH** | 7.4 | Action Required |
| **SEC-03** | Docker Bridge Subnet Filter Bypass via Reverse Proxy / RFC 1918 Range | **HIGH** | 7.2 | Action Required |
| **SEC-04** | Insecure Fallback Cryptographic Secrets (`CTF_MASTER_SECRET`) | **MEDIUM** | 6.5 | Action Required |
| **SEC-05** | Unbounded Memory Growth & Zombie Tokens in `INTERNAL_TOKENS` | **MEDIUM** | 5.8 | Action Required |
| **SEC-06** | Missing `SESSION_COOKIE_SECURE` Flag in Flask Configuration | **MEDIUM** | 5.4 | Action Required |
| **SEC-07** | Unauthenticated Socket Proxy with Unsanitized Input on `/api/whois` | **MEDIUM** | 5.3 | Action Required |
| **SEC-08** | Incomplete CSRF Protection on Interactive State Mutation Routes | **MEDIUM** | 5.0 | Action Required |
| **SEC-09** | Empty List SQL Formatting Risk in Tournament Phase Advancement | **LOW** | 3.7 | Action Required |
| **SEC-10** | `shell=True` Subprocess Execution in Admin Container Cleanup | **LOW** | 3.5 | Action Required |
| **SEC-11** | Unbounded Memory Growth in `_SUBMISSION_HISTORY` Rate Limiter | **LOW** | 3.1 | Action Required |
| **SEC-12** | Information Disclosure via Verbose Database Exception Strings | **INFO** | 2.1 | Action Required |

---

## 2. Threat Model & Attack Surface

```
[ UNTRUSTED INTERNET ]
        │
        │ HTTPS (443) / WSS (443)
        ▼
[ Nginx Reverse Proxy ] ──> X-Forwarded-For, Host, WebSocket Upgrade
        │
        ▼
[ Flask Application (Port 8080) ]
  ├── /login, /admin ─────────────> Plaintext Auth, No Rate Limit (SEC-01, SEC-02)
  ├── Subnet Middleware ──────────> Bypassed by 172.19-31.* or Nginx (SEC-03)
  ├── /api/score ─────────────────> INTERNAL_TOKENS Memory Leak (SEC-05)
  ├── /api/whois ─────────────────> Unauthenticated TCP Socket Proxy (SEC-07)
  └── Dynamic Flag Hashes ────────> Hardcoded fallback secret (SEC-04)
        │
        ▼
[ Host Docker Daemon ]
  └── Challenge Containers (jumanji-level2, jumanji-level3, jumanji-gauntlet)
```

### Primary Threat Actors:
1. **Malicious External Attackers**: Attempting brute-force attacks against `/login` to acquire tournament administrative privileges.
2. **Competitive CTF Participants**: Attempting to bypass challenge isolation, extract secret tokens from other participants, replay expired internal tokens, or forge dynamic flag HMACs using default secrets.
3. **Escalated Container Users**: Participants who achieved root inside their challenge container attempting to pivot back into the host server via the Docker bridge network.

---

## 3. Detailed Vulnerability Findings

### SEC-01: Missing Brute-Force Rate Limiting on Admin Login
- **Severity**: **HIGH** (CVSS: 7.5 — `CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N`)
- **Component**: [`DAY 1/www/app.py`](file:///Users/akashverma/Desktop/TechnozionXSDC/DAY%201/www/app.py#L747-L766) (`login()`)
- **Description**: The `/login` route permits password authentication for users and administrators. To protect against automated dictionary or credential-stuffing attacks, sliding-window IP rate limiting and salted scrypt/pbkdf2 password hashing are strictly enforced.
- **Impact**: An attacker can execute automated dictionary or credential-stuffing attacks at thousands of requests per second against the administrative interface.
- **Remediation**: Implement a sliding-window rate limiter per client IP on `/login` (e.g., maximum 5 failed attempts per 15 minutes, with exponential backoff).

---

### SEC-02: Plaintext Admin Password Storage & Comparison
- **Severity**: **HIGH** (CVSS: 7.4 — `CVSS:3.1/AV:L/AC:L/PR:H/UI:N/S:U/C:H/I:H/A:N`)
- **Component**: [`DAY 1/www/app.py`](file:///Users/akashverma/Desktop/TechnozionXSDC/DAY%201/www/app.py#L761-L766), [`DAY 1/www/jumanji_auth.db`](file:///Users/akashverma/Desktop/TechnozionXSDC/DAY%201/www/jumanji_auth.db)
- **Description**: In `app.py`:
  ```python
  user = conn.execute("SELECT ... FROM users WHERE username = ? AND password = ? ...", (username, password)).fetchone()
  ```
  The administrator password is stored as unhashed, raw plaintext (`Admin_ShadowDrop!2026`) in SQLite.
- **Impact**: Any unauthorized read of `jumanji_auth.db`, database backups, or memory dumps immediately exposes the administrative credentials.
- **Remediation**: Hash administrative passwords using `werkzeug.security.generate_password_hash` (PBKDF2-HMAC-SHA256) and verify using `check_password_hash`.

---

### SEC-03: Docker Bridge Subnet Filter Bypass via Reverse Proxy / RFC 1918 Range
- **Severity**: **HIGH** (CVSS: 7.2 — `CVSS:3.1/AV:A/AC:L/PR:N/UI:N/S:C/C:H/I:N/A:N`)
- **Component**: [`DAY 1/www/app.py`](file:///Users/akashverma/Desktop/TechnozionXSDC/DAY%201/www/app.py#L138-L143) (`enforce_security_and_csrf()`)
- **Description**: 
  1. The subnet check checks:
     ```python
     client_ip = request.remote_addr or ''
     if client_ip.startswith('172.17.') or client_ip.startswith('172.18.'):
     ```
     Docker bridge networks span the entire `172.16.0.0/12` CIDR (`172.16.0.0` to `172.31.255.255`). Containers allocated on `172.19.*` through `172.31.*` completely bypass this filter.
  2. In production behind Nginx, `request.remote_addr` resolves to `127.0.0.1` unless `werkzeug.middleware.proxy_fix.ProxyFix` is configured.
- **Impact**: A participant who reaches root inside a challenge container could connect to `host.docker.internal` through the gateway and access `/admin` without being blocked.
- **Remediation**: Use Python's `ipaddress.ip_network` to evaluate whether `client_ip` belongs to Docker bridge ranges, inspect `X-Forwarded-For` with `ProxyFix`, and block administrative routes.

---

### SEC-04: Insecure Fallback Cryptographic Secrets (`CTF_MASTER_SECRET`)
- **Severity**: **MEDIUM** (CVSS: 6.5 — `CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:N/A:N`)
- **Component**: [`DAY 1/www/app.py`](file:///Users/akashverma/Desktop/TechnozionXSDC/DAY%201/www/app.py#L51-L52)
- **Description**: If `.env` is missing or variables are unset, the application falls back to publicly known static secrets:
  ```python
  CTF_MASTER_SECRET = os.environ.get('CTF_MASTER_SECRET', '8f7b6c5d4a3e2f1g0h9i8j7k6l5m4n3')
  CYBERSEC_SHARED_SECRET = os.environ.get('CYBERSEC_SHARED_SECRET', 'jumanji_cybersec_secret_key_2026_xyz')
  ```
- **Impact**: Any participant inspecting the repository history could calculate all dynamic flag hashes offline using the fallback secret without solving challenges.
- **Remediation**: Enforce strict startup assertions: raise an exception if `CTF_MASTER_SECRET` equals the default key in production mode.

---

### SEC-05: Unbounded Memory Growth & Zombie Tokens in `INTERNAL_TOKENS`
- **Severity**: **MEDIUM** (CVSS: 5.8 — `CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:N/I:L/A:L`)
- **Component**: [`DAY 1/www/app.py`](file:///Users/akashverma/Desktop/TechnozionXSDC/DAY%201/www/app.py#L1554-L1564), [`DAY 1/www/app.py`](file:///Users/akashverma/Desktop/TechnozionXSDC/DAY%201/www/app.py#L2024-L2028)
- **Description**: Whenever a PTY container starts, an entry is added to `INTERNAL_TOKENS[token]`. However, this dictionary is never cleaned up when the container is destroyed or when the WebSocket disconnects.
- **Impact**:
  1. Memory leaks under prolonged tournament usage.
  2. Zombie tokens remain valid indefinitely in `/api/score`, allowing delayed flag submissions after container sessions have ended.
- **Remediation**: Clean up the token when `disconnect()` or `handle_stop_pty()` fires, and enforce an expiration timestamp (TTL) on each token.

---

### SEC-06: Missing `SESSION_COOKIE_SECURE` Flag in Flask Configuration
- **Severity**: **MEDIUM** (CVSS: 5.4 — `CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:U/C:L/I:L/A:N`)
- **Component**: [`DAY 1/www/app.py`](file:///Users/akashverma/Desktop/TechnozionXSDC/DAY%201/www/app.py#L64-L65)
- **Description**: `app.config['SESSION_COOKIE_HTTPONLY'] = True` and `SESSION_COOKIE_SAMESITE = 'Lax'` are set, but `SESSION_COOKIE_SECURE = True` is not configured.
- **Impact**: Browser sessions can be transmitted over unencrypted HTTP channels if an HTTP request is made prior to the HTTPS upgrade redirect.
- **Remediation**: Set `app.config['SESSION_COOKIE_SECURE'] = True` when running in production (`os.environ.get('ENVIRONMENT') == 'production'`).

---

### SEC-07: Unauthenticated Socket Proxy with Unsanitized Input on `/api/whois`
- **Severity**: **MEDIUM** (CVSS: 5.3 — `CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N`)
- **Component**: [`DAY 1/www/app.py`](file:///Users/akashverma/Desktop/TechnozionXSDC/DAY%201/www/app.py#L1535-L1552) (`proxy_whois()`)
- **Description**: The `/api/whois` endpoint takes unvalidated user JSON input `target` and opens a raw TCP socket to `127.0.0.1:4343`, sending `target + '\n'`. The endpoint does not verify session authentication or sanitize newlines (`\r\n`).
- **Impact**: Unauthenticated users can perform protocol injection / CRLF injection against any local service listening on port 4343.
- **Remediation**: Require authentication on `/api/whois`, restrict `target` to alphanumeric characters/hostnames using regex `^[a-zA-Z0-9.-]+$`, and reject newlines.

---

### SEC-08: Incomplete CSRF Protection on Interactive State Mutation Routes
- **Severity**: **MEDIUM** (CVSS: 5.0 — `CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:U/C:N/I:L/A:N`)
- **Component**: [`DAY 1/www/app.py`](file:///Users/akashverma/Desktop/TechnozionXSDC/DAY%201/www/app.py#L154-L161)
- **Description**: The CSRF validation middleware only executes if `request.path.startswith('/admin') and request.form`. Other mutating endpoints (e.g. `/gauntlet/curse/cast`, `/gauntlet/relic/solve`, `/choose-username`) do not enforce CSRF tokens.
- **Impact**: While protected against cross-origin `fetch()` by `is_allowed_origin`, non-admin routes lack explicit CSRF token verification.
- **Remediation**: Enforce CSRF token validation on all state-mutating requests, including JSON payloads via custom headers (`X-CSRFToken`).

---

### SEC-09: Empty List SQL Formatting Risk in Tournament Phase Advancement
- **Severity**: **LOW** (CVSS: 3.7 — `CVSS:3.1/AV:N/AC:H/PR:H/UI:N/S:U/C:N/I:L/A:L`)
- **Component**: [`DAY 2/level2/gauntlet_engine.py`](file:///Users/akashverma/Desktop/TechnozionXSDC/DAY%202/level2/gauntlet_engine.py#L538-L539)
- **Description**: In `advance_tournament_phase()`:
  ```python
  conn.execute("UPDATE gauntlet_teams SET phase = 'phase2_duels' WHERE id IN ({})".format(','.join(map(str, advanced))))
  ```
  If `advanced` is an empty list, SQLite throws a syntax error on `WHERE id IN ()`.
- **Impact**: An administrator advancing a phase before any teams have scored will trigger an uncaught operational error and freeze the admin interface.
- **Remediation**: Guard against empty lists: `if advanced: ...` and use parameterized queries `WHERE id IN ({})` with `?` placeholders.

---

### SEC-10: `shell=True` Subprocess Execution in Admin Container Cleanup
- **Severity**: **LOW** (CVSS: 3.5 — `CVSS:3.1/AV:L/AC:L/PR:H/UI:N/S:U/C:N/I:L/A:N`)
- **Component**: [`DAY 1/www/app.py`](file:///Users/akashverma/Desktop/TechnozionXSDC/DAY%201/www/app.py#L1045) & [`L1056`](file:///Users/akashverma/Desktop/TechnozionXSDC/DAY%201/www/app.py#L1056)
- **Description**: Admin container pruning executes:
  ```python
  subprocess.run("docker ps -q ... | xargs -r docker rm -f", shell=True, ...)
  ```
- **Impact**: While the command string is hardcoded, invoking `/bin/sh` introduces unnecessary process overhead and shell-parsing attack surface.
- **Remediation**: Split into native Python list commands: query IDs with `subprocess.check_output(["docker", "ps", "-q", ...])` and remove directly with `["docker", "rm", "-f"] + ids`.

---

### SEC-11: Unbounded Memory Growth in `_SUBMISSION_HISTORY` Rate Limiter
- **Severity**: **LOW** (CVSS: 3.1 — `CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:L`)
- **Component**: [`DAY 1/www/app.py`](file:///Users/akashverma/Desktop/TechnozionXSDC/DAY%201/www/app.py#L112-L123)
- **Description**: `_SUBMISSION_HISTORY = collections.defaultdict(list)` records timestamps for all identifiers. It never evicts keys that haven't submitted in hours or days.
- **Impact**: During an event with hundreds of participants, dictionary size increases monotonically.
- **Remediation**: Periodically prune identifiers with empty lists, or replace with an LRU cache / Redis rate limiter.

---

### SEC-12: Information Disclosure via Verbose Database Exception Strings
- **Severity**: **INFORMATIONAL** (CVSS: 2.1 — `CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:L/I:N/A:N`)
- **Component**: [`DAY 1/www/app.py`](file:///Users/akashverma/Desktop/TechnozionXSDC/DAY%201/www/app.py#L1183)
- **Description**: On database or script errors, raw exceptions (`str(e)`) are flashed to the UI.
- **Impact**: Internal file paths or database structure may be visible to admins if an error occurs.
- **Remediation**: Log detailed stack traces to disk logs (`/var/log/jumanji-ctf.error.log`) and display sanitized user-facing error messages.

---

## 4. Remediation Implementation Plan

### Phase 1: Authentication & Password Security
1. **Password Hashing**:
   - Update `app.py` to use `werkzeug.security.generate_password_hash` and `check_password_hash`.
   - On server startup (`init_db()`), automatically migrate plaintext admin passwords to hashed passwords.
2. **Login Rate Limiter**:
   - Apply a sliding-window rate limit (5 attempts per 15 minutes per IP) on `POST /login`.

### Phase 2: Reverse Proxy & Subnet Security
1. **Docker Subnet Isolation**:
   - Update `enforce_security_and_csrf()` to use `ipaddress.ip_network` covering `172.16.0.0/12` and `10.0.0.0/8`.
   - Enable `ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)` so `request.remote_addr` accurately reflects the real client IP behind Nginx.
2. **Session Cookie Hardening**:
   - Enable `app.config['SESSION_COOKIE_SECURE'] = True` if `WEB_ORIGIN` starts with `https://`.

### Phase 3: In-Memory Lifecycle & Token Sanitization
1. **`INTERNAL_TOKENS` TTL**:
   - Add a `created_at` timestamp to each token in `INTERNAL_TOKENS`.
   - Expire tokens after 2 hours or immediately upon WebSocket `disconnect()`.
2. **WHOIS Socket Hardening**:
   - Enforce `session.get('user_id')` on `/api/whois`.
   - Validate `target` against `^[a-zA-Z0-9.-]{1,64}$` to eliminate CRLF injection.

### Phase 4: Subprocess & Code Quality Fixes
1. **Remove `shell=True`**:
   - Replace piped shell calls with native Docker subprocess executions.
2. **SQL Phase Advancement Guard**:
   - Check `if advanced:` and use parameterized SQL query generation in `gauntlet_engine.py`.

---

## 5. Verification & Regression Testing Strategy

Every patch must be verified against the **52-test automated regression suite** (`./verify_all.sh`):
1. **Web Endpoints & Auth**: Verify admin login with hashed password, Google OAuth redirect, and unauthenticated redirects.
2. **Challenge Containers**: Verify Day 1 Level 2, Day 1 Level 3 SUID privilege escalation, and Day 2 Gauntlet split-key logic.
3. **Admin Controls**: Verify locks, resets, and phase advancement.
4. **Target Benchmark**: **52/52 PASS (0 regressions)**.

