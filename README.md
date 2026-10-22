# 🕹️ Technozion SDC Games — Jumanji Edition

An interactive, multi-stage cybersecurity competition (CTF) platform featuring web-based terminal emulation, containerized avatar challenges, and mainframe privilege escalation.

---

## 🏗️ Architecture & Overview

The platform coordinates isolated player sandbox containers with a central scoring and PTY orchestration server:

```
                        [ Player Browser ]
                                |
                    (HTTP :8080 / WebSockets)
                                v
               +----------------------------------+
               |     Flask + SocketIO Server      |
               |          (DAY 1/www)             |
               +-----------------+----------------+
                                 |
         +-----------------------+-----------------------+
         |                                               |
         v                                               v
+-----------------------------+         +-----------------------------+
|    Docker: Round 2 CTF      |         |    Docker: Round 3 CTF      |
|    (jumanji-round2:latest)  |         |    (jumanji-round3:latest)  |
|  - 5 Character Flag Relics  |         |  - Mainframe DB Flag        |
|  - parrot_hint (Lore & Tech)|         |  - SUID Root Binary Exploit |
|  - CLI submission: complete |         |  - deploy_override CLI      |
+-----------------------------+         +-----------------------------+
```

### 🎮 Game Rounds & Capabilities
- **Central Expedition Command Hub (`/hub`)**: Main navigation gateway routing players between active game rounds with live countdowns and status indicators.
- **Level 2 (Round 2): Cybersec Reconnaissance (`/dashboard`)**: Web terminal connected via SocketIO PTY to isolated Docker containers (`jumanji-round2:latest`). Players solve 5 avatar challenges (Bravestone 20, Ruby 30, Finbar 25, Oberon 25, Seaplane 50) for **150 points**.
- **Level 3 (Round 3): Mainframe Core Breach (`/round3`)**: Advanced challenge environment (`jumanji-round3:latest`). Players perform database extraction (User Override, **80 pts**) and exploit a custom SUID binary `lift_curse` using the `CHANT=JUMANJI` environment variable to claim Root Override (**120 pts**, total **200 pts**).
- **Admin Control Center (`/admin`)**: Real-time global leaderboard, round locking/unlocking, per-user unsuspension, and timer resets.
- **Dynamic HMAC Flags**: Flags are cryptographically generated per player via MD5 HMAC tied to unique user IDs. Static flags are strictly rejected.
- **Google OAuth 2.0 Integration**: One-click Google sign-in using wildcard IP resolution via `nip.io`.
- **Cross-Stack Integration & SSO Bridge**: Full single sign-on (SSO) handoff from SDC Games (`/arena/cybersec/launch-token`) and real-time score sync webhooks (`/api/internal/scores/update`). See **[SDC_GAMES_AND_OUTSIDE_SERVER_HOSTING_CHANGES.md](file:///Users/akashverma/Desktop/TechnozionXSDC/SDC_GAMES_AND_OUTSIDE_SERVER_HOSTING_CHANGES.md)** and **[HOSTING_AND_INTEGRATION_GUIDE.md](file:///Users/akashverma/Desktop/TechnozionXSDC/HOSTING_AND_INTEGRATION_GUIDE.md)** for hosting architectures and specifications.

---

## 📁 Repository Structure

```
TechnozionXSDC/
├── README.md                                     <-- This overview documentation
├── SDC_GAMES_AND_OUTSIDE_SERVER_HOSTING_CHANGES.md <-- Complete networking & multi-server hosting guide
├── HOSTING_AND_INTEGRATION_GUIDE.md              <-- Cross-stack integration architecture
├── SETUP_AND_DEPLOYMENT_GUIDE.md                 <-- End-to-end event setup manual
├── CREDENTIALS_AND_SECRETS.txt                   <-- Authoritative competition secrets & credentials
├── walkthrough.md                                <-- Complete solution walkthrough & challenge notes
├── .env.example                                  <-- Environment variables template with bridge keys
├── verify_all.py                                 <-- Automated 35-check end-to-end verification suite
├── verify_all.sh                                 <-- 1-click test suite runner
├── sdc-games/                                    <-- SDC Games Platform (Server 1)
│   ├── apps/
│   │   ├── api/                                  <-- Express.js + MongoDB API & Cybersec Bridge
│   │   ├── web/                                  <-- React / Vite Participant & Admin Web App
│   │   ├── quiz-api/                             <-- Level 1 Quiz Microservice
│   │   └── quiz-web/                             <-- Level 1 Quiz Frontend
│   └── packages/
│       └── event-contracts/                      <-- Shared TypeScript data contracts
└── DAY 1/                                        <-- Cybersecurity Wing CTF Arena (Server 2)
    ├── round2/                                   <-- Round 2 Docker environment
    │   ├── Dockerfile.r2                         <-- Round 2 container specification
    │   ├── complete                              <-- Player flag submission CLI tool
    │   ├── parrot_hint.sh                        <-- Interactive hint system (parrot_hint 1-5)
    │   └── setup_round2.sh                       <-- Container startup & challenge initialization
    ├── round3/                                   <-- Round 3 Docker environment
    │   ├── Dockerfile.r3                         <-- Round 3 container specification
    │   ├── deploy_override                       <-- Player override submission CLI tool
    │   ├── lift_curse.c                          <-- SUID root privilege escalation binary source
    │   ├── nigel_comms.sh                        <-- Context-aware transmission guidance
    │   └── setup_round3.sh                       <-- Container startup & DB initialization
    └── www/                                      <-- CTF Web Application & Scoring Server
        ├── app.py                                <-- Flask backend, PTY spawner, OAuth, APIs
        ├── requirements.txt                      <-- Python package dependencies
        ├── .env                                  <-- CTF server environment variables
        ├── CREDENTIALS_AND_SECRETS.txt           <-- Synchronized credentials copy
        ├── static/                               <-- Sounds, cutscenes, avatars, CSS, JS
        │   ├── assets/                           <-- Video cutscenes, character portraits
        │   ├── css/                              <-- Retro terminal & hub stylesheets
        │   └── js/                               <-- SocketIO client, xterm.js terminal
        └── templates/                            <-- HTML5 Jinja templates
            ├── hub.html                          <-- Expedition Command Center
            ├── dashboard.html                    <-- Round 2 Reconnaissance HUD
            ├── round3.html                       <-- Round 3 Simulation HUD
            ├── admin.html                        <-- Game Master Admin Dashboard
            ├── login.html                        <-- Login page with Google OAuth
            ├── choose_username.html              <-- Team alias selection
            └── register.html                     <-- Manual account registration
```

---

## 🚀 Quickstart Guide

### 1. Prerequisites
- **Docker Desktop** (or Docker Engine on Linux)
- **Python 3.10+** (Python 3.11 recommended)

### 2. Set Up Virtual Environment
```bash
cd "DAY 1/www"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cd ../..
```

### 3. Build Docker Images
```bash
# Round 2 Challenge Image
docker build -t jumanji-round2:latest -f "DAY 1/round2/Dockerfile.r2" "DAY 1/round2/"

# Round 3 Challenge Image
docker build -t jumanji-round3:latest -f "DAY 1/round3/Dockerfile.r3" "DAY 1/round3/"
```

### 4. Configure Environment
```bash
cp .env.example .env
# Edit .env to set your Google OAuth credentials and secrets
```

### 5. Run Verification Suite
Verify 100% operational readiness across all 35 test checks:
```bash
./verify_all.sh
```

### 6. Start the Server
```bash
cd "DAY 1/www"
source venv/bin/activate
python3 app.py
```

The server binds to `0.0.0.0:8080`.
- **Local Access**: `http://localhost:8080`
- **Admin Control**: `http://localhost:8080/admin`

---

## 🔒 Security & Secrets Management
- All sensitive API keys, OAuth secrets, and session salts are configured via environment variables.
- SQLite databases and virtual environments are excluded from source tracking.
- Dynamic HMAC flag generation prevents flag sharing across competing teams.
