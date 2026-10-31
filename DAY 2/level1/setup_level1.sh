#!/bin/bash

# setup_level1.sh (Day 2 Level 1: Simulation Core Hardened)
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
mkdir -p /level1 /level3 /level2
cd /level1 || cd /level3 || exit 1
rm -f mainframe.db

USER_HASH=$(generate_override_hash user)
H1="${USER_HASH:0:4}"
H2="${USER_HASH:4:4}"

# Schema: Normalized shards with decoy honeypot registry
sqlite3 mainframe.db "CREATE TABLE _system_nodes (id INTEGER PRIMARY KEY, subsystem TEXT, status TEXT, cluster_id INTEGER);"
sqlite3 mainframe.db "INSERT INTO _system_nodes VALUES (1, 'admin_access', 'ONLINE', 101);"
sqlite3 mainframe.db "INSERT INTO _system_nodes VALUES (2, 'telemetry_sink', 'OFFLINE', 102);"
sqlite3 mainframe.db "INSERT INTO _system_nodes VALUES (3, 'aux_matrix', 'OFFLINE', 103);"
sqlite3 mainframe.db "INSERT INTO _system_nodes VALUES (4, 'grid_monitor', 'DEPRECATED', 104);"
sqlite3 mainframe.db "INSERT INTO _system_nodes VALUES (5, 'core_cooling', 'FAULT', 105);"
sqlite3 mainframe.db "INSERT INTO _system_nodes VALUES (6, 'comm_relays', 'ONLINE', 106);"
sqlite3 mainframe.db "INSERT INTO _system_nodes VALUES (7, 'sensor_pod', 'DRAINED', 107);"

sqlite3 mainframe.db "CREATE TABLE _vault_shards (shard_id INTEGER PRIMARY KEY, node_id INTEGER, tier_tag TEXT, shard_part1 TEXT, shard_part2 TEXT, parity_chk TEXT);"
sqlite3 mainframe.db "INSERT INTO _vault_shards VALUES (1, 1, 'USER', '$H1', '$H2', '0x432');"
sqlite3 mainframe.db "INSERT INTO _vault_shards VALUES (2, 2, 'DECOY', 'fa10', '9bc2', '0x000');"
sqlite3 mainframe.db "INSERT INTO _vault_shards VALUES (3, 3, 'DECOY', 'c73e', '82a1', '0x111');"
sqlite3 mainframe.db "INSERT INTO _vault_shards VALUES (4, 4, 'DECOY', '910b', '44f0', '0x222');"
sqlite3 mainframe.db "INSERT INTO _vault_shards VALUES (5, 5, 'DECOY', 'e52a', '118c', '0x333');"
sqlite3 mainframe.db "INSERT INTO _vault_shards VALUES (6, 6, 'DECOY', '3d77', 'b001', '0x444');"
sqlite3 mainframe.db "INSERT INTO _vault_shards VALUES (7, 7, 'DECOY', '702f', 'a894', '0x555');"

sqlite3 mainframe.db "CREATE TABLE _decoy_registry (decoy_id INTEGER PRIMARY KEY, label TEXT, flag_decoy TEXT, trap_vector TEXT);"
sqlite3 mainframe.db "INSERT INTO _decoy_registry VALUES (1, 'honey_vault_1', 'OVERRIDE-USER-de01ba5e', 'HONEYPOT_TRIGGER');"
sqlite3 mainframe.db "INSERT INTO _decoy_registry VALUES (2, 'honey_vault_2', 'OVERRIDE-ADMIN-c4f82029', 'HONEYPOT_TRIGGER');"
sqlite3 mainframe.db "INSERT INTO _decoy_registry VALUES (3, 'honey_vault_3', 'OVERRIDE-CORE-9021beef', 'HONEYPOT_TRIGGER');"
sqlite3 mainframe.db "INSERT INTO _decoy_registry VALUES (4, 'honey_vault_4', 'OVERRIDE-ROOT-baadcafe', 'HONEYPOT_TRIGGER');"

# Backward compatible relational view for standard queries
sqlite3 mainframe.db "CREATE VIEW overrides AS SELECT n.id, n.subsystem AS target, ('OVERRIDE-' || s.tier_tag || '-' || s.shard_part1 || s.shard_part2) AS code FROM _system_nodes n JOIN _vault_shards s ON n.id = s.node_id WHERE n.status = 'ONLINE';"
chmod 444 mainframe.db

# Hidden .env file with mainframe DB config
cat << 'EOF' > .env
DB_TYPE=sqlite3
DB_FILE=mainframe.db
ADMIN_TABLE=overrides
EOF
chmod 444 .env

# 2. Mainframe Audit Log (forensic trail)
mkdir -p /var/log/mainframe
cat << 'LOGEOF' > /var/log/mainframe/node_state.log
[2026-10-31 04:00:01] [AUDIT] System node scan initiated by jumanji_admin.
[2026-10-31 04:00:02] [INFO] Node 1 (admin_access): ONLINE. Cluster 101 healthy. Parity 0x432 verified.
[2026-10-31 04:00:03] [WARN] Node 2 (telemetry_sink): OFFLINE. Shard disconnected.
[2026-10-31 04:00:04] [WARN] Node 3 (aux_matrix): OFFLINE. Routing disabled.
[2026-10-31 04:00:05] [WARN] Node 4 (grid_monitor): DEPRECATED. Legacy shard.
[2026-10-31 04:00:06] [ERROR] Node 5 (core_cooling): FAULT. Coolant pressure loss.
[2026-10-31 04:00:07] [INFO] Node 6 (comm_relays): ONLINE. Auxiliary telemetry only.
[2026-10-31 04:00:08] [ALERT] Decoy registry initialized with 4 honey tokens.
LOGEOF
chmod 644 /var/log/mainframe/node_state.log

# 3. Alan Parrish's Lost Field Journal
cat << 'PARRISHEOF' > /level1/parrish_journal.txt
================================================================================
          EXCERPTS FROM THE LOST EXPEDITION JOURNAL OF ALAN PARRISH
================================================================================
Found half-buried in the moss-covered roots of the golden fig tree, near the
obsidian vault entrance.

[ENTRY 1: OCTOBER 14]
"The jungle's heart does not yield to careless plunder. In the bronze vault
(mainframe.db), a dozen glittering tokens lay scattered like fool's gold.
The dark hunter Van Pelt has seeded the registry with phantom mirrors
(_decoy_registry) to lure the hasty into deadly traps.
Trust only the branch that breathes life ('ONLINE') within the system tree.
Before striking, read the weathered scrolls preserved in /var/log/mainframe;
their parchment records the true frequency of the living nodes."

[ENTRY 2: MARCH 22]
"I watched the overseer from the high canopies today. His mechanical hound
runs maintenance rounds through /opt/jumanji/maintenance/audit_vault.py.
It possesses power beyond ordinary wanderers, yet it suffers a curious blindness:
it searches for its tools (vault_utils) only where its feet currently tread.
Plant your own seed in the dirt beneath your boots, give it the name it seeks,
and when the overseer commands the audit, his voice will become your own."

[ENTRY 3: AUGUST 09]
"Twenty-six years I waited in this realm—from the day the dice rolled in '69
until the hour of awakening in 1995. The great stone altar at the summit
will remain cold and mute to those who merely touch it.
Two rites must be observed before the curse will shatter:
First, you must attune the atmosphere with the sacred vibration:
the ancient chant that resonates at 432 Hertz (CHANT_432HZ in JUMANJI_RITUAL).
Second, you must proclaim the year the sleepers awoke (--awaken 1995).
If the automaton's heart resists, look into its bronze clockwork
with the artificer's lenses (gdb, ltrace) to align the true numeric rune.
Only then will the bronze sentinel yield the core override."
================================================================================
PARRISHEOF
chmod 644 /level1/parrish_journal.txt

# Ensure auditor script permissions in /opt/jumanji/maintenance
if [ -d /opt/jumanji/maintenance ]; then
    chown -R jumanji_admin:jumanji_admin /opt/jumanji
    chmod 755 /opt/jumanji /opt/jumanji/maintenance
    [ -f /opt/jumanji/maintenance/audit_vault.py ] && chmod 755 /opt/jumanji/maintenance/audit_vault.py
fi

# Mirror into /level3 and /level2 if separate dirs
for d in /level3 /level2; do
    if [ ! -L "$d" ] && [ "$d" != "$(pwd)" ]; then
        cp -p mainframe.db .env parrish_journal.txt "$d/" 2>/dev/null || true
        chown -R recon_user:recon_user "$d" 2>/dev/null || true
    fi
done

# 4. Root Override (SUID Root Challenge)
echo "$(generate_override root)" > /root/core_override.txt
chmod 400 /root/core_override.txt
chown root:root /home/jumanji_admin/lift_curse 2>/dev/null || true
chmod 4755 /home/jumanji_admin/lift_curse 2>/dev/null || true

chown -R recon_user:recon_user /level1 /level3 2>/dev/null || true

echo "==================================================="
echo "    Welcome to the Simulation Core (Day 2 Level 1), $PLAYER_USERNAME!"
echo "    If you get lost, type: nigel_comms"
echo "    Consult the field notes: cat parrish_journal.txt"
echo "    To submit an override: deploy_override OVERRIDE-..."
echo "==================================================="

# Security hardening: Remove setup scripts so secrets cannot be inspected by recon_user
rm -f /usr/local/bin/setup_level*.sh 2>/dev/null || true
unset SECRET CTF_MASTER_SECRET
