
# 🌐 Hosting & Connection Guide: Connecting SDC Games & The Outside CTF Server Anywhere

This guide explains **every single file, line, and environment variable** you need to change when hosting **SDC Games** (Server 1) and the **Cybersecurity Wing CTF Arena** (Outside Server / Server 2) on separate cloud machines, VPS servers, or local venue Wi-Fi networks.

---

## 📑 Table of Contents

1. [How Both Servers Connect (The 2-Minute Summary)](#1-how-both-servers-connect)
2. [Server 1 (SDC Games): All Changes Needed](#2-server-1-sdc-games-all-changes-needed)
3. [Server 2 (Outside CTF Server): All Changes Needed](#3-server-2-outside-ctf-server-all-changes-needed)
4. [External Services Setup (Google OAuth &amp; MongoDB Atlas)](#4-external-services-setup)
5. [Firewall &amp; Port Rules](#5-firewall--port-rules)
6. [3 Ready-to-Use Deployment Scenarios](#6-3-ready-to-use-deployment-scenarios)
   - [Scenario A: Two Cloud VPS with Domains (Recommended)](#scenario-a-two-cloud-vps-with-domains)
   - [Scenario B: Two Cloud VPS with Public IPs (nip.io)](#scenario-b-two-cloud-vps-with-public-ips-nipio)
   - [Scenario C: Single VPS Hosting Both Services](#scenario-c-single-vps-hosting-both-services)
7. [Step-by-Step Launch Checklist](#7-step-by-step-launch-checklist)
8. [Sanity Testing (Run These 3 Commands Before Launch)](#8-sanity-testing-before-launch)
9. [Troubleshooting Common Issues](#9-troubleshooting-common-issues)

---

## 1. How Both Servers Connect

```
+----------------------------------------------------+          +----------------------------------------------------+
|                SERVER 1: SDC GAMES                 |          |             SERVER 2: OUTSIDE CTF SERVER           |
|                                                    |          |                                                    |
|  - React Frontend (Vite)                           |          |  - Flask + SocketIO App (Python)                   |
|  - Node.js / Express API                           |          |  - SQLite DB (jumanji_auth.db)                     |
|  - MongoDB (Users, Attendance, Leaderboard)        |          |  - Docker containers (Round 2 & Round 3)           |
+----------------------------------------------------+          +----------------------------------------------------+
                          |                                                               ^
                          |  [CONNECTION 1: SSO Launch in Player's Browser]               |
                          |  Redirect: http://SERVER_2_URL/auth/launch?token=...          |
                          +---------------------------------------------------------------+
                          |
                          |  [CONNECTION 2: Live Score Webhook (Server-to-Server)]
                          |  POST: http://SERVER_1_URL/api/internal/scores/update
                          |  Header: X-Internal-Secret: <CYBERSEC_SHARED_SECRET>
                          +<--------------------------------------------------------------+
                          |
                          |  [CONNECTION 3: Roster Sync (Server-to-Server)]
                          |  GET: http://SERVER_1_URL/api/internal/cybersec/roster
                          |  Header: X-Internal-Secret: <CYBERSEC_SHARED_SECRET>
                          +<--------------------------------------------------------------+
```

### The 3 Connections:

1. **Player Browser Launch (SSO Handshake)**:
   - When a participant clicks **"⚔️ Enter Level 2 Arena"** on SDC Games, SDC API generates a 5-minute cryptographic HMAC token and redirects the player's browser to Server 2:
     `https://<SERVER_2_URL>/auth/launch?token=<TOKEN>&level=2`
   - Server 2 verifies the signature using the shared secret, logs the player in automatically, and opens their CTF dashboard.
2. **Live Score Webhook (Backend-to-Backend)**:
   - When the player solves a challenge inside the terminal, the Docker container informs Flask, and Flask makes an HTTP POST request directly to Server 1:
     `POST https://<SERVER_1_URL>/api/internal/scores/update`
   - SDC Games instantly awards the points (e.g. +20 pts) and recalculates ranks live on the main leaderboard.
3. **Roster Sync (Admin Tool)**:
   - On Server 2's admin panel (`/admin`), you can click **"Sync Players from SDC Games"**. Server 2 queries `https://<SERVER_1_URL>/api/internal/cybersec/roster` and auto-provisions all registered cybersecurity participants.

---

## 2. Server 1 (SDC Games): All Changes Needed

### Change 1: Edit `sdc-games/apps/api/.env`

This is the main configuration file for the SDC Games backend.

```env
# ==============================================================================
# SDC GAMES BACKEND CONFIGURATION
# Location: sdc-games/apps/api/.env
# ==============================================================================
NODE_ENV=production
HOST=0.0.0.0
PORT=4000

# 1. MONGODB DATABASE
# Set this to your MongoDB Atlas connection string (or local MongoDB)
MONGODB_URI=mongodb+srv://<USER>:<PASSWORD>@<CLUSTER>.mongodb.net/sdc_games?retryWrites=true&w=majority

# 2. WEB ORIGIN (CRITICAL FOR CSRF SECURITY)
# MUST BE the exact URL players type in their browser to access SDC Games (NO trailing slash).
# If this doesn't match the browser URL, Express will reject requests with "ORIGIN_REJECTED".
WEB_ORIGIN=https://games.yourdomain.com

# 3. OUTSIDE CTF SERVER URL
# The public URL where participants can reach Server 2 in their browser (NO trailing slash).
CYBERSEC_WING_URL=https://ctf.yourdomain.com

# 4. SHARED SECRET (CRITICAL FOR HANDSHAKE & WEBHOOKS)
# Any long random string. MUST BE 100% IDENTICAL on both servers!
CYBERSEC_SHARED_SECRET=my_super_secret_shared_key_2026_xyz

# 5. GOOGLE OAUTH CREDENTIALS
# Used for participant Google sign-in on SDC Games.
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-client-secret
# MUST match Authorized Redirect URIs in Google Cloud Console:
GOOGLE_REDIRECT_URI=https://games.yourdomain.com/api/auth/google/callback

# 6. INITIAL SUPER ADMIN (Created automatically on first seed)
ADMIN_USERNAME=sdcadmin
ADMIN_PASSWORD=CreateAStrongPasswordHere123!

# 7. SESSION SETTINGS
SESSION_SECRET=make_a_random_32_character_hex_string_here
TRUST_PROXY=true
```

### Change 2: Edit `sdc-games/apps/web/.env`

This file configures the frontend web server (Vite):

```env
# Location: sdc-games/apps/web/.env
WEB_HOST=0.0.0.0
WEB_PORT=5173
API_PROXY_TARGET=http://127.0.0.1:4000
```

> [!NOTE]
> In production, if you serve the React app via **Nginx** on ports 80/443 instead of `npm run dev`, Nginx will proxy `/api` requests to `http://127.0.0.1:4000` (see Nginx snippet in Section 6).

---

## 3. Server 2 (Outside CTF Server): All Changes Needed

### Change 1: Edit `DAY 1/www/.env`

This file configures the Flask application that hosts the CTF arena.

```env
# ==============================================================================
# CYBERSECURITY WING CTF ARENA CONFIGURATION
# Location: DAY 1/www/.env
# ==============================================================================

# 1. SHARED SECRET
# MUST BE EXACTLY THE SAME STRING as CYBERSEC_SHARED_SECRET on Server 1!
CYBERSEC_SHARED_SECRET=my_super_secret_shared_key_2026_xyz

# 2. SDC GAMES API URL (BACKEND-TO-BACKEND WEBHOOK TARGET)
# The URL where Server 2 sends HTTP requests to reach Server 1's API (NO trailing slash).
# - If Server 1 has a domain: https://games.yourdomain.com
# - If Server 1 uses an IP & port: http://<SERVER_1_IP>:4000
SDC_GAMES_API_URL=https://games.yourdomain.com

# 3. GOOGLE OAUTH (Optional fallback direct login)
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=https://ctf.yourdomain.com/auth/callback
```

### Change 2: Build the Docker Images on Server 2

The CTF terminal sessions run inside Docker containers. You must build them once on Server 2:

```bash
# Navigate to the repo root on Server 2
cd "DAY 1/round2"
docker build -t jumanji-round2:latest -f Dockerfile.r2 .

cd "../round3"
docker build -t jumanji-round3:latest -f Dockerfile.r3 .
```

### Change 3: Verify Docker Container Host Networking

When participants solve flags in their interactive terminal, the container submits the score to Flask:

- `DAY 1/round2/complete` -> calls `http://host.docker.internal:8080/api/score`
- `DAY 1/round3/deploy_override` -> calls `http://host.docker.internal:8080/api/score`

Flask automatically runs containers with:

```bash
--add-host=host.docker.internal:host-gateway
```

> [!IMPORTANT]
> If running on Linux with Docker version < 20.10 where `host-gateway` is unsupported, replace `host.docker.internal` inside `DAY 1/round2/complete` and `DAY 1/round3/deploy_override` with the Linux Docker bridge IP: `172.17.0.1`.

---

## 4. External Services Setup

### 1. Google Cloud Console (OAuth 2.0 Credentials)

Go to [Google Cloud Console](https://console.cloud.google.com/) -> **APIs & Services** -> **Credentials** -> Select your OAuth 2.0 Client ID:

Under **Authorized JavaScript origins**, add:

- `https://games.yourdomain.com` (or `http://<SERVER_1_IP>:5173`)
- `https://ctf.yourdomain.com` (or `http://<SERVER_2_IP>:8080`)

Under **Authorized redirect URIs**, add BOTH:

- `https://games.yourdomain.com/api/auth/google/callback`
- `https://ctf.yourdomain.com/auth/callback`

---

### 2. MongoDB Atlas (Network Access & Whitelisting)

Go to [MongoDB Atlas](https://cloud.mongodb.com/) -> **Security** -> **Network Access**:

- Click **Add IP Address**.
- Add the **Public IPv4 address of Server 1** (SDC Games).
- *(For event day or testing, you can temporarily allow `0.0.0.0/0` - Allow Access From Anywhere).*

---

## 5. Firewall & Port Rules

Configure your Cloud Firewall (AWS Security Group, DigitalOcean Firewall, or Ubuntu UFW):

| Server                         | Port                           | Protocol | Source                  | Purpose                                                                        |
| :----------------------------- | :----------------------------- | :------- | :---------------------- | :----------------------------------------------------------------------------- |
| **Server 1 (SDC Games)** | `80` & `443`               | TCP      | `0.0.0.0/0` (Public)  | Web traffic to SDC Games                                                       |
| **Server 1 (SDC Games)** | `4000`                       | TCP      | Server 2 IP (or Public) | Inbound score webhooks from Server 2 (if not using Nginx reverse proxy on 443) |
| **Server 2 (CTF Site)**  | `80` & `443` (or `8080`) | TCP      | `0.0.0.0/0` (Public)  | Web & WebSocket terminal traffic to CTF site                                   |

---

## 6. 3 Ready-to-Use Deployment Scenarios

### Scenario A: Two Cloud VPS with Domains

- **Server 1**: `https://games.yourdomain.com`
- **Server 2**: `https://ctf.yourdomain.com`

**Server 1 (`sdc-games/apps/api/.env`)**:

```env
WEB_ORIGIN=https://games.yourdomain.com
CYBERSEC_WING_URL=https://ctf.yourdomain.com
CYBERSEC_SHARED_SECRET=jumanji_event_2026_secret_key
GOOGLE_REDIRECT_URI=https://games.yourdomain.com/api/auth/google/callback
```

**Server 2 (`DAY 1/www/.env`)**:

```env
SDC_GAMES_API_URL=https://games.yourdomain.com
CYBERSEC_SHARED_SECRET=jumanji_event_2026_secret_key
GOOGLE_REDIRECT_URI=https://ctf.yourdomain.com/auth/callback
```

---

### Scenario B: Two Cloud VPS with Public IPs (nip.io)

If you don't have custom domains yet, use wildcard DNS via `nip.io`:

- **Server 1 Public IP**: `143.110.150.10` -> `http://143.110.150.10.nip.io:5173`
- **Server 2 Public IP**: `165.22.80.20` -> `http://165.22.80.20.nip.io:8080`

**Server 1 (`sdc-games/apps/api/.env`)**:

```env
HOST=0.0.0.0
PORT=4000
WEB_ORIGIN=http://143.110.150.10.nip.io:5173
CYBERSEC_WING_URL=http://165.22.80.20.nip.io:8080
CYBERSEC_SHARED_SECRET=jumanji_event_2026_secret_key
GOOGLE_REDIRECT_URI=http://143.110.150.10.nip.io:5173/api/auth/google/callback
```

**Server 2 (`DAY 1/www/.env`)**:

```env
SDC_GAMES_API_URL=http://143.110.150.10.nip.io:4000
CYBERSEC_SHARED_SECRET=jumanji_event_2026_secret_key
GOOGLE_REDIRECT_URI=http://165.22.80.20.nip.io:8080/auth/callback
```

---

### Scenario C: Single VPS Hosting Both Services

If hosting both on one machine (e.g. AWS EC2 with public IP `54.200.10.20`):

**Server 1 (`sdc-games/apps/api/.env`)**:

```env
HOST=0.0.0.0
PORT=4000
WEB_ORIGIN=http://54.200.10.20.nip.io:5173
CYBERSEC_WING_URL=http://54.200.10.20.nip.io:8080
CYBERSEC_SHARED_SECRET=jumanji_event_2026_secret_key
```

**Server 2 (`DAY 1/www/.env`)**:

```env
SDC_GAMES_API_URL=http://127.0.0.1:4000
CYBERSEC_SHARED_SECRET=jumanji_event_2026_secret_key
```

---

## 7. Step-by-Step Launch Checklist

### On Server 1 (SDC Games):

1. [ ] Install Node.js v20+ and npm:
    ```bash
    cd sdc-games
    npm install
    ```
2. [ ] Set all values in `sdc-games/apps/api/.env`.
3. [ ] Build the packages:
    ```bash
    npm run build
    ```
4. [ ] Start the servers (via systemd or PM2):
    ```bash
    npm run start
    ```

### On Server 2 (CTF Site):

1. [ ] Install Python 3.10+, Docker, and SQLite:
    ```bash
    cd "DAY 1/www"
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```
2. [ ] Build the challenge Docker images:
    ```bash
    cd "../round2" && docker build -t jumanji-round2:latest -f Dockerfile.r2 .
    cd "../round3" && docker build -t jumanji-round3:latest -f Dockerfile.r3 .
    ```
3. [ ] Set all values in `DAY 1/www/.env`.
4. [ ] Start the Flask CTF server:
    ```bash
    cd "DAY 1/www"
    python3 app.py
    ```

---

## 8. Sanity Testing (Before Launch)

Run these 3 tests from Server 2's terminal to verify that the bridge is 100% operational:

### Test 1: Verify Server-to-Server Authentication & Roster Sync

```bash
curl -i -H "X-Internal-Secret: <YOUR_SHARED_SECRET>" \
  https://games.yourdomain.com/api/internal/cybersec/roster
```

- **Expected Output**: `HTTP 200 OK`
- **Response JSON**: `{"status": "success", "count": ...}`

### Test 2: Verify Live Score Ingestion Webhook

```bash
curl -i -X POST \
  -H "Content-Type: application/json" \
  -H "X-Internal-Secret: <YOUR_SHARED_SECRET>" \
  -d '{"participantId":"TEST_USER","roundId":"day-1-r2","rawScore":20,"checkpoint":"bravestone","checkpointPoints":20}' \
  https://games.yourdomain.com/api/internal/scores/update
```

- **Expected Output**:
  - If participant exists: `HTTP 200 OK` with `{"status":"success"}`
  - If participant doesn't exist: `HTTP 404 Not Found` with `PARTICIPANT_NOT_FOUND`
    *(Both confirm that the network route, port, and shared secret handshake are working perfectly).*

### Test 3: Verify Single Sign-On (SSO) Launch

1. On SDC Games, register a participant and select **Cybersecurity** for Level 2 or Level 3.
2. Mark attendance as **PRESENT** for that level.
3. In **My Updates**, click **⚔️ Enter Level 2 Arena**.
4. You should immediately land in `https://ctf.yourdomain.com/dashboard` logged in as your participant without needing to enter a password!

---

## 9. Troubleshooting Common Issues

### Issue 1: "ORIGIN_REJECTED: Request origin rejected"

- **Cause**: The `WEB_ORIGIN` in `sdc-games/apps/api/.env` does not match the exact URL the user typed in their browser.
- **Fix**: Check your browser address bar. If you access `http://192.168.1.50:5173`, your `WEB_ORIGIN` must be set to `http://192.168.1.50:5173` (no trailing slash).

### Issue 2: "UNAUTHORIZED: Invalid or missing internal secret"

- **Cause**: The `CYBERSEC_SHARED_SECRET` in `sdc-games/apps/api/.env` and `DAY 1/www/.env` do not match.
- **Fix**: Copy the exact string from Server 1 to Server 2 and restart both servers.

### Issue 3: Score solves in container, but SDC Games leaderboard doesn't update

- **Cause**: Server 2 cannot connect to `SDC_GAMES_API_URL` over the network (firewall blocking port 4000, or invalid URL).
- **Fix**: Check `DAY 1/www/.env` -> `SDC_GAMES_API_URL`. Run `curl -I <SDC_GAMES_API_URL>/api/health` from Server 2's terminal. If it times out, open port 4000 in Server 1's firewall.
- **Fail-Safe**: If disconnected during an event, scores are safely queued in `pending_score_syncs` in SQLite and retried automatically every 30 seconds once the connection returns. You can also download the CSV from Server 2's Admin panel at any time.

### Issue 4: "Error: redirect_uri_mismatch" during Google Login

- **Cause**: The URL in `GOOGLE_REDIRECT_URI` is not listed under Authorized Redirect URIs in Google Cloud Console.
- **Fix**: Copy the exact redirect URL from the Google error screen and add it to your Google Cloud Console credentials.
