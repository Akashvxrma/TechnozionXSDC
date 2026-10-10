#!/usr/bin/env python3
"""
Comprehensive Automated Verification Suite for Technozion SDC CTF
Tests Round 2 & Round 3:
 - Web Endpoints & Google Auth
 - Container File Generation & Isolation
 - Dynamic Flag Parity & Scoring Matrix
 - Privilege Escalation (SUID Root)
 - Admin Lock Routing & Session Retention
"""

import sys
import os
import sqlite3
import hashlib
import requests
import subprocess
import time
import json

BASE_URL = "http://127.0.0.1:8080"
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "round_2_sdc_games", "www", "jumanji_auth.db")
SECRET = "8f7b6c5d4a3e2f1g0h9i8j7k6l5m4n3"

TEST_USER_ID = 99999
TEST_USERNAME = "verification_pilot"
TEST_PASSWORD = "TestPassword_99999!"

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

passed_tests = 0
failed_tests = 0

def log_pass(msg):
    global passed_tests
    passed_tests += 1
    print(f" {GREEN}[PASS]{RESET} {msg}")

def log_fail(msg, detail=None):
    global failed_tests
    failed_tests += 1
    print(f" {RED}[FAIL]{RESET} {msg}")
    if detail:
        print(f"        {YELLOW}Detail:{RESET} {detail}")

def log_info(msg):
    print(f" {CYAN}[INFO]{RESET} {msg}")

def compute_flag(user_id, avatar_id):
    if avatar_id == 'round3_user':
        h = hashlib.md5(f"{user_id}:user:{SECRET}".encode()).hexdigest()[:8]
        return f"OVERRIDE-USER-{h}"
    elif avatar_id == 'round3_root':
        h = hashlib.md5(f"{user_id}:root:{SECRET}".encode()).hexdigest()[:8]
        return f"OVERRIDE-ROOT-{h}"
    else:
        h = hashlib.md5(f"{user_id}:{avatar_id}:{SECRET}".encode()).hexdigest()[:8]
        return f"JUMANJI{{{avatar_id}_{h}}}"

def setup_test_user():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM users WHERE id = ? OR username = ?", (TEST_USER_ID, TEST_USERNAME))
    conn.execute("DELETE FROM solved_challenges WHERE user_id = ?", (TEST_USER_ID,))
    conn.execute("""
        INSERT INTO users (id, username, password, role, points, round3_points, status, round3_status, has_seen_intro, has_seen_r3_intro)
        VALUES (?, ?, ?, 'player', 0, 0, 'active', 'active', 1, 1)
    """, (TEST_USER_ID, TEST_USERNAME, TEST_PASSWORD))
    # Ensure both rounds are unlocked
    conn.execute("INSERT OR REPLACE INTO global_settings (key, value) VALUES ('round2_unlocked', '1')")
    conn.execute("INSERT OR REPLACE INTO global_settings (key, value) VALUES ('round3_unlocked', '1')")
    conn.commit()
    conn.close()

def cleanup_test_user():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM users WHERE id = ? OR username = ?", (TEST_USER_ID, TEST_USERNAME))
    conn.execute("DELETE FROM solved_challenges WHERE user_id = ?", (TEST_USER_ID,))
    conn.commit()
    conn.close()

# ==============================================================================
# MODULE 1: WEB ENDPOINTS & AUTHENTICATION
# ==============================================================================
def test_web_endpoints():
    print(f"\n{BOLD}{CYAN}=== MODULE 1: WEB ENDPOINTS & AUTHENTICATION ==={RESET}")
    session = requests.Session()
    
    # 1.1 /login endpoint
    try:
        r = session.get(f"{BASE_URL}/login", timeout=5)
        if r.status_code == 200 and ("google-btn" in r.text or "LOGIN WITH GOOGLE" in r.text):
            log_pass("GET /login returns 200 OK with Google Sign-In branded button")
        else:
            log_fail("GET /login response invalid", f"Status: {r.status_code}")
    except Exception as e:
        log_fail("GET /login request failed", str(e))
        
    # 1.2 /auth/google redirect
    try:
        r = session.get(f"{BASE_URL}/auth/google", allow_redirects=False, timeout=5)
        if r.status_code in [302, 303, 307] and "accounts.google.com" in r.headers.get("Location", ""):
            log_pass("GET /auth/google redirects to Google Accounts OAuth 2.0")
        else:
            log_fail("GET /auth/google redirect invalid", f"Status: {r.status_code}, Location: {r.headers.get('Location')}")
    except Exception as e:
        log_fail("GET /auth/google request failed", str(e))
        
    # 1.3 Unauthenticated protections
    for route in ['/hub', '/dashboard', '/round3']:
        try:
            r = session.get(f"{BASE_URL}{route}", allow_redirects=False, timeout=5)
            if r.status_code in [302, 303, 307] and "/login" in r.headers.get("Location", ""):
                log_pass(f"Unauthenticated {route} redirects to /login")
            else:
                log_fail(f"Unauthenticated {route} did not redirect to /login", f"Status: {r.status_code}")
        except Exception as e:
            log_fail(f"Testing {route} failed", str(e))

    # 1.4 Player session login
    try:
        r = session.post(f"{BASE_URL}/login", data={"username": TEST_USERNAME, "password": TEST_PASSWORD}, allow_redirects=True, timeout=5)
        if r.status_code == 200 and ("EXPEDITION COMMAND CENTER" in r.text or "JUMANJI" in r.text):
            log_pass(f"Player login successful for '{TEST_USERNAME}'")
        else:
            log_fail("Player login failed", f"Status: {r.status_code}")
    except Exception as e:
        log_fail("Player login request failed", str(e))

    # 1.5 Authenticated access to /hub
    try:
        r = session.get(f"{BASE_URL}/hub", timeout=5)
        if r.status_code == 200 and "ROUND 2" in r.text and "ROUND 3" in r.text:
            log_pass("GET /hub renders Expedition Command Center with Round 2 and Round 3 cards")
        else:
            log_fail("GET /hub render missing round cards", f"Status: {r.status_code}")
    except Exception as e:
        log_fail("GET /hub request failed", str(e))

    # 1.6 Authenticated access to /dashboard (Round 2)
    try:
        r = session.get(f"{BASE_URL}/dashboard", timeout=5)
        if r.status_code == 200 and "countdown-timer" in r.text and "btn-bravestone" in r.text:
            log_pass("GET /dashboard renders Round 2 HUD with timer and avatars")
        else:
            log_fail("GET /dashboard render invalid", f"Status: {r.status_code}")
    except Exception as e:
        log_fail("GET /dashboard request failed", str(e))

    # 1.7 Authenticated access to /round3
    try:
        r = session.get(f"{BASE_URL}/round3", timeout=5)
        if r.status_code == 200 and "THE DEEP JUNGLE" in r.text and "countdown-timer" in r.text:
            log_pass("GET /round3 renders Round 3 simulation HUD")
        else:
            log_fail("GET /round3 render invalid", f"Status: {r.status_code}")
    except Exception as e:
        log_fail("GET /round3 request failed", str(e))

    return session

# ==============================================================================
# MODULE 2: ROUND 2 CONTAINER & CHALLENGE VERIFICATION
# ==============================================================================
def test_round2_container(auth_session):
    print(f"\n{BOLD}{CYAN}=== MODULE 2: ROUND 2 CONTAINER & CHALLENGE VERIFICATION ==={RESET}")
    
    # 2.1 Verify image exists
    res = subprocess.run(["docker", "image", "inspect", "jumanji-round2:latest"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if res.returncode == 0:
        log_pass("Docker image 'jumanji-round2:latest' is available")
    else:
        log_fail("Docker image 'jumanji-round2:latest' not found")
        return

    # 2.2 Spin up test container and execute setup_round2.sh
    cont_name = f"test_r2_verify_{int(time.time())}"
    token = "test_r2_token_abc123"
    
    # Map token into app's INTERNAL_TOKENS via app.py or direct session testing
    # Note: we test both the token via /api/score and direct session /api/score
    
    try:
        run_cmd = [
            "docker", "run", "-d", "--name", cont_name,
            "--cap-add", "SYS_ADMIN",
            "-e", f"PLAYER_ID={TEST_USER_ID}",
            "-e", f"PLAYER_USERNAME={TEST_USERNAME}",
            "-e", f"CTF_TOKEN={token}",
            "jumanji-round2:latest", "tail", "-f", "/dev/null"
        ]
        subprocess.run(run_cmd, check=True, stdout=subprocess.DEVNULL)
        log_pass(f"Container '{cont_name}' started")

        # Run setup_round2.sh
        setup_res = subprocess.run(
            ["docker", "exec", "-u", "recon_user", cont_name, "sudo", "-E", "/usr/local/bin/setup_round2.sh"],
            capture_output=True, text=True
        )
        if setup_res.returncode == 0:
            log_pass("setup_round2.sh executed successfully inside container")
        else:
            log_fail("setup_round2.sh failed", setup_res.stderr)

        # Avatar 1: Bravestone (/opt/jungle/ruins/.bravestone_relic)
        bravestone_flag_cmd = subprocess.run(
            ["docker", "exec", cont_name, "cat", "/opt/jungle/ruins/.bravestone_relic"],
            capture_output=True, text=True
        )
        bravestone_flag = bravestone_flag_cmd.stdout.strip()
        expected_bravestone = compute_flag(TEST_USER_ID, 'bravestone')
        if bravestone_flag == expected_bravestone:
            log_pass(f"Bravestone Flag in /opt/jungle/ruins/.bravestone_relic confirmed: {bravestone_flag}")
        else:
            log_fail(f"Bravestone flag mismatch", f"Got: {bravestone_flag}, Expected: {expected_bravestone}")

        # Avatar 2: Ruby (/home/recon_user/Documents/ruby_dance_moves.txt Base64)
        ruby_cmd = subprocess.run(
            ["docker", "exec", cont_name, "bash", "-c", "cat /home/recon_user/Documents/ruby_dance_moves.txt | base64 -d"],
            capture_output=True, text=True
        )
        ruby_flag = ruby_cmd.stdout.strip()
        expected_ruby = compute_flag(TEST_USER_ID, 'ruby')
        if ruby_flag == expected_ruby:
            log_pass(f"Ruby Roundhouse Base64 decode parity confirmed: {ruby_flag}")
        else:
            log_fail(f"Ruby flag mismatch", f"Got: {ruby_flag}, Expected: {expected_ruby}")

        # Avatar 3: Finbar (sudo -u finbar_admin /bin/cat /home/finbar_admin/flag.txt)
        finbar_cmd = subprocess.run(
            ["docker", "exec", "-u", "recon_user", cont_name, "sudo", "-u", "finbar_admin", "/bin/cat", "/home/finbar_admin/flag.txt"],
            capture_output=True, text=True
        )
        finbar_flag = finbar_cmd.stdout.strip()
        expected_finbar = compute_flag(TEST_USER_ID, 'finbar')
        if finbar_flag == expected_finbar:
            log_pass(f"Franklin Finbar sudo access parity confirmed: {finbar_flag}")
        else:
            log_fail(f"Finbar flag mismatch", f"Got: {finbar_flag}, Expected: {expected_finbar}")

        # Avatar 4: Oberon (Process table ps aux map_generator)
        oberon_cmd = subprocess.run(
            ["docker", "exec", cont_name, "bash", "-c", "ps aux | grep map_generator | grep -v grep | head -n 1"],
            capture_output=True, text=True
        )
        expected_oberon = compute_flag(TEST_USER_ID, 'oberon')
        if expected_oberon in oberon_cmd.stdout:
            log_pass(f"Prof Oberon process table parity confirmed: {expected_oberon}")
        else:
            log_fail(f"Oberon process inspection failed", f"Output: {oberon_cmd.stdout}")

        # Avatar 5: Seaplane (HTTP server port 8080)
        seaplane_cmd = subprocess.run(
            ["docker", "exec", cont_name, "curl", "-s", "http://127.0.0.1:8080"],
            capture_output=True, text=True
        )
        seaplane_flag = seaplane_cmd.stdout.strip()
        expected_seaplane = compute_flag(TEST_USER_ID, 'seaplane')
        if seaplane_flag == expected_seaplane:
            log_pass(f"Seaplane HTTP server parity confirmed: {seaplane_flag}")
        else:
            log_fail(f"Seaplane flag mismatch", f"Got: {seaplane_flag}, Expected: {expected_seaplane}")

        # 2.3 Verify parrot_hint hints 1 to 5
        hint_check_passed = True
        for h in range(1, 6):
            h_res = subprocess.run(["docker", "exec", cont_name, "parrot_hint", str(h)], capture_output=True, text=True)
            if h_res.returncode != 0 or "[LORE]" not in h_res.stdout:
                hint_check_passed = False
                break
        if hint_check_passed:
            log_pass("parrot_hint script 1-5 functional with lore and tech hints")
        else:
            log_fail("parrot_hint hints verification failed")

        # 2.4 Verify Submissions and Scoring Matrix for Round 2
        round2_flags = {
            'bravestone': (expected_bravestone, 400),
            'ruby': (expected_ruby, 600),
            'finbar': (expected_finbar, 500),
            'oberon': (expected_oberon, 450),
            'seaplane': (expected_seaplane, 1000)
        }
        
        cumulative_points = 0
        all_score_pass = True
        for avatar, (flag, pts) in round2_flags.items():
            r = auth_session.post(f"{BASE_URL}/api/score", json={"avatar_id": avatar, "flag": flag})
            data = r.json()
            if data.get("status") == "success" and data.get("points_awarded") == pts:
                cumulative_points += pts
                if data.get("total_points") == cumulative_points:
                    continue
            all_score_pass = False
            log_fail(f"Submission failed for {avatar}", str(data))
            break
            
        if all_score_pass and cumulative_points == 2950:
            log_pass("Round 2 All 5 Avatars scored successfully: Exactly 2,950 points awarded!")
        else:
            log_fail("Round 2 cumulative points mismatch", f"Total: {cumulative_points}")

        # Test duplicate submission rejection
        dup_r = auth_session.post(f"{BASE_URL}/api/score", json={"avatar_id": "bravestone", "flag": expected_bravestone})
        if dup_r.json().get("status") == "already_solved":
            log_pass("Duplicate submission rejection verified for Round 2")
        else:
            log_fail("Duplicate submission was not rejected", str(dup_r.text))

    finally:
        subprocess.run(["docker", "rm", "-f", cont_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        log_info(f"Cleaned up test container '{cont_name}'")

# ==============================================================================
# MODULE 3: ROUND 3 CONTAINER & PRIVILEGE ESCALATION
# ==============================================================================
def test_round3_container(auth_session):
    print(f"\n{BOLD}{CYAN}=== MODULE 3: ROUND 3 CONTAINER & PRIVILEGE ESCALATION ==={RESET}")

    # 3.1 Verify image exists
    res = subprocess.run(["docker", "image", "inspect", "jumanji-round3:latest"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if res.returncode == 0:
        log_pass("Docker image 'jumanji-round3:latest' is available")
    else:
        log_fail("Docker image 'jumanji-round3:latest' not found")
        return

    # 3.2 Spin up test container and execute setup_round3.sh
    cont_name = f"test_r3_verify_{int(time.time())}"
    token = "test_r3_token_xyz789"
    
    try:
        run_cmd = [
            "docker", "run", "-d", "--name", cont_name,
            "--cap-add", "SYS_ADMIN",
            "-e", f"PLAYER_ID={TEST_USER_ID}",
            "-e", f"PLAYER_USERNAME={TEST_USERNAME}",
            "-e", f"CTF_TOKEN={token}",
            "jumanji-round3:latest", "tail", "-f", "/dev/null"
        ]
        subprocess.run(run_cmd, check=True, stdout=subprocess.DEVNULL)
        log_pass(f"Container '{cont_name}' started")

        # Run setup_round3.sh
        setup_res = subprocess.run(
            ["docker", "exec", "-u", "recon_user", cont_name, "sudo", "-E", "/usr/local/bin/setup_round3.sh"],
            capture_output=True, text=True
        )
        if setup_res.returncode == 0:
            log_pass("setup_round3.sh executed successfully inside container")
        else:
            log_fail("setup_round3.sh failed", setup_res.stderr)

        # 3.3 Mainframe SQLite Database Check
        sql_cmd = subprocess.run(
            ["docker", "exec", cont_name, "sqlite3", "/round3/mainframe.db", "SELECT code FROM overrides WHERE target = 'admin_access';"],
            capture_output=True, text=True
        )
        db_user_flag = sql_cmd.stdout.strip()
        expected_user_flag = compute_flag(TEST_USER_ID, 'round3_user')
        if db_user_flag == expected_user_flag:
            log_pass(f"Mainframe DB user override parity confirmed: {db_user_flag}")
        else:
            log_fail("Mainframe DB override mismatch", f"Got: {db_user_flag}, Expected: {expected_user_flag}")

        # 3.4 SUID Root binary permissions and Privilege Escalation Check
        stat_cmd = subprocess.run(
            ["docker", "exec", cont_name, "stat", "-c", "%a %U:%G", "/home/jumanji_admin/lift_curse"],
            capture_output=True, text=True
        )
        stat_output = stat_cmd.stdout.strip()
        if stat_output.startswith("4755 root:root"):
            log_pass(f"SUID Root binary permissions confirmed: {stat_output}")
        else:
            log_fail(f"lift_curse binary permissions invalid: {stat_output}")

        # Test lift_curse without CHANT (must fail)
        no_chant_cmd = subprocess.run(
            ["docker", "exec", "-u", "recon_user", cont_name, "sudo", "-u", "jumanji_admin", "/home/jumanji_admin/lift_curse"],
            capture_output=True, text=True
        )
        if "The curse cannot be lifted in silence" in no_chant_cmd.stdout:
            log_pass("lift_curse safely denies escalation when CHANT is not set")
        else:
            log_fail("lift_curse failed to protect un-chanted invocation")

        # Test lift_curse with CHANT=JUMANJI (must yield root privileges and read /root/core_override.txt)
        chant_cmd = subprocess.run(
            ["docker", "exec", "-u", "recon_user", cont_name, "bash", "-c", "echo 'cat /root/core_override.txt' | sudo -u jumanji_admin CHANT=JUMANJI /home/jumanji_admin/lift_curse"],
            capture_output=True, text=True
        )
        expected_root_flag = compute_flag(TEST_USER_ID, 'round3_root')
        if expected_root_flag in chant_cmd.stdout:
            log_pass(f"Privilege Escalation Verified! Root override flag extracted: {expected_root_flag}")
        else:
            log_fail("Privilege Escalation failed to read root override", chant_cmd.stdout + chant_cmd.stderr)

        # 3.5 Verify nigel_comms script outputs
        recon_comm = subprocess.run(["docker", "exec", "-u", "recon_user", cont_name, "nigel_comms"], capture_output=True, text=True)
        admin_comm = subprocess.run(["docker", "exec", "-u", "jumanji_admin", cont_name, "nigel_comms"], capture_output=True, text=True)
        root_comm = subprocess.run(["docker", "exec", "-u", "root", cont_name, "nigel_comms"], capture_output=True, text=True)
        if "basic user" in recon_comm.stdout and "ROOT access" in admin_comm.stdout and "curse is broken" in root_comm.stdout:
            log_pass("nigel_comms context-aware guidance verified across all user privilege tiers")
        else:
            log_fail("nigel_comms output verification failed")

        # 3.6 Submit User & Root Overrides for Round 3
        r_user = auth_session.post(f"{BASE_URL}/api/score", json={"avatar_id": "round3", "flag": expected_user_flag})
        d_user = r_user.json()
        if d_user.get("status") == "success" and d_user.get("points_awarded") == 1000:
            log_pass("Round 3 User Override scored: +1,000 points awarded")
        else:
            log_fail("Round 3 User Override score failed", str(d_user))

        r_root = auth_session.post(f"{BASE_URL}/api/score", json={"avatar_id": "round3", "flag": expected_root_flag})
        d_root = r_root.json()
        if d_root.get("status") == "success" and d_root.get("points_awarded") == 1500 and d_root.get("total_points") == 2500:
            log_pass("Round 3 Root Override scored: +1,500 points awarded (Total: 2,500 points)!")
        else:
            log_fail("Round 3 Root Override score failed", str(d_root))

        # Check Round 3 duplicate submission
        dup_r3 = auth_session.post(f"{BASE_URL}/api/score", json={"avatar_id": "round3", "flag": expected_root_flag})
        if dup_r3.json().get("status") == "already_solved":
            log_pass("Duplicate submission rejection verified for Round 3")
        else:
            log_fail("Duplicate submission was not rejected in Round 3", str(dup_r3.text))

    finally:
        subprocess.run(["docker", "rm", "-f", cont_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        log_info(f"Cleaned up test container '{cont_name}'")

# ==============================================================================
# MODULE 4: ADMIN LOCK & SESSION INTEGRITY
# ==============================================================================
def test_admin_locks(auth_session):
    print(f"\n{BOLD}{CYAN}=== MODULE 4: ADMIN LOCK & SESSION INTEGRITY ==={RESET}")
    conn = sqlite3.connect(DB_PATH)
    
    try:
        # 4.1 Lock Round 2
        conn.execute("UPDATE global_settings SET value = '0' WHERE key = 'round2_unlocked'")
        conn.commit()
        
        r = auth_session.get(f"{BASE_URL}/dashboard", allow_redirects=False)
        if r.status_code in [302, 303, 307] and r.headers.get("Location") in ["/", "/hub"]:
            log_pass("Admin Lock Round 2 successfully redirects dashboard to /hub or /")
        else:
            log_fail("Round 2 lock did not redirect properly", f"Status: {r.status_code}, Location: {r.headers.get('Location')}")

        # Check player is NOT logged out
        r_hub = auth_session.get(f"{BASE_URL}/hub", allow_redirects=False)
        if r_hub.status_code == 200:
            log_pass("Session preserved when Round 2 locked (player not kicked out)")
        else:
            log_fail("Player was inappropriately logged out when Round 2 locked")

        # 4.2 Lock Round 3
        conn.execute("UPDATE global_settings SET value = '0' WHERE key = 'round3_unlocked'")
        conn.commit()
        
        r = auth_session.get(f"{BASE_URL}/round3", allow_redirects=False)
        if r.status_code in [302, 303, 307] and r.headers.get("Location") in ["/", "/hub"]:
            log_pass("Admin Lock Round 3 successfully redirects /round3 to /hub or /")
        else:
            log_fail("Round 3 lock did not redirect properly", f"Status: {r.status_code}, Location: {r.headers.get('Location')}")

        # Check player is STILL logged in
        r_hub2 = auth_session.get(f"{BASE_URL}/hub", allow_redirects=False)
        if r_hub2.status_code == 200:
            log_pass("Session preserved when Round 3 locked (player not kicked out)")
        else:
            log_fail("Player was inappropriately logged out when Round 3 locked")

    finally:
        # Restore both rounds unlocked
        conn.execute("UPDATE global_settings SET value = '1' WHERE key = 'round2_unlocked'")
        conn.execute("UPDATE global_settings SET value = '1' WHERE key = 'round3_unlocked'")
        conn.commit()
        conn.close()
        log_info("Restored global_settings: both rounds unlocked")

def main():
    print(f"{BOLD}{CYAN}===================================================================={RESET}")
    print(f"{BOLD}{CYAN}      TECHNOZION SDC GAMES - AUTOMATED VERIFICATION SUITE           {RESET}")
    print(f"{BOLD}{CYAN}===================================================================={RESET}")
    
    setup_test_user()
    try:
        session = test_web_endpoints()
        test_round2_container(session)
        test_round3_container(session)
        test_admin_locks(session)
    finally:
        cleanup_test_user()
        log_info("Cleaned up temporary test user database records")

    print(f"\n{BOLD}{CYAN}===================================================================={RESET}")
    print(f"{BOLD}SUMMARY:{RESET} Passed: {GREEN}{passed_tests}{RESET} | Failed: {RED}{failed_tests}{RESET}")
    print(f"{BOLD}{CYAN}===================================================================={RESET}")

    if failed_tests > 0:
        sys.exit(1)
    else:
        print(f"\n{BOLD}{GREEN}ALL VERIFICATION CHECKS PASSED WITH 100% SUCCESS!{RESET}\n")
        sys.exit(0)

if __name__ == "__main__":
    main()
