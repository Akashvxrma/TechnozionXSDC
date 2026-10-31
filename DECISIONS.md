# 🏛️ Architecture Decision Records (ADRs)

This document records the foundational architectural, security, and game-design decisions implemented across the Technozion SDC Games CTF Platform.

---

## ADR 001: Hybrid Authentication (Google OAuth + Explicit Admin Passwords)

- **Status**: Accepted & Implemented
- **Context**: Participants registered on the SDC Games website authenticate seamlessly via Google OAuth 2.0. In addition, tournament administrators require the ability to create manual player accounts and assign explicit custom passwords via the Admin panel without shared default password backdoors.
- **Decision**: 
  - Support dual authentication avenues:
    1. **Google OAuth 2.0**: The primary authentication mechanism for participants registered on the SDC Games portal.
    2. **ID & Explicit Password**: Accounts created by administrators or given explicit passwords in `/admin` authenticate via Username or Participant ID.
  - Zero Shared Default Passwords: Eliminate universal shared default passwords (such as `ShadowDrop2026!`) to prevent credential-stuffing and squad impersonation attacks. Synced OAuth accounts remain protected under `!OAUTH_ONLY!_<hex>` unless an administrator explicitly assigns a custom password.
  - Transparent cryptographic password upgrade: Plaintext passwords automatically upgrade to salted `scrypt` hashes upon first authentication.
  - Full admin control: Tournament administrators can create accounts with mandatory custom passwords or update participant credentials dynamically via `/admin`.
- **Consequences**: Zero default-credential attack surface; guarantees authentic identity verification for Google-synced players while providing full password flexibility for admin-provisioned competitors.

---

## ADR 002: Direct MongoDB Synchronization (Zero HTTP Bridge Dependency)

- **Status**: Accepted & Implemented
- **Context**: The platform initially depended on an HTTP bridging microservice to synchronize roster registrations and dispatch scores between the CTF platform and the SDC Games portal. Network latency, CORS failures, and unreachable bridge ports caused synchronization drops.
- **Decision**:
  - Completely decommission the HTTP bridge API and pending sync retry queues.
  - Connect directly to the production SDC Games MongoDB Atlas cluster (`mongodb+srv://sdclubgames_db_user:...@sdcgames26.nivm9mr.mongodb.net/`).
  - Read `users` and `participants` collections directly using `pymongo` and upsert local SQLite records non-destructively.
  - Implement an Admin one-click sync button (`/admin/sync-sdc-roster`) and a CLI utility (`sync_from_mongodb.py`).
- **Consequences**: Instant, reliable roster synchronization with zero intermediate points of failure.

---

## ADR 003: Strict 32-Player Tournament Ceiling (16 Squads of 2)

- **Status**: Accepted & Implemented
- **Context**: Day 2 Level 2 ("The Jumanji Gauntlet") is designed as a co-op challenge requiring exactly 2 players per squad: 1 Navigator (Terminal CLI) and 1 Cartographer (Radar HUD). Unchecked scaling caused player collisions on single container sessions.
- **Decision**:
  - Enforce table-level database constraints: `UNIQUE(team_id, role)` and `CHECK(role IN ('navigator', 'cartographer'))`.
  - Cap the roster strictly at **16 teams $\times$ 2 players = 32 players total**.
  - Update `auto_assign_user_to_team` to return `None` when all 32 slots are filled.
  - Gracefully deny entry to player 33+ with a flash notice and block PTY terminal container spawning.
- **Consequences**: Deterministic 1v1 squad collaboration; zero container session conflicts; strict tournament fairness.

---

## ADR 004: Top 4 Teams Selection for Final Championship

- **Status**: Accepted & Implemented
- **Context**: The tournament must conclude by identifying the **Top 4 Teams** (8 finalists) to advance to the grand coding challenge.
- **Decision**:
  - Implement `gauntlet_engine.get_top_4_teams(conn)` ordering by total cumulative tournament score (`phase1_score + duel_score + shrine_score + lagoon_score`).
  - Showcase the Top 4 Qualifiers prominently at the top of Gauntlet Mission Control (`/admin/gauntlet`).
  - Implement a 1-click CSV export endpoint (`/admin/export-gauntlet-finalists`) generating the exact 8-finalist roster for event organizers.
  - Add fallback logic in `advance_tournament_phase('phase3_shrine')` so the Top 4 teams are guaranteed to advance even if duels are bypassed.
- **Consequences**: Immediate transparency for stage commentators and tournament directors.

---

## ADR 005: Container Secret Protection & Elimination of Host Bind Mounts

- **Status**: Accepted & Implemented
- **Context**: `DAY 1/www/app.py` previously launched Gauntlet containers with a read-only bind mount to the host directory: `-v {gauntlet_dir}:/gauntlet_src:ro`. Because `setup_gauntlet.sh` contained the master HMAC key (`SECRET="8f7b6c5d4a3e2f1g0h9i8j7k6l5m4n3"`), any player inside a terminal container could run `cat /gauntlet_src/setup_gauntlet.sh` and forge flags for all phases.
- **Decision**:
  - Remove all host source bind mounts from the container launch configuration.
  - Bake setup scripts directly into the Docker image (`COPY setup_gauntlet.sh /usr/local/bin/setup_gauntlet.sh`).
  - Add self-destruction (`rm -f /usr/local/bin/setup_gauntlet.sh /usr/local/bin/setup_shrine.sh`) at the end of the initialization script.
- **Consequences**: Container filesystem is hardened; master flag derivation secrets cannot be extracted by participants.

---

## ADR 006: Asymmetric Cryptographic Split-Key Mechanism

- **Status**: Accepted & Implemented
- **Context**: Traditional CTF flags allow solo solvers to hoard flags or submit independently without team collaboration.
- **Decision**:
  - Every relic requires two halves generated via HMAC:
    $$\text{NAV\_HASH} = \text{MD5}(\text{TEAM\_ID} : \text{MATCH\_ID} : \text{RELIC} : \text{"nav"} : \text{SECRET})[:8]$$
    $$\text{CART\_HASH} = \text{MD5}(\text{TEAM\_ID} : \text{MATCH\_ID} : \text{RELIC} : \text{"cart"} : \text{SECRET})[:8]$$
  - The Navigator extracts `NAV_...` from the Linux container; the Cartographer extracts `CART_...` from the web HUD.
  - Neither half alone can score points. Teammates must communicate and submit the recombined flag `JUMANJI{relic_navhash_carthash}`.
- **Consequences**: Forces verbal squad communication and mutual dependency.

---

## ADR 007: Timestamp-Based Tie-Breaking for Tournament Pods

- **Status**: Accepted & Implemented
- **Context**: In Phase 1 Pods, teams were initially sorted by `ORDER BY phase1_score DESC, id ASC LIMIT 2`. In the event of equal scores, teams with lower numeric IDs (e.g., Team 1, 2) were automatically favored over higher IDs (Team 3, 4).
- **Decision**:
  - Upgrade the tie-breaker in `advance_tournament_phase` to:
    ```sql
    ORDER BY t.phase1_score DESC, COUNT(s.id) DESC, MIN(s.solved_at) ASC, t.id ASC
    ```
  - Prioritizes solve count, followed by the timestamp of the earliest relic solve.
- **Consequences**: Absolute competitive integrity and merit-based advancement.

---

## ADR 008: Master Secret Externalization and Persistent Session Key

- **Status**: Accepted & Implemented
- **Context**: Dynamic flag generation and split-key formulas previously relied on hardcoded fallback keys (`8f7b...` and `e5b9...`). If an operator omitted `FLASK_SECRET_KEY`, predictable session cookies could be forged.
- **Decision**:
  - Unify the flag and split-key secret under `CTF_MASTER_SECRET`, loaded early via `load_ctf_env()`.
  - Automatically generate a cryptographically strong 32-byte `FLASK_SECRET_KEY` and persist it to `.flask_secret_key` with strict permissions (`0600`) if not explicitly defined in the environment.
  - Hardcode zero secrets in `CREDENTIALS_AND_SECRETS.txt`, converting all credentials to environment variable templates.
  - In container setups (`setup_level2.sh`, `setup_level3.sh`, `setup_gauntlet.sh`), source `CTF_MASTER_SECRET`, provision challenges, and immediately execute `unset SECRET CTF_MASTER_SECRET` before deleting the script.
- **Consequences**: Eliminates session cookie forgery, stops secret leakage via memory or repository snapshots, and protects against unauthorized flag computation.

---

## ADR 009: Container Subnet Request Filtering and Network Boundary Hardening

- **Status**: Accepted & Implemented
- **Context**: Sandboxed Docker containers must be able to reach `http://host.docker.internal:8080/api/score` via the CLI `complete` tool. However, containers on default Docker bridges (`172.17.0.0/16`, `172.18.0.0/16`) could pivot to administrative URLs (`/admin/*`) or authentication flows (`/login`, `/register`).
- **Decision**:
  - Implement an `@app.before_request` network subnet filter on the CTF Flask gateway.
  - Check the client IP (`request.remote_addr`). If it falls within Docker container bridge subnets (`172.17.0.0/16` or `172.18.0.0/16`) and targets `/admin`, `/login`, `/register`, `/auth/*`, or `/choose-username`, immediately abort with `HTTP 403 Forbidden`.
  - Maintain permitted access for scoring endpoints (`/api/score`, `/api/whois/`).
  - Ensure host SQLite databases and auxiliary services bind exclusively to `127.0.0.1`.
- **Consequences**: Containerized competitors are strictly contained; administrative privilege escalation via container network pivots is prevented.

---

## ADR 010: Anti-CSRF Protection and Dynamic WebSocket Origin Validation

- **Status**: Accepted & Implemented
- **Context**: The administrative console and Gauntlet tournament control room handled state modifications (round locking, timer overrides, manual bracket advancement, roster sync) via standard HTTP POST without anti-CSRF tokens or origin enforcement. Additionally, SocketIO configured `cors_allowed_origins="*"`.
- **Decision**:
  - Add session-bound cryptographic tokens (`get_csrf_token()`) injected into all 15 administrative POST forms across `admin.html` and `gauntlet_admin.html`.
  - Enforce `hmac.compare_digest` token validation and strict `Origin`/`Referer` validation in `@app.before_request`.
  - Deprecate wildcard SocketIO CORS; replace with `is_allowed_origin` callable restricting connections to loopback (`127.0.0.1`, `localhost`), RFC 1918 private subnets (`10.x`, `172.16-31.x`, `192.168.x`), and `.nip.io` domains.
  - Implement a 30 req/min sliding-window rate limiter on all flag submission routes.
- **Consequences**: Complete immunity against cross-site request forgery, cross-site WebSocket hijacking, and automated rapid flag brute-forcing.

---

## ADR 011: Restructure Day 1 Level 3 as Day 2 Level 1 and Safely Archive the Gauntlet

- **Status**: Accepted & Implemented
- **Context**: The competition format was adjusted to feature a two-day event: Day 1 (Avatar Reconnaissance) and Day 2 (Simulation Core Mainframe DB & SUID Privilege Escalation). The multi-player Gauntlet engine introduced background tick threads, complex split-key dependencies, and per-keystroke curse queries that were not needed for this tournament phase.
- **Decision**:
  - Rename and promote Day 1 Level 3 to **Day 2 Level 1** (`/day2/level1`).
  - Retain full backward-compatibility for `/level3` and `/round3` so existing bookmarks and scripts function without issue.
  - Create `DAY 2/level1/` with unified Dockerfile and setup scripts symlinking `/level1` $\leftrightarrow$ `/level3`.
  - Isolate and safely back up all Gauntlet engine code (`gauntlet_engine.py`, `setup_gauntlet.sh`, `setup_shrine.sh`, `Dockerfile.gauntlet`) and templates (`gauntlet_hud.html`, `gauntlet_bracket.html`, `gauntlet_admin.html`) into `archive/gauntlet/`.
  - Delete `DAY 2/level2/` and Gauntlet templates from the active workspace.
  - Strip Gauntlet imports, background ticker threads, and per-keystroke SQLite curse lookups from `app.py`.
  - Redirect legacy `/day2/level2` and `/gauntlet` routes cleanly to `/hub` with HTTP 302.
  - Update automated verification and security test suites (`test_security.py`, `verify_all.py`) to test the new structure.
- **Consequences**: Platform performance is improved (keystroke latency eliminated), architecture is simplified, and all Gauntlet assets are preserved in `archive/gauntlet/` for future tournament seasons.

---

## ADR 012: Terminal Window Pre-Sizing and Readline Redraw Synchronization

- **Status**: Accepted & Implemented
- **Context**: In wide browser viewports (~138 columns), long shell commands ($>80$ characters) triggered severe readline line-wrapping corruption and text overlapping. The backend PTY was spawned with default 80x24 kernel geometry because initial frontend `pty-resize` events were dropped while Docker was launching, and `~/.bashrc` overwrites stripped Debian's `shopt -s checkwinsize`.
- **Decision**:
  - Accept initial viewport dimensions (`cols` and `rows`) directly in the WebSocket `start-pty` event payload.
  - Apply `termios.TIOCSWINSZ` immediately to both master and slave PTY file descriptors before launching `docker run`.
  - Maintain a thread-safe `pending_pty_sizes` cache to capture any asynchronous resize events received during container launch.
  - Pass `COLUMNS` and `LINES` environment variables into the Docker container.
  - Enable `shopt -s checkwinsize` and `export TERM=xterm-256color` in container `.bashrc`.
  - Attach modern `ResizeObserver` instances in the frontend (`level3.html` and `level2.html`) and synchronize dimensions with `document.fonts.ready`.
- **Consequences**: Complete elimination of readline cursor drift, cursor-up line collisions, and text overlapping across all display resolutions.


