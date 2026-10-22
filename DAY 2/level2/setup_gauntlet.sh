#!/bin/bash
# setup_gauntlet.sh - Dynamic In-Container Challenge Setup for Day 2 Jumanji Gauntlet
# Variables passed via environment:
# TEAM_ID, TEAM_NAME, TEAM_ROLE, MATCH_ID, PHASE, CTF_TOKEN, SECRET

SECRET="${SECRET:-8f7b6c5d4a3e2f1g0h9i8j7k6l5m4n3}"
TEAM_ID="${TEAM_ID:-1}"
MATCH_ID="${MATCH_ID:-1}"
PHASE="${PHASE:-phase1_pods}"
TEAM_ROLE="${TEAM_ROLE:-navigator}"

if [ -n "$CTF_TOKEN" ]; then
    echo -n "$CTF_TOKEN" > /etc/ctf_token
    chmod 644 /etc/ctf_token
fi

cat << EOF > /etc/profile.d/gauntlet_env.sh
export TEAM_ID="$TEAM_ID"
export TEAM_NAME="$TEAM_NAME"
export TEAM_ROLE="$TEAM_ROLE"
export MATCH_ID="$MATCH_ID"
export GAUNTLET_PHASE="$PHASE"
export CTF_TOKEN="$CTF_TOKEN"
EOF
chmod 644 /etc/profile.d/gauntlet_env.sh

generate_nav_key() {
    local relic=$1
    echo -n "${TEAM_ID}:${MATCH_ID}:${relic}:nav:${SECRET}" | md5sum | cut -d' ' -f1 | head -c 8
}

generate_cart_key() {
    local relic=$1
    echo -n "${TEAM_ID}:${MATCH_ID}:${relic}:cart:${SECRET}" | md5sum | cut -d' ' -f1 | head -c 8
}

mkdir -p /gauntlet /opt/jungle
chown -R recon_user:recon_user /gauntlet /opt/jungle 2>/dev/null || true

# -------------------------------------------------------------
# PHASE 1: JUNGLE PODS CHALLENGES
# -------------------------------------------------------------
if [ "$PHASE" = "phase1_pods" ] || [ "$PHASE" = "all" ]; then
    mkdir -p /gauntlet/compass /gauntlet/blade /gauntlet/jaguar /gauntlet/idol

    # 1. Sun Compass: Port 4141 local daemon
    NAV_COMPASS=$(generate_nav_key "compass")
    pkill -f 'compass_daemon' 2>/dev/null || true
    cat << PYEOF > /gauntlet/compass/compass_daemon.py
import socket, sys
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    s.bind(('127.0.0.1', 4141))
    s.listen(5)
    while True:
        conn, addr = s.accept()
        conn.sendall(b"=== JUMANJI SATELLITE BEACON ACTIVE ===\n")
        conn.sendall(f"NAVIGATOR KEY: NAV_COMPASS_{NAV_COMPASS}\n".encode())
        conn.sendall(b"HINT: Cartographer must find CART_COMPASS key from telemetry web radar.\n")
        conn.close()
except Exception:
    sys.exit(0)
PYEOF
    python3 /gauntlet/compass/compass_daemon.py >/dev/null 2>&1 &

    # 2. Obsidian Blade: Sudo /usr/bin/find or root file
    NAV_BLADE=$(generate_nav_key "blade")
    mkdir -p /root/blade_vault
    echo "NAVIGATOR KEY: NAV_BLADE_${NAV_BLADE}" > /root/blade_vault/blade_key.txt
    chmod 400 /root/blade_vault/blade_key.txt
    echo "recon_user ALL=(root) NOPASSWD: /usr/bin/find" > /etc/sudoers.d/99_gauntlet_find
    chmod 440 /etc/sudoers.d/99_gauntlet_find

    # 3. Jaguar Fang: Hidden file & base64
    NAV_JAGUAR=$(generate_nav_key "jaguar")
    mkdir -p /opt/jungle/jaguar_shrine
    echo "NAVIGATOR KEY: NAV_JAGUAR_${NAV_JAGUAR}" | base64 > /opt/jungle/jaguar_shrine/.totem_cipher
    chmod 444 /opt/jungle/jaguar_shrine/.totem_cipher

    # 4. Golden Idol: Process inspection
    NAV_IDOL=$(generate_nav_key "idol")
    pkill -f 'idol_keeper' 2>/dev/null || true
    bash -c "exec -a 'idol_keeper NAV_IDOL_${NAV_IDOL}' sleep 7200" >/dev/null 2>&1 &
fi

# -------------------------------------------------------------
# PHASE 2: MIRROR TEMPLE DUELS
# -------------------------------------------------------------
if [ "$PHASE" = "phase2_duels" ] || [ "$PHASE" = "all" ]; then
    mkdir -p /gauntlet/temple/mirror /gauntlet/temple/sun /gauntlet/temple/serpent /gauntlet/temple/moon /gauntlet/temple/skull

    # Mirror Shard
    NAV_MIRROR=$(generate_nav_key "mirror_shard")
    echo "NAV_MIRROR_${NAV_MIRROR}" > /gauntlet/temple/mirror/.reflections

    # Sun Disk
    NAV_SUNDISK=$(generate_nav_key "sun_disk")
    pkill -f 'sundisk_api' 2>/dev/null || true
    cat << PYEOF > /gauntlet/temple/sun/sundisk_api.py
import socket, sys
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    s.bind(('127.0.0.1', 5050))
    s.listen(5)
    while True:
        conn, addr = s.accept()
        req = conn.recv(1024)
        body = f"NAV_SUNDISK_{NAV_SUNDISK}\n"
        resp = f"HTTP/1.1 200 OK\r\nContent-Length: {len(body)}\r\n\r\n{body}"
        conn.sendall(resp.encode())
        conn.close()
except Exception:
    sys.exit(0)
PYEOF
    python3 /gauntlet/temple/sun/sundisk_api.py >/dev/null 2>&1 &

    # Serpent Eye (SQLite database)
    NAV_SERPENT=$(generate_nav_key "serpent_eye")
    sqlite3 /gauntlet/temple/serpent/vault.db "CREATE TABLE IF NOT EXISTS sanctum (id INTEGER PRIMARY KEY, secret TEXT);"
    sqlite3 /gauntlet/temple/serpent/vault.db "INSERT INTO sanctum (secret) VALUES ('NAV_SERPENT_${NAV_SERPENT}');"
    chmod 444 /gauntlet/temple/serpent/vault.db

    # Moon Crystal
    NAV_MOON=$(generate_nav_key "moon_crystal")
    mkdir -p /root/moon_altar
    echo "NAV_MOON_${NAV_MOON}" > /root/moon_altar/altar_seal.txt
    chmod 400 /root/moon_altar/altar_seal.txt
    echo "recon_user ALL=(root) NOPASSWD: /bin/cat /root/moon_altar/altar_seal.txt" > /etc/sudoers.d/99_gauntlet_moon
    chmod 440 /etc/sudoers.d/99_gauntlet_moon

    # Temple Skull
    NAV_SKULL=$(generate_nav_key "temple_skull")
    # Rot13 encoded skull key
    echo "NAV_SKULL_${NAV_SKULL}" | tr 'A-Za-z' 'N-ZA-Mn-za-m' > /gauntlet/temple/skull/ancient_chant.txt
fi

# -------------------------------------------------------------
# PHASE 4: FINAL ROLL (Chained Recon -> SQLi -> SUID Root)
# -------------------------------------------------------------
if [ "$PHASE" = "phase4_final" ] || [ "$PHASE" = "all" ]; then
    mkdir -p /gauntlet/final /root
    NAV_FINAL=$(generate_nav_key "final_jewel")
    echo "JUMANJI-VICTORY-ROOT-${NAV_FINAL}" > /root/final_jewel.txt
    chmod 400 /root/final_jewel.txt

    cat << 'CEOF' > /tmp/lift_gauntlet.c
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int main() {
    char *chant = getenv("CHANT");
    if (chant && strcmp(chant, "JUMANJI_GAUNTLET") == 0) {
        printf("THE JUMANJI CHANT ECHOES! ANCIENT GATES SLAM OPEN! WELCOME, GRANDMASTER.\n");
        setuid(0);
        setgid(0);
        system("/bin/bash -p");
    } else {
        printf("The Gauntlet Seal remains locked. CHANT is missing or incorrect.\n");
        printf("HINT: Set CHANT=JUMANJI_GAUNTLET in your environment and invoke this again.\n");
    }
    return 0;
}
CEOF
    gcc /tmp/lift_gauntlet.c -o /usr/local/bin/lift_gauntlet 2>/dev/null || cp /usr/local/bin/lift_curse /usr/local/bin/lift_gauntlet 2>/dev/null || true
    chown root:root /usr/local/bin/lift_gauntlet 2>/dev/null || true
    chmod 4755 /usr/local/bin/lift_gauntlet 2>/dev/null || true
fi

# Universal complete submission helper
cat << 'COMPLETE_EOF' > /usr/local/bin/complete
#!/bin/bash
if [ -z "$1" ]; then
  echo "Usage: complete JUMANJI{...} or complete NAV_... CART_..."
  exit 1
fi

FLAG="$1"
PART2="$2"
TOKEN="${CTF_TOKEN:-$(cat /etc/ctf_token 2>/dev/null)}"

curl -s -X POST -H "Content-Type: application/json" \
  -d "{\"flag\":\"$FLAG\", \"part2\":\"$PART2\", \"token\":\"$TOKEN\", \"team_id\":\"$TEAM_ID\"}" \
  http://host.docker.internal:8080/gauntlet/relic/solve | jq -r '. | if .status == "success" then "RELIC SECURED! +" + (.points_awarded|tostring) + " POINTS. (" + (.total_points|tostring) + " PTS TOTAL)" elif .status == "split_key_required" then "SPLIT KEY REQUIRED: " + .message elif .status == "already_solved" then "RELIC ALREADY SECURED." else "ERROR: " + (.error // "Invalid relic flag.") end'
COMPLETE_EOF
chmod 755 /usr/local/bin/complete

echo "==================================================="
echo "   THE JUMANJI GAUNTLET - TEAM $TEAM_NAME (#$TEAM_ID)"
echo "   Role: $TEAM_ROLE | Phase: $PHASE"
echo "   Submit relics with: complete JUMANJI{...}"
echo "==================================================="
