# 🕹️ Technozion SDC Games — Jumanji Edition

An interactive, multi-stage cybersecurity competition (CTF) platform featuring web-based terminal emulation, containerized avatar challenges, mainframe privilege escalation, and real-time tournament gauntlet mechanics.

---

## 🏗️ Architecture & Overview

The platform coordinates isolated player sandbox containers with a central scoring and PTY orchestration server:

```
                            [ Player Browser ]
                                    |
                        (HTTP :8080 / WebSockets)
                                    v
                   +----------------------------------+
                   |     Flask + SocketIO Server      | <--- Direct Roster Sync
                   |          (DAY 1/www)             |      (MongoDB Atlas)
                   +-----------------+----------------+
                                     |
             +-----------------------+-----------------------+
             |                                               |
             v                                               v
    +-----------------+                             +-----------------+
    | Day 1 Level 2   |                             | Day 2 Level 1   |
    | (jumanji-level2)|                             |(jumanji-day2-l1)|
    | - 5 Avatar Relics|                            | - Mainframe DB  |
    | - parrot_hint   |                             | - SUID Root     |
    | - complete CLI  |                             | - lift_curse    |
    +-----------------+                             +-----------------+
                                     |
               (Gauntlet Tournament Engine Archived)
                                     v
                   +----------------------------------+
                   |         archive/gauntlet/        |
                   +----------------------------------+
```

### 🎮 Game Modules & Capabilities
- **Central Expedition Command Hub (`/hub`)**: Main navigation gateway routing players between active game rounds with live countdowns and status indicators.
- **Day 1 Level 2: Avatar Reconnaissance (`/level2`)**: Web terminal connected via SocketIO PTY to isolated Docker containers (`jumanji-level2:latest`). Players solve 5 avatar challenges (Bravestone 20, Ruby 30, Finbar 25, Oberon 35, Seaplane 40) for **150 points**.
- **Day 2 Level 1: Mainframe Simulation (`/day2/level1` & `/level3`)**: Advanced privilege escalation environment (`jumanji-day2-level1:latest`). Players perform database extraction (User Override, **80 pts**) and exploit a custom SUID binary `lift_curse` using `CHANT=JUMANJI` to claim Root Override (**120 pts**, total **200 pts**). Backward-compatible aliases (`/level3`, `/round3`) remain supported.
- **Archived Gauntlet Tournament (`archive/gauntlet`)**: The multi-team Jumanji Gauntlet tournament engine and templates are safely backed up and isolated in `archive/gauntlet/`. Any incoming requests to `/day2/level2` or `/gauntlet` cleanly redirect to `/hub`.
- **Admin Control Center (`/admin`)**: Real-time multi-level leaderboards (Day 1 Level 2 and Day 2 Level 1), player creation, password resets, round locking/unlocking, and direct MongoDB roster sync.
- **Direct MongoDB Atlas Roster Sync**: Seamless one-way participant roster ingestion from MongoDB Atlas (`sync_from_mongodb.py`). Scores remain strictly in the local CTF SQLite database.
- **Hybrid Authentication (Google OAuth 2.0 & Explicit Admin Passwords)**: Participants authenticate strictly via Google OAuth (synced one-way from MongoDB Atlas with unusable `!OAUTH_ONLY!_<hex>` password hashes). Universal default password fallbacks are eliminated. Local password logins are permitted strictly for administrator-created local accounts with explicit passwords ($\ge 8$ chars).
- **Container Isolation & Security**: Containers run under default AppArmor restrictions without `SYS_ADMIN` capability. Dynamic flag generation scripts self-destruct upon container startup to protect the master secret. Strict single-active-container constraint per user prevents multi-tab DoS.
- **Enterprise Security Hardening**: Subnet-level request filtering blocking Docker bridge pivots to admin endpoints (covering full RFC 1918 scope), anti-CSRF token verification across all administrative forms and state mutations, strict Socket.IO CORS domain lockdown, proxy-aware sliding-window rate limiting on logins and flag submissions, thread-safe CLI tokens, SQLite WAL mode with 30s busy timeout, PTY dimension pre-sizing with readline redraw protection, and OWASP CWE-1236 CSV injection sanitization.

---

## 📚 Master Documentation Index

All platform documentation is consolidated into **authoritative markdown files**:

1. [**`README.md`**](file:///Users/akashverma/Desktop/TechnozionXSDC/README.md): Primary tournament overview, module summary, and architecture introduction.
2. [**`SECURITY.md`**](file:///Users/akashverma/Desktop/TechnozionXSDC/SECURITY.md): Comprehensive production security audit report covering threat modeling, 24 identified vulnerabilities (SEC-01 to SEC-24), CVSS v3.1 scoring, and patch diffs.
3. [**`WALKTHROUGH.md`**](file:///Users/akashverma/Desktop/TechnozionXSDC/WALKTHROUGH.md): Step-by-step challenge solutions, avatar exploit commands, and Gauntlet split-key formulas.
4. [**`HOSTING.md`**](file:///Users/akashverma/Desktop/TechnozionXSDC/HOSTING.md): Complete operations manual, Docker build commands, port bindings, and daemon execution cheatsheet.
5. [**`FUNCTIONS.md`**](file:///Users/akashverma/Desktop/TechnozionXSDC/FUNCTIONS.md): Exhaustive function catalog, cross-file caller-callee call graphs, and dead code audit log.
6. [**`DECISIONS.md`**](file:///Users/akashverma/Desktop/TechnozionXSDC/DECISIONS.md): Architecture Decision Records (ADRs 001–011) documenting design, security, and game invariants.
7. [**`ARCHITECTURE.md`**](file:///Users/akashverma/Desktop/TechnozionXSDC/ARCHITECTURE.md): Technical topology diagrams, SQLite schema models, Docker PTY isolation, and security defenses.

---

## 📁 Repository Structure

```
TechnozionXSDC/
├── README.md                      <-- Master platform documentation (this file)
├── SECURITY.md                    <-- Full defensive security audit and exploit analysis
├── WALKTHROUGH.md                 <-- Comprehensive challenge solutions & walkthrough
├── HOSTING.md                     <-- Deployment, Docker, ports, and operations manual
├── FUNCTIONS.md                   <-- Complete function catalog & call graph
├── DECISIONS.md                   <-- Architecture Decision Records (ADRs)
├── ARCHITECTURE.md                <-- System topology, database schemas & socket specs
├── test_security.py               <-- Automated 13-check defensive security & stress suite
├── CREDENTIALS_AND_SECRETS.txt     <-- Administrator credentials & secret tokens
├── .env.example                   <-- Environment variables template
├── sync_from_mongodb.py           <-- Direct MongoDB Atlas player roster sync CLI
├── verify_all.py                  <-- Automated 52-check verification suite
├── verify_all.sh                  <-- 1-click test suite runner
├── DAY 1/
│   ├── level2/                    <-- Day 1 Level 2 (Avatars) Docker environment
│   └── www/                       <-- CTF Web Application, SocketIO PTY, Flask Server
├── DAY 2/
│   └── level1/                    <-- Day 2 Level 1 (Mainframe DB & SUID) Docker environment
└── archive/
    └── gauntlet/                  <-- Safely isolated Gauntlet tournament files & templates
```

---

## 🚀 Quick Execution Cheatsheet

### 1. Build Challenge Containers
```bash
# Day 1 Level 2 (Avatar Recon)
docker build -t jumanji-level2:latest "DAY 1/level2" -f "DAY 1/level2/Dockerfile"

# Day 2 Level 1 (Simulation Core Mainframe)
docker build -t jumanji-day2-level1:latest "DAY 2/level1" -f "DAY 2/level1/Dockerfile"
docker tag jumanji-day2-level1:latest jumanji-level3:latest
```

### 2. Launch CTF Server Daemon (Port 8080)
```bash
cd "DAY 1/www"
source venv/bin/activate
python3 app.py
```

### 3. Run Automated Security & Stress Test Suite
```bash
python3 test_security.py
```

### 4. Run Automated 52-Check End-to-End Verification Suite
```bash
./verify_all.sh
```
