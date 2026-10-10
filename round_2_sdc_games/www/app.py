from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
import os
import pty
import subprocess
import select
import urllib.parse
import requests
import secrets
import re
from flask_socketio import SocketIO
from datetime import datetime, timedelta, timezone

def get_utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
socketio = SocketIO(app, cors_allowed_origins="*")
app.secret_key = 'e5b9f7c41a238d6b9f47a192c34d8e5f'

# Try loading .env if present
_env_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(_env_path):
    try:
        with open(_env_path) as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith('#') and '=' in _line:
                    _k, _v = _line.split('=', 1)
                    os.environ.setdefault(_k.strip(), _v.strip())
    except Exception:
        pass

# Google OAuth Configuration
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', 'YOUR_GOOGLE_CLIENT_ID.apps.googleusercontent.com')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', 'YOUR_GOOGLE_CLIENT_SECRET')
GOOGLE_REDIRECT_URI = os.environ.get('GOOGLE_REDIRECT_URI', 'http://172.20.183.90.nip.io:8080/auth/callback')

DB_PATH = 'jumanji_auth.db'

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    # Adding points column and recreate if needed
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            points INTEGER DEFAULT 0,
            start_time DATETIME,
            status TEXT DEFAULT 'active',
            has_seen_intro INTEGER DEFAULT 0
        )
    ''')
    
    conn.execute('''
        CREATE TABLE IF NOT EXISTS solved_challenges (
            user_id INTEGER,
            challenge_id TEXT,
            PRIMARY KEY (user_id, challenge_id)
        )
    ''')
    
    # Check if new columns exist (in case table already existed without them)
    cursor = conn.execute("PRAGMA table_info(users)")
    columns = [col['name'] for col in cursor.fetchall()]
    if 'points' not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN points INTEGER DEFAULT 0")
    if 'start_time' not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN start_time DATETIME")
    if 'status' not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN status TEXT DEFAULT 'active'")
    if 'has_seen_intro' not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN has_seen_intro INTEGER DEFAULT 0")
    if 'last_active' not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN last_active DATETIME")
    if 'google_id' not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN google_id TEXT")
    if 'email' not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN email TEXT")

    # Insert default admin user if not exists
    user = conn.execute("SELECT * FROM users WHERE username = 'admin'").fetchone()
    if not user:
        conn.execute("INSERT INTO users (username, password, role, points, status, has_seen_intro) VALUES ('admin', 'Admin_ShadowDrop!2026', 'admin', 0, 'active', 1)")
    else:
        # Enforce new secure admin password even if already exists
        conn.execute("UPDATE users SET password = 'Admin_ShadowDrop!2026' WHERE username = 'admin'")
    # Round 3 & 2 settings
    conn.execute('''
        CREATE TABLE IF NOT EXISTS global_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    conn.execute("INSERT OR IGNORE INTO global_settings (key, value) VALUES ('round3_unlocked', '0')")
    conn.execute("INSERT OR IGNORE INTO global_settings (key, value) VALUES ('round2_unlocked', '1')")
    
    cursor = conn.execute("PRAGMA table_info(users)")
    columns = [col['name'] for col in cursor.fetchall()]
    if 'round3_start_time' not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN round3_start_time DATETIME")
    if 'round3_status' not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN round3_status TEXT DEFAULT 'active'")
    if 'has_seen_r3_intro' not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN has_seen_r3_intro INTEGER DEFAULT 0")
        
    conn.commit()
    conn.close()

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
    r2_unlocked = conn.execute("SELECT value FROM global_settings WHERE key = 'round2_unlocked'").fetchone()['value'] == '1'
    r3_unlocked = conn.execute("SELECT value FROM global_settings WHERE key = 'round3_unlocked'").fetchone()['value'] == '1'
    user = conn.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],)).fetchone()
    conn.close()
    
    can_play_r2 = r2_unlocked and user['status'] == 'active' and (user['points'] or 0) < 2950
    can_play_r3 = r3_unlocked and user['round3_status'] == 'active' and (user['round3_points'] or 0) < 2500
    
    return render_template('hub.html', user=user, can_play_r2=can_play_r2, can_play_r3=can_play_r3, r2_unlocked=r2_unlocked, r3_unlocked=r3_unlocked)

@app.before_request
def check_timer():
    if request.path.startswith('/static') or request.path.startswith('/auth') or request.path in ['/login', '/register', '/logout', '/choose-username', '/hub']:
        return
        
    if 'user_id' in session and session.get('role') != 'admin':
        conn = get_db_connection()
        user = conn.execute("SELECT start_time, status, round3_start_time, round3_status FROM users WHERE id = ?", (session['user_id'],)).fetchone()
        
        if user:
            needs_commit = False
            # Check Round 2 timer
            if user['start_time'] and user['status'] != 'suspended':
                start_time = datetime.fromisoformat(user['start_time'])
                if get_utc_now() > start_time + timedelta(minutes=60):
                    conn.execute("UPDATE users SET status = 'suspended' WHERE id = ?", (session['user_id'],))
                    needs_commit = True
                    flash('ROUND 2 TIME IS UP. ACCOUNT SUSPENDED FROM ROUND 2.')
            
            # Check Round 3 timer
            if user['round3_start_time'] and user['round3_status'] != 'suspended':
                r3_start_time = datetime.fromisoformat(user['round3_start_time'])
                if get_utc_now() > r3_start_time + timedelta(minutes=60):
                    conn.execute("UPDATE users SET round3_status = 'suspended' WHERE id = ?", (session['user_id'],))
                    needs_commit = True
                    flash('ROUND 3 TIME IS UP. ACCOUNT SUSPENDED FROM ROUND 3.')
                    
            if needs_commit:
                conn.commit()
                
        conn.close()

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        user = conn.execute("SELECT id, username, role, points, start_time, status FROM users WHERE username = ? AND password = ?", (username, password)).fetchone()
        
        if user:
            if user['status'] == 'suspended':
                conn.close()
                flash('ACCOUNT SUSPENDED: GAME COMPLETED OR BANNED.')
                return render_template('login.html')
                
            conn.close()
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            session['points'] = user['points']
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
            "INSERT INTO users (username, password, role, points, status, google_id, email) VALUES (?, ?, 'player', 0, 'active', ?, ?)",
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
        
        return redirect(url_for('index'))
        
    return render_template('choose_username.html', email=pending['email'])

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        user = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        
        if user:
            flash('ERROR: Player name already taken.')
        else:
            conn.execute("INSERT INTO users (username, password, role, points) VALUES (?, ?, 'player', 0)", (username, password))
            conn.commit()
            flash('REGISTRATION SUCCESSFUL. PLEASE LOG IN.')
            conn.close()
            return redirect(url_for('login'))
        conn.close()
            
    return render_template('register.html')

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'update':
            user_id = request.form.get('user_id')
            new_points = request.form.get('points')
            round_num = request.form.get('round')
            if user_id and new_points is not None:
                if round_num == '3':
                    conn.execute("UPDATE users SET round3_points = ? WHERE id = ?", (new_points, user_id))
                else:
                    conn.execute("UPDATE users SET points = ? WHERE id = ?", (new_points, user_id))
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
        elif action == 'toggle_round3':
            current = conn.execute("SELECT value FROM global_settings WHERE key = 'round3_unlocked'").fetchone()
            new_val = '1' if current['value'] == '0' else '0'
            conn.execute("UPDATE global_settings SET value = ? WHERE key = 'round3_unlocked'", (new_val,))
            conn.commit()
            if new_val == '0':
                subprocess.run("docker ps -q --filter 'name=jumanji_r3_' | xargs -r docker rm -f", shell=True, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            flash(f"Round 3 is now {'UNLOCKED' if new_val == '1' else 'LOCKED'}")
        elif action == 'toggle_round2':
            current = conn.execute("SELECT value FROM global_settings WHERE key = 'round2_unlocked'").fetchone()
            new_val = '1' if current['value'] == '0' else '0'
            conn.execute("UPDATE global_settings SET value = ? WHERE key = 'round2_unlocked'", (new_val,))
            conn.commit()
            if new_val == '0':
                subprocess.run("docker ps -q --filter 'name=jumanji_r2_' | xargs -r docker rm -f", shell=True, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            flash(f"Round 2 is now {'UNLOCKED' if new_val == '1' else 'LOCKED'}")
        elif action == 'toggle_status':
            user_id = request.form.get('user_id')
            round_num = request.form.get('round')
            if user_id:
                if round_num == '3':
                    cur_stat = conn.execute("SELECT round3_status FROM users WHERE id = ?", (user_id,)).fetchone()
                    new_stat = 'active' if (cur_stat and cur_stat['round3_status'] == 'suspended') else 'suspended'
                    conn.execute("UPDATE users SET round3_status = ? WHERE id = ?", (new_stat, user_id))
                    conn.commit()
                    flash(f"Round 3 status updated to {new_stat.upper()} for player #{user_id}.")
                else:
                    cur_stat = conn.execute("SELECT status FROM users WHERE id = ?", (user_id,)).fetchone()
                    new_stat = 'active' if (cur_stat and cur_stat['status'] == 'suspended') else 'suspended'
                    conn.execute("UPDATE users SET status = ? WHERE id = ?", (new_stat, user_id))
                    conn.commit()
                    flash(f"Round 2 status updated to {new_stat.upper()} for player #{user_id}.")
        elif action == 'reset_timer':
            user_id = request.form.get('user_id')
            round_num = request.form.get('round')
            if user_id:
                if round_num == '3':
                    conn.execute("UPDATE users SET round3_start_time = NULL, round3_status = 'active', has_seen_r3_intro = 0 WHERE id = ?", (user_id,))
                    conn.commit()
                    flash(f"Round 3 timer reset for player #{user_id}. Ready for fresh session.")
                else:
                    conn.execute("UPDATE users SET start_time = NULL, status = 'active', has_seen_intro = 0 WHERE id = ?", (user_id,))
                    conn.commit()
                    flash(f"Round 2 timer reset for player #{user_id}. Ready for fresh session.")
            
    users_r2 = conn.execute("SELECT * FROM users ORDER BY points DESC").fetchall()
    users_r3 = conn.execute("SELECT * FROM users ORDER BY round3_points DESC").fetchall()
    round3_unlocked = conn.execute("SELECT value FROM global_settings WHERE key = 'round3_unlocked'").fetchone()['value'] == '1'
    round2_unlocked = conn.execute("SELECT value FROM global_settings WHERE key = 'round2_unlocked'").fetchone()['value'] == '1'
    conn.close()
    
    current_time = get_utc_now()
    stats = {
        'online': 0,
        'offline': 0,
        'completed': 0,
        'suspended': 0,
        'r3_completed': 0,
        'r3_suspended': 0
    }
    
    for u in users_r2:
        if u['role'] == 'admin': continue
        
        # Round 2 Stats
        if u['points'] >= 2950: stats['completed'] += 1
        if u['status'] == 'suspended': stats['suspended'] += 1
        
        # Round 3 Stats
        if u['round3_points'] >= 2500: stats['r3_completed'] += 1
        if u['round3_status'] == 'suspended': stats['r3_suspended'] += 1
        
        if u['last_active']:
            last_active = datetime.fromisoformat(u['last_active'])
            if (current_time - last_active).total_seconds() < 30:
                stats['online'] += 1
            else:
                stats['offline'] += 1
        else:
            stats['offline'] += 1
            
    return render_template('admin.html', users_r2=users_r2, users_r3=users_r3, stats=stats, round3_unlocked=round3_unlocked, round2_unlocked=round2_unlocked)

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
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    if session.get('role') == 'admin':
        return redirect(url_for('admin'))
        
    conn = get_db_connection()
    r2_unlocked = conn.execute("SELECT value FROM global_settings WHERE key = 'round2_unlocked'").fetchone()['value'] == '1'
    user = conn.execute("SELECT start_time, has_seen_intro, points, status FROM users WHERE id = ?", (session['user_id'],)).fetchone()
    
    if not r2_unlocked or user['status'] == 'suspended' or user['points'] >= 2950:
        conn.close()
        return redirect(url_for('index'))
        
    if not user['start_time']:
        start_time = get_utc_now().isoformat()
        conn.execute("UPDATE users SET start_time = ? WHERE id = ?", (start_time, session['user_id']))
        conn.commit()
        user = conn.execute("SELECT start_time, has_seen_intro, points, status FROM users WHERE id = ?", (session['user_id'],)).fetchone()
        
    conn.close()
    
    start_time = datetime.fromisoformat(user['start_time'])
    time_elapsed = (get_utc_now() - start_time).total_seconds()
    remaining_seconds = max(0, 3600 - time_elapsed)
            
    return render_template('dashboard.html', remaining_seconds=int(remaining_seconds), has_seen_intro=user['has_seen_intro'], initial_points=user['points'])

@app.route('/api/set_intro_watched', methods=['POST'])
def set_intro_watched():
    if 'user_id' in session:
        conn = get_db_connection()
        conn.execute("UPDATE users SET has_seen_intro = 1 WHERE id = ?", (session['user_id'],))
        conn.commit()
        conn.close()
    return jsonify({'status': 'success'})

SCORE_MATRIX = {
    'bravestone': 400,
    'oberon': 450,
    'ruby': 600,
    'seaplane': 1000,
    'finbar': 500,
    'round3_user': 1000,
    'round3_root': 1500
}

import hashlib

def generate_dynamic_flag(user_id, avatar_id):
    secret = "8f7b6c5d4a3e2f1g0h9i8j7k6l5m4n3"
    
    if avatar_id == 'round3_user':
        hash_input = f"{user_id}:user:{secret}"
        hex_digest = hashlib.md5(hash_input.encode()).hexdigest()[:8]
        return f"OVERRIDE-USER-{hex_digest}"
    
    if avatar_id == 'round3_root':
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
    data = request.get_json()
    token = data.get('token')
    
    if token and token in INTERNAL_TOKENS:
        user_id = INTERNAL_TOKENS[token]['user_id']
        sid = INTERNAL_TOKENS[token]['sid']
    elif 'user_id' in session:
        user_id = session['user_id']
        sid = None
    else:
        return jsonify({'error': 'Unauthorized'}), 401
        
    data = request.get_json()
    avatar_id = data.get('avatar_id')
    submitted_flag = data.get('flag', '').strip()
    
    if avatar_id == 'round3':
        expected_user = generate_dynamic_flag(user_id, 'round3_user')
        expected_root = generate_dynamic_flag(user_id, 'round3_root')
        if submitted_flag == expected_user:
            avatar_id = 'round3_user'
        elif submitted_flag == expected_root:
            avatar_id = 'round3_root'
        else:
            return jsonify({'status': 'invalid_flag', 'error': 'INCORRECT OVERRIDE CODE!'}), 400

    if avatar_id not in SCORE_MATRIX:
        if submitted_flag.startswith('JUMANJI{') and '_' in submitted_flag:
            inferred = submitted_flag.split('{')[1].split('_')[0]
            if inferred in SCORE_MATRIX:
                avatar_id = inferred
        elif submitted_flag.startswith('OVERRIDE-USER-'):
            avatar_id = 'round3_user'
        elif submitted_flag.startswith('OVERRIDE-ROOT-'):
            avatar_id = 'round3_root'

    if avatar_id not in SCORE_MATRIX:
        return jsonify({'error': 'Invalid checkpoint'}), 400
        
    expected_flag = generate_dynamic_flag(user_id, avatar_id)
    if submitted_flag != expected_flag:
        return jsonify({'status': 'invalid_flag', 'error': 'INCORRECT FLAG SUPPLIED!'}), 400
        
    points_to_add = SCORE_MATRIX[avatar_id]
    
    conn = get_db_connection()
    # Check if already solved
    solved = conn.execute("SELECT 1 FROM solved_challenges WHERE user_id = ? AND challenge_id = ?", (user_id, avatar_id)).fetchone()
    
    if solved:
        conn.close()
        return jsonify({'status': 'already_solved', 'message': 'Checkpoint already completed.'})
        
    # Award points
    solved_time = get_utc_now().isoformat()
    conn.execute("INSERT INTO solved_challenges (user_id, challenge_id, solved_at) VALUES (?, ?, ?)", (user_id, avatar_id, solved_time))
    
    is_round3 = avatar_id in ['round3_user', 'round3_root']
    
    if is_round3:
        conn.execute("UPDATE users SET round3_points = round3_points + ? WHERE id = ?", (points_to_add, user_id))
    else:
        conn.execute("UPDATE users SET points = points + ? WHERE id = ?", (points_to_add, user_id))
    conn.commit()
    
    # Get new total
    if is_round3:
        new_points = conn.execute("SELECT round3_points FROM users WHERE id = ?", (user_id,)).fetchone()['round3_points']
        session['round3_points'] = new_points
    else:
        new_points = conn.execute("SELECT points FROM users WHERE id = ?", (user_id,)).fetchone()['points']
        session['points'] = new_points
    
    if sid:
        if is_round3:
            r3_user = conn.execute("SELECT 1 FROM solved_challenges WHERE user_id = ? AND challenge_id = 'round3_user'", (user_id,)).fetchone()
            r3_root = conn.execute("SELECT 1 FROM solved_challenges WHERE user_id = ? AND challenge_id = 'round3_root'", (user_id,)).fetchone()
            if r3_user and r3_root:
                conn.execute("UPDATE users SET round3_status = 'suspended' WHERE id = ?", (user_id,))
                conn.commit()
                socketio.emit('game-win-r3', {}, room=sid)
            else:
                socketio.emit('score-update', {'new_points': new_points}, room=sid)
        else:
            socketio.emit('score-update', {'new_points': new_points}, room=sid)
            
        socketio.emit('flag-solved', {'avatar_id': avatar_id}, room=sid)
        
        if not is_round3 and new_points >= 2950:
            socketio.emit('game-win', {}, room=sid)
            
    conn.close()
    return jsonify({'status': 'success', 'points_awarded': points_to_add, 'total_points': new_points})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/round3')
def round3():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    if session.get('role') == 'admin':
        return redirect(url_for('admin'))
        
    conn = get_db_connection()
    unlocked = conn.execute("SELECT value FROM global_settings WHERE key = 'round3_unlocked'").fetchone()['value'] == '1'
    user = conn.execute("SELECT round3_start_time, round3_status, round3_points, has_seen_r3_intro FROM users WHERE id = ?", (session['user_id'],)).fetchone()
    
    if not unlocked or user['round3_status'] == 'suspended':
        conn.close()
        return redirect(url_for('index'))
        
    if not user['round3_start_time']:
        remaining_seconds = 3600
    else:
        start_time = datetime.fromisoformat(user['round3_start_time'])
        time_elapsed = (get_utc_now() - start_time).total_seconds()
        remaining_seconds = max(0, 3600 - time_elapsed)
    
    solved_user = conn.execute("SELECT 1 FROM solved_challenges WHERE user_id = ? AND challenge_id = 'round3_user'", (session['user_id'],)).fetchone() is not None
    solved_root = conn.execute("SELECT 1 FROM solved_challenges WHERE user_id = ? AND challenge_id = 'round3_root'", (session['user_id'],)).fetchone() is not None
    
    conn.close()
    
    return render_template('round3.html', points=user['round3_points'], solved_user=solved_user, solved_root=solved_root, remaining_seconds=int(remaining_seconds), has_seen_r3_intro=user['has_seen_r3_intro'])

@app.route('/api/start_r3', methods=['POST'])
def start_r3():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    conn = get_db_connection()
    user = conn.execute("SELECT round3_start_time FROM users WHERE id = ?", (session['user_id'],)).fetchone()
    if not user['round3_start_time']:
        r3_start_time = get_utc_now().isoformat()
        conn.execute("UPDATE users SET round3_start_time = ?, has_seen_r3_intro = 1 WHERE id = ?", (r3_start_time, session['user_id']))
        conn.commit()
    conn.close()
    return jsonify({'status': 'success'})

# --- Web Shell PTY Logic ---

clients = {}

@socketio.on('start-pty')
def start_pty(data):
    sid = request.sid
    avatar_id = data.get('avatar_id', 'bravestone')
    
    if sid in clients:
        return
        
    master_fd, slave_fd = pty.openpty()
    
    session_id = session.get('user_id', 'anon')
    username = session.get('username', 'player')
    
    # Isolate Round 2 and Round 3 containers
    is_round3 = (avatar_id == 'round3')
    if is_round3:
        container_name = f"jumanji_r3_{session_id}_{sid}"
        image_name = "jumanji-round3:latest"
        working_dir = "/round3"
        init_cmd = f"sudo -E /usr/local/bin/setup_round3.sh && echo -e \"PS1='{username}@sdc-mainframe:\\\\w\\\\$ '\\nenable -n complete\\nenable -n deploy_override\" > ~/.bashrc && exec bash"
    else:
        container_name = f"jumanji_r2_{session_id}_{sid}"
        image_name = "jumanji-round2:latest"
        working_dir = f"/{avatar_id}"
        init_cmd = f"sudo -E /usr/local/bin/setup_round2.sh && echo -e \"PS1='{username}@sdc-jungle:\\\\w\\\\$ '\\nenable -n complete\" > ~/.bashrc && exec bash"
    
    # Prune any previous container for this user/sid
    subprocess.run(["docker", "rm", "-f", f"jumanji_r2_{session_id}_{sid}", f"jumanji_r3_{session_id}_{sid}", f"jumanji_session_{session_id}_{sid}"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    import secrets
    token = secrets.token_hex(16)
    INTERNAL_TOKENS[token] = {
        'user_id': session_id,
        'sid': sid
    }
    
    p = subprocess.Popen(
        [
            "docker", "run", "-it", "--rm", "--name", container_name,
            "--cap-add", "SYS_ADMIN", "--security-opt", "apparmor=unconfined",
            "--memory=512m", "--cpus=0.75", "--pids-limit=100",
            "-u", "recon_user",
            "-e", f"CTF_TOKEN={token}",
            "-e", f"PLAYER_ID={session_id}",
            "-e", f"PLAYER_USERNAME={username}",
            "-e", "TERM=xterm-256color",
            "--add-host=host.docker.internal:host-gateway",
            "-w", working_dir,
            image_name, "bash", "-c", init_cmd
        ],
        preexec_fn=os.setsid,
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd
    )
    
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

@socketio.on('pty-input')
def pty_input(data):
    sid = request.sid
    if sid in clients:
        fd = clients[sid]['fd']
        try:
            os.write(fd, data['input'].encode('utf-8'))
        except OSError:
            pass

@socketio.on('stop-pty')
def handle_stop_pty():
    sid = request.sid
    if sid in clients:
        p = clients[sid]['process']
        fd = clients[sid]['fd']
        container_name = clients[sid].get('container_name')
        try:
            p.terminate()
            os.close(fd)
        except:
            pass
        
        session_id = session.get('user_id', 'anon')
        if container_name:
            subprocess.run(["docker", "rm", "-f", container_name], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.run(["docker", "rm", "-f", f"jumanji_r2_{session_id}_{sid}", f"jumanji_r3_{session_id}_{sid}", f"jumanji_session_{session_id}_{sid}"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        del clients[sid]

@socketio.on('disconnect')
def disconnect():
    handle_stop_pty()

if __name__ == '__main__':
    try:
        init_db()
    except Exception as e:
        print("DB Init failed:", e)
    socketio.run(app, host='0.0.0.0', port=8080, debug=True)
