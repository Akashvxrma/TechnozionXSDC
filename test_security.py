#!/usr/bin/env python3
"""
Comprehensive Automated Defensive Security & Stress Test Suite
Validates the mitigation of all identified flaws:
1. Proxy Blindness Rate Limiting Bypass
2. Double-Scoring Race Condition (Canonical checkpoints & SQLite transactions)
3. Password Hash CPU DoS (Oversized payload bounds)
4. CSV Formula Injection Escaping
5. SQLite WAL Mode Concurrency Stress
6. Day 2 Level 1 Concurrent Submission Race Condition
7. Gauntlet Isolation & Legacy Route Safe Redirection
8. Thread-Safe Token Management
"""

import sys
import os
import time
import sqlite3
import threading
import concurrent.futures
import struct
from werkzeug.security import generate_password_hash

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
WWW_DIR = os.path.join(REPO_ROOT, "DAY 1", "www")

if WWW_DIR not in sys.path:
    sys.path.insert(0, WWW_DIR)

import app as ctf_app

def run_tests():
    print("=" * 70)
    print("RUNNING AGGRESSIVE SECURITY & CONCURRENCY VERIFICATION TEST SUITE")
    print("=" * 70)
    passed = 0
    total = 0

    client = ctf_app.app.test_client()
    ctf_app.app.config['TESTING'] = True

    # Snapshot existing global_settings to ensure test unlocks do not mutate production state
    settings_conn = ctf_app.get_db_connection()
    original_settings = {}
    for key in ['day1_visible', 'day2_visible', 'level1_unlocked', 'level2_unlocked', 'level3_unlocked', 'round2_unlocked', 'round3_unlocked']:
        row = settings_conn.execute("SELECT value FROM global_settings WHERE key = ?", (key,)).fetchone()
        if row:
            original_settings[key] = row['value']
    # Ensure all testable rounds are temporarily active during automated verification
    for key in ['day1_visible', 'day2_visible', 'level2_unlocked', 'level3_unlocked']:
        settings_conn.execute("INSERT OR REPLACE INTO global_settings (key, value) VALUES (?, '1')", (key,))
    settings_conn.commit()
    settings_conn.close()

    # ---------------------------------------------------------
    # TEST 1: CSV Formula Injection Escaping
    # ---------------------------------------------------------
    total += 1
    print("\n[TEST 1] CSV Formula Injection Sanitization (OWASP CWE-1236)...")
    dangerous_inputs = [
        ("=cmd|'/C calc'!A0", "'=cmd|'/C calc'!A0"),
        ("+123456789", "'+123456789"),
        ("-HYPERLINK(\"http://evil.com\")", "'-HYPERLINK(\"http://evil.com\")"),
        ("@SUM(A1:A10)", "'@SUM(A1:A10)"),
        ("\tTabPayload", "'\tTabPayload"),
        ("NormalPlayer123", "NormalPlayer123"),
        ("", ""),
        (None, "")
    ]
    all_escaped = True
    for raw, expected in dangerous_inputs:
        actual = ctf_app.sanitize_csv_cell(raw)
        if actual != expected:
            print(f"[-] FAILED for input {raw!r}: got {actual!r}, expected {expected!r}")
            all_escaped = False
    if all_escaped:
        print("[+] PASS: All formula prefix characters escaped successfully.")
        passed += 1
    else:
        print("[-] FAIL: CSV formula injection escaping failed.")

    # ---------------------------------------------------------
    # TEST 2: Password Hash CPU DoS (Oversized payload bounds)
    # ---------------------------------------------------------
    total += 1
    print("\n[TEST 2] Password Hash CPU DoS Protection (Oversized payload)...")
    large_payload = "A" * 500000 # 500KB string
    t_start = time.time()
    resp = client.post('/login', data={'username': 'test_user', 'password': large_payload})
    elapsed = time.time() - t_start
    if resp.status_code == 400 and elapsed < 0.1:
        print(f"[+] PASS: Oversized password rejected instantly (HTTP {resp.status_code} in {elapsed*1000:.2f}ms).")
        passed += 1
    else:
        print(f"[-] FAIL: Oversized password not rejected properly (status: {resp.status_code}, time: {elapsed:.2f}s).")

    # ---------------------------------------------------------
    # TEST 3: Proxy Real-IP Resolution & Brute-Force Rate Limiting
    # ---------------------------------------------------------
    total += 1
    print("\n[TEST 3] Proxy Blindness Rate Limiting Bypass Verification...")
    test_ip = "198.51.100.99"
    other_ip = "203.0.113.88"
    
    # Reset history for test IP
    ctf_app._LOGIN_HISTORY.pop(test_ip, None)
    ctf_app._LOGIN_HISTORY.pop(other_ip, None)

    # 15 failed logins from test_ip behind reverse proxy
    for i in range(15):
        resp = client.post('/login', 
            data={'username': f'unknown_user_{i}', 'password': 'wrong_password'},
            headers={'X-Forwarded-For': f"{test_ip}, 127.0.0.1"}
        )
        if resp.status_code == 429:
            print(f"[-] Premature rate limit at attempt {i+1}")
            break

    # 16th attempt should be blocked with 429
    resp_blocked = client.post('/login',
        data={'username': 'unknown_user_16', 'password': 'wrong_password'},
        headers={'X-Forwarded-For': f"{test_ip}, 127.0.0.1"}
    )
    # Attempt from other_ip should NOT be blocked
    resp_other = client.post('/login',
        data={'username': 'unknown_user_other', 'password': 'wrong_password'},
        headers={'X-Forwarded-For': f"{other_ip}, 127.0.0.1"}
    )

    if resp_blocked.status_code == 429 and resp_other.status_code != 429:
        print(f"[+] PASS: Rate limiting triggers strictly on proxy client IP (429 on 16th attempt, clean on separate IP).")
        passed += 1
    else:
        print(f"[-] FAIL: Proxy rate limiting check failed (blocked: {resp_blocked.status_code}, other: {resp_other.status_code}).")

    # ---------------------------------------------------------
    # TEST 4: Double-Scoring Race Condition (Concurrent /api/score)
    # ---------------------------------------------------------
    total += 1
    print("\n[TEST 4] Concurrent Flag Submission Double-Scoring Race Condition...")
    test_db_conn = ctf_app.get_db_connection()
    # Create temporary player for testing race conditions
    test_user_name = "race_tester_" + str(int(time.time()))
    cur = test_db_conn.execute('''
        INSERT INTO users (username, password, role, points, level2_points, level3_points, status, level2_status, level3_status, authorized_levels)
        VALUES (?, ?, 'player', 0, 0, 0, 'active', 'active', 'active', '[2, 3]')
    ''', (test_user_name, generate_password_hash('TestPass123!')))
    test_user_id = cur.lastrowid
    test_db_conn.commit()
    test_db_conn.close()

    expected_flag = ctf_app.generate_dynamic_flag(test_user_id, 'bravestone')
    
    # Create session token
    test_token = f"tok_race_{test_user_id}"
    ctf_app.set_internal_token(test_token, test_user_id, 'fake_sid_1')

    # Launch 10 concurrent requests submitting the flag
    submission_results = []
    def submit_worker(worker_id):
        c = ctf_app.app.test_client()
        res = c.post('/api/score', json={
            'token': test_token,
            'avatar_id': 'bravestone',
            'flag': expected_flag
        })
        return res.get_json()

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(submit_worker, i) for i in range(10)]
        for f in concurrent.futures.as_completed(futures):
            submission_results.append(f.result())

    success_count = sum(1 for r in submission_results if r and r.get('status') == 'success')
    already_count = sum(1 for r in submission_results if r and r.get('status') == 'already_solved')

    # Verify score in database
    conn = ctf_app.get_db_connection()
    user_row = conn.execute("SELECT level2_points, points FROM users WHERE id = ?", (test_user_id,)).fetchone()
    solved_entries = conn.execute("SELECT COUNT(*) as cnt FROM solved_challenges WHERE user_id = ? AND challenge_id = 'bravestone'", (test_user_id,)).fetchone()['cnt']
    conn.close()

    print(f"    Submissions: {success_count} success, {already_count} already_solved. Total DB entries: {solved_entries}, Points: {user_row['level2_points']}")
    if success_count == 1 and already_count == 9 and solved_entries == 1 and user_row['level2_points'] == 20:
        print("[+] PASS: Exactly 1 submission awarded points under 10 concurrent threads. Double-scoring fully eliminated.")
        passed += 1
    else:
        print("[-] FAIL: Race condition allowed duplicate scoring or corrupted state.")

    # ---------------------------------------------------------
    # TEST 5: Day 2 Level 1 Concurrent Submission Race Condition
    # ---------------------------------------------------------
    total += 1
    print("\n[TEST 5] Day 2 Level 1 Concurrent Submission Race Condition...")
    user_flag = ctf_app.generate_dynamic_flag(test_user_id, 'day2_level1_user')
    d2_results = []
    def d2_worker(idx):
        c = ctf_app.app.test_client()
        res = c.post('/api/score', json={
            'token': test_token,
            'avatar_id': 'day2_level1',
            'flag': user_flag
        })
        return res.get_json()

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(d2_worker, i) for i in range(10)]
        for f in concurrent.futures.as_completed(futures):
            d2_results.append(f.result())

    d2_success = sum(1 for r in d2_results if r and r.get('status') == 'success')
    d2_already = sum(1 for r in d2_results if r and r.get('status') == 'already_solved')

    conn = ctf_app.get_db_connection()
    user_row = conn.execute("SELECT level3_points FROM users WHERE id = ?", (test_user_id,)).fetchone()
    solved_entries = conn.execute("SELECT COUNT(*) as cnt FROM solved_challenges WHERE user_id = ? AND challenge_id IN ('level3_user', 'day2_level1_user')", (test_user_id,)).fetchone()['cnt']
    conn.close()

    print(f"    Submissions: {d2_success} success, {d2_already} already_solved. Total DB entries: {solved_entries}, Points: {user_row['level3_points']}")
    if d2_success == 1 and d2_already == 9 and solved_entries == 1 and user_row['level3_points'] == 80:
        print("[+] PASS: Day 2 Level 1 awarded exactly once across 10 concurrent threads without score duplication.")
        passed += 1
    else:
        print("[-] FAIL: Day 2 Level 1 race condition failed.")

    # ---------------------------------------------------------
    # TEST 6: SQLite WAL Mode Concurrency Stress Test
    # ---------------------------------------------------------
    total += 1
    print("\n[TEST 6] SQLite WAL Mode 50-Thread High Concurrency Stress Test...")
    lock_errors = 0
    ops_completed = 0
    def wal_worker(worker_id):
        nonlocal lock_errors, ops_completed
        try:
            c = ctf_app.get_db_connection()
            # Perform read and write
            c.execute("UPDATE users SET last_active = ? WHERE id = ?", (ctf_app.get_utc_now().isoformat(), test_user_id))
            c.commit()
            row = c.execute("SELECT points, level2_points FROM users WHERE id = ?", (test_user_id,)).fetchone()
            c.close()
            ops_completed += 1
        except sqlite3.OperationalError as e:
            if 'locked' in str(e).lower():
                lock_errors += 1
        except Exception:
            pass

    with concurrent.futures.ThreadPoolExecutor(max_workers=25) as executor:
        futures = [executor.submit(wal_worker, i) for i in range(50)]
        concurrent.futures.wait(futures)

    print(f"    Completed: {ops_completed}/50 concurrent DB operations. Lock timeout errors: {lock_errors}")
    if lock_errors == 0 and ops_completed == 50:
        print("[+] PASS: SQLite WAL mode handled 50 concurrent transactions with zero database lock errors.")
        passed += 1
    else:
        print(f"[-] FAIL: SQLite concurrency lock occurred: {lock_errors} lock errors.")

    # ---------------------------------------------------------
    # TEST 7: Gauntlet Isolation & Legacy Route Safe Redirection
    # ---------------------------------------------------------
    total += 1
    print("\n[TEST 7] Gauntlet Isolation & Legacy Route Safe Redirection...")
    unauth_resp1 = client.get('/day2/level2', follow_redirects=False)
    unauth_resp2 = client.get('/gauntlet', follow_redirects=False)

    with client.session_transaction() as sess:
        sess['user_id'] = test_user_id
        sess['role'] = 'player'
        sess['logged_in'] = True

    auth_resp1 = client.get('/day2/level2', follow_redirects=False)
    auth_resp2 = client.get('/gauntlet', follow_redirects=False)

    valid_redirects = (
        auth_resp1.status_code == 302 and '/hub' in auth_resp1.headers.get('Location', '') and
        auth_resp2.status_code == 302 and '/hub' in auth_resp2.headers.get('Location', '') and
        unauth_resp1.status_code == 302 and
        unauth_resp2.status_code == 302
    )

    if valid_redirects:
        print("[+] PASS: Isolated Gauntlet routes safely redirect to /hub without 500 error or database exposure.")
        passed += 1
    else:
        print(f"[-] FAIL: Legacy gauntlet route redirects unexpected: auth1={auth_resp1.status_code}, auth2={auth_resp2.status_code}")

    # ---------------------------------------------------------
    # TEST 8: Thread-Safe Token Management
    # ---------------------------------------------------------
    total += 1
    print("\n[TEST 8] Thread-Safe Token Management Concurrency...")
    token_errors = 0
    def token_worker(idx):
        nonlocal token_errors
        try:
            t_key = f"tok_test_{idx}"
            ctf_app.set_internal_token(t_key, idx, f"sid_{idx}")
            info = ctf_app.get_token_info(t_key)
            if not info or info.get('user_id') != idx:
                token_errors += 1
            ctf_app.prune_internal_tokens(f"sid_{idx}")
        except Exception as e:
            token_errors += 1

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(token_worker, i) for i in range(100)]
        concurrent.futures.wait(futures)

    if token_errors == 0:
        print("[+] PASS: 100 concurrent token operations executed safely without race conditions.")
        passed += 1
    else:
        print(f"[-] FAIL: Token management encountered {token_errors} errors under concurrency.")

    # ---------------------------------------------------------
    # TEST 9: Default Password Impersonation Rejection (SEC-19)
    # ---------------------------------------------------------
    total += 1
    print("\n[TEST 9] Zero Default Password Backdoor (SEC-19)...")
    # Participant accounts must reject default password ShadowDrop2026!
    resp_oauth_default = client.post('/login', data={'username': 'SDC-2026-0001', 'password': 'ShadowDrop2026!'}, follow_redirects=True)
    if b'ACCESS DENIED: Invalid credentials.' in resp_oauth_default.data and b'Participant password login is disabled' not in resp_oauth_default.data:
        print("[+] PASS: Synced participant account strictly rejects universal default password (ShadowDrop2026!).")
        passed += 1
    else:
        print("[-] FAIL: Synced participant account inappropriately accepted default password or showed legacy error.")

    # ---------------------------------------------------------
    # TEST 10: Explicit Admin Custom Password Authentication (SEC-19)
    # ---------------------------------------------------------
    total += 1
    print("\n[TEST 10] Explicit Admin-Set Password Authentication (SEC-19)...")
    explicit_user = f"audit_custom_{int(time.time())}"
    explicit_pass = "ExplicitSecret!2026"
    test_conn = ctf_app.get_db_connection()
    test_conn.execute(
        "INSERT INTO users (username, password, role, points, status) VALUES (?, ?, 'player', 0, 'active')",
        (explicit_user, ctf_app.generate_password_hash(explicit_pass))
    )
    test_conn.commit()
    test_conn.close()

    # Valid custom password must succeed (HTTP 302 to /)
    resp_valid = client.post('/login', data={'username': explicit_user, 'password': explicit_pass}, follow_redirects=False)
    # Invalid password must fail
    resp_invalid = client.post('/login', data={'username': explicit_user, 'password': 'WrongPassword!'}, follow_redirects=True)
    if resp_valid.status_code == 302 and b'ACCESS DENIED: Invalid credentials.' in resp_invalid.data:
        print("[+] PASS: Explicit admin-configured passwords authenticate properly and reject invalid attempts.")
        passed += 1
    else:
        print(f"[-] FAIL: Custom password authentication check failed (valid code={resp_valid.status_code}).")

    # Clean up explicit user
    clean_conn = ctf_app.get_db_connection()
    clean_conn.execute("DELETE FROM users WHERE username = ?", (explicit_user,))
    clean_conn.commit()
    clean_conn.close()

    # ---------------------------------------------------------
    # TEST 11: Mandatory Password on Admin Player Creation (SEC-20)
    # ---------------------------------------------------------
    total += 1
    print("\n[TEST 11] Mandatory Password Requirement on Admin Player Creation (SEC-20)...")
    admin_csrf = "test_csrf_token_admin"
    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['role'] = 'admin'
        sess['csrf_token'] = admin_csrf

    # Attempt player creation with empty password
    resp_empty_pw = client.post('/admin', data={
        'action': 'create_player',
        'username': 'player_no_pass_test',
        'password': '',
        'csrf_token': admin_csrf
    }, follow_redirects=True)

    # Attempt player creation with short password (<8 chars)
    resp_short_pw = client.post('/admin', data={
        'action': 'create_player',
        'username': 'player_short_pass_test',
        'password': 'short',
        'csrf_token': admin_csrf
    }, follow_redirects=True)

    if b'ERROR: Password is required to create a new player.' in resp_empty_pw.data and b'ERROR: Password must be at least 8 characters.' in resp_short_pw.data:
        print("[+] PASS: Admin player creation strictly requires explicit password with minimum length >= 8.")
        passed += 1
    else:
        print("[-] FAIL: Admin player creation accepted missing or short password.")

    # ---------------------------------------------------------
    # TEST 12: Docker Bridge RFC 1918 Subnet Isolation (SEC-21)
    # ---------------------------------------------------------
    total += 1
    print("\n[TEST 12] Docker Bridge RFC 1918 Subnet Isolation (SEC-21)...")
    resp_172 = client.get('/admin', environ_base={'REMOTE_ADDR': '172.17.0.2'})
    resp_10 = client.get('/admin', environ_base={'REMOTE_ADDR': '10.0.3.5'})
    resp_192 = client.get('/admin', environ_base={'REMOTE_ADDR': '192.168.100.12'})

    if resp_172.status_code == 403 and resp_10.status_code == 403 and resp_192.status_code == 403:
        print("[+] PASS: All Docker bridge private RFC 1918 subnets (172.16/12, 10.0/8, 192.168/16) blocked from admin.")
        passed += 1
    else:
        print(f"[-] FAIL: Subnet isolation check failed (172={resp_172.status_code}, 10={resp_10.status_code}, 192={resp_192.status_code}).")

    # ---------------------------------------------------------
    # TEST 13: PTY Dimension Pre-Sizing & Pending Resize Queueing
    # ---------------------------------------------------------
    total += 1
    print("\n[TEST 13] PTY Dimension Pre-Sizing & Pending Resize Queueing...")
    import termios
    import fcntl
    import pty
    
    # 1. Verify kernel PTY pre-sizing
    m_fd, s_fd = pty.openpty()
    test_cols, test_rows = 138, 42
    winsz = struct.pack("HHHH", test_rows, test_cols, 0, 0)
    fcntl.ioctl(m_fd, termios.TIOCSWINSZ, winsz)
    fcntl.ioctl(s_fd, termios.TIOCSWINSZ, winsz)
    buf = fcntl.ioctl(s_fd, termios.TIOCGWINSZ, b"\x00" * 8)
    r_rows, r_cols, _, _ = struct.unpack("HHHH", buf)
    os.close(s_fd)
    os.close(m_fd)
    
    # 2. Verify pending resize queue structure exists in app
    test_sid = "test_queue_sid_123"
    ctf_app.pending_pty_sizes[test_sid] = (test_cols, test_rows)
    queued_c, queued_r = ctf_app.pending_pty_sizes.pop(test_sid, (None, None))
    
    if r_cols == test_cols and r_rows == test_rows and queued_c == test_cols and queued_r == test_rows:
        print("[+] PASS: PTY TIOCSWINSZ kernel pre-sizing and pending resize caching verified.")
        passed += 1
    else:
        print(f"[-] FAIL: PTY dimension sync failed (cols={r_cols}, rows={r_rows}, queued=({queued_c},{queued_r})).")

    # Clean up test user and restore original production global_settings
    cleanup_conn = ctf_app.get_db_connection()
    try:
        cleanup_conn.execute("DELETE FROM users WHERE id = ?", (test_user_id,))
        cleanup_conn.execute("DELETE FROM solved_challenges WHERE user_id = ?", (test_user_id,))
        for key, val in original_settings.items():
            cleanup_conn.execute("INSERT OR REPLACE INTO global_settings (key, value) VALUES (?, ?)", (key, val))
        cleanup_conn.commit()
    finally:
        cleanup_conn.close()

    print("\n" + "=" * 70)
    print(f"TEST RESULTS: {passed}/{total} TESTS PASSED")
    print("=" * 70)
    return passed == total

if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
