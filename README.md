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
             |                       |                       |
             v                       v                       v
    +-----------------+     +-----------------+     +-----------------+
    | Day 1 Level 2   |     | Day 1 Level 3   |     | Day 2 Level 2   |
    | (jumanji-level2)|     | (jumanji-level3)|     |(jumanji-gauntlet|
    | - 5 Avatar Relics|    | - Mainframe DB  |     | - Pod Tournaments
    | - parrot_hint   |     | - SUID Root     |     | - Split Keys    |
    | - complete CLI  |     | - deploy_override|    | - King of Hill  |
    +-----------------+     +-----------------+     +-----------------+
```

### 🎮 Game Modules & Capabilities
- **Central Expedition Command Hub (`/hub`)**: Main navigation gateway routing players between active game rounds with live countdowns and status indicators.
- **Day 1 Level 2: Avatar Reconnaissance (`/level2`)**: Web terminal connected via SocketIO PTY to isolated Docker containers (`jumanji-level2:latest`). Players solve 5 avatar challenges (Bravestone 20, Ruby 30, Finbar 25, Oberon 35, Seaplane 40) for **150 points**.
- **Day 1 Level 3: Mainframe Simulation (`/level3`)**: Advanced privilege escalation environment (`jumanji-level3:latest`). Players perform database extraction (User Override, **80 pts**) and exploit a custom SUID binary `lift_curse` using `CHANT=JUMANJI_MAINFRAME_OVERRIDE` to claim Root Override (**120 pts**, total **200 pts**).
- **Day 2 Level 2: The Jumanji Gauntlet (`/gauntlet`)**: Strict 32-player tournament (16 squads of 2: 1 Navigator, 1 Cartographer) across 4 round-robin pods, asymmetric split-key cryptanalysis, interactive tactical curses, King-of-the-Hill shrine holding, and Top 4 Teams final championship qualification.
- **Admin Control Center (`/admin` & `/admin/gauntlet`)**: Real-time multi-level leaderboards (Day 1 Level 2, Level 3, and Day 2 Gauntlet squads showing assigned player IDs), user creation with Day 2 Level 2 squad allotments, password resets, round locking/unlocking, MongoDB roster sync trigger, Top 4 Teams showcase, and bracket phase advancement.
- **Direct MongoDB Atlas Roster Sync**: Seamless one-way participant roster ingestion from MongoDB Atlas (`sync_from_mongodb.py`). Scores remain strictly in the local CTF SQLite database.
- **Dual Authentication (Google OAuth 2.0 & ID/Password Login)**: Players can sign in via Google OAuth or using their assigned Username / SDC Participant ID with password. Game administrators authenticate with secure hashed credentials.
- **Container Isolation & Security**: Containers run under default AppArmor restrictions without `SYS_ADMIN` capability. Dynamic flag generation scripts self-destruct upon container startup to protect the master secret.
- **Enterprise Security Hardening**: Subnet-level request filtering blocking Docker bridge pivots to admin endpoints, anti-CSRF token verification across all administrative forms, strict Socket.IO CORS domain lockdown, in-memory sliding-window rate limiting on flag submissions, and high-entropy persistent session keys.

---

## 📚 Master Documentation Index

All platform documentation is consolidated into **exactly 7 authoritative markdown files**:

1. [**`README.md`**](file:///Users/akashverma/Desktop/TechnozionXSDC/README.md): Primary tournament overview, module summary, and architecture introduction.
2. [**`SECURITY.md`**](file:///Users/akashverma/Desktop/TechnozionXSDC/SECURITY.md): Comprehensive production security audit report for the **SDC Games** platform (`prod` branch, commit `daadf1f`), covering threat modeling, CVSS v3.1 scoring, and patch diffs.
3. [**`WALKTHROUGH.md`**](file:///Users/akashverma/Desktop/TechnozionXSDC/WALKTHROUGH.md): Step-by-step challenge solutions, avatar exploit commands, and Gauntlet split-key formulas.
4. [**`HOSTING.md`**](file:///Users/akashverma/Desktop/TechnozionXSDC/HOSTING.md): Complete operations manual, Docker build commands, port bindings, and daemon execution cheatsheet.
5. [**`FUNCTIONS.md`**](file:///Users/akashverma/Desktop/TechnozionXSDC/FUNCTIONS.md): Exhaustive function catalog, cross-file caller-callee call graphs, and dead code audit log.
6. [**`DECISIONS.md`**](file:///Users/akashverma/Desktop/TechnozionXSDC/DECISIONS.md): Architecture Decision Records (ADRs 001–010) documenting design, security, and game invariants.
7. [**`ARCHITECTURE.md`**](file:///Users/akashverma/Desktop/TechnozionXSDC/ARCHITECTURE.md): Technical topology diagrams, SQLite schema models, Docker PTY isolation, and security defenses.

---

## 📁 Repository Structure

```
TechnozionXSDC/
├── README.md                      <-- Master platform documentation (this file)
├── SECURITY_AUDIT.md              <-- Full defensive security audit and exploit analysis
├── WALKTHROUGH.md                 <-- Comprehensive challenge solutions & walkthrough
├── HOSTING.md                     <-- Deployment, Docker, ports, and operations manual
├── FUNCTIONS.md                   <-- Complete function catalog & call graph
├── DECISIONS.md                   <-- Architecture Decision Records (ADRs)
├── ARCHITECTURE.md                <-- System topology, database schemas & socket specs
├── CREDENTIALS_AND_SECRETS.txt     <-- Administrator credentials & secret tokens
├── .env.example                   <-- Environment variables template
├── sync_from_mongodb.py           <-- Direct MongoDB Atlas player roster sync CLI
├── verify_all.py                  <-- Automated 52-check end-to-end verification suite
├── verify_all.sh                  <-- 1-click test suite runner
├── DAY 1/
│   ├── level2/                    <-- Day 1 Level 2 (Avatars) Docker environment
│   ├── level3/                    <-- Day 1 Level 3 (Mainframe) Docker environment
│   └── www/                       <-- CTF Web Application, SocketIO PTY, Flask Server
└── DAY 2/
    └── level2/                    <-- Day 2 Level 2 (Gauntlet) tournament engine
```

---

## 🚀 Quick Execution Cheatsheet

### 1. Build Challenge Containers
```bash
docker build -t jumanji-level2:latest "DAY 1/level2" -f "DAY 1/level2/Dockerfile"
docker build -t jumanji-level3:latest "DAY 1/level3" -f "DAY 1/level3/Dockerfile"
docker build -t jumanji-gauntlet:latest "DAY 2/level2" -f "DAY 2/level2/Dockerfile.gauntlet"
```

### 2. Launch CTF Server Daemon (Port 8080)
```bash
cd "DAY 1/www"
source venv/bin/activate
python3 app.py
```

### 3. Run Automated 52-Check Verification Suite
```bash
./verify_all.sh
```
