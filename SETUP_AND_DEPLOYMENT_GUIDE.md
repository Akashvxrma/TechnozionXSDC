# 🕹️ Technozion SDC Games - Complete Setup & Deployment Guide

This guide provides end-to-end instructions for deploying, configuring, and operating the **Technozion SDC Games (Jumanji Edition)** platform. It covers deployment from scratch on a **brand-new computer** as well as day-of-event operations on an **existing computer**.

---

## 🏗️ 1. Architecture & System Overview

The platform is an interactive, multi-stage cybersecurity competition environment featuring:
- **Central Expedition Command Hub (`/hub`)**: Gateway routing players between game rounds, with live timers and status cards.
- **Round 2: Cybersec Reconnaissance (`/dashboard`)**: Web terminal connected via SocketIO PTY to isolated Docker containers running the `jumanji-round2:latest` image. Players solve 5 avatar challenges (Bravestone, Ruby, Finbar, Oberon, Seaplane) for **2,950 points**.
- **Round 3: Mainframe Core Breach (`/round3`)**: Higher-tier challenge running `jumanji-round3:latest`. Players perform database extraction (User Override, **1,000 pts**) and exploit a custom SUID binary `lift_curse` using the `CHANT=JUMANJI` environment variable to claim Root Override (**1,500 pts**, total **2,500 pts**).
- **Independent Round Isolation**: Rounds 2 and 3 operate on completely independent 60-minute timers, independent suspension statuses, and isolated Docker container lifecycles.
- **Admin Control Center (`/admin`)**: Live global leaderboard, round locking/unlocking, per-user unsuspension, and timer resets.
- **Google OAuth 2.0 Integration**: One-click Google sign-in using wildcard IP resolution via `nip.io`.

```
                        [ Player Browser ]
                                |
                   (HTTP :8080 / WebSockets)
                                v
               +----------------------------------+
               |     Flask + SocketIO Server      |
               |       (round_2_sdc_games/www)    |
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

---

## 📁 2. Cleaned Repository Structure

```
TechnozionXSDC/
├── SETUP_AND_DEPLOYMENT_GUIDE.md    <-- This comprehensive documentation
├── verify_all.py                    <-- Automated 35-check end-to-end verification suite
├── verify_all.sh                    <-- 1-click test suite runner
└── round_2_sdc_games/
    ├── round2/                      <-- Round 2 Docker environment
    │   ├── Dockerfile.r2            <-- Round 2 container specification
    │   ├── complete                 <-- Player flag submission CLI tool
    │   ├── parrot_hint.sh           <-- Interactive hint system (parrot_hint 1-5)
    │   └── setup_round2.sh          <-- Container startup & challenge initialization
    ├── round3/                      <-- Round 3 Docker environment
    │   ├── Dockerfile.r3            <-- Round 3 container specification
    │   ├── deploy_override          <-- Player override submission CLI tool
    │   ├── lift_curse.c             <-- SUID root privilege escalation binary source
    │   ├── nigel_comms.sh           <-- Context-aware transmission guidance
    │   └── setup_round3.sh          <-- Container startup & DB initialization
    └── www/                         <-- Web Application & Scoring Server
        ├── app.py                   <-- Flask backend, PTY spawner, OAuth, APIs
        ├── requirements.txt         <-- Python package dependencies
        ├── jumanji_auth.db          <-- SQLite database (Users, Points, Settings)
        ├── static/                  <-- Sounds, cutscenes, avatars, CSS, JS
        │   ├── assets/              <-- Video cutscenes, character portraits
        │   ├── css/                 <-- Retro terminal & hub stylesheets
        │   └── js/                  <-- SocketIO client, xterm.js terminal
        └── templates/               <-- HTML5 Jinja templates
            ├── hub.html             <-- Expedition Command Center
            ├── dashboard.html       <-- Round 2 Reconnaissance HUD
            ├── round3.html          <-- Round 3 Simulation HUD
            ├── admin.html           <-- Game Master Admin Dashboard
            ├── login.html           <-- Login page with Google OAuth
            ├── choose_username.html <-- Team alias selection
            └── register.html        <-- Manual account registration
```

---

## 🚀 3. Setup on a Brand-New Computer (From Scratch)

Follow these steps if you are deploying the project on a freshly formatted machine or a new server.

### 3.1. System Prerequisites
Ensure the target system has the following software installed:
1. **Operating System**: macOS (Apple Silicon or Intel), Linux (Ubuntu/Debian 22.04+), or Windows 10/11 with WSL2.
2. **Docker Desktop** (or Docker Engine on Linux):
   - Make sure Docker is running: `docker info`
3. **Python 3.10 or higher**:
   - Check version: `python3 --version`
4. **Git**:
   - Check version: `git --version`

---

### 3.2. Step-by-Step Installation Commands

#### Step 1: Open Terminal in Project Directory
```bash
cd "/path/to/TechnozionXSDC "
```

#### Step 2: Set Up Python Virtual Environment
```bash
cd round_2_sdc_games/www
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cd ../..
```

#### Step 3: Build Docker Container Images
Build both Round 2 and Round 3 isolated images:

```bash
# 1. Build Round 2 image
docker build -t jumanji-round2:latest -f round_2_sdc_games/round2/Dockerfile.r2 round_2_sdc_games/round2/

# 2. Build Round 3 image
docker build -t jumanji-round3:latest -f round_2_sdc_games/round3/Dockerfile.r3 round_2_sdc_games/round3/
```

Verify that both images are present:
```bash
docker images | grep jumanji
```
*Expected Output:*
```
jumanji-round3   latest   ...
jumanji-round2   latest   ...
```

---

### 3.3. Google OAuth 2.0 Configuration

The platform supports seamless Google Sign-In for players. Google OAuth requires a valid, publicly resolvable domain or IP in the Redirect URI. We use **`nip.io`** (e.g., `http://<YOUR_IP>.nip.io:8080/auth/callback`).

#### 1. Identify Your Machine's Local IP Address
- **macOS**:
  ```bash
  ipconfig getifaddr en0   # Wi-Fi
  # or
  ipconfig getifaddr en1   # Ethernet
  ```
- **Linux**:
  ```bash
  hostname -I | awk '{print $1}'
  ```

*Example IP:* `172.20.183.90`

#### 2. Configure Google Cloud Console
1. Go to [Google Cloud Console - Credentials](https://console.cloud.google.com/apis/credentials).
2. Select your project and edit your **OAuth 2.0 Client ID** (Web application).
3. Under **Authorized JavaScript origins**, add:
   - `http://localhost:8080`
   - `http://<YOUR_IP>.nip.io:8080` (e.g. `http://172.20.183.90.nip.io:8080`)
4. Under **Authorized redirect URIs**, add:
   - `http://localhost:8080/auth/callback`
   - `http://<YOUR_IP>.nip.io:8080/auth/callback` (e.g. `http://172.20.183.90.nip.io:8080/auth/callback`)
5. Click **Save**.

#### 3. Update `app.py` Configuration (if IP changed)
In `round_2_sdc_games/www/app.py`, check lines 22–24:
```python
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', 'YOUR_CLIENT_ID.apps.googleusercontent.com')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', 'YOUR_CLIENT_SECRET')
GOOGLE_REDIRECT_URI = os.environ.get('GOOGLE_REDIRECT_URI', 'http://172.20.183.90.nip.io:8080/auth/callback')
```
*(Or simply supply them as environment variables without modifying the file).*

---

### 3.4. Run the Full Verification Suite
Before starting the competition, run the automated test suite to confirm 100% system readiness:

```bash
./verify_all.sh
```

*Expected Result:*
```
====================================================================
SUMMARY: Passed: 35 | Failed: 0
====================================================================
ALL VERIFICATION CHECKS PASSED WITH 100% SUCCESS!
```

---

### 3.5. Start the Web Server
Launch the Flask + SocketIO application:

```bash
cd round_2_sdc_games/www
source venv/bin/activate
python3 app.py
```

The server binds to `0.0.0.0:8080`.
- **Local machine access**: `http://localhost:8080`
- **Network / Participant access**: `http://<YOUR_IP>.nip.io:8080` or `http://<YOUR_IP>:8080`

---

## ⚡ 4. Operating on an Existing Computer (Day of Event)

If the computer already has the repository, Docker images, and virtual environment configured:

### 4.1. Fast 1-Line Launch
```bash
cd "round_2_sdc_games/www" && source venv/bin/activate && python3 app.py
```

---

### 4.2. Handling Wi-Fi / IP Address Changes
If you change Wi-Fi networks or mobile hotspots on the day of the event:

1. **Find new IP**:
   ```bash
   ipconfig getifaddr en0
   ```
2. **Update `GOOGLE_REDIRECT_URI` in `round_2_sdc_games/www/app.py`**:
   Replace the old IP with your new IP in line 24:
   ```python
   GOOGLE_REDIRECT_URI = os.environ.get('GOOGLE_REDIRECT_URI', 'http://<NEW_IP>.nip.io:8080/auth/callback')
   ```
3. **Update Google Cloud Console**:
   Add the new `http://<NEW_IP>.nip.io:8080/auth/callback` to Authorized Redirect URIs.
4. **Restart the server**:
   Save `app.py` (Flask reloads automatically), or press `Ctrl+C` and run:
   ```bash
   source venv/bin/activate && python3 app.py
   ```

---

### 4.3. Admin Panel Operations

#### Accessing Admin Portal
- Navigate to: `http://<YOUR_IP>.nip.io:8080/admin`
- **Username**: `admin`
- **Password**: `Admin_ShadowDrop!2026`

#### Key Admin Capabilities
1. **Lock / Unlock Round 2**:
   - Blocks access to Round 2 without logging players out or affecting Round 3.
2. **Lock / Unlock Round 3**:
   - Blocks access to Round 3 without affecting Round 2.
3. **Unsuspend Player**:
   - If a player's timer ran out in Round 2 or Round 3, click **`[UNSUSPEND R2]`** or **`[UNSUSPEND R3]`** next to their username.
4. **Reset Player Timer**:
   - Click **`[RESET R2 TIMER]`** or **`[RESET R3 TIMER]`** to grant a fresh 60-minute countdown for that round.
5. **Score Adjustments**:
   - View real-time player scores, solved challenges, and connected terminals.

---

## 🛠️ 5. Troubleshooting & FAQ

### Issue 1: "Address already in use" (Port 8080 Busy)
If another process is using port 8080:
```bash
# Find and terminate the process holding port 8080
lsof -ti :8080 | xargs kill -9
```

---

### Issue 2: Google OAuth "Error 400: redirect_uri_mismatch"
**Cause**: The redirect URI requested by `app.py` does not match the exact URI registered in Google Cloud Console.
**Fix**:
1. Look at the error details in the Google error page. Note the `redirect_uri` parameter (e.g. `http://172.20.183.90.nip.io:8080/auth/callback`).
2. Copy this exact string.
3. Paste it under **Authorized redirect URIs** in your Google Cloud Console OAuth 2.0 Client credentials.
4. Ensure `GOOGLE_REDIRECT_URI` in `round_2_sdc_games/www/app.py` matches it identically.

---

### Issue 3: Stale or Leftover Docker Containers
When players disconnect, their container is automatically removed. If you ever need to clean up all orphaned session containers:
```bash
# Stop and remove all containers starting with jumanji_
docker ps -a --filter "name=jumanji_" -q | xargs -r docker rm -f
```

---

### Issue 4: Resetting Player Database
If you wish to wipe test players and start fresh before the event:
```bash
# Keep table schema but clear users and submissions (preserves admin)
sqlite3 round_2_sdc_games/www/jumanji_auth.db "DELETE FROM users WHERE role != 'admin'; DELETE FROM solved_challenges;"
```

---

### Issue 5: Verifying Container Shell & Hints
To manually test a container environment:
```bash
# Test Round 2 container interactively
docker run --rm -it jumanji-round2:latest /bin/bash

# Inside container:
parrot_hint 1
cat /opt/jungle/ruins/.bravestone_relic
complete JUMANJI{...}
```

---

## 🏁 Summary Checklist for Event Day

- [ ] Docker Desktop is open and running.
- [ ] Both Docker images are built: `docker images | grep jumanji`.
- [ ] Machine local IP identified and configured in `app.py` and Google Cloud Console.
- [ ] Full verification suite executed and passing: `./verify_all.sh` (35/35 checks).
- [ ] Server running: `cd round_2_sdc_games/www && source venv/bin/activate && python3 app.py`.
- [ ] Admin credentials tested: login to `/admin`.
- [ ] Participants connected to `http://<YOUR_IP>.nip.io:8080`.
