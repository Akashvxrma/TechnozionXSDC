#!/bin/bash

# setup_level3.sh
# Injected vars: PLAYER_ID, PLAYER_USERNAME, CTF_TOKEN
SECRET="${CTF_MASTER_SECRET:-${SECRET:-8f7b6c5d4a3e2f1g0h9i8j7k6l5m4n3}}"

if [ -n "$CTF_TOKEN" ]; then
    echo -n "$CTF_TOKEN" > /etc/ctf_token
    chmod 644 /etc/ctf_token
fi

cat << EOF > /etc/profile.d/ctf_env.sh
export PLAYER_ID="$PLAYER_ID"
export PLAYER_USERNAME="$PLAYER_USERNAME"
export CTF_TOKEN="$CTF_TOKEN"
EOF
chmod 644 /etc/profile.d/ctf_env.sh

generate_override() {
    local level=$1
    local hash=$(echo -n "${PLAYER_ID}:${level}:${SECRET}" | md5sum | cut -d' ' -f1 | head -c 8)
    echo "OVERRIDE-${level^^}-${hash}"
}

generate_override_hash() {
    local level=$1
    echo -n "${PLAYER_ID}:${level}:${SECRET}" | md5sum | cut -d' ' -f1 | head -c 8
}

# 1. Mainframe Database Setup (Database Enum Challenge)
mkdir -p /level3 /level2
cd /level3 || exit 1
rm -f mainframe.db

USER_HASH=$(generate_override_hash user)
H1="${USER_HASH:0:4}"
H2="${USER_HASH:4:4}"

sqlite3 mainframe.db "CREATE TABLE _mainframe_vault (id INTEGER PRIMARY KEY, subsystem TEXT, tier_tag TEXT, token_seg1 TEXT, token_seg2 TEXT);"
sqlite3 mainframe.db "INSERT INTO _mainframe_vault VALUES (1, 'admin_access', 'USER', '$H1', '$H2');"
sqlite3 mainframe.db "INSERT INTO _mainframe_vault VALUES (2, 'telemetry_sink', 'DECOY', 'fa10', '9bc2');"
sqlite3 mainframe.db "INSERT INTO _mainframe_vault VALUES (3, 'aux_matrix', 'DECOY', 'c73e', '82a1');"
sqlite3 mainframe.db "INSERT INTO _mainframe_vault VALUES (4, 'grid_monitor', 'DECOY', '910b', '44f0');"
sqlite3 mainframe.db "INSERT INTO _mainframe_vault VALUES (5, 'core_cooling', 'DECOY', 'e52a', '118c');"
sqlite3 mainframe.db "INSERT INTO _mainframe_vault VALUES (6, 'comm_relays', 'DECOY', '3d77', 'b001');"
sqlite3 mainframe.db "INSERT INTO _mainframe_vault VALUES (7, 'sensor_pod', 'DECOY', '702f', 'a894');"

sqlite3 mainframe.db "CREATE VIEW overrides AS SELECT id, subsystem AS target, ('OVERRIDE-' || tier_tag || '-' || token_seg1 || token_seg2) AS code FROM _mainframe_vault;"
chmod 444 mainframe.db

# Hidden .env file with mainframe DB config
cat << 'EOF' > .env
DB_TYPE=sqlite3
DB_FILE=mainframe.db
ADMIN_TABLE=overrides
EOF
chmod 444 .env

# Mirror into /level2 if separate dir
if [ ! -L /level2 ]; then
    cp -p mainframe.db .env /level2/ 2>/dev/null || true
    chown -R recon_user:recon_user /level2 2>/dev/null || true
fi

# 2. Root Override (SUID Root Challenge)
echo "$(generate_override root)" > /root/core_override.txt
chmod 400 /root/core_override.txt

chown -R recon_user:recon_user /level3

echo "==================================================="
echo "    Welcome to the Simulation Core, $PLAYER_USERNAME!"
echo "    If you get lost, type: nigel_comms"
echo "    To submit an override: deploy_override OVERRIDE-..."
echo "==================================================="

# Security hardening: Remove setup scripts so secrets cannot be inspected by recon_user
rm -f /usr/local/bin/setup_level*.sh 2>/dev/null || true
unset SECRET CTF_MASTER_SECRET

