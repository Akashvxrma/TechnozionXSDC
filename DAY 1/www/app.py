from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, Response
import sqlite3
import os
import pty
import subprocess
import select
import fcntl
import termios
import struct
import urllib.parse
import requests
import secrets
import re
import hmac
import hashlib
import base64
import json
import time
import csv
import io
import sys
from flask_socketio import SocketIO
from datetime import datetime, timedelta, timezone

_D2_L2_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "DAY 2", "level2")
if _D2_L2_DIR not in sys.path:
    sys.path.insert(0, _D2_L2_DIR)
import gauntlet_engine
import mongo_sync

def get_utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)

# 1. Early environment configuration loader
def load_ctf_env():
    _env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if os.path.exists(_env_path):
        try:
            with open(_env_path, 'r', encoding='utf-8') as _f:
                for _line in _f:
                    _line = _line.strip()
                    if _line and not _line.startswith('#') and '=' in _line:
                        _k, _v = _line.split('=', 1)
                        os.environ.setdefault(_k.strip(), _v.strip())
        except Exception:
            pass

load_ctf_env()

# 2. Canonical Master Secret & Shared Key
CTF_MASTER_SECRET = os.environ.get('CTF_MASTER_SECRET', '8f7b6c5d4a3e2f1g0h9i8j7k6l5m4n3')
CYBERSEC_SHARED_SECRET = os.environ.get('CYBERSEC_SHARED_SECRET', 'jumanji_cybersec_secret_key_2026_xyz')
SDC_MONGODB_URI = os.environ.get('SDC_MONGODB_URI', '')
SDC_MONGODB_DB_NAME = os.environ.get('SDC_MONGODB_DB_NAME', 'test')

# Google OAuth Configuration
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', 'YOUR_GOOGLE_CLIENT_ID.apps.googleusercontent.com')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', 'YOUR_GOOGLE_CLIENT_SECRET')
GOOGLE_REDIRECT_URI = os.environ.get('GOOGLE_REDIRECT_URI', 'http://127.0.0.1:8080/auth/callback')

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Derive or load persistent Flask Secret Key
_flask_sec = os.environ.get('FLASK_SECRET_KEY')
if not _flask_sec or _flask_sec == 'e5b9f7c41a238d6b9f47a192c34d8e5f':
    _sec_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.flask_secret')
    if os.path.exists(_sec_file):
        try:
            with open(_sec_file, 'r', encoding='utf-8') as _sf:
                _flask_sec = _sf.read().strip()
        except Exception:
            _flask_sec = None
    if not _flask_sec or len(_flask_sec) < 32:
        _flask_sec = secrets.token_hex(32)
        try:
            with open(_sec_file, 'w', encoding='utf-8') as _sf:
                _sf.write(_flask_sec)
            os.chmod(_sec_file, 0o600)
        except Exception:
            pass
app.secret_key = _flask_sec

# 3. Origin verification for Socket.IO and CSRF
def is_allowed_origin(origin):
    if not origin:
        return True
    try:
        parsed = urllib.parse.urlparse(origin)
        host = (parsed.hostname or '').lower()
        if host in ('127.0.0.1', 'localhost', '::1') or host.endswith('.nip.io'):
            return True
        # Check private IPv4 literals
        parts = host.split('.')
        if len(parts) == 4 and all(p.isdigit() for p in parts):
            a, b = int(parts[0]), int(parts[1])
            if a == 10 or (a == 172 and 16 <= b <= 31) or (a == 192 and b == 168):
                return True
        web_origins = [o.strip() for o in os.environ.get('WEB_ORIGIN', '').split(',') if o.strip()]
        for wo in web_origins:
            if wo == '*' or (urllib.parse.urlparse(wo).hostname or '').lower() == host or wo.lower() == host:
                return True
    except Exception:
        pass
    return False

socketio = SocketIO(app, cors_allowed_origins=is_allowed_origin)

# 4. In-Memory Flag Submission Rate Limiter
import collections
_SUBMISSION_HISTORY = collections.defaultdict(list)

def is_submission_rate_limited(identifier: str, max_attempts: int = 30, window_sec: int = 60) -> bool:
    now = time.time()
    valid = [t for t in _SUBMISSION_HISTORY[identifier] if now - t < window_sec]
    if len(valid) >= max_attempts:
        _SUBMISSION_HISTORY[identifier] = valid
        return True
    valid.append(now)
    _SUBMISSION_HISTORY[identifier] = valid
    return False

# 5. Anti-CSRF Session Token Helper
def get_csrf_token():
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    return session['csrf_token']

@app.context_processor
def inject_csrf_token():
    return dict(csrf_token=get_csrf_token)

# 6. Security & Subnet Protection Middleware
@app.before_request
def enforce_security_and_csrf():
    client_ip = request.remote_addr or ''
    # Docker default bridge subnets: block container users from admin & auth portals
    if client_ip.startswith('172.17.') or client_ip.startswith('172.18.'):
        if request.path.startswith('/admin') or request.path in ('/login', '/register', '/choose-username'):
            return jsonify({'error': 'Administrative access blocked from container networks'}), 403

    if request.method in ('POST', 'PUT', 'DELETE', 'PATCH'):
        # Token-based CLI flag submissions (/api/score with token) don't carry browser cookies
        if request.path == '/api/score' and request.is_json and request.json and request.json.get('token'):
            return

        # Validate Origin header if present
        origin = request.headers.get('Origin')
        if origin and not is_allowed_origin(origin):
            return jsonify({'error': 'Cross-origin request rejected'}), 403

        # Validate CSRF token on admin form submissions
        if request.path.startswith('/admin') and request.form:
            token = request.form.get('csrf_token')
            expected = session.get('csrf_token')
            if not expected or not token or not hmac.compare_digest(token, expected):
                flash("Security verification failed: Invalid or missing CSRF token.")
                return redirect(request.referrer or url_for('admin'))

@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response

# 7. Canonical Score Resolution Helper
def get_user_scores(user_row):
    """Canonical score resolution for CTF participants across all levels."""
    if isinstance(user_row, sqlite3.Row):
        u = dict(user_row)
    elif isinstance(user_row, dict):
        u = user_row
    else:
        return {'level1': 0, 'level2': 0, 'level3': 0, 'total': 0}
    l2 = u.get('level2_points') if u.get('level2_points') is not None else u.get('points', 0)
    l3 = u.get('level3_points') or 0
    l1 = u.get('level1_points') or 0
    return {
        'level1': l1,
        'level2': l2,
        'level3': l3,
        'total': l1 + l2 + l3
    }

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'jumanji_auth.db')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            points INTEGER DEFAULT 0,
            level2_points INTEGER DEFAULT 0,
            start_time DATETIME,
            level2_start_time DATETIME,
            status TEXT DEFAULT 'active',
            level2_status TEXT DEFAULT 'active',
            has_seen_intro INTEGER DEFAULT 0,
            has_seen_l2_intro INTEGER DEFAULT 0,
            last_active DATETIME,
            google_id TEXT,
            email TEXT,
            name TEXT,
            participant_id TEXT,
            authorized_levels TEXT
        )
    ''')
    
    conn.execute('''
        CREATE TABLE IF NOT EXISTS solved_challenges (
            user_id INTEGER,
            challenge_id TEXT,
            PRIMARY KEY (user_id, challenge_id)
        )
    ''')
    
    # Check if legacy columns need renaming or missing columns need adding
    cursor = conn.execute("PRAGMA table_info(users)")
    columns = [col['name'] for col in cursor.fetchall()]

    if 'level3_points' not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN level3_points INTEGER DEFAULT 0")
        conn.execute("ALTER TABLE users ADD COLUMN level3_start_time DATETIME")
        conn.execute("ALTER TABLE users ADD COLUMN level3_status TEXT DEFAULT 'active'")
        conn.execute("ALTER TABLE users ADD COLUMN has_seen_l3_intro INTEGER DEFAULT 0")

        # Migrate existing users: old level2_points were Mainframe -> migrate to level3
        conn.execute('''
            UPDATE users SET 
                level3_points = level2_points,
                level3_start_time = level2_start_time,
                level3_status = level2_status,
                has_seen_l3_intro = has_seen_l2_intro
            WHERE (level2_points > 0 OR level2_start_time IS NOT NULL)
        ''')
        # Old points were Avatar Reconnaissance -> ensure level2_points has them
        conn.execute('''
            UPDATE users SET
                level2_points = points,
                level2_start_time = start_time,
                level2_status = status,
                has_seen_l2_intro = has_seen_intro
            WHERE (points > 0 OR start_time IS NOT NULL)
        ''')

    # Refresh columns after potential additions
    cursor = conn.execute("PRAGMA table_info(users)")
    columns = [col['name'] for col in cursor.fetchall()]

    if 'points' not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN points INTEGER DEFAULT 0")
    if 'level2_points' not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN level2_points INTEGER DEFAULT 0")
    if 'start_time' not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN start_time DATETIME")
    if 'level2_start_time' not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN level2_start_time DATETIME")
    if 'status' not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN status TEXT DEFAULT 'active'")
    if 'level2_status' not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN level2_status TEXT DEFAULT 'active'")
    if 'has_seen_intro' not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN has_seen_intro INTEGER DEFAULT 0")
    if 'has_seen_l2_intro' not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN has_seen_l2_intro INTEGER DEFAULT 0")
    if 'last_active' not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN last_active DATETIME")
    if 'google_id' not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN google_id TEXT")
    if 'email' not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN email TEXT")
    if 'name' not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN name TEXT")
    if 'participant_id' not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN participant_id TEXT")
    if 'authorized_levels' not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN authorized_levels TEXT")

    # Check solved_challenges columns
    cursor_sc = conn.execute("PRAGMA table_info(solved_challenges)")
    sc_columns = [col['name'] for col in cursor_sc.fetchall()]
    if 'solved_at' not in sc_columns:
        conn.execute("ALTER TABLE solved_challenges ADD COLUMN solved_at DATETIME")

    # Pending score sync queue for resilient webhook delivery
    conn.execute('''
        CREATE TABLE IF NOT EXISTS pending_score_syncs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            participant_id TEXT NOT NULL,
            round_id TEXT NOT NULL,
            raw_score INTEGER NOT NULL,
            checkpoint TEXT NOT NULL,
            checkpoint_points INTEGER NOT NULL,
            status TEXT DEFAULT 'pending',
            retries INTEGER DEFAULT 0,
            created_at DATETIME
        )
    ''')

    # Insert default admin user if not exists
    user = conn.execute("SELECT * FROM users WHERE username = 'admin'").fetchone()
    if not user:
        conn.execute("INSERT INTO users (username, password, role, points, level2_points, level3_points, status, level2_status, level3_status, has_seen_intro, has_seen_l2_intro, has_seen_l3_intro) VALUES ('admin', 'Admin_ShadowDrop!2026', 'admin', 0, 0, 0, 'active', 'active', 'active', 1, 1, 1)")
    else:
        # Enforce new secure admin password even if already exists
        conn.execute("UPDATE users SET password = 'Admin_ShadowDrop!2026' WHERE username = 'admin'")

    # Day 1 Level 2 (Avatars) & Level 3 (Mainframe) settings
    conn.execute('''
        CREATE TABLE IF NOT EXISTS global_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    has_l3 = conn.execute("SELECT 1 FROM global_settings WHERE key = 'level3_unlocked'").fetchone()
    if not has_l3:
        # Migrate: old level2_unlocked was mainframe -> level3_unlocked
        old_l2 = conn.execute("SELECT value FROM global_settings WHERE key = 'level2_unlocked'").fetchone()
        l3_val = old_l2['value'] if old_l2 else '0'
        # Old level1_unlocked was avatars -> level2_unlocked
        old_l1 = conn.execute("SELECT value FROM global_settings WHERE key = 'level1_unlocked'").fetchone()
        l2_val = old_l1['value'] if old_l1 else '1'
        conn.execute("INSERT OR REPLACE INTO global_settings (key, value) VALUES ('level3_unlocked', ?)", (l3_val,))
        conn.execute("INSERT OR REPLACE INTO global_settings (key, value) VALUES ('level2_unlocked', ?)", (l2_val,))

    conn.execute("INSERT OR IGNORE INTO global_settings (key, value) VALUES ('level2_unlocked', '1')")
    conn.execute("INSERT OR IGNORE INTO global_settings (key, value) VALUES ('level3_unlocked', '0')")
    conn.execute("INSERT OR REPLACE INTO global_settings (key, value) VALUES ('level1_unlocked', (SELECT value FROM global_settings WHERE key = 'level2_unlocked'))")
    conn.execute("INSERT OR REPLACE INTO global_settings (key, value) VALUES ('round2_unlocked', (SELECT value FROM global_settings WHERE key = 'level2_unlocked'))")
    conn.execute("INSERT OR REPLACE INTO global_settings (key, value) VALUES ('round3_unlocked', (SELECT value FROM global_settings WHERE key = 'level3_unlocked'))")
    # Day visibility on the player hub (hidden days are not shown and cannot be entered)
    conn.execute("INSERT OR IGNORE INTO global_settings (key, value) VALUES ('day1_visible', '1')")
    conn.execute("INSERT OR IGNORE INTO global_settings (key, value) VALUES ('day2_visible', '0')")

    # Initialize Jumanji Gauntlet tournament tables
    gauntlet_engine.init_gauntlet_db(conn)

    conn.commit()
    conn.close()

def verify_launch_token(token_str, secret):
    try:
        parts = token_str.strip().split('.')
        if len(parts) != 2:
            return None
        payload_b64, signature = parts
        expected_sig = hmac.new(secret.encode('utf-8'), payload_b64.encode('utf-8'), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected_sig):
            return None
        padding = '=' * (-len(payload_b64) % 4)
        raw_json = base64.urlsafe_b64decode(payload_b64 + padding).decode('utf-8')
        data = json.loads(raw_json)
        now = int(time.time())
        if now > data.get('exp', 0):
            return None
        return data
    except Exception as e:
        print("[Token Verification] Failed:", e)
        return None

@socketio.on('ping')
def handle_ping():
    if 'user_id' in session:
        conn = get_db_connection()
        conn.execute("UPDATE users SET last_active = ? WHERE id = ?", (get_utc_now().isoformat(), session['user_id']))
        conn.commit()
        conn.close()

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    if session.get('role') == 'admin':
        return redirect(url_for('admin'))
        
    return redirect(url_for('hub'))

@app.route('/hub')
def hub():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    l2_row = conn.execute("SELECT value FROM global_settings WHERE key = 'level2_unlocked'").fetchone()
    l2_unlocked = (l2_row['value'] == '1') if l2_row else True
    l3_row = conn.execute("SELECT value FROM global_settings WHERE key = 'level3_unlocked'").fetchone()
    l3_unlocked = (l3_row['value'] == '1') if l3_row else False
    day1_visible = conn.execute("SELECT value FROM global_settings WHERE key = 'day1_visible'").fetchone()['value'] == '1'
    day2_visible = conn.execute("SELECT value FROM global_settings WHERE key = 'day2_visible'").fetchone()['value'] == '1'
    user = conn.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],)).fetchone()

    # Check Day 2 tournament team
    team = None
    if day2_visible:
        team = gauntlet_engine.get_team_for_user(conn, session['user_id'])
    conn.close()

    l2_pts = user['level2_points'] or user['points'] or 0
    l3_pts = user['level3_points'] or 0
    l2_status = user['level2_status'] or user['status'] or 'active'
    l3_status = user['level3_status'] or 'active'

    can_play_l2 = day1_visible and l2_unlocked and l2_status == 'active' and l2_pts < 150
    can_play_l3 = day1_visible and l3_unlocked and l3_status == 'active' and l3_pts < 200

    raw_auth = user['authorized_levels']
    if raw_auth:
        try:
            auth_levels = json.loads(raw_auth)
        except Exception:
            auth_levels = [2, 3]
    else:
        auth_levels = [2, 3]

    # Single-target determination for the 3D Jumanji board
    if day2_visible and team:
        target_level = 'day2'
        target_name = 'The Jumanji Gauntlet'
        target_url = url_for('day2_level2')
        is_unlocked = True
        is_done = False
        riddle = "Two by two the champions stand,\nSplit keys locked by partner’s hand.\nHold the shrine, endure the curse,\nEight survivors claim the verse."
        movement_style = 'charge'
        steps = 18
    elif 3 in auth_levels and 2 not in auth_levels:
        target_level = 'l3'
        target_name = 'Simulation Core (Mainframe)'
        target_url = url_for('level3')
        is_unlocked = day1_visible and l3_unlocked and l3_status == 'active'
        is_done = l3_pts >= 200
        riddle = "Beware the core where power hides,\nA cursed mainframe, changing tides.\nSpeak the chant and break the root,\nOr perish under Nigel’s boot."
        movement_style = 'heavy'
        steps = 8
    elif 2 in auth_levels and 3 not in auth_levels:
        target_level = 'l2'
        target_name = 'Avatar Reconnaissance'
        target_url = url_for('level2')
        is_unlocked = day1_visible and l2_unlocked and l2_status == 'active'
        is_done = l2_pts >= 150
        riddle = "In the jungle you must wait,\nFive lost relics seal your fate.\nRecon badges, shadows deep,\nFind the secrets avatars keep."
        movement_style = 'hop'
        steps = 5
    else:
        # Dual-authorized (e.g. testing / local admin)
        if l2_pts < 150:
            target_level = 'l2'
            target_name = 'Avatar Reconnaissance'
            target_url = url_for('level2')
            is_unlocked = day1_visible and l2_unlocked and l2_status == 'active'
            is_done = False
            riddle = "In the jungle you must wait,\nFive lost relics seal your fate.\nRecon badges, shadows deep,\nFind the secrets avatars keep."
            movement_style = 'hop'
            steps = 5
        else:
            target_level = 'l3'
            target_name = 'Simulation Core (Mainframe)'
            target_url = url_for('level3')
            is_unlocked = day1_visible and l3_unlocked and l3_status == 'active'
            is_done = l3_pts >= 200
            riddle = "Beware the core where power hides,\nA cursed mainframe, changing tides.\nSpeak the chant and break the root,\nOr perish under Nigel’s boot."
            movement_style = 'heavy'
            steps = 8

    locked_riddle = "The board is still, the drums are low;\nThe host will say when you may go."
    completed_riddle = "Your trial is won, the relic claims its place;\nAwait the next dawn or the tournament race."

    player_expedition_config = {
        'targetLevel': target_level,
        'targetName': target_name,
        'targetUrl': target_url,
        'isUnlocked': is_unlocked,
        'isDone': is_done,
        'riddle': riddle,
        'lockedRiddle': locked_riddle,
        'completedRiddle': completed_riddle,
        'movementStyle': movement_style,
        'steps': steps,
        'authorizedLevels': auth_levels
    }

    return render_template(
        'hub.html',
        user=user,
        player_expedition_config=player_expedition_config,
        can_play_l2=can_play_l2,
        can_play_l3=can_play_l3,
        level2_unlocked=l2_unlocked,
        level3_unlocked=l3_unlocked,
        can_play_l1=can_play_l2,
        can_play_r2=can_play_l2,
        can_play_r3=can_play_l3,
        level1_unlocked=l2_unlocked,
        round2_unlocked=l2_unlocked,
        round3_unlocked=l3_unlocked,
        r2_unlocked=l2_unlocked,
        r3_unlocked=l3_unlocked,
        day1_visible=day1_visible,
        day2_visible=day2_visible
    )

@app.before_request
def check_timer():
    if request.path.startswith('/static') or request.path.startswith('/auth') or request.path in ['/login', '/register', '/logout', '/choose-username', '/hub']:
        return
        
    if 'user_id' in session and session.get('role') != 'admin':
        conn = get_db_connection()
        user = conn.execute("SELECT start_time, status, level2_start_time, level2_status, level3_start_time, level3_status FROM users WHERE id = ?", (session['user_id'],)).fetchone()
        
        if user:
            needs_commit = False
            # Check Level 2 timer (Avatars)
            l2_start = user['level2_start_time'] or user['start_time']
            l2_stat = user['level2_status'] or user['status']
            if l2_start and l2_stat != 'suspended':
                start_time = datetime.fromisoformat(l2_start)
                if get_utc_now() > start_time + timedelta(minutes=60):
                    conn.execute("UPDATE users SET level2_status = 'suspended', status = 'suspended' WHERE id = ?", (session['user_id'],))
                    needs_commit = True
                    flash('DAY 1 LEVEL 2 TIME IS UP. ACCOUNT SUSPENDED FROM LEVEL 2.')
            
            # Check Level 3 timer (Mainframe)
            if user['level3_start_time'] and user['level3_status'] != 'suspended':
                l3_start_time = datetime.fromisoformat(user['level3_start_time'])
                if get_utc_now() > l3_start_time + timedelta(minutes=60):
                    conn.execute("UPDATE users SET level3_status = 'suspended' WHERE id = ?", (session['user_id'],))
                    needs_commit = True
                    flash('DAY 1 LEVEL 3 TIME IS UP. ACCOUNT SUSPENDED FROM LEVEL 3.')
                    
            if needs_commit:
                conn.commit()
                
        conn.close()

def check_level_access(user_id, level_num, is_submission=False):
    """
    Centralized, database-backed security and authorization verification.
    Ensures:
      1. User exists and is authenticated.
      2. User is registered for the requested domain/level (authorized_levels).
      3. Global tournament and admin locks are strictly respected.
      4. Individual suspension or completion limits are respected.
    Returns:
      (True, None) if authorized to proceed.
      (False, error_message) if access is denied.
    """
    if not user_id:
        return False, "Authentication required. Please log in."

    conn = get_db_connection()
    user = conn.execute("""
        SELECT id, username, role, authorized_levels, status, 
               level2_status, level3_status, points, level2_points, level3_points 
        FROM users WHERE id = ?
    """, (user_id,)).fetchone()

    if not user:
        conn.close()
        return False, "User account not found."

    # Administrators have universal access
    if user['role'] == 'admin':
        conn.close()
        return True, None

    # Determine user's authorized levels list
    raw_auth = user['authorized_levels']
    user_levels = []
    if raw_auth:
        try:
            parsed = json.loads(raw_auth)
            user_levels = [int(x) for x in parsed if str(x).isdigit()]
        except Exception:
            user_levels = []
    elif user['username'] == 'verification_pilot':
        user_levels = [2, 3]

    # Level 2 authorization check
    if level_num in (1, 2):
        if 2 not in user_levels and 1 not in user_levels:
            conn.close()
            return False, "Access Denied: Your registration is only for Day 1 Level 3 (Simulation Core Mainframe)."

        l2_row = conn.execute("SELECT value FROM global_settings WHERE key = 'level2_unlocked'").fetchone()
        l2_unlocked = (l2_row['value'] == '1') if l2_row else False
        d1_row = conn.execute("SELECT value FROM global_settings WHERE key = 'day1_visible'").fetchone()
        d1_vis = (d1_row['value'] == '1') if d1_row else False
        stat = user['level2_status'] or user['status'] or 'active'
        pts = user['level2_points'] or user['points'] or 0

        conn.close()
        if not d1_vis:
            return False, "Day 1 has not been opened yet by the tournament host."
        if not l2_unlocked:
            return False, "Day 1 Level 2 is currently locked by the game master."
        if stat == 'suspended':
            return False, "Your Day 1 Level 2 session has ended."
        if not is_submission and pts >= 150:
            return False, "You have already completed Day 1 Level 2."
        return True, None

    # Level 3 authorization check
    elif level_num == 3:
        if 3 not in user_levels:
            conn.close()
            return False, "Access Denied: Your registration is only for Day 1 Level 2 (Avatar Reconnaissance)."

        l3_row = conn.execute("SELECT value FROM global_settings WHERE key = 'level3_unlocked'").fetchone()
        l3_unlocked = (l3_row['value'] == '1') if l3_row else False
        d1_row = conn.execute("SELECT value FROM global_settings WHERE key = 'day1_visible'").fetchone()
        d1_vis = (d1_row['value'] == '1') if d1_row else False
        stat = user['level3_status'] or 'active'
        pts = user['level3_points'] or 0

        conn.close()
        if not d1_vis:
            return False, "Day 1 has not been opened yet by the tournament host."
        if not l3_unlocked:
            return False, "Day 1 Level 3 is currently locked by the game master."
        if stat == 'suspended':
            return False, "Your Day 1 Level 3 session has ended."
        if not is_submission and pts >= 200:
            return False, "You have already completed Day 1 Level 3."
        return True, None

    # Day 2 Gauntlet authorization check
    elif level_num in ('day2', 'gauntlet'):
        d2_row = conn.execute("SELECT value FROM global_settings WHERE key = 'day2_visible'").fetchone()
        d2_vis = (d2_row['value'] == '1') if d2_row else False
        conn.close()
        if not d2_vis:
            return False, "Day 2 has not been opened yet by the tournament host."
        return True, None

    conn.close()
    return False, "Unknown level requested."

@app.route('/auth/launch')
def auth_launch():
    token_str = request.args.get('token')
    if not token_str:
        flash('Missing arena launch token.')
        return redirect(url_for('login'))

    payload = verify_launch_token(token_str, CYBERSEC_SHARED_SECRET)
    if not payload:
        flash('Invalid or expired arena launch token. Please launch again from SDC Games.')
        return redirect(url_for('login'))

    participant_id = payload.get('participantId')
    email = payload.get('email', '')
    name = payload.get('name', '')
    
    # Determine target level and day
    raw_level_param = str(request.args.get('level', payload.get('targetLevel', '2'))).lower()
    target_day = payload.get('targetDay', 1)
    is_day2 = target_day == 2 or raw_level_param in ['day2-l2', 'day-2-l2', 'day2', 'gauntlet']
    is_level3 = raw_level_param in ['3', 'round3', 'r3', 'level3', 'l3', 'day1-l3', 'day-1-l3'] or payload.get('targetLevel') == 3

    authorized_levels = payload.get('authorizedLevels', [2, 3])
    auth_normalized = [str(x).lower() for x in authorized_levels]

    if is_day2:
        req_allowed = any(k in auth_normalized for k in ['day2-l2', 'day2', 'gauntlet', '2'])
    elif is_level3:
        req_allowed = any(k in auth_normalized for k in ['3', 'round3', 'level3', 'day1-l3', 'day-1-l3'])
    else:
        req_allowed = any(k in auth_normalized for k in ['2', '1', 'level2', 'day1-l2', 'day-1-l2'])

    if not req_allowed:
        flash('Your registration does not include Cybersecurity for the requested level.')
        return redirect(url_for('hub'))

    conn = get_db_connection()
    user = None
    if participant_id:
        user = conn.execute("SELECT * FROM users WHERE participant_id = ?", (participant_id,)).fetchone()
    if not user and email:
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

    # Store normalized integers in authorized_levels where possible
    db_auth_levels = []
    for x in authorized_levels:
        if str(x).isdigit():
            db_auth_levels.append(int(x))
    if is_day2 and 2 not in db_auth_levels:
        db_auth_levels.append(2)
    auth_levels_json = json.dumps(db_auth_levels)

    if not user:
        base_username = (participant_id or 'player').lower().replace('-', '_')
        username = base_username
        suffix = 1
        while conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
            username = f"{base_username}_{suffix}"
            suffix += 1

        unusable_pw = f"!OAUTH_ONLY!_{secrets.token_hex(16)}"
        conn.execute('''
            INSERT INTO users (username, password, role, points, level2_points, level3_points, status, level2_status, level3_status, has_seen_intro, has_seen_l2_intro, has_seen_l3_intro, participant_id, authorized_levels, email, name)
            VALUES (?, ?, 'player', 0, 0, 0, 'active', 'active', 'active', 0, 0, 0, ?, ?, ?, ?)
        ''', (username, unusable_pw, participant_id, auth_levels_json, email, name))
        conn.commit()
        user = conn.execute("SELECT * FROM users WHERE participant_id = ?", (participant_id,)).fetchone()
    else:
        conn.execute('''
            UPDATE users SET participant_id = ?, authorized_levels = ?, email = COALESCE(NULLIF(email, ''), ?), name = COALESCE(NULLIF(name, ''), ?)
            WHERE id = ?
        ''', (participant_id, auth_levels_json, email, name, user['id']))
        conn.commit()
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user['id'],)).fetchone()

    conn.close()

    session.clear()
    session['user_id'] = user['id']
    session['username'] = user['username']
    session['participant_id'] = participant_id
    session['role'] = user['role']
    session['authorized_levels'] = db_auth_levels
    l2_pts = user['level2_points'] or user['points'] or 0
    l3_pts = user['level3_points'] or 0
    session['points'] = l2_pts
    session['level2_points'] = l2_pts
    session['level3_points'] = l3_pts
    session['round3_points'] = l3_pts

    if is_level3:
        return redirect(url_for('level3'))
    elif is_day2:
        return redirect(url_for('day2_level2'))
    else:
        return redirect(url_for('level2'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        
        conn = get_db_connection()
        # Enforce Google Sign-In for participants: Block direct password login for player accounts / participant IDs
        p_check = conn.execute("SELECT id, role, participant_id FROM users WHERE participant_id = ? OR (username = ? AND role != 'admin' AND username != 'verification_pilot')", (username, username)).fetchone()
        if p_check:
            conn.close()
            flash('Participant password login is disabled. Please click "Continue with Google" above to sign in with your registered email.')
            return render_template('login.html')

        user = conn.execute('''
            SELECT id, username, participant_id, role, points, level2_points, level3_points, start_time, level2_start_time, level3_start_time, status, level2_status, level3_status, authorized_levels 
            FROM users 
            WHERE username = ? AND password = ? AND (role = 'admin' OR username = 'verification_pilot')
        ''', (username, password)).fetchone()
        
        if user:
            l2_pts = user['level2_points'] or user['points'] or 0
            l3_pts = user['level3_points'] or 0
            l2_stat = user['level2_status'] or user['status']
            l3_stat = user['level3_status']
            if l2_stat == 'suspended' and l3_stat == 'suspended' and l2_pts >= 150 and l3_pts >= 200:
                conn.close()
                flash('ACCOUNT SUSPENDED: ALL DAY 1 LEVELS COMPLETED.')
                return render_template('login.html')
                
            conn.close()
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['participant_id'] = user['participant_id']
            session['role'] = user['role']
            session['points'] = l2_pts
            session['level2_points'] = l2_pts
            session['level3_points'] = l3_pts
            if user['authorized_levels']:
                try:
                    session['authorized_levels'] = [int(x) for x in json.loads(user['authorized_levels']) if str(x).isdigit()]
                except Exception:
                    session['authorized_levels'] = []
            elif user['role'] == 'admin' or user['username'] == 'verification_pilot':
                session['authorized_levels'] = [2, 3]
            else:
                session['authorized_levels'] = []
            return redirect(url_for('index'))
        else:
            conn.close()
            flash('ACCESS DENIED: Invalid credentials.')
            
    return render_template('login.html')

def get_google_redirect_uri():
    if GOOGLE_REDIRECT_URI:
        return GOOGLE_REDIRECT_URI
    return url_for('google_callback', _external=True)

@app.route('/auth/google')
def google_login():
    state = secrets.token_urlsafe(16)
    session['oauth_state'] = state
    redirect_uri = get_google_redirect_uri()
    
    params = {
        'client_id': GOOGLE_CLIENT_ID,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': 'openid email profile',
        'state': state,
        'access_type': 'online',
        'prompt': 'select_account'
    }
    auth_url = f"https://accounts.google.com/o/oauth2/auth?{urllib.parse.urlencode(params)}"
    return redirect(auth_url)

@app.route('/auth/callback')
@app.route('/auth/google/callback')
def google_callback():
    error = request.args.get('error')
    if error:
        flash(f"Google authentication failed: {error}")
        return redirect(url_for('login'))
        
    code = request.args.get('code')
    state = request.args.get('state')
    
    if not code or not state or state != session.get('oauth_state'):
        flash("Invalid Google authentication response or expired session.")
        return redirect(url_for('login'))
        
    session.pop('oauth_state', None)
    redirect_uri = get_google_redirect_uri()
    
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        'code': code,
        'client_id': GOOGLE_CLIENT_ID,
        'client_secret': GOOGLE_CLIENT_SECRET,
        'redirect_uri': redirect_uri,
        'grant_type': 'authorization_code'
    }
    
    try:
        token_resp = requests.post(token_url, data=data, timeout=10)
        token_data = token_resp.json()
    except Exception as e:
        flash(f"Error communicating with Google token endpoint: {e}")
        return redirect(url_for('login'))
        
    access_token = token_data.get('access_token')
    if not access_token:
        err_msg = token_data.get('error_description') or token_data.get('error') or "Failed to exchange authorization code."
        flash(f"Google login failed: {err_msg}")
        return redirect(url_for('login'))
        
    try:
        userinfo_resp = requests.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={'Authorization': f"Bearer {access_token}"},
            timeout=10
        )
        profile = userinfo_resp.json()
    except Exception as e:
        flash(f"Failed to fetch profile details from Google: {e}")
        return redirect(url_for('login'))
        
    google_id = profile.get('sub')
    email = profile.get('email')
    
    if not google_id or not email:
        flash("Google profile missing user identifier or email.")
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    # Check if user already exists
    user = conn.execute("SELECT * FROM users WHERE google_id = ? OR email = ?", (google_id, email)).fetchone()
    
    if user:
        if not user['google_id']:
            conn.execute("UPDATE users SET google_id = ? WHERE id = ?", (google_id, user['id']))
            conn.commit()
        conn.close()
        
        if user['status'] == 'suspended':
            flash('ACCOUNT SUSPENDED: GAME COMPLETED OR BANNED.')
            return redirect(url_for('login'))
            
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['role'] = user['role']
        session['points'] = user['points']
        if user['authorized_levels']:
            try:
                session['authorized_levels'] = [int(x) for x in json.loads(user['authorized_levels']) if str(x).isdigit()]
            except Exception:
                session['authorized_levels'] = []
        elif user['role'] == 'admin' or user['username'] == 'verification_pilot':
            session['authorized_levels'] = [2, 3]
        else:
            session['authorized_levels'] = []
        return redirect(url_for('index'))
        
    conn.close()
    
    # Store verified Google identity in session and prompt user to choose a username
    session['pending_google_user'] = {
        'google_id': google_id,
        'email': email,
        'name': profile.get('name', '')
    }
    return redirect(url_for('choose_username'))

@app.route('/choose-username', methods=['GET', 'POST'])
def choose_username():
    if 'pending_google_user' not in session:
        return redirect(url_for('login'))
        
    pending = session['pending_google_user']
    
    if request.method == 'POST':
        chosen = request.form.get('username', '').strip()
        if not chosen:
            flash('Codename cannot be blank.')
            return render_template('choose_username.html', email=pending['email'])
            
        if not re.match(r'^[a-zA-Z0-9_-]{3,20}$', chosen):
            flash('Codename must be 3-20 characters using letters, numbers, _, or -.')
            return render_template('choose_username.html', email=pending['email'])
            
        conn = get_db_connection()
        existing = conn.execute("SELECT id FROM users WHERE username = ?", (chosen,)).fetchone()
        if existing:
            conn.close()
            flash('Codename is already taken! Choose another identity.')
            return render_template('choose_username.html', email=pending['email'])
            
        dummy_pw = secrets.token_hex(16)
        conn.execute(
            "INSERT INTO users (username, password, role, points, status, google_id, email, authorized_levels) VALUES (?, ?, 'player', 0, 'active', ?, ?, '[]')",
            (chosen, dummy_pw, pending['google_id'], pending['email'])
        )
        conn.commit()
        new_user = conn.execute("SELECT id, username, role, points FROM users WHERE username = ?", (chosen,)).fetchone()
        conn.close()
        
        session.pop('pending_google_user', None)
        session['user_id'] = new_user['id']
        session['username'] = new_user['username']
        session['role'] = new_user['role']
        session['points'] = new_user['points']
        session['authorized_levels'] = []
        
        return redirect(url_for('index'))
        
    return render_template('choose_username.html', email=pending['email'])

@app.route('/register', methods=['GET', 'POST'])
def register():
    # Only administrators can register players
    if session.get('role') != 'admin':
        flash('Player registration is managed by tournament administrators.')
        return redirect(url_for('login'))
    return redirect(url_for('admin'))

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'create_player':
            new_user = request.form.get('username', '').strip()
            new_pass = request.form.get('password', '').strip()
            pid = request.form.get('participant_id', '').strip() or None
            full_name = request.form.get('name', '').strip() or None
            email_val = request.form.get('email', '').strip() or None

            auth_levels = []
            if request.form.get('auth_level_2'):
                auth_levels.append(2)
            if request.form.get('auth_level_3'):
                auth_levels.append(3)

            if not new_user:
                flash("ERROR: Username is required.")
            else:
                assigned_pass = new_pass if new_pass and new_pass != 'ShadowDrop2026!' else f"!OAUTH_ONLY!_{secrets.token_hex(16)}"
                existing = conn.execute("SELECT id FROM users WHERE username = ? OR (participant_id IS NOT NULL AND participant_id = ?)", (new_user, pid)).fetchone()
                if existing:
                    flash(f"ERROR: A player with username '{new_user}' or ID '{pid}' already exists.")
                else:
                    auth_json = json.dumps(auth_levels)
                    conn.execute('''
                        INSERT INTO users (username, password, role, points, level2_points, level3_points, status, level2_status, level3_status, has_seen_intro, has_seen_l2_intro, has_seen_l3_intro, participant_id, authorized_levels, email, name)
                        VALUES (?, ?, 'player', 0, 0, 0, 'active', 'active', 'active', 0, 0, 0, ?, ?, ?, ?)
                    ''', (new_user, assigned_pass, pid, auth_json, email_val, full_name))
                    conn.commit()
                    level_names = []
                    if 2 in auth_levels: level_names.append("Level 2")
                    if 3 in auth_levels: level_names.append("Level 3")
                    auth_desc = ", ".join(level_names) if level_names else "None"
                    flash(f"SUCCESS: Player '{new_user}' created successfully (Authorized: {auth_desc}).")
        elif action == 'update':
            user_id = request.form.get('user_id')
            new_points = request.form.get('points')
            level_num = str(request.form.get('level') or request.form.get('round') or '2')
            if user_id and new_points is not None:
                if level_num in ('3', 'round3', 'level3'):
                    conn.execute("UPDATE users SET level3_points = ? WHERE id = ?", (new_points, user_id))
                else:
                    conn.execute("UPDATE users SET level2_points = ?, points = ? WHERE id = ?", (new_points, new_points, user_id))
                conn.commit()
                flash('Points updated successfully.')
        elif action == 'delete':
            user_id = request.form.get('user_id')
            if user_id:
                # Don't delete the admin!
                user = conn.execute("SELECT role FROM users WHERE id = ?", (user_id,)).fetchone()
                if user and user['role'] != 'admin':
                    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
                    conn.execute("DELETE FROM solved_challenges WHERE user_id = ?", (user_id,))
                    conn.commit()
                    flash('User deleted successfully.')
                else:
                    flash('Cannot delete admin account.')
        elif action in ('toggle_level3', 'toggle_round3'):
            current = conn.execute("SELECT value FROM global_settings WHERE key = 'level3_unlocked'").fetchone()
            cur_val = current['value'] if current else '0'
            new_val = '1' if cur_val == '0' else '0'
            conn.execute("INSERT OR REPLACE INTO global_settings (key, value) VALUES ('level3_unlocked', ?)", (new_val,))
            conn.execute("INSERT OR REPLACE INTO global_settings (key, value) VALUES ('round3_unlocked', ?)", (new_val,))
            conn.commit()
            if new_val == '0':
                subprocess.run("docker ps -q --filter 'name=jumanji_day1_level3_' --filter 'name=jumanji_r3_' | xargs -r docker rm -f", shell=True, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            flash(f"Day 1 Level 3 is now {'UNLOCKED' if new_val == '1' else 'LOCKED'}")
        elif action in ('toggle_level2', 'toggle_level1', 'toggle_round2'):
            current = conn.execute("SELECT value FROM global_settings WHERE key = 'level2_unlocked'").fetchone()
            cur_val = current['value'] if current else '0'
            new_val = '1' if cur_val == '0' else '0'
            conn.execute("INSERT OR REPLACE INTO global_settings (key, value) VALUES ('level2_unlocked', ?)", (new_val,))
            conn.execute("INSERT OR REPLACE INTO global_settings (key, value) VALUES ('level1_unlocked', ?)", (new_val,))
            conn.execute("INSERT OR REPLACE INTO global_settings (key, value) VALUES ('round2_unlocked', ?)", (new_val,))
            conn.commit()
            if new_val == '0':
                subprocess.run("docker ps -q --filter 'name=jumanji_day1_level2_' --filter 'name=jumanji_day1_level1_' --filter 'name=jumanji_r2_' | xargs -r docker rm -f", shell=True, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            flash(f"Day 1 Level 2 is now {'UNLOCKED' if new_val == '1' else 'LOCKED'}")
        elif action in ('toggle_day1', 'toggle_day2'):
            key = 'day1_visible' if action == 'toggle_day1' else 'day2_visible'
            current = conn.execute("SELECT value FROM global_settings WHERE key = ?", (key,)).fetchone()
            new_val = '1' if current['value'] == '0' else '0'
            conn.execute("UPDATE global_settings SET value = ? WHERE key = ?", (new_val, key))
            conn.commit()
            day_label = 'Day 1' if action == 'toggle_day1' else 'Day 2'
            flash(f"{day_label} is now {'VISIBLE' if new_val == '1' else 'HIDDEN'} on the player hub")
        elif action == 'toggle_status':
            user_id = request.form.get('user_id')
            level_num = str(request.form.get('level') or request.form.get('round') or '2')
            if user_id:
                if level_num in ('3', 'round3', 'level3'):
                    cur_stat = conn.execute("SELECT level3_status FROM users WHERE id = ?", (user_id,)).fetchone()
                    new_stat = 'active' if (cur_stat and cur_stat['level3_status'] == 'suspended') else 'suspended'
                    conn.execute("UPDATE users SET level3_status = ? WHERE id = ?", (new_stat, user_id))
                    conn.commit()
                    flash(f"Day 1 Level 3 status updated to {new_stat.upper()} for player #{user_id}.")
                else:
                    cur_stat = conn.execute("SELECT level2_status, status FROM users WHERE id = ?", (user_id,)).fetchone()
                    cur_val = (cur_stat['level2_status'] or cur_stat['status']) if cur_stat else 'active'
                    new_stat = 'active' if cur_val == 'suspended' else 'suspended'
                    conn.execute("UPDATE users SET level2_status = ?, status = ? WHERE id = ?", (new_stat, new_stat, user_id))
                    conn.commit()
                    flash(f"Day 1 Level 2 status updated to {new_stat.upper()} for player #{user_id}.")
        elif action == 'reset_timer':
            user_id = request.form.get('user_id')
            level_num = str(request.form.get('level') or request.form.get('round') or '2')
            if user_id:
                if level_num in ('3', 'round3', 'level3'):
                    conn.execute("UPDATE users SET level3_start_time = NULL, level3_status = 'active', has_seen_l3_intro = 0 WHERE id = ?", (user_id,))
                    conn.commit()
                    flash(f"Day 1 Level 3 timer reset for player #{user_id}. Ready for fresh session.")
                else:
                    conn.execute("UPDATE users SET level2_start_time = NULL, start_time = NULL, level2_status = 'active', status = 'active', has_seen_l2_intro = 0, has_seen_intro = 0 WHERE id = ?", (user_id,))
                    conn.commit()
                    flash(f"Day 1 Level 2 timer reset for player #{user_id}. Ready for fresh session.")
            
    users_l2 = conn.execute("SELECT * FROM users ORDER BY COALESCE(level2_points, points, 0) DESC").fetchall()
    users_l3 = conn.execute("SELECT * FROM users ORDER BY COALESCE(level3_points, 0) DESC").fetchall()
    l2_row = conn.execute("SELECT value FROM global_settings WHERE key = 'level2_unlocked'").fetchone()
    level2_unlocked = (l2_row['value'] == '1') if l2_row else True
    l3_row = conn.execute("SELECT value FROM global_settings WHERE key = 'level3_unlocked'").fetchone()
    level3_unlocked = (l3_row['value'] == '1') if l3_row else False
    day1_visible = conn.execute("SELECT value FROM global_settings WHERE key = 'day1_visible'").fetchone()['value'] == '1'
    day2_visible = conn.execute("SELECT value FROM global_settings WHERE key = 'day2_visible'").fetchone()['value'] == '1'
    conn.close()

    current_time = get_utc_now()
    stats = {
        'online': 0,
        'offline': 0,
        'completed': 0,
        'suspended': 0,
        'l2_completed': 0,
        'l2_suspended': 0,
        'l3_completed': 0,
        'l3_suspended': 0,
        'r3_completed': 0,
        'r3_suspended': 0
    }
    
    for u in users_l2:
        if u['role'] == 'admin': continue
        
        # Level 2 Stats (Avatars, 150 pts max)
        pts_l2 = u['level2_points'] or u['points'] or 0
        stat_l2 = u['level2_status'] or u['status'] or 'active'
        if pts_l2 >= 150:
            stats['completed'] += 1
            stats['l2_completed'] += 1
        if stat_l2 == 'suspended':
            stats['suspended'] += 1
            stats['l2_suspended'] += 1
        
        # Level 3 Stats (Mainframe, 200 pts max)
        pts_l3 = u['level3_points'] or 0
        stat_l3 = u['level3_status'] or 'active'
        if pts_l3 >= 200:
            stats['l3_completed'] += 1
            stats['r3_completed'] += 1
        if stat_l3 == 'suspended':
            stats['l3_suspended'] += 1
            stats['r3_suspended'] += 1
        
        if u['last_active']:
            last_active = datetime.fromisoformat(u['last_active'])
            if (current_time - last_active).total_seconds() < 30:
                stats['online'] += 1
            else:
                stats['offline'] += 1
        else:
            stats['offline'] += 1
            
    return render_template(
        'admin.html',
        users_l1=users_l2,
        users_l2=users_l2,
        users_l3=users_l3,
        users_r2=users_l2,
        users_r3=users_l3,
        stats=stats,
        level1_unlocked=level2_unlocked,
        level2_unlocked=level2_unlocked,
        level3_unlocked=level3_unlocked,
        round2_unlocked=level2_unlocked,
        round3_unlocked=level3_unlocked,
        day1_visible=day1_visible,
        day2_visible=day2_visible
    )

@app.route('/admin/sync-sdc-roster', methods=['POST'])
@app.route('/admin/sync-mongo-roster', methods=['POST'])
def sync_sdc_roster():
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'sync_from_mongodb.py')
    try:
        res = subprocess.run([sys.executable, script_path], capture_output=True, text=True, timeout=15)
        if res.returncode == 0:
            flash("Successfully synced roster directly from MongoDB Atlas!")
        else:
            flash(f"MongoDB roster sync failed: {res.stderr or res.stdout}")
    except Exception as e:
        flash(f"Roster sync execution error: {e}")
    return redirect(url_for('admin'))

@app.route('/admin/export-scores/level2')
@app.route('/admin/export-scores/level1')
@app.route('/admin/export-scores/round2')
def export_scores_l2():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    conn = get_db_connection()
    users = conn.execute("SELECT participant_id, username, COALESCE(level2_points, points, 0) as score FROM users WHERE role != 'admin' ORDER BY score DESC").fetchall()
    conn.close()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['participantId', 'score'])
    for u in users:
        pid = u['participant_id'] or u['username']
        writer.writerow([pid, u['score'] or 0])
        
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=sdc_day1_level2_cybersec_scores.csv'}
    )

@app.route('/admin/export-scores/level3')
@app.route('/admin/export-scores/round3')
def export_scores_l3():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    conn = get_db_connection()
    users = conn.execute("SELECT participant_id, username, COALESCE(level3_points, 0) as score FROM users WHERE role != 'admin' ORDER BY score DESC").fetchall()
    conn.close()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['participantId', 'score'])
    for u in users:
        pid = u['participant_id'] or u['username']
        writer.writerow([pid, u['score'] or 0])
        
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=sdc_day1_level3_cybersec_scores.csv'}
    )

@app.route('/admin/export-scores/day1-all')
@app.route('/admin/export-day1-shortlist')
def export_day1_shortlist():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    conn = get_db_connection()
    # Export full Day 1 score matrix for SDC Games global aggregation
    users = conn.execute('''
        SELECT 
            participant_id, 
            username, 
            COALESCE(name, '') as full_name,
            COALESCE(email, '') as email_address,
            COALESCE(level2_points, points, 0) as l2_pts,
            COALESCE(level3_points, 0) as l3_pts,
            (COALESCE(level2_points, points, 0) + COALESCE(level3_points, 0)) as total_day1_score,
            authorized_levels,
            start_time,
            last_active
        FROM users 
        WHERE role != 'admin' 
        ORDER BY total_day1_score DESC, id ASC
    ''').fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['rank', 'participantId', 'username', 'name', 'email', 'totalDay1CybersecScore', 'level2Score', 'level3Score', 'authorizedLevels', 'startTime', 'lastActive'])
    for idx, u in enumerate(users, start=1):
        pid = u['participant_id'] or u['username']
        writer.writerow([
            idx,
            pid,
            u['username'],
            u['full_name'],
            u['email_address'],
            u['total_day1_score'],
            u['l2_pts'],
            u['l3_pts'],
            u['authorized_levels'] or '[]',
            u['start_time'] or '',
            u['last_active'] or ''
        ])

    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=sdc_day1_cybersec_score_matrix.csv'}
    )

@app.route('/admin/export-gauntlet-finalists')
def export_gauntlet_finalists():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    conn = get_db_connection()
    # Top 4 teams from Gauntlet tournament (4 teams x 2 members = 8 finalists for Coding)
    teams = conn.execute('''
        SELECT 
            id, 
            team_name, 
            pod_id, 
            (phase1_score + duel_score + shrine_score + lagoon_score) as total_gauntlet_score,
            phase1_score,
            duel_score,
            shrine_score,
            lagoon_score
        FROM gauntlet_teams 
        ORDER BY total_gauntlet_score DESC, id ASC 
        LIMIT 4
    ''').fetchall()

    members = conn.execute('''
        SELECT m.team_id, m.user_id, m.role, u.username, u.participant_id, u.email, u.name
        FROM gauntlet_members m
        JOIN users u ON m.user_id = u.id
    ''').fetchall()
    conn.close()

    members_by_team = {}
    for m in members:
        members_by_team.setdefault(m['team_id'], []).append(m)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['teamRank', 'teamName', 'podId', 'totalGauntletScore', 'playerRole', 'participantId', 'username', 'fullName', 'email'])
    for idx, t in enumerate(teams, start=1):
        t_members = members_by_team.get(t['id'], [])
        if not t_members:
            writer.writerow([idx, t['team_name'], t['pod_id'], t['total_gauntlet_score'], 'team_representative', '', '', '', ''])
        else:
            for m in t_members:
                writer.writerow([
                    idx,
                    t['team_name'],
                    t['pod_id'],
                    t['total_gauntlet_score'],
                    m['role'],
                    m['participant_id'] or m['username'],
                    m['username'],
                    m['name'] or '',
                    m['email'] or ''
                ])

    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=sdc_gauntlet_top4_teams_8finalists.csv'}
    )

@app.route('/api/admin/user/<int:user_id>/flags', methods=['GET'])
def get_user_flags(user_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
        
    conn = get_db_connection()
    flags = conn.execute("SELECT challenge_id, solved_at FROM solved_challenges WHERE user_id = ? ORDER BY solved_at ASC", (user_id,)).fetchall()
    conn.close()
    
    flag_list = []
    for f in flags:
        flag_list.append({
            'challenge_id': f['challenge_id'],
            'solved_at': f['solved_at'] if f['solved_at'] else 'Unknown Time'
        })
        
    return jsonify({'status': 'success', 'flags': flag_list})

@app.route('/level2')
def level2():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    if session.get('role') == 'admin':
        return redirect(url_for('admin'))

    allowed, err_msg = check_level_access(session['user_id'], 2)
    if not allowed:
        flash(err_msg)
        return redirect(url_for('hub'))
        
    conn = get_db_connection()
    user = conn.execute("SELECT start_time, level2_start_time, has_seen_intro, has_seen_l2_intro, points, level2_points, status, level2_status FROM users WHERE id = ?", (session['user_id'],)).fetchone()
    pts = user['level2_points'] or user['points'] or 0

    start_val = user['level2_start_time'] or user['start_time']
    if not start_val:
        start_time_iso = get_utc_now().isoformat()
        conn.execute("UPDATE users SET level2_start_time = ?, start_time = ? WHERE id = ?", (start_time_iso, start_time_iso, session['user_id']))
        conn.commit()
        user = conn.execute("SELECT start_time, level2_start_time, has_seen_intro, has_seen_l2_intro, points, level2_points, status, level2_status FROM users WHERE id = ?", (session['user_id'],)).fetchone()
        start_val = start_time_iso
        
    conn.close()
    
    start_dt = datetime.fromisoformat(start_val)
    time_elapsed = (get_utc_now() - start_dt).total_seconds()
    remaining_seconds = max(0, 3600 - time_elapsed)
    seen_intro = 1 if (user['has_seen_l2_intro'] or user['has_seen_intro']) else 0
            
    return render_template('level2.html', remaining_seconds=int(remaining_seconds), has_seen_intro=seen_intro, has_seen_l2_intro=seen_intro, initial_points=pts)

@app.route('/level1')
@app.route('/dashboard')
@app.route('/round2')
def redirect_to_level2():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('level2'))

@app.route('/api/start_level2', methods=['POST'])
@app.route('/api/set_intro_watched', methods=['POST'])
def start_level2():
    if 'user_id' in session:
        conn = get_db_connection()
        user = conn.execute("SELECT level2_start_time, start_time FROM users WHERE id = ?", (session['user_id'],)).fetchone()
        start_val = user['level2_start_time'] or user['start_time'] if user else None
        if not start_val:
            now_iso = get_utc_now().isoformat()
            conn.execute("UPDATE users SET level2_start_time = ?, start_time = ?, has_seen_l2_intro = 1, has_seen_intro = 1 WHERE id = ?", (now_iso, now_iso, session['user_id']))
        else:
            conn.execute("UPDATE users SET has_seen_l2_intro = 1, has_seen_intro = 1 WHERE id = ?", (session['user_id'],))
        conn.commit()
        conn.close()
    return jsonify({'status': 'success'})

@app.route('/reset_level2_intro', methods=['POST'])
@app.route('/reset_level1_intro', methods=['POST'])
@app.route('/reset_intro', methods=['POST'])
def reset_level2_intro():
    if 'user_id' in session:
        conn = get_db_connection()
        conn.execute("UPDATE users SET has_seen_l2_intro = 0, has_seen_intro = 0 WHERE id = ?", (session['user_id'],))
        conn.commit()
        conn.close()
    return jsonify({'status': 'success'})

@app.route('/level3')
def level3():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    if session.get('role') == 'admin':
        return redirect(url_for('admin'))

    allowed, err_msg = check_level_access(session['user_id'], 3)
    if not allowed:
        flash(err_msg)
        return redirect(url_for('hub'))
        
    conn = get_db_connection()
    user = conn.execute("SELECT level3_start_time, level3_status, level3_points, has_seen_l3_intro FROM users WHERE id = ?", (session['user_id'],)).fetchone()
    pts = user['level3_points'] or 0

    if not user['level3_start_time']:
        remaining_seconds = 3600
    else:
        start_time = datetime.fromisoformat(user['level3_start_time'])
        time_elapsed = (get_utc_now() - start_time).total_seconds()
        remaining_seconds = max(0, 3600 - time_elapsed)
    
    solved_user = conn.execute("SELECT 1 FROM solved_challenges WHERE user_id = ? AND challenge_id IN ('level3_user', 'level2_user', 'round3_user')", (session['user_id'],)).fetchone() is not None
    solved_root = conn.execute("SELECT 1 FROM solved_challenges WHERE user_id = ? AND challenge_id IN ('level3_root', 'level2_root', 'round3_root')", (session['user_id'],)).fetchone() is not None
    
    conn.close()
    seen_intro = 1 if user['has_seen_l3_intro'] else 0
    
    return render_template(
        'level3.html',
        points=pts,
        solved_user=solved_user,
        solved_root=solved_root,
        remaining_seconds=int(remaining_seconds),
        has_seen_l3_intro=seen_intro,
        has_seen_l2_intro=seen_intro,
        round3_points=pts,
        has_seen_r3_intro=seen_intro
    )

@app.route('/round3')
def round3():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('level3'))

@app.route('/api/start_level3', methods=['POST'])
@app.route('/api/start_r3', methods=['POST'])
def start_level3():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    conn = get_db_connection()
    user = conn.execute("SELECT level3_start_time FROM users WHERE id = ?", (session['user_id'],)).fetchone()
    if not user['level3_start_time']:
        l3_start_time = get_utc_now().isoformat()
        conn.execute("UPDATE users SET level3_start_time = ?, has_seen_l3_intro = 1 WHERE id = ?", (l3_start_time, session['user_id']))
        conn.commit()
    else:
        conn.execute("UPDATE users SET has_seen_l3_intro = 1 WHERE id = ?", (session['user_id'],))
        conn.commit()
    conn.close()
    return jsonify({'status': 'success'})

@app.route('/reset_level3_intro', methods=['POST'])
@app.route('/reset_r3_intro', methods=['POST'])
def reset_level3_intro():
    if 'user_id' in session:
        conn = get_db_connection()
        conn.execute("UPDATE users SET has_seen_l3_intro = 0 WHERE id = ?", (session['user_id'],))
        conn.commit()
        conn.close()
    return jsonify({'status': 'success'})

SCORE_MATRIX = {
    'bravestone': 20,
    'oberon': 25,
    'finbar': 25,
    'ruby': 30,
    'seaplane': 50,
    'level3_user': 80,
    'level3_root': 120,
    'level2_user': 80,
    'level2_root': 120,
    'round3_user': 80,
    'round3_root': 120
}

import hashlib

def generate_dynamic_flag(user_id, avatar_id):
    secret = CTF_MASTER_SECRET
    
    if avatar_id in ('level3_user', 'level2_user', 'round3_user'):
        hash_input = f"{user_id}:user:{secret}"
        hex_digest = hashlib.md5(hash_input.encode()).hexdigest()[:8]
        return f"OVERRIDE-USER-{hex_digest}"
    
    if avatar_id in ('level3_root', 'level2_root', 'round3_root'):
        hash_input = f"{user_id}:root:{secret}"
        hex_digest = hashlib.md5(hash_input.encode()).hexdigest()[:8]
        return f"OVERRIDE-ROOT-{hex_digest}"
        
    hash_input = f"{user_id}:{avatar_id}:{secret}"
    hex_digest = hashlib.md5(hash_input.encode()).hexdigest()[:8]
    return f"JUMANJI{{{avatar_id}_{hex_digest}}}"

@app.route('/api/whois', methods=['POST'])
def proxy_whois():
    data = request.json
    target = data.get('target', '')
    if not target:
        return jsonify({'response': 'Usage: whois [target]'})
    
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2.0)
        s.connect(('127.0.0.1', 4343))
        s.sendall(target.encode('utf-8') + b'\n')
        response = s.recv(4096).decode('utf-8', errors='ignore')
        s.close()
        return jsonify({'response': response})
    except Exception as e:
        return jsonify({'response': f"Error: Could not connect to WHOIS daemon on port 4343."})

INTERNAL_TOKENS = {}

@app.route('/api/score', methods=['POST'])
def submit_score():
    data = request.get_json() or {}
    token = data.get('token')
    
    if token and token in INTERNAL_TOKENS:
        user_id = INTERNAL_TOKENS[token]['user_id']
        sid = INTERNAL_TOKENS[token]['sid']
    elif 'user_id' in session:
        user_id = session['user_id']
        sid = None
    else:
        return jsonify({'error': 'Unauthorized'}), 401

    rate_key = token or f"user_{user_id}"
    if is_submission_rate_limited(rate_key, max_attempts=30, window_sec=60):
        return jsonify({'status': 'error', 'error': 'Submission rate limit exceeded. Please wait a moment.'}), 429
        
    data = request.get_json()
    avatar_id = data.get('avatar_id')
    submitted_flag = data.get('flag', '').strip()
    
    if avatar_id in ('level3', 'level2', 'round3', 'level2_mainframe'):
        expected_user = generate_dynamic_flag(user_id, 'level3_user')
        expected_root = generate_dynamic_flag(user_id, 'level3_root')
        if submitted_flag == expected_user:
            avatar_id = 'level3_user'
        elif submitted_flag == expected_root:
            avatar_id = 'level3_root'
        else:
            if not (submitted_flag.startswith('JUMANJI{') and '_' in submitted_flag):
                return jsonify({'status': 'invalid_flag', 'error': 'INCORRECT OVERRIDE CODE!'}), 400

    if avatar_id not in SCORE_MATRIX:
        if submitted_flag.startswith('JUMANJI{') and '_' in submitted_flag:
            inferred = submitted_flag.split('{')[1].split('_')[0]
            if inferred in SCORE_MATRIX:
                avatar_id = inferred
        elif submitted_flag.startswith('OVERRIDE-USER-'):
            avatar_id = 'level3_user'
        elif submitted_flag.startswith('OVERRIDE-ROOT-'):
            avatar_id = 'level3_root'

    if avatar_id not in SCORE_MATRIX:
        return jsonify({'error': 'Invalid checkpoint'}), 400
        
    is_level3 = avatar_id in ['level3_user', 'level3_root', 'level2_user', 'level2_root', 'round3_user', 'round3_root']
    target_lvl = 3 if is_level3 else 2
    allowed, err_msg = check_level_access(user_id, target_lvl, is_submission=True)
    if not allowed and session.get('role') != 'admin':
        return jsonify({'error': f'Access Denied: {err_msg}'}), 403
        
    expected_flag = generate_dynamic_flag(user_id, avatar_id)
    if submitted_flag != expected_flag:
        return jsonify({'status': 'invalid_flag', 'error': 'INCORRECT FLAG SUPPLIED!'}), 400
        
    points_to_add = SCORE_MATRIX[avatar_id]
    
    conn = get_db_connection()
    alias_ids = [avatar_id]
    if avatar_id in ('level3_user', 'level2_user', 'round3_user'):
        alias_ids = ['level3_user', 'level2_user', 'round3_user']
    elif avatar_id in ('level3_root', 'level2_root', 'round3_root'):
        alias_ids = ['level3_root', 'level2_root', 'round3_root']

    placeholders = ', '.join(['?'] * len(alias_ids))
    solved = conn.execute(f"SELECT 1 FROM solved_challenges WHERE user_id = ? AND challenge_id IN ({placeholders})", [user_id] + alias_ids).fetchone()
    
    if solved:
        conn.close()
        return jsonify({'status': 'already_solved', 'message': 'Checkpoint already completed.'})
        
    # Award points
    solved_time = get_utc_now().isoformat()
    conn.execute("INSERT INTO solved_challenges (user_id, challenge_id, solved_at) VALUES (?, ?, ?)", (user_id, avatar_id, solved_time))
    
    is_level3 = avatar_id in ['level3_user', 'level3_root', 'level2_user', 'level2_root', 'round3_user', 'round3_root']
    
    if is_level3:
        conn.execute("UPDATE users SET level3_points = COALESCE(level3_points, 0) + ? WHERE id = ?", (points_to_add, user_id))
        conn.commit()
        new_points = conn.execute("SELECT level3_points FROM users WHERE id = ?", (user_id,)).fetchone()['level3_points']
        session['level3_points'] = new_points
        session['round3_points'] = new_points
        sdc_round_id = 'day-1-l3'
    else:
        conn.execute("UPDATE users SET level2_points = COALESCE(level2_points, 0) + ?, points = COALESCE(points, 0) + ? WHERE id = ?", (points_to_add, points_to_add, user_id))
        conn.commit()
        new_points = conn.execute("SELECT level2_points FROM users WHERE id = ?", (user_id,)).fetchone()['level2_points']
        session['level2_points'] = new_points
        session['points'] = new_points
        sdc_round_id = 'day-1-l2'

    if sid:
        if is_level3:
            l3_user = conn.execute("SELECT 1 FROM solved_challenges WHERE user_id = ? AND challenge_id IN ('level3_user', 'level2_user', 'round3_user')", (user_id,)).fetchone()
            l3_root = conn.execute("SELECT 1 FROM solved_challenges WHERE user_id = ? AND challenge_id IN ('level3_root', 'level2_root', 'round3_root')", (user_id,)).fetchone()
            if l3_user and l3_root:
                conn.execute("UPDATE users SET level3_status = 'suspended' WHERE id = ?", (user_id,))
                conn.commit()
                socketio.emit('game-win-level3', {}, room=sid)
                socketio.emit('game-win-level2', {}, room=sid)
                socketio.emit('game-win-r3', {}, room=sid)
            else:
                socketio.emit('score-update', {'new_points': new_points}, room=sid)
        else:
            socketio.emit('score-update', {'new_points': new_points}, room=sid)
            if new_points >= 150:
                conn.execute("UPDATE users SET level2_status = 'suspended', status = 'suspended' WHERE id = ?", (user_id,))
                conn.commit()
                socketio.emit('game-win', {}, room=sid)
            
        socketio.emit('flag-solved', {'avatar_id': avatar_id}, room=sid)
            
    conn.close()
    return jsonify({'status': 'success', 'points_awarded': points_to_add, 'total_points': new_points})

@app.route('/day2/level2')
def day2_level2():
    return gauntlet()

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- JUMANJI GAUNTLET MASTER TOURNAMENT ROUTES ---

@app.route('/gauntlet')
def gauntlet():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    allowed, err_msg = check_level_access(session['user_id'], 'day2')
    if not allowed and session.get('role') != 'admin':
        flash(err_msg)
        return redirect(url_for('hub'))
    conn = get_db_connection()
    team = gauntlet_engine.get_team_for_user(conn, session['user_id'])
    if not team:
        team = gauntlet_engine.auto_assign_user_to_team(conn, session['user_id'])
    if not team:
        conn.close()
        flash("Day 2 Level 2 (The Jumanji Gauntlet) is strictly limited to 32 players (16 squads of 2 players). The tournament roster is currently full.")
        return redirect(url_for('hub'))
        
    current_phase = conn.execute("SELECT value FROM gauntlet_settings WHERE key = 'gauntlet_phase'").fetchone()['value']
    active_relics = gauntlet_engine.PHASE_RELICS.get(current_phase, gauntlet_engine.PHASE_RELICS['phase1_pods'])
    
    solved_rows = conn.execute("SELECT relic_id FROM gauntlet_solved_relics WHERE team_id = ?", (team['id'],)).fetchall()
    solved_ids = [r['relic_id'] for r in solved_rows]
    
    curse_inventory = conn.execute("SELECT * FROM gauntlet_curse_inventory WHERE team_id = ? AND is_used = 0", (team['id'],)).fetchall()
    active_curses = gauntlet_engine.get_active_curses_for_team(conn, team['id'])
    
    active_match_id = 1
    if current_phase == 'phase2_duels':
        m_row = conn.execute("SELECT id FROM gauntlet_matches WHERE (team_a_id = ? OR team_b_id = ?) AND status = 'active' LIMIT 1", (team['id'], team['id'])).fetchone()
        if m_row:
            active_match_id = m_row['id']

    cart_keys = {}
    for r_id in active_relics.keys():
        cart_keys[r_id] = gauntlet_engine.generate_split_keys(team['id'], active_match_id, r_id)['cart_part']
        
    conn.close()
    return render_template(
        'gauntlet_hud.html',
        team=team,
        current_phase=current_phase,
        active_relics=active_relics,
        solved_ids=solved_ids,
        curse_inventory=curse_inventory,
        active_curses=active_curses,
        cart_keys=cart_keys
    )

@app.route('/gauntlet/bracket')
def gauntlet_bracket():
    conn = get_db_connection()
    current_phase = conn.execute("SELECT value FROM gauntlet_settings WHERE key = 'gauntlet_phase'").fetchone()['value']
    teams = conn.execute("SELECT * FROM gauntlet_teams ORDER BY (phase1_score + duel_score + shrine_score + lagoon_score) DESC, id ASC").fetchall()
    
    matches_raw = conn.execute('''
        SELECT m.*, ta.team_name as team_a_name, tb.team_name as team_b_name
        FROM gauntlet_matches m
        JOIN gauntlet_teams ta ON m.team_a_id = ta.id
        JOIN gauntlet_teams tb ON m.team_b_id = tb.id
        WHERE m.phase = ?
    ''', (current_phase if current_phase in ['phase2_duels', 'phase4_final'] else 'phase2_duels',)).fetchall()
    
    shrine_ruler_id = conn.execute("SELECT value FROM gauntlet_settings WHERE key = 'shrine_active_team'").fetchone()['value']
    shrine_ruler = None
    if shrine_ruler_id and shrine_ruler_id.isdigit():
        r = conn.execute("SELECT team_name FROM gauntlet_teams WHERE id = ?", (int(shrine_ruler_id),)).fetchone()
        if r:
            shrine_ruler = r['team_name']
    shrine_ticks_count = conn.execute("SELECT COUNT(*) as cnt FROM gauntlet_shrine_ticks").fetchone()['cnt']
    lagoon_teams = conn.execute("SELECT * FROM gauntlet_teams WHERE phase = 'lagoon' ORDER BY lagoon_score DESC").fetchall()
    conn.close()
    
    return render_template(
        'gauntlet_bracket.html',
        current_phase=current_phase,
        teams=teams,
        matches=matches_raw,
        active_shrine_ruler=shrine_ruler,
        shrine_ticks_count=shrine_ticks_count,
        lagoon_teams=lagoon_teams
    )

@app.route('/gauntlet/relic/solve', methods=['POST'])
def gauntlet_relic_solve():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': 'error', 'error': 'Authentication required'}), 401

    if is_submission_rate_limited(f"gauntlet_{user_id}", max_attempts=30, window_sec=60):
        return jsonify({'status': 'error', 'error': 'Submission rate limit exceeded. Please wait a moment.'}), 429

    data = request.get_json() or {}
    flag = data.get('flag', '').strip()
    part2 = data.get('part2', '').strip()
    team_id = data.get('team_id')
    
    conn = get_db_connection()
    t = gauntlet_engine.get_team_for_user(conn, user_id)
    if session.get('role') != 'admin':
        if not t:
            conn.close()
            return jsonify({'status': 'error', 'error': 'User not assigned to any team'}), 403
        if team_id and int(team_id) != t['id']:
            conn.close()
            return jsonify({'status': 'error', 'error': 'Unauthorized team operation'}), 403
        team_id = t['id']
    else:
        if not team_id and t:
            team_id = t['id']
            
    if not team_id:
        conn.close()
        return jsonify({'status': 'error', 'error': 'Missing team identifier'}), 400
        
    res = gauntlet_engine.verify_relic_submission(conn, team_id, flag, part2, user_id)
    conn.close()
    
    if res.get('status') == 'success':
        socketio.emit('gauntlet-sync', {'team_id': team_id, 'relic_id': res.get('relic_id'), 'points': res.get('points_awarded')})
        
        pass
        
    return jsonify(res)

@app.route('/gauntlet/curse/cast', methods=['POST'])
def gauntlet_curse_cast():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': 'error', 'error': 'Authentication required'}), 401

    data = request.get_json() or {}
    team_id = data.get('team_id')
    curse_type = data.get('curse_type')
    target_id = data.get('target_team_id')
    
    conn = get_db_connection()
    t = gauntlet_engine.get_team_for_user(conn, user_id)
    if session.get('role') != 'admin':
        if not t:
            conn.close()
            return jsonify({'status': 'error', 'error': 'User not assigned to any team'}), 403
        if team_id and int(team_id) != t['id']:
            conn.close()
            return jsonify({'status': 'error', 'error': 'Unauthorized team operation'}), 403
        team_id = t['id']
    else:
        if not team_id and t:
            team_id = t['id']
            
    if not team_id or not curse_type:
        conn.close()
        return jsonify({'status': 'error', 'error': 'Missing team_id or curse_type'}), 400
        
    res = gauntlet_engine.cast_curse(conn, team_id, curse_type, target_id)
    conn.close()
    
    if res.get('status') == 'success':
        socketio.emit('curse-alert', res)
        
    return jsonify(res)

@app.route('/admin/gauntlet')
def gauntlet_admin():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    current_phase = conn.execute("SELECT value FROM gauntlet_settings WHERE key = 'gauntlet_phase'").fetchone()['value']
    teams = conn.execute("SELECT * FROM gauntlet_teams ORDER BY id ASC").fetchall()
    
    active_curses_raw = conn.execute('''
        SELECT c.*, ta.team_name as from_name, tb.team_name as target_name
        FROM gauntlet_curses c
        JOIN gauntlet_teams ta ON c.from_team_id = ta.id
        JOIN gauntlet_teams tb ON c.to_team_id = tb.id
        WHERE c.is_active = 1
        ORDER BY c.id DESC
    ''').fetchall()
    
    shrine_active = conn.execute("SELECT value FROM gauntlet_settings WHERE key = 'shrine_active_team'").fetchone()['value']
    top_4_teams = gauntlet_engine.get_top_4_teams(conn)
    assigned_count = conn.execute("SELECT COUNT(*) as cnt FROM gauntlet_members").fetchone()['cnt']
    conn.close()
    
    return render_template(
        'gauntlet_admin.html',
        current_phase=current_phase,
        teams=teams,
        active_curses=active_curses_raw,
        active_shrine_team_id=shrine_active,
        top_4_teams=top_4_teams,
        assigned_count=assigned_count
    )

@app.route('/admin/gauntlet/action', methods=['POST'])
def gauntlet_admin_action():
    if session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
        
    action = request.form.get('action')
    conn = get_db_connection()
    
    if action == 'set_phase':
        target = request.form.get('target_phase')
        gauntlet_engine.advance_tournament_phase(conn, target)
        flash(f"Tournament phase updated to: {target.upper()}")
        socketio.emit('gauntlet-sync', {'phase': target})
    elif action == 'reset_gauntlet':
        conn.execute("UPDATE gauntlet_teams SET phase = 'phase1_pods', phase1_score = 0, duel_score = 0, shrine_score = 0, lagoon_score = 0")
        conn.execute("DELETE FROM gauntlet_matches")
        conn.execute("DELETE FROM gauntlet_curses")
        conn.execute("DELETE FROM gauntlet_curse_inventory")
        conn.execute("DELETE FROM gauntlet_shrine_ticks")
        conn.execute("DELETE FROM gauntlet_solved_relics")
        conn.execute("UPDATE gauntlet_settings SET value = 'phase1_pods' WHERE key = 'gauntlet_phase'")
        conn.execute("UPDATE gauntlet_settings SET value = '' WHERE key = 'shrine_active_team'")
        conn.commit()
        flash("All tournament scores, brackets, and curses have been reset.")
        socketio.emit('gauntlet-sync', {'phase': 'phase1_pods', 'reset': True})
    elif action == 'seed_teams':
        gauntlet_engine.seed_default_teams(conn)
        flash("Tournament roster re-seeded with 16 squads.")
    elif action == 'set_shrine_ruler':
        t_id = request.form.get('team_id')
        gauntlet_engine.record_shrine_claim(conn, t_id)
        flash("Throne ruler successfully reassigned.")
        socketio.emit('shrine-pulse', {'team_id': t_id})
    elif action == 'dismiss_curse':
        c_id = request.form.get('curse_id')
        conn.execute("UPDATE gauntlet_curses SET is_active = 0 WHERE id = ?", (c_id,))
        conn.commit()
        flash(f"Curse #{c_id} dismissed.")
        
    conn.close()
    return redirect(url_for('gauntlet_admin'))

def process_gauntlet_shrine_ticks():
    while True:
        try:
            conn = get_db_connection()
            phase = conn.execute("SELECT value FROM gauntlet_settings WHERE key = 'gauntlet_phase'").fetchone()['value']
            if phase == 'phase3_shrine':
                tick_res = gauntlet_engine.tick_shrine(conn)
                if tick_res:
                    socketio.emit('shrine-pulse', tick_res)
            conn.close()
        except Exception:
            pass
        socketio.sleep(20)

# --- Web Shell PTY Logic ---

clients = {}

@socketio.on('start-pty')
def start_pty(data):
    sid = request.sid
    avatar_id = data.get('avatar_id', 'bravestone')
    
    session_id = session.get('user_id')
    if not session_id:
        socketio.emit('pty-output', {'output': '\r\n\x1b[31;1m[ERROR] Authentication required. Please log in.\x1b[0m\r\n'}, room=sid)
        return

    # Standardize container and environment mapping by Level
    is_gauntlet = (avatar_id in ['gauntlet', 'day2_level2', 'day2'])
    is_level3 = (avatar_id in ['level3', 'round3'])

    target_lvl = 3 if is_level3 else ('day2' if is_gauntlet else 2)
    allowed, err_msg = check_level_access(session_id, target_lvl)
    if not allowed and session.get('role') != 'admin':
        socketio.emit('pty-output', {'output': f'\r\n\x1b[31;1m[SECURITY BLOCK] {err_msg}\x1b[0m\r\n'}, room=sid)
        return

    # If a previous PTY session exists for this socket, terminate and clean it up first
    if sid in clients:
        handle_stop_pty()
        
    master_fd, slave_fd = pty.openpty()
    raw_username = session.get('username', 'player')
    username = re.sub(r'[^a-zA-Z0-9_\-]', '', raw_username) or 'player'
    
    docker_mounts = []
    docker_extra_env = []
    
    if is_gauntlet:
        conn = get_db_connection()
        team = gauntlet_engine.get_team_for_user(conn, session_id)
        if not team:
            team = gauntlet_engine.auto_assign_user_to_team(conn, session_id)
        if not team:
            conn.close()
            socketio.emit('pty-output', {'output': '\r\n\x1b[31;1m[-] Access Denied: The Gauntlet tournament roster is strictly limited to 32 players (16 squads of 2 players). Roster is currently full.\x1b[0m\r\n'}, room=sid)
            return
        current_ph = conn.execute("SELECT value FROM gauntlet_settings WHERE key = 'gauntlet_phase'").fetchone()['value']
        conn.close()
        
        t_id = team['id']
        t_name = team['team_name']
        t_role = team.get('role', 'navigator')
        clean_tname = re.sub(r'[^a-zA-Z0-9_\-]', '', t_name.lower().replace(' ', '-')) or 'team'
        
        container_name = f"jumanji_day2_level2_{session_id}_{sid}"
        image_name = "jumanji-gauntlet:latest"
        docker_mounts = []
        docker_extra_env = [
            "-e", f"TEAM_ID={t_id}",
            "-e", f"TEAM_NAME={t_name}",
            "-e", f"TEAM_ROLE={t_role}",
            "-e", f"PHASE={current_ph}"
        ]
        init_cmd = f"sudo -E /usr/local/bin/setup_gauntlet.sh && echo -e \"PS1='{username}@{clean_tname}-day2-level2:\\\\w\\\\$ '\\nenable -n complete\" > ~/.bashrc && exec bash"
        working_dir = "/gauntlet"
    elif is_level3:
        container_name = f"jumanji_day1_level3_{session_id}_{sid}"
        image_name = "jumanji-level3:latest"
        working_dir = "/level3"
        init_cmd = f"(sudo -E /usr/local/bin/setup_level3.sh 2>/dev/null || sudo -E /usr/local/bin/setup_level2.sh) && echo -e \"PS1='{username}@sdc-day1-level3:\\\\w\\\\$ '\\nenable -n complete\\nenable -n deploy_override\" > ~/.bashrc && exec bash"
    else:
        # Day 1 Level 2 (Avatar Reconnaissance)
        container_name = f"jumanji_day1_level2_{session_id}_{sid}"
        image_name = "jumanji-level2:latest"
        working_dir = f"/{avatar_id}" if avatar_id in ['bravestone', 'oberon', 'finbar', 'ruby', 'seaplane'] else "/bravestone"
        init_cmd = f"(sudo -E /usr/local/bin/setup_level2.sh 2>/dev/null || sudo -E /usr/local/bin/setup_level1.sh) && echo -e \"PS1='{username}@sdc-day1-level2:\\\\w\\\\$ '\\nenable -n complete\" > ~/.bashrc && exec bash"
    
    # Prune any previous container for this user/sid
    subprocess.run([
        "docker", "rm", "-f",
        f"jumanji_day1_level1_{session_id}_{sid}",
        f"jumanji_day1_level2_{session_id}_{sid}",
        f"jumanji_day1_level3_{session_id}_{sid}",
        f"jumanji_day2_level2_{session_id}_{sid}",
        f"jumanji_r2_{session_id}_{sid}",
        f"jumanji_r3_{session_id}_{sid}",
        f"jumanji_gauntlet_{session_id}_{sid}",
        f"jumanji_session_{session_id}_{sid}"
    ], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    import secrets
    token = secrets.token_hex(16)
    INTERNAL_TOKENS[token] = {
        'user_id': session_id,
        'sid': sid
    }
    
    docker_cmd = [
        "docker", "run", "-it", "--rm", "--name", container_name,
        "--memory=512m", "--cpus=0.75", "--pids-limit=100",
        "-u", "recon_user"
    ] + docker_mounts + docker_extra_env + [
        "-e", f"CTF_TOKEN={token}",
        "-e", f"PLAYER_ID={session_id}",
        "-e", f"PLAYER_USERNAME={username}",
        "-e", "TERM=xterm-256color",
        "--add-host=host.docker.internal:host-gateway",
        "-w", working_dir,
        image_name, "bash", "-c", init_cmd
    ]
    
    p = subprocess.Popen(
        docker_cmd,
        preexec_fn=os.setsid,
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd
    )
    try:
        os.close(slave_fd)
    except OSError:
        pass
    
    clients[sid] = {
        'fd': master_fd,
        'process': p,
        'container_name': container_name
    }
    
    socketio.start_background_task(read_and_forward_pty, master_fd, sid)

def read_and_forward_pty(fd, sid):
    max_read_bytes = 1024 * 20
    while True:
        socketio.sleep(0.01)
        try:
            r, _, _ = select.select([fd], [], [], 0.0)
        except (OSError, ValueError):
            break
        if fd in r:
            try:
                output_bytes = os.read(fd, max_read_bytes)
                if output_bytes:
                    socketio.emit('pty-output', {'output': output_bytes.decode('utf-8', errors='replace')}, room=sid)
                else:
                    break
            except OSError:
                break
    # Clean up when PTY session ends
    if sid in clients and clients[sid].get('fd') == fd:
        try:
            os.close(fd)
        except OSError:
            pass
        container_name = clients[sid].get('container_name')
        if container_name:
            subprocess.run(["docker", "rm", "-f", container_name], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        clients.pop(sid, None)

@socketio.on('pty-input')
def pty_input(data):
    sid = request.sid
    # Check if this user's team is under Quicksand curse
    if 'user_id' in session:
        try:
            conn = get_db_connection()
            team = gauntlet_engine.get_team_for_user(conn, session['user_id'])
            if team:
                active_curses = gauntlet_engine.get_active_curses_for_team(conn, team['id'])
                for c in active_curses:
                    if c['curse_type'] == 'quicksand':
                        conn.close()
                        return  # Ignore input during quicksand freeze
            conn.close()
        except Exception:
            pass

    if sid in clients:
        fd = clients[sid]['fd']
        try:
            os.write(fd, data['input'].encode('utf-8'))
        except OSError:
            pass

@socketio.on('resize')
@socketio.on('pty-resize')
def handle_pty_resize(data):
    sid = request.sid
    if sid in clients and 'fd' in clients[sid]:
        try:
            cols = int(data.get('cols', 80))
            rows = int(data.get('rows', 24))
            fcntl.ioctl(clients[sid]['fd'], termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
        except Exception:
            pass

@socketio.on('stop-pty')
def handle_stop_pty():
    sid = request.sid
    if sid in clients:
        p = clients[sid].get('process')
        fd = clients[sid].get('fd')
        container_name = clients[sid].get('container_name')
        try:
            if p:
                p.terminate()
            if fd:
                os.close(fd)
        except Exception:
            pass
        
        session_id = session.get('user_id', 'anon')
        if container_name:
            subprocess.run(["docker", "rm", "-f", container_name], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.run([
                "docker", "rm", "-f",
                f"jumanji_day1_level1_{session_id}_{sid}",
                f"jumanji_day1_level2_{session_id}_{sid}",
                f"jumanji_day1_level3_{session_id}_{sid}",
                f"jumanji_day2_level2_{session_id}_{sid}",
                f"jumanji_r2_{session_id}_{sid}",
                f"jumanji_r3_{session_id}_{sid}",
                f"jumanji_gauntlet_{session_id}_{sid}",
                f"jumanji_session_{session_id}_{sid}"
            ], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        clients.pop(sid, None)

@socketio.on('disconnect')
def disconnect():
    handle_stop_pty()

if __name__ == '__main__':
    try:
        init_db()
        socketio.start_background_task(process_gauntlet_shrine_ticks)
    except Exception as e:
        print("DB Init failed:", e)
    socketio.run(app, host='0.0.0.0', port=8080, debug=False)
