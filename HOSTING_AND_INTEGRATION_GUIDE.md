# 🌐 Cross-Server Hosting & Deployment Integration Guide
### Connecting SDC Games Platform with the Cybersecurity Wing on Any Host / Cloud

This guide explains **every configuration, environment variable, port, and network setting** required to deploy and connect the **Main SDC Games Platform** and the **Cybersecurity Wing Arena** when hosting them on separate VPS servers, cloud providers (AWS, DigitalOcean, GCP), or venue LAN networks.

---

## 1. High-Level Architecture & Traffic Flow

When deployed across separate machines (or different ports/domains):

```
+----------------------------------------------------------------------------------------------------+
|                                      SERVER 1: SDC GAMES                                           |
|                               (e.g., https://games.yourdomain.com)                                 |
|                                                                                                    |
|   Frontend (Vite / React)                     Backend (Node.js / Express API)                      |
|   Port: 5173 (or 80/443 via Nginx)            Port: 4000                                           |
|   +------------------------------------+      +-----------------------------------------------+    |
|   | - Participant signs in with Google |      | - MongoDB (Users, Priorities, Attendance)     |    |
|   | - Chooses Cybersecurity (L2 / L3)  |      | - Verifies domain choice & NFC room check-in  |    |
|   | - Clicks "Enter Cybersec Arena"    | ---> | - Issues signed launch token                  |    |
|   +------------------------------------+      | - Exposes /api/internal/scores/update         |    |
+----------------------|------------------------+-------------------+---------------------------+----+
                       |                                            ^
                       | 1. Redirect to Arena with Token            | 2. Server-to-Server
                       |    (via Participant Browser)               |    Score Webhook
                       v                                            |    (X-Internal-Secret)
+-------------------------------------------------------------------|--------------------------------+
|                               SERVER 2: CYBERSECURITY WING ARENA                                   |
|                                (e.g., https://ctf.yourdomain.com)                                  |
|                                                                                                    |
|   Flask + SocketIO Engine (Port 8080 or 80/443 via Nginx)                                          |
|   +-------------------------------------------------------------------------------------------+    |
|   | - /auth/launch: Verifies HMAC signature, auto-provisions user in local SQLite             |    |
|   | - Seeds session: user_id, participant_id, authorized_levels                               |    |
|   | - On flag solve: pushes live score to Server 1 (/api/internal/scores/update)              |    |
|   +------------------------------------+------------------------------------------------------+    |
|                                        |                                                           |
|                                        v Launches Docker PTY Containers                            |
|                    +---------------------------------------+                                       |
|                    |  jumanji-round2 / jumanji-round3       |                                       |
|                    |  - Submits flag back to Flask:8080    |                                       |
|                    +---------------------------------------+                                       |
+----------------------------------------------------------------------------------------------------+
```

### The 2 Communication Channels:
1. **Browser Navigation (SSO Launch)**:
   - When the player clicks **"Enter Cybersec Arena"** on SDC Games, the browser is redirected to Server 2:
     `http://<SERVER_2_HOST>:8080/auth/launch?token=<SIGNED_TOKEN>&level=2`
2. **Backend Server-to-Server (Live Score Webhooks & Roster Sync)**:
   - When a player solves a flag inside the CTF terminal, Flask sends an HTTP POST request directly from Server 2 to Server 1:
     `POST http://<SERVER_1_HOST>:4000/api/internal/scores/update` with header `X-Internal-Secret: <SHARED_SECRET>`.

---

## 2. Server 1 Configuration (Main SDC Games)

### File: `sdc-games/apps/api/.env`

When deploying SDC Games to a new server or IP address, configure these keys:

```env
# ==============================================================================
# SDC GAMES API CONFIGURATION
# ==============================================================================
NODE_ENV=production
HOST=0.0.0.0
PORT=4000

# 1. DATABASE (MongoDB Atlas or Self-Hosted MongoDB)
# Note: Ensure Network Access in MongoDB Atlas has your Server 1 IP whitelisted (or 0.0.0.0/0).
MONGODB_URI=mongodb+srv://sdclubgames_db_user:CXxQ1V5kVJbHtPrJ@sdcgames26.nivm9mr.mongodb.net/sdc_games?retryWrites=true&w=majority

# 2. PUBLIC WEB ORIGIN
# The public URL where participants open SDC Games in their browser (NO trailing slash).
WEB_ORIGIN=https://games.yourdomain.com

# 3. CYBERSECURITY WING BRIDGE
# Must match CYBERSEC_SHARED_SECRET on Server 2!
CYBERSEC_SHARED_SECRET=your_long_random_shared_secret_key_2026

# The public URL where participants reach Server 2 in their browser (NO trailing slash).
CYBERSEC_WING_URL=https://ctf.yourdomain.com
# (Or if using raw IP/port: http://192.168.1.50:8080 or http://your-ip.nip.io:8080)

# 4. INITIAL SUPER ADMIN ACCOUNT (Used only on first seed)
ADMIN_USERNAME=sdcadmin
ADMIN_PASSWORD=YourSecureAdminPassword123!

# 5. GOOGLE OAUTH CONFIGURATION
# Authorized Redirect URI in Google Cloud Console MUST match:
# https://games.yourdomain.com/api/auth/google/callback
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=https://games.yourdomain.com/api/auth/google/callback

# 6. SESSIONS
SESSION_SECRET=at_least_32_characters_random_hex_string_here
TRUST_PROXY=true
```

---

## 3. Server 2 Configuration (Cybersecurity Wing / Flask)

### File: `DAY 1/www/.env`

On the dedicated CTF server, configure these keys:

```env
# ==============================================================================
# CYBERSECURITY WING FLASK CONFIGURATION
# ==============================================================================

# 1. SHARED SECRET
# MUST MATCH CYBERSEC_SHARED_SECRET from Server 1 exactly!
CYBERSEC_SHARED_SECRET=your_long_random_shared_secret_key_2026

# 2. SDC GAMES API URL (Backend-to-Backend endpoint)
# The URL where Server 2 can reach Server 1 over HTTP/HTTPS to dispatch scores.
# - If on the same VPS: http://127.0.0.1:4000
# - If on different VPSs: https://games.yourdomain.com (or http://<SERVER_1_PUBLIC_IP>:4000)
# - If on local LAN: http://192.168.1.10:4000
SDC_GAMES_API_URL=https://games.yourdomain.com

# 3. GOOGLE OAUTH CONFIGURATION (For fallback direct logins on CTF site)
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=https://ctf.yourdomain.com/auth/callback
```

---

## 4. Summary Matrix of Settings to Change

| Setting | Location on Server 1 (SDC Games) | Location on Server 2 (CTF Site) | Rule / Requirement |
| :--- | :--- | :--- | :--- |
| **Shared Secret** | `sdc-games/apps/api/.env`<br>`CYBERSEC_SHARED_SECRET` | `DAY 1/www/.env`<br>`CYBERSEC_SHARED_SECRET` | **Must be 100% identical**. Used to sign launch tokens and verify webhook scores. |
| **CTF Public URL** | `sdc-games/apps/api/.env`<br>`CYBERSEC_WING_URL` | Used as public domain/IP | The URL the player's browser navigates to when clicking "Enter Cybersec Arena". |
| **SDC API URL** | Automatically listens on `HOST:PORT` | `DAY 1/www/.env`<br>`SDC_GAMES_API_URL` | The URL Server 2 calls to send score webhooks (`/api/internal/scores/update`). |
| **Google Redirect URIs** | `sdc-games/apps/api/.env`<br>`GOOGLE_REDIRECT_URI` | `DAY 1/www/.env`<br>`GOOGLE_REDIRECT_URI` | Must both be registered under **Authorized Redirect URIs** in Google Cloud Console. |
| **MongoDB Atlas** | `sdc-games/apps/api/.env`<br>`MONGODB_URI` | *Not connected to MongoDB* (uses SQLite) | Whitelist Server 1's public IP (or `0.0.0.0/0`) in MongoDB Atlas Network Access. |

---

## 5. Docker Container Network Configuration (Server 2)

Inside `DAY 1/www/app.py`, Docker containers for Round 2 and Round 3 are spawned dynamically:
```bash
docker run -it --rm --name jumanji_r2_... \
  --add-host=host.docker.internal:host-gateway \
  jumanji-round2:latest ...
```

### Critical Rules for Server 2 Docker:
1. **Linux / Ubuntu Host**:
   - `--add-host=host.docker.internal:host-gateway` works on Docker v20.10+ on Linux.
   - If using an older Docker daemon, replace `host.docker.internal` in `DAY 1/round2/complete` and `DAY 1/round3/deploy_override` with the Docker bridge IP (typically `172.17.0.1`).
2. **Build Docker Images on Server 2**:
   Ensure images are built locally on Server 2 before starting the server:
   ```bash
   cd "DAY 1/round2"
   docker build -t jumanji-round2:latest -f Dockerfile.r2 .
   
   cd "../round3"
   docker build -t jumanji-round3:latest -f Dockerfile.r3 .
   ```

---

## 6. Firewall & Port Requirements

Make sure the respective ports are open in AWS Security Groups / UFW / Cloud firewalls:

### On Server 1 (SDC Games):
- **Port 80 / 443**: Inbound from anywhere (Public web traffic).
- **Port 4000**: Inbound from Server 2 IP (If Server 2 calls API directly on port 4000 instead of reverse proxy).

### On Server 2 (Cybersecurity Wing):
- **Port 80 / 443** (or **8080**): Inbound from anywhere (Participants accessing arena terminals).

---

## 7. Step-by-Step Deployment Checklist

### Step 1: Deploy Server 1 (SDC Games)
1. Clone the repo and navigate to `sdc-games`:
   ```bash
   cd sdc-games
   npm install
   ```
2. Configure `sdc-games/apps/api/.env` with your `MONGODB_URI`, `WEB_ORIGIN`, `CYBERSEC_WING_URL`, and `CYBERSEC_SHARED_SECRET`.
3. Build all workspaces:
   ```bash
   npm run build
   ```
4. Start API and Web servers (via PM2, systemd, or Docker):
   ```bash
   # Production build run:
   npm run start
   ```

### Step 2: Deploy Server 2 (Cybersecurity Wing)
1. On Server 2, navigate to `DAY 1/www`:
   ```bash
   cd "DAY 1/www"
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
2. Build the challenge Docker images:
   ```bash
   docker build -t jumanji-round2:latest -f ../round2/Dockerfile.r2 ../round2
   docker build -t jumanji-round3:latest -f ../round3/Dockerfile.r3 ../round3
   ```
3. Configure `DAY 1/www/.env`:
   - Set `CYBERSEC_SHARED_SECRET` (matching Server 1).
   - Set `SDC_GAMES_API_URL=https://games.yourdomain.com`.
4. Start the Flask CTF server:
   ```bash
   python3 app.py
   ```

---

## 8. Verification & Sanity Test

Once both servers are running:

1. **Verify Backend Connectivity from Server 2 to Server 1**:
   Run this curl command from Server 2:
   ```bash
   curl -i -H "X-Internal-Secret: <YOUR_SECRET>" https://games.yourdomain.com/api/internal/cybersec/roster
   ```
   **Expected Response**: `HTTP 200 OK` with JSON `{"status": "success", "count": ...}`.

2. **Verify Single Sign-On (SSO)**:
   - Sign in as a participant on SDC Games (`https://games.yourdomain.com`).
   - Pick **Cybersecurity** for Level 2 or Level 3.
   - Have attendance marked `PRESENT`.
   - Click **⚔️ Enter Level 2 Arena** on **My Updates**.
   - Verify that you land in `https://ctf.yourdomain.com/dashboard` logged in immediately without a password prompt.

3. **Verify Live Score Ingestion**:
   - Solve Dr. Bravestone flag (`JUMANJI{bravestone_...}`).
   - Check SDC Games Standings: the participant's score should instantly update by **+20 pts** and ranks recompute live!
