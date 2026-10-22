#!/bin/bash

# setup_level2.sh
# Injected vars: PLAYER_ID, PLAYER_USERNAME, CTF_TOKEN
SECRET="8f7b6c5d4a3e2f1g0h9i8j7k6l5m4n3"

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

# 1. Mainframe Database Setup (Database Enum Challenge)
mkdir -p /level2
cd /level2 || exit 1
rm -f mainframe.db
sqlite3 mainframe.db "CREATE TABLE overrides (id INTEGER PRIMARY KEY, target TEXT, code TEXT);"
sqlite3 mainframe.db "INSERT INTO overrides (target, code) VALUES ('admin_access', '$(generate_override user)');"
sqlite3 mainframe.db "INSERT INTO overrides (target, code) VALUES ('decoy_1', 'OVERRIDE-USER-invalid1');"
sqlite3 mainframe.db "INSERT INTO overrides (target, code) VALUES ('decoy_2', 'OVERRIDE-USER-invalid2');"
chmod 444 mainframe.db

# Hidden .env file with mainframe DB config
cat << 'EOF' > .env
DB_TYPE=sqlite3
DB_FILE=mainframe.db
ADMIN_TABLE=overrides
EOF
chmod 444 .env

# 2. Root Override (SUID Root Challenge)
echo "$(generate_override root)" > /root/core_override.txt
chmod 400 /root/core_override.txt

chown -R recon_user:recon_user /level2

echo "==================================================="
echo "    Welcome to the Simulation Core, $PLAYER_USERNAME!"
echo "    If you get lost, type: nigel_comms"
echo "    To submit an override: deploy_override OVERRIDE-..."
echo "==================================================="
