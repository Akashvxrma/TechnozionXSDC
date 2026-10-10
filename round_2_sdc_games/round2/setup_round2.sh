#!/bin/bash

# setup_round2.sh
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

generate_flag() {
    local avatar=$1
    local hash=$(echo -n "${PLAYER_ID}:${avatar}:${SECRET}" | md5sum | cut -d' ' -f1 | head -c 8)
    echo "JUMANJI{${avatar}_${hash}}"
}

# Avatar 1: Bravestone (Hidden file in /bravestone and /opt/jungle/ruins)
mkdir -p /opt/jungle/ruins /bravestone
FLAG_BRAVESTONE="$(generate_flag bravestone)"
echo "$FLAG_BRAVESTONE" > /opt/jungle/ruins/.bravestone_relic
chmod 444 /opt/jungle/ruins/.bravestone_relic
chown -R recon_user:recon_user /bravestone

# Avatar 2: Ruby (Base64 in Documents and /ruby)
mkdir -p /home/recon_user/Documents /ruby
FLAG_RUBY="$(generate_flag ruby)"
echo "$FLAG_RUBY" | base64 > /home/recon_user/Documents/ruby_dance_moves.txt
chmod 444 /home/recon_user/Documents/ruby_dance_moves.txt 
chown -R recon_user:recon_user /home/recon_user/Documents

# Avatar 3: Finbar (Sudo -l to read finbar_admin flag)
mkdir -p /home/finbar_admin /finbar
FLAG_FINBAR="$(generate_flag finbar)"
echo "$FLAG_FINBAR" > /home/finbar_admin/flag.txt
chown finbar_admin:finbar_admin /home/finbar_admin/flag.txt
chmod 400 /home/finbar_admin/flag.txt
cat << 'EOF' > /finbar/finbar_briefing.txt
[CLASSIFIED MEMO - MOUSE FINBAR]
The sacred weapon specs are sealed inside /home/finbar_admin/flag.txt.
Basic recon personnel cannot read this file directly.
HINT: Check your superuser permissions using 'sudo -l'.
EOF
chmod 444 /finbar/finbar_briefing.txt
chown -R recon_user:recon_user /finbar

# Avatar 4: Shelly / Oberon (Process hunting)
mkdir -p /oberon
pkill -f 'map_generator' 2>/dev/null || true
FLAG_OBERON="$(generate_flag oberon)"
bash -c "exec -a 'map_generator $FLAG_OBERON' sleep 3600" >/dev/null 2>&1 &
cat << 'EOF' > /oberon/cartography_notes.txt
[PROFESSOR OBERON FIELD LOG]
My sensor probes and map calculations are running as an active background process.
HINT: Inspect running system processes using 'ps aux | grep map_generator'.
EOF
chmod 444 /oberon/cartography_notes.txt
chown -R recon_user:recon_user /oberon

# Avatar 5: Seaplane (Local Port HTTP server)
mkdir -p /seaplane /tmp/seaplane_broadcast
pkill -f 'http.server 8080' 2>/dev/null || true
FLAG_SEAPLANE="$(generate_flag seaplane)"
echo "$FLAG_SEAPLANE" > /tmp/seaplane_broadcast/index.html
(cd /tmp/seaplane_broadcast && python3 -m http.server 8080 >/dev/null 2>&1 &)
cat << 'EOF' > /seaplane/hangar_radio.txt
[SEAPLANE HANGAR FREQUENCY LOG]
Emergency beacon broadcast is active on localhost port 8080.
HINT: Tune your receiver using 'curl http://127.0.0.1:8080' or check open ports with 'netstat -tuln'.
EOF
chmod 444 /seaplane/hangar_radio.txt
chown -R recon_user:recon_user /seaplane

echo "==================================================="
echo "    Welcome to the Jungle, $PLAYER_USERNAME!"
echo "    If you get lost, type: parrot_hint <1-5>"
echo "    To submit a flag: complete JUMANJI{...}"
echo "==================================================="
