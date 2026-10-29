#!/usr/bin/env python3
"""
Comprehensive Automated Defensive Security & Stress Test Suite
Validates the mitigation of all identified flaws:
1. Proxy Blindness Rate Limiting Bypass
2. Double-Scoring Race Condition (Canonical checkpoints & SQLite transactions)
3. Gauntlet Relic Submission Race Condition
4. Password Hash CPU DoS (Oversized payload bounds)
5. CSV Formula Injection Escaping
6. SQLite WAL Mode Concurrency Stress
7. Curse Input Validation
8. Thread-Safe Token Management
"""

import sys
import os
import time
import sqlite3
import threading
import concurrent.futures
from werkzeug.security import generate_password_hash

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
WWW_DIR = os.path.join(REPO_ROOT, "DAY 1", "www")
D2_DIR = os.path.join(REPO_ROOT, "DAY 2", "level2")

if WWW_DIR not in sys.path:
    sys.path.insert(0, WWW_DIR)
if D2_DIR not in sys.path:
    sys.path.insert(0, D2_DIR)

import app as ctf_app
import gauntlet_engine

def run_tests():
    print("=" * 70)
    print("RUNNING AGGRESSIVE SECURITY & CONCURRENCY VERIFICATION TEST SUITE")
    print("=" * 70)
    passed = 0
    total = 0

    client = ctf_app.app.test_client()
    ctf_app.app.config['TESTING'] = True

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
    # TEST 5: Gauntlet Relic Submission Race Condition
    # ---------------------------------------------------------
    total += 1
    print("\n[TEST 5] Gauntlet Relic Concurrent Submission Race Condition...")
    conn = ctf_app.get_db_connection()
    gauntlet_engine.init_gauntlet_db(conn)
    team_cur = conn.execute("INSERT INTO gauntlet_teams (team_name, access_code, pod_id) VALUES (?, ?, 'pod_alpha')",
        (f"RaceSquad_{int(time.time())}", f"CODE_{int(time.time())}"))
    test_team_id = team_cur.lastrowid
    conn.commit()

    split_keys = gauntlet_engine.generate_split_keys(test_team_id, 1, 'compass')
    combined_flag = split_keys['combined_flag']

    relic_results = []
    def relic_worker(idx):
        thread_conn = ctf_app.get_db_connection()
        res = gauntlet_engine.verify_relic_submission(thread_conn, test_team_id, combined_flag, user_id=test_user_id)
        thread_conn.close()
        return res

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(relic_worker, i) for i in range(10)]
        for f in concurrent.futures.as_completed(futures):
            relic_results.append(f.result())

    relic_success = sum(1 for r in relic_results if r and r.get('status') == 'success')
    relic_already = sum(1 for r in relic_results if r and r.get('status') == 'already_solved')

    team_db = conn.execute("SELECT phase1_score FROM gauntlet_teams WHERE id = ?", (test_team_id,)).fetchone()
    relic_db_cnt = conn.execute("SELECT COUNT(*) as cnt FROM gauntlet_solved_relics WHERE team_id = ? AND relic_id = 'compass'", (test_team_id,)).fetchone()['cnt']
    conn.close()

    print(f"    Gauntlet: {relic_success} success, {relic_already} already_solved. Relic DB records: {relic_db_cnt}, Score: {team_db['phase1_score']}")
    if relic_success == 1 and relic_already == 9 and relic_db_cnt == 1 and team_db['phase1_score'] == 25:
        print("[+] PASS: Gauntlet relic awarded exactly once across 10 threads without 500 error or score duplication.")
        passed += 1
    else:
        print("[-] FAIL: Gauntlet relic race condition failed.")

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
    # TEST 7: Gauntlet Curse Input Validation
    # ---------------------------------------------------------
    total += 1
    print("\n[TEST 7] Gauntlet Curse Input Validation...")
    conn = ctf_app.get_db_connection()
    conn.execute("INSERT OR REPLACE INTO gauntlet_members (team_id, user_id, role) VALUES (?, ?, 'navigator')", (test_team_id, test_user_id))
    conn.commit()
    conn.close()

    with client.session_transaction() as sess:
        sess['user_id'] = test_user_id
        sess['role'] = 'player'

    invalid_curse_resp = client.post('/gauntlet/curse/cast', json={
        'team_id': test_team_id,
        'curse_type': 'unauthorized_nuclear_wipe'
    })
    if invalid_curse_resp.status_code == 400 and 'unsupported' in invalid_curse_resp.get_json().get('error', '').lower():
        print(f"[+] PASS: Arbitrary curse type rejected with HTTP 400.")
        passed += 1
    else:
        print(f"[-] FAIL: Invalid curse type not properly rejected: {invalid_curse_resp.status_code}")

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

    # Clean up test user
    cleanup_conn = ctf_app.get_db_connection()
    cleanup_conn.execute("DELETE FROM users WHERE id = ?", (test_user_id,))
    cleanup_conn.execute("DELETE FROM solved_challenges WHERE user_id = ?", (test_user_id,))
    cleanup_conn.execute("DELETE FROM gauntlet_teams WHERE id = ?", (test_team_id,))
    cleanup_conn.execute("DELETE FROM gauntlet_solved_relics WHERE team_id = ?", (test_team_id,))
    cleanup_conn.commit()
    cleanup_conn.close()

    print("\n" + "=" * 70)
    print(f"TEST RESULTS: {passed}/{total} TESTS PASSED")
    print("=" * 70)
    return passed == total

if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
