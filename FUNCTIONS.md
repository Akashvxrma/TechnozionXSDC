# 🧩 Technozion SDC CTF: Comprehensive Function Catalog & Dependency Call Graph

This document provides an exhaustive, function-by-function reference of all services, scripts, and modules across the entire Technozion SDC Games CTF codebase.

---

## 1. Cross-File Dependency Call Graph

```
                                  [ USER HTTP / WEBSOCKET REQUESTS ]
                                                   |
                                                   v
                                          DAY 1/www/app.py
                                                   |
         +-----------------------------------------+-----------------------------------------+
         |                                         |                                         |
         v                                         v                                         v
   mongo_sync.py                          gauntlet_engine.py                        Docker Daemon (PTY)
   - test_mongo_connection()              - init_gauntlet_db()                      - jumanji-level2
   - sync_roster_from_mongodb()            - seed_default_teams()                    - jumanji-level3
         |                                 - get_team_for_user()                     - jumanji-gauntlet
         v                                 - auto_assign_user_to_team()                      |
  [ MongoDB Atlas ]                        - get_top_4_teams()                               v
  (Collection: users,                      - verify_relic_submission()              [ Container Scripts ]
   participants)                           - get_active_curses_for_team()           - setup_level2.sh
                                           - cast_curse()                           - parrot_hint.sh
                                           - advance_tournament_phase()             - setup_level3.sh
                                           - record_shrine_claim()                  - nigel_comms.sh
                                           - tick_shrine()                          - lift_curse (SUID)
                                                   |                                - setup_gauntlet.sh
                                                   v                                - setup_shrine.sh
                                         [ jumanji_auth.db ]
```

---

## 2. Core Application: `DAY 1/www/app.py`

| Function / Route | Trigger / Caller | Callees / Dependencies | Purpose / Description |
| :--- | :--- | :--- | :--- |
| `load_ctf_env()` | App startup / Module import | `pathlib.Path`, `os.environ` | Loads `.env` file key-value pairs into `os.environ` if not already set. |
| `is_allowed_origin(origin)` | SocketIO CORS validator | `urllib.parse`, `ipaddress` | Strictly allows loopback, RFC 1918 private IPv4 subnets, `.nip.io`, and `WEB_ORIGIN`. |
| `is_submission_rate_limited(key, limit, window_sec)` | Submission routes | `collections.deque`, `time.time` | Sliding-window rate limiter (30 req/min) guarding `/api/score` and relic solves. |
| `get_csrf_token()` | Session init / Form render | `secrets.token_hex(32)`, `session` | Generates or retrieves session-bound 32-byte cryptographic CSRF token. |
| `enforce_security_and_csrf()` | `@app.before_request` | `hmac.compare_digest` | Blocks container subnets from auth/admin; enforces CSRF/Origin checks on admin POSTs. |
| `get_user_scores(user_row)` | Scoring routes / Admin views | Database row tuple/dict | Canonical score resolver returning `(total_score, level2_pts, level3_pts)`. |
| `get_utc_now()` | Internal helper | `datetime.now(timezone.utc)` | Generates timezone-aware naive UTC timestamp for SQLite storage. |
| `add_security_headers(response)` | `@app.after_request` | N/A | Injects OWASP defense headers (`X-Content-Type-Options`, `X-Frame-Options`, `Content-Security-Policy`). |
| `get_db_connection()` | Database access across app | `sqlite3.connect('jumanji_auth.db')` | Opens SQLite database connection with row factory enabled. |
| `init_db()` | App startup | `gauntlet_engine.init_gauntlet_db()` | Creates SQLite tables for users, scores, global settings, audit logs. |
| `handle_ping()` | `@socketio.on('ping')` | `get_db_connection()` | Updates `users.last_active` timestamp for live telemetry. |
| `index()` | `GET /` | `login()`, `admin()`, `hub()` | Entrypoint redirect based on authentication and role. |
| `hub()` | `GET /hub` | `check_level_access()`, `get_db_connection()` | Renders main Expedition Command Center displaying unlocked rounds. |
| `check_timer()` | `GET /api/timer` | `get_db_connection()`, `get_utc_now()` | Returns remaining countdown seconds for Level 2 or Level 3 sessions. |
| `check_level_access(user_id, level)` | Internal security gateway | `get_db_connection()`, `json.loads()` | Validates user registration (`authorized_levels`), global lock, and status. |
| `login()` | `GET/POST /login` | `get_db_connection()` | Renders 3D login portal and processes administrator authentication. |
| `get_google_redirect_uri()` | OAuth helper | `request.host_url` | Resolves standard Google OAuth callback URI dynamically. |
| `google_login()` | `GET /auth/google` | Google OAuth2 API | Redirects participant to Google Accounts authentication. |
| `google_callback()` | `GET /auth/callback` | `get_db_connection()`, Google Token API | Exchanges auth code for Google user profile and establishes session. |
| `choose_username()` | `GET/POST /auth/choose-username` | `get_db_connection()` | Prompts first-time OAuth players to configure an in-game codename. |
| `register()` | `GET /register` | `login()` | Deprecated legacy route redirecting directly to `/login`. |
| `admin()` | `GET /admin` | `get_db_connection()` | Host management console for level locking, timers, and score matrix. |
| `sync_sdc_roster()` | `POST /admin/sync-sdc-roster` | `mongo_sync.sync_roster_from_mongodb()` | Triggers manual roster synchronization directly from MongoDB. |
| `export_scores_l2()` | `GET /admin/export-scores/level2`| `get_db_connection()`, `csv.writer` | Streams CSV of Day 1 Level 2 (Avatar) participant rankings. |
| `export_scores_l3()` | `GET /admin/export-scores/level3`| `get_db_connection()`, `csv.writer` | Streams CSV of Day 1 Level 3 (Mainframe) privilege escalation ranks. |
| `export_day1_shortlist()` | `GET /admin/export-scores/day1-all` | `get_db_connection()`, `csv.writer` | Streams complete aggregated Day 1 cybersec score matrix. |
| `export_gauntlet_finalists()` | `GET /admin/export-gauntlet-finalists` | `get_db_connection()`, `csv.writer` | Exports the Top 4 teams (8 finalists) for championship qualification. |
| `get_user_flags(user_id)` | Internal helper | `get_db_connection()` | Fetches solved avatar challenge IDs for the current player. |
| `level2()` | `GET /level2` | `check_level_access()`, `get_user_flags()` | Renders Day 1 Level 2 Avatar Reconnaissance mission station. |
| `redirect_to_level2()` | `GET /level1`, `/round2` | `level2()` | Legacy backward-compatibility redirect to `level2()`. |
| `start_level2()` | `POST /level2/start` | `get_db_connection()`, `get_utc_now()` | Starts individual 60-minute countdown timer for Level 2. |
| `reset_level2_intro()` | `POST /level2/reset-intro` | `get_db_connection()` | Clears intro flag allowing player to re-watch avatar briefing. |
| `level3()` | `GET /level3` | `check_level_access()`, `get_db_connection()` | Renders Day 1 Level 3 Mainframe cybersec simulation station. |
| `round3()` | `GET /round3` | `level3()` | Legacy backward-compatibility redirect to `level3()`. |
| `start_level3()` | `POST /level3/start` | `get_db_connection()`, `get_utc_now()` | Starts individual 60-minute countdown timer for Level 3. |
| `reset_level3_intro()` | `POST /level3/reset-intro` | `get_db_connection()` | Clears intro flag for Level 3 mainframe briefing. |
| `generate_dynamic_flag(user_id, avatar)` | Internal crypto helper | `hashlib.md5()` | Derives deterministic keyed flag `JUMANJI{avatar_hash}` for player. |
| `proxy_whois()` | `GET /api/whois/<ip>` | `requests.get()` | Safe API proxy querying local whois microservice. |
| `submit_score()` | `POST /submit-score` | `generate_dynamic_flag()`, `socketio.emit`| Validates flag submission, credits points, updates database, emits sync. |
| `day2_level2()` | `GET /day2/level2` | `gauntlet()` | Canonical route alias routing directly into `gauntlet()`. |
| `logout()` | `GET /logout` | `session.clear()` | Destroys Flask session and redirects to login portal. |
| `gauntlet()` | `GET /gauntlet` | `gauntlet_engine.get_team_for_user()`, `auto_assign_user_to_team()` | Renders Day 2 Level 2 dual-role tournament telemetry HUD. |
| `gauntlet_bracket()` | `GET /gauntlet/bracket` | `get_db_connection()` | Stadium Projector live arena showing Pod standings and Duels. |
| `gauntlet_relic_solve()` | `POST /gauntlet/relic/solve`| `gauntlet_engine.verify_relic_submission()` | Validates split-key submissions and awards tournament relic points. |
| `gauntlet_curse_cast()` | `POST /gauntlet/curse/cast`| `gauntlet_engine.cast_curse()`, `socketio.emit` | Deploys tactical curse card against opposing squad and emits alert. |
| `gauntlet_admin()` | `GET /admin/gauntlet` | `gauntlet_engine.get_top_4_teams()`, `get_db_connection()` | Tournament Director control room showing top 4 qualifiers & controls. |
| `gauntlet_admin_action()` | `POST /admin/gauntlet/action`| `gauntlet_engine.advance_tournament_phase()` | Manually advances tournament phases, resets state, or assigns throne. |
| `process_gauntlet_shrine_ticks()`| Background task (20s) | `gauntlet_engine.tick_shrine()`, `socketio.emit` | Periodically awards +10 PTS to active ruler of the Sacred Shrine. |
| `start_pty(data)` | `@socketio.on('pty-connect')`| `pty.openpty()`, `docker run` (subprocess) | Spawns sandboxed ephemeral Docker container linked to xterm.js terminal. |
| `read_and_forward_pty(fd, sid)` | Background thread | `os.read()`, `socketio.emit('pty-output')` | Asynchronously pipes container stdout/stderr back to player's browser. |
| `pty_input(data)` | `@socketio.on('pty-input')` | `os.write()` | Pipes player keystrokes into active container PTY file descriptor. |
| `pty_resize(data)` | `@socketio.on('pty-resize')`| `fcntl.ioctl()` | Synchronizes terminal column and row dimensions with browser window. |
| `pty_cleanup(sid)` | Disconnect / exit | `docker rm -f` (subprocess) | Destroys orphaned Docker containers and terminates worker threads. |

---

## 3. Gauntlet Tournament Engine: `DAY 2/level2/gauntlet_engine.py`

| Function | Called By | Callees / Tables | Description |
| :--- | :--- | :--- | :--- |
| `get_utc_now()` | Internal | `datetime.now(timezone.utc)` | Returns naive UTC timestamp. |
| `init_gauntlet_db(conn)` | `app.py:init_db()` | `gauntlet_teams`, `gauntlet_members` | Creates gauntlet schema and enforces strict `UNIQUE(team_id, role)`. |
| `seed_default_teams(conn)` | `app.py:gauntlet_admin_action()` | `gauntlet_teams` | Seeds 16 canonical animal teams across Pods Alpha, Bravo, Charlie, Delta. |
| `generate_split_keys(team_id, match_id, relic)`| `app.py:gauntlet()`, `verify_relic_submission()` | `hashlib.md5()` | Derives `NAV_` and `CART_` cryptographic split-key components. |
| `get_team_for_user(conn, user_id)`| `app.py:gauntlet()`, `pty_connect()` | `gauntlet_members`, `gauntlet_teams` | Resolves team metadata and assigned player role (`navigator` or `cartographer`). |
| `auto_assign_user_to_team(conn, user_id)` | `app.py:gauntlet()` | `gauntlet_members` | Enforces strict 32-player limit; rejects 33+ players with `None`. |
| `get_top_4_teams(conn)` | `app.py:gauntlet_admin()` | `gauntlet_teams`, `gauntlet_members` | Fetches the Top 4 ranked teams with full player details for qualification. |
| `verify_relic_submission(conn, team_id, flag)` | `app.py:gauntlet_relic_solve()` | `generate_split_keys()`, `gauntlet_solved_relics` | Validates single halves vs combined token `JUMANJI{relic_nav_cart}`. |
| `get_active_curses_for_team(conn, team_id)` | `app.py:gauntlet()` | `gauntlet_curses` | Checks whether team is currently under active curse debuff. |
| `cast_curse(conn, from_team, type, target)` | `app.py:gauntlet_curse_cast()` | `gauntlet_curse_inventory`, `gauntlet_curses` | Applies curse card debuff against target with countdown expiry. |
| `advance_tournament_phase(conn, phase)` | `app.py:gauntlet_admin_action()` | `gauntlet_matches`, `gauntlet_teams` | Advances tournament phase (Pods $\rightarrow$ Duels $\rightarrow$ Shrine $\rightarrow$ Final). |
| `record_shrine_claim(conn, access_code)` | `app.py:gauntlet_admin_action()` | `gauntlet_settings` | Changes active ruler of the King of the Hill throne. |
| `tick_shrine(conn)` | `app.py:process_gauntlet_shrine_ticks()` | `gauntlet_teams`, `gauntlet_shrine_ticks` | Awards +10 PTS to active throne holder and logs tick. |

---

## 4. Database Sync Engine: `DAY 1/www/mongo_sync.py` & `sync_from_mongodb.py`

| Script / Function | Called By | Dependencies | Description |
| :--- | :--- | :--- | :--- |
| `get_default_mongo_config()` | `test_mongo_connection()`, `sync_roster_from_mongodb()` | `.env`, `os.environ` | Resolves MongoDB URI and database name (`sdcgames26`). |
| `test_mongo_connection(uri)` | `sync_from_mongodb.py` CLI | `pymongo.MongoClient` | Validates credentials and lists accessible MongoDB databases. |
| `sync_roster_from_mongodb(db_path, uri)` | `app.py:sync_sdc_roster()`, CLI runner | `pymongo`, `jumanji_auth.db` | Reads `users` & `participants` from MongoDB and upserts SQLite accounts. |
| `sync_from_mongodb.py:main()` | Standalone terminal command | `mongo_sync.py` | CLI execution wrapper printing formatted sync summaries. |

---

## 5. Verification & Test Suite: `verify_all.py`

| Function | Called By | Verification Scope |
| :--- | :--- | :--- |
| `log_pass(msg)` / `log_fail(msg, detail)` | Module runners | Formats pass/fail test output with color highlighting. |
| `test_module_1_web_endpoints()` | Main execution | Tests authentication, login, Google OAuth redirects, and authorization barriers. |
| `test_module_2_level2_avatars()` | Main execution | Tests container spin-up, all 5 avatar solves, flags, hints, and duplicate limits. |
| `test_module_3_level3_mainframe()` | Main execution | Tests mainframe container, user override, and SUID root exploit parity. |
| `test_module_4_admin_lock()` | Main execution | Tests Game Master locks, session preservation, and route protection. |
| `test_module_5_jumanji_gauntlet()` | Main execution | Tests 16 squads, split-key submission, curses, King of the Hill, and phase advancement. |

---

## 6. Dead & Legacy Code Audit Log

The following legacy and obsolete components were audited and purged:

| Component | Previous Location | Reason for Removal | Status |
| :--- | :--- | :--- | :--- |
| `dispatch_score_to_sdc_games` | `DAY 1/www/app.py` | Obsolete HTTP score bridge replaced by direct MongoDB sync. | **Purged** |
| `record_pending_sync` | `DAY 1/www/app.py` | Dead sync retry stub no longer needed. | **Purged** |
| `process_pending_score_syncs` | `DAY 1/www/app.py` | Dead background retry loop. | **Purged** |
| `jumanji.db` | `DAY 1/www/jumanji.db` | 0-byte abandoned ghost database. | **Deleted** |
| `database.db` | `DAY 1/www/database.db` | Orphaned duplicate database file; active DB is `jumanji_auth.db`. | **Deleted** |
| Host Bind Mount `/gauntlet_src` | `DAY 1/www/app.py` | Security flaw that exposed HMAC secrets to container users. | **Purged** |
| Hardcoded `match_id = 1` | `DAY 1/www/app.py` | Phase 2 duel synchronization bug causing unsolvable split keys. | **Fixed** |
