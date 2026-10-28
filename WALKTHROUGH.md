
# 🧭 Technozion SDC Games: Master Challenge Walkthrough

This document provides the definitive, step-by-step solver guide and cheat-sheet for all challenges across **Day 1 Level 2 (Avatars)**, **Day 1 Level 3 (Simulation Core Mainframe)**, and **Day 2 Level 2 (The Jumanji Gauntlet)**.

---

## 1. Quick Tournament Scoring Matrix

| Event / Level           | Focus Area                       | Objectives / Flags                                                         | Max Score         | Progression Trigger                                  |
| :---------------------- | :------------------------------- | :------------------------------------------------------------------------- | :---------------- | :--------------------------------------------------- |
| **Day 1 Level 2** | Jungle Recon & Cryptanalysis     | 5 Avatars (`bravestone`, `ruby`, `finbar`, `oberon`, `seaplane`) | **150 PTS** | Victory video (`jumanji_win.mp4`) & Level 3 unlock |
| **Day 1 Level 3** | Mainframe Core & PrivEsc         | 2 Overrides (`round3_user`, `round3_root`)                             | **200 PTS** | Purge video (`round3_win.mp4`) & auto-completion   |
| **Day 2 Level 2** | The Jumanji Gauntlet (16 Squads) | Pod Relics, Duels, Shrine KotH, Final Jewel                                | **Dynamic** | Crown tournament champion & export Top 4 teams       |

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
- **Enumeration**: `sudo -l` reveals `(finbar_admin) NOPASSWD: /usr/bin/find`
- **Solve Command**:
  ```bash
  sudo -u finbar_admin find /home/finbar_admin -name "flag.txt" -exec cat {} +
  complete $(sudo -u finbar_admin find /home/finbar_admin -name "flag.txt" -exec cat {} +)
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

## 3. Day 1 Level 3: Simulation Core Mainframe (200 Points)

When players access `/level3`, an interactive security terminal (`recon_user@sdc-day1-level3:~$`) is provisioned.

### Step 3.1: Database Extraction (80 PTS)

- **Concept**: SQLite database query and schema reconnaissance.
- **Location**: `/var/sdc_mainframe/mainframe.db`
- **Solve Command**:
  ```bash
  sqlite3 /var/sdc_mainframe/mainframe.db "SELECT override_key FROM system_overrides WHERE privilege_tier='user';"
  deploy_override $(sqlite3 /var/sdc_mainframe/mainframe.db "SELECT override_key FROM system_overrides WHERE privilege_tier='user';")
  ```

### Step 3.2: SUID Binary Privilege Escalation (120 PTS)

- **Concept**: Ephemeral SUID binary inspection and environment variable injection.
- **Binary**: `/usr/local/bin/lift_curse` (Permissions: `-rwsr-xr-x 1 root root`)
- **Inspection**:
  ```bash
  strings /usr/local/bin/lift_curse | grep CHANT
  # Reveals required environment variable CHANT=JUMANJI_MAINFRAME_OVERRIDE
  ```
- **Escalation & Solve Command**:
  ```bash
  export CHANT="JUMANJI_MAINFRAME_OVERRIDE"
  /usr/local/bin/lift_curse
  deploy_override $(cat /root/root_override.txt)
  ```

---

## 4. Day 2 Level 2: The Jumanji Gauntlet (Dual-Role Co-Op)

In Day 2 Level 2, squads consist of **strictly 2 players**:

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
