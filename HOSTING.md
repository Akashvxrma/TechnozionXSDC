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

Create the server launcher script `/home/ubuntu/ctf-platform/start_server.sh`:

```bash
#!/bin/bash
set -e
cd "/home/ubuntu/ctf-platform/DAY 1/www"
exec "/home/ubuntu/ctf-platform/DAY 1/www/venv/bin/python3" app.py
```

Make it executable:
```bash
chmod +x /home/ubuntu/ctf-platform/start_server.sh
```

Create `/etc/systemd/system/jumanji-ctf.service`:

```ini
[Unit]
Description=Jumanji CTF Game Server Daemon
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=ubuntu
Group=ubuntu
SupplementaryGroups=docker
WorkingDirectory=/home/ubuntu/ctf-platform
ExecStart=/home/ubuntu/ctf-platform/start_server.sh
Restart=always
RestartSec=3
StandardOutput=append:/var/log/jumanji-ctf.log
StandardError=append:/var/log/jumanji-ctf.error.log
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now jumanji-ctf
```

---

## 5. Nginx Reverse Proxy Configuration

Create `/etc/nginx/sites-available/jumanji-ctf`:

```nginx
server {
    listen 80 default_server;
    listen [::]:80 default_server;

    server_name _;

    client_max_body_size 50M;

    # WebSocket Proxy for interactive terminal PTY
    location /socket.io/ {
        proxy_pass http://127.0.0.1:8080/socket.io/;
        proxy_http_version 1.1;
        proxy_buffering off;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
    }

    # Main CTF application
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
    }
}
```

Enable and reload:
```bash
sudo rm -f /etc/nginx/sites-enabled/default
sudo ln -sf /etc/nginx/sites-available/jumanji-ctf /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
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

---

## 7. Applying Updates to AWS EC2 Hosting (Production Deployment Guide)

When updating the CTF platform with new features (such as ID/Password player authentication, Day 2 Gauntlet leaderboards, or squad allotments), follow these steps on your AWS EC2 instance:

### Step 1: Connect to AWS EC2 Instance via SSH
```bash
ssh -i /path/to/your-key.pem ubuntu@<AWS_EC2_PUBLIC_IP>
```

### Step 2: Navigate to CTF Project Directory & Pull Changes
```bash
cd /home/ubuntu/ctf-platform
git pull origin main
```

### Step 3: Verify Environment Configuration (`DAY 1/www/.env`)
Ensure `DAY 1/www/.env` contains your correct `WEB_ORIGIN`, `ADMIN_PASSWORD`, and OAuth secrets:
```bash
cat "DAY 1/www/.env"
```

### Step 4: Restart the Systemd Game Service
The SQLite database schema and tables will automatically initialize upon server start:
```bash
sudo systemctl restart jumanji-ctf
```

### Step 5: Check Service Status and Logs
Ensure the CTF game server booted cleanly on port 8080:
```bash
sudo systemctl status jumanji-ctf --no-pager
sudo journalctl -u jumanji-ctf -n 40 --no-pager
```

### Step 6: Verify Nginx Reverse Proxy
```bash
sudo nginx -t
sudo systemctl reload nginx
```

### Step 7: Post-Deployment Smoke Verification
1. Open `http://<AWS_EC2_PUBLIC_IP>/login` in your browser.
2. Verify dual sign-in options are visible: **"Continue with Google"** and **"Sign in with ID & Password"**.
3. Log in with admin credentials (`admin` / `ADMIN_PASSWORD`).
4. Click on the **"Day 2 Gauntlet leaderboard"** tab in `/admin` and confirm all 16 squads, assigned player IDs, and scores are displayed.
5. Click **"Register New Player"** and verify the Day 2 Level 2 allotment checkbox and squad dropdown.

### Step 8: Run Automated Security Verification Suite
Verify all patches against race conditions, rate-limiting, and concurrency locks:
```bash
python3 test_security.py
```
Expected output: **`TEST RESULTS: 8/8 TESTS PASSED`**.
