# 🚀 Production Hosting & Operations Manual

This guide provides the complete operational manual for deploying, configuring, and hosting the standalone Technozion CTF Game Server on AWS or Linux servers.

---

## 1. Network & Port Allocation Table

| Port | Service | Process / Daemon | Required For |
| :--- | :--- | :--- | :--- |
| **`443`** | **HTTPS / WSS Reverse Proxy** | Nginx + Certbot SSL | Production player access, WebSockets, Google OAuth compliance |
| **`80`** | **HTTP Reverse Proxy** | Nginx | HTTP -> HTTPS redirect and ACME verification |
| **`8080`** | **CTF Game Server** | `python3 app.py` (Flask + Socket.IO) | Core CTF server: HUDs, Avatars, Mainframe, Gauntlet, Terminal PTY |

---

## 2. Environment Configuration (`DAY 1/www/.env`)

Ensure the file `DAY 1/www/.env` exists with the following production configuration:

```ini
# Flask Security Secrets
FLASK_SECRET_KEY=generate_with_openssl_rand_hex_32
CTF_MASTER_SECRET=generate_with_openssl_rand_hex_32
CYBERSEC_SHARED_SECRET=generate_with_openssl_rand_hex_32

# Origin & WebSocket Security (Matches public domain or IP)
WEB_ORIGIN=https://ctf.yourdomain.com

# Google OAuth 2.0 Credentials (Mandatory for Player Sign-In)
GOOGLE_CLIENT_ID=your_google_client_id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_google_client_secret
GOOGLE_REDIRECT_URI=https://ctf.yourdomain.com/auth/callback

# Default Admin Credentials
ADMIN_USERNAME=admin
ADMIN_PASSWORD=YourStrongAdminPassword2026!

# MongoDB Atlas Sync (Optional - leave blank if managing players in Admin Portal)
SDC_MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/?retryWrites=true&w=majority
SDC_MONGODB_DB_NAME=test
```

---

## 3. Step-by-Step Docker Container Build Commands

Build all three challenge container images before starting the platform:

```bash
# 1. Day 1 Level 2 (Avatar Reconnaissance)
docker build -t jumanji-level2:latest "DAY 1/level2" -f "DAY 1/level2/Dockerfile"

# 2. Day 1 Level 3 (Simulation Core Mainframe)
docker build -t jumanji-level3:latest "DAY 1/level3" -f "DAY 1/level3/Dockerfile"

# 3. Day 2 Level 2 (The Jumanji Gauntlet)
docker build -t jumanji-gauntlet:latest "DAY 2/level2" -f "DAY 2/level2/Dockerfile.gauntlet"
```

Verify images are present:

```bash
docker images | grep jumanji
```

---

## 4. Starting the CTF Game Server

### A. Development / Testing Launch

```bash
cd "DAY 1/www"
source venv/bin/activate
python3 app.py
```

### B. Production Systemd Daemon (`jumanji-ctf.service`)

Create `/etc/systemd/system/jumanji-ctf.service`:

```ini
[Unit]
Description=Jumanji CTF Game Server Daemon
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=ubuntu
Group=docker
WorkingDirectory=/home/ubuntu/ctf-platform/DAY 1/www
EnvironmentFile=/home/ubuntu/ctf-platform/DAY 1/www/.env
ExecStart=/home/ubuntu/ctf-platform/DAY 1/www/venv/bin/python3 app.py
Restart=always
RestartSec=5
StandardOutput=append:/var/log/jumanji-ctf.log
StandardError=append:/var/log/jumanji-ctf.error.log
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable jumanji-ctf
sudo systemctl start jumanji-ctf
```

---

## 5. Synchronizing Roster from MongoDB (Optional)

To sync registered participants from MongoDB Atlas into the CTF platform:

### Method A: Terminal CLI Command
```bash
./DAY\ 1/www/venv/bin/python3 sync_from_mongodb.py
```

### Method B: Web Admin Button
1. Log in to `https://<domain>/admin` (or `http://<IP>:8080/admin`).
2. Click **"Sync Roster from MongoDB"**.

---

## 6. Operational Cheatsheet & Troubleshooting

### Check if Port 8080 is in use:
```bash
lsof -i :8080
```

### Check Systemd Service Status & Logs:
```bash
sudo systemctl status jumanji-ctf
sudo journalctl -u jumanji-ctf -f
```

### Clean up orphaned test Docker containers:
```bash
docker ps -a --filter "name=jumanji_" -q | xargs docker rm -f
```

### Run Full Verification Test Suite (52 Tests):
```bash
./verify_all.sh
```
