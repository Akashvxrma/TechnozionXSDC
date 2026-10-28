# gauntlet_engine.py
# Core Tournament Logic for Day 2 Level 2: "The Jumanji Gauntlet"

import sqlite3
import hashlib
import time
import secrets
import json
from datetime import datetime, timedelta, timezone

import os
SECRET = os.environ.get('CTF_MASTER_SECRET', '8f7b6c5d4a3e2f1g0h9i8j7k6l5m4n3')

CURSE_CONFIG = {
    'quicksand': {'duration': 45, 'name': 'Quicksand', 'desc': 'Terminal locked for 45s'},
    'monkeys': {'duration': 60, 'name': 'Monkeys in the Wire', 'desc': 'Terminal prompt scrambled for 60s'},
    'fog_of_war': {'duration': 60, 'name': 'Fog of War', 'desc': 'Cartographer radar & hints obscured for 60s'},
    'stampede': {'duration': 45, 'name': 'Stampede', 'desc': 'Process noise & log spam deployed for 45s'}
}

PHASE_RELICS = {
    'phase1_pods': {
        'compass': {'name': 'Sun Compass', 'points': 25, 'category': 'Network Beacon'},
        'blade': {'name': 'Obsidian Blade', 'points': 35, 'category': 'Privilege Escalation'},
        'jaguar': {'name': 'Jaguar Fang', 'points': 40, 'category': 'Stego & Ciphers'},
        'idol': {'name': 'Golden Idol', 'points': 50, 'category': 'Process Recon'}
    },
    'phase2_duels': {
        'mirror_shard': {'name': 'Mirror Shard', 'points': 30, 'category': 'System Recon'},
        'sun_disk': {'name': 'Sun Disk', 'points': 30, 'category': 'Local HTTP Daemon'},
        'serpent_eye': {'name': 'Serpent Eye', 'points': 30, 'category': 'Database Vault'},
        'moon_crystal': {'name': 'Moon Crystal', 'points': 30, 'category': 'Sudo Delegation'},
        'temple_skull': {'name': 'Temple Skull', 'points': 30, 'category': 'Ancient ROT Cipher'}
    },
    'phase4_final': {
        'final_jewel': {'name': 'The Eye of the Jaguar', 'points': 100, 'category': 'Final Root Override'}
    },
    'lagoon': {
        f'lagoon_relic_{i}': {'name': f'Lagoon Relic #{i}', 'points': 20, 'category': 'Bonus Recon'} for i in range(1, 9)
    }
}

DEFAULT_TEAMS = [
    # Pod Alpha
    {'name': 'Team Jaguar', 'pod': 'pod_alpha', 'code': 'JUMANJI-JAGUAR-99'},
    {'name': 'Team Viper', 'pod': 'pod_alpha', 'code': 'JUMANJI-VIPER-88'},
    {'name': 'Team Rhino', 'pod': 'pod_alpha', 'code': 'JUMANJI-RHINO-77'},
    {'name': 'Team Falcon', 'pod': 'pod_alpha', 'code': 'JUMANJI-FALCON-66'},
    # Pod Bravo
    {'name': 'Team Cobra', 'pod': 'pod_bravo', 'code': 'JUMANJI-COBRA-55'},
    {'name': 'Team Mantis', 'pod': 'pod_bravo', 'code': 'JUMANJI-MANTIS-44'},
    {'name': 'Team Shadow', 'pod': 'pod_bravo', 'code': 'JUMANJI-SHADOW-33'},
    {'name': 'Team Elephant', 'pod': 'pod_bravo', 'code': 'JUMANJI-ELEPHANT-22'},
    # Pod Charlie
    {'name': 'Team Hippo', 'pod': 'pod_charlie', 'code': 'JUMANJI-HIPPO-11'},
    {'name': 'Team Crocodile', 'pod': 'pod_charlie', 'code': 'JUMANJI-CROC-00'},
    {'name': 'Team Panther', 'pod': 'pod_charlie', 'code': 'JUMANJI-PANTHER-91'},
    {'name': 'Team Eagle', 'pod': 'pod_charlie', 'code': 'JUMANJI-EAGLE-82'},
    # Pod Delta
    {'name': 'Team Wolf', 'pod': 'pod_delta', 'code': 'JUMANJI-WOLF-73'},
    {'name': 'Team Bear', 'pod': 'pod_delta', 'code': 'JUMANJI-BEAR-64'},
    {'name': 'Team Shark', 'pod': 'pod_delta', 'code': 'JUMANJI-SHARK-55'},
    {'name': 'Team Scorpion', 'pod': 'pod_delta', 'code': 'JUMANJI-SCORPION-46'}
]

def get_utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)

def init_gauntlet_db(conn):
    """Create all required tables for Gauntlet tournament."""
    conn.execute('''
        CREATE TABLE IF NOT EXISTS gauntlet_teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_name TEXT UNIQUE NOT NULL,
            access_code TEXT UNIQUE NOT NULL,
            pod_id TEXT DEFAULT 'pod_alpha',
            phase TEXT DEFAULT 'phase1_pods',
            phase1_score INTEGER DEFAULT 0,
            duel_score INTEGER DEFAULT 0,
            shrine_score INTEGER DEFAULT 0,
            lagoon_score INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS gauntlet_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('navigator', 'cartographer')),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(team_id) REFERENCES gauntlet_teams(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(team_id, role),
            UNIQUE(user_id)
        )
    ''')

    # Migration: enforce strict 2 players per squad (UNIQUE(team_id, role))
    try:
        cur = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='gauntlet_members'")
        row = cur.fetchone()
        if row and 'UNIQUE(team_id, role)' not in row[0]:
            conn.execute('''
                CREATE TABLE gauntlet_members_temp (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    team_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('navigator', 'cartographer')),
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(team_id) REFERENCES gauntlet_teams(id) ON DELETE CASCADE,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                    UNIQUE(team_id, role),
                    UNIQUE(user_id)
                )
            ''')
            conn.execute("INSERT OR IGNORE INTO gauntlet_members_temp (id, team_id, user_id, role, created_at) SELECT id, team_id, user_id, role, created_at FROM gauntlet_members WHERE role IN ('navigator', 'cartographer')")
            conn.execute("DROP TABLE gauntlet_members")
            conn.execute("ALTER TABLE gauntlet_members_temp RENAME TO gauntlet_members")
            conn.commit()
    except Exception:
        pass

    conn.execute('''
        CREATE TABLE IF NOT EXISTS gauntlet_matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phase TEXT NOT NULL,
            match_code TEXT UNIQUE NOT NULL,
            team_a_id INTEGER NOT NULL,
            team_b_id INTEGER NOT NULL,
            score_a INTEGER DEFAULT 0,
            score_b INTEGER DEFAULT 0,
            winner_team_id INTEGER DEFAULT NULL,
            status TEXT DEFAULT 'active',
            started_at DATETIME,
            completed_at DATETIME,
            FOREIGN KEY(team_a_id) REFERENCES gauntlet_teams(id),
            FOREIGN KEY(team_b_id) REFERENCES gauntlet_teams(id)
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS gauntlet_curses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_team_id INTEGER NOT NULL,
            to_team_id INTEGER NOT NULL,
            curse_type TEXT NOT NULL,
            applied_at DATETIME NOT NULL,
            expires_at DATETIME NOT NULL,
            is_active INTEGER DEFAULT 1,
            FOREIGN KEY(from_team_id) REFERENCES gauntlet_teams(id),
            FOREIGN KEY(to_team_id) REFERENCES gauntlet_teams(id)
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS gauntlet_curse_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL,
            curse_type TEXT NOT NULL,
            acquired_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_used INTEGER DEFAULT 0,
            FOREIGN KEY(team_id) REFERENCES gauntlet_teams(id)
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS gauntlet_shrine_ticks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER,
            tick_time DATETIME NOT NULL,
            points_awarded INTEGER DEFAULT 10,
            FOREIGN KEY(team_id) REFERENCES gauntlet_teams(id)
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS gauntlet_solved_relics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL,
            relic_id TEXT NOT NULL,
            phase TEXT NOT NULL,
            points INTEGER NOT NULL,
            solved_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            solved_by_user_id INTEGER,
            UNIQUE(team_id, relic_id)
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS gauntlet_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')

    # Seed initial global tournament settings
    conn.execute("INSERT OR IGNORE INTO gauntlet_settings (key, value) VALUES ('gauntlet_phase', 'phase1_pods')")
    conn.execute("INSERT OR IGNORE INTO gauntlet_settings (key, value) VALUES ('gauntlet_unlocked', '1')")
    conn.execute("INSERT OR IGNORE INTO gauntlet_settings (key, value) VALUES ('shrine_active_team', '')")
    conn.execute("INSERT OR IGNORE INTO gauntlet_settings (key, value) VALUES ('shrine_interval_seconds', '20')")
    conn.execute("INSERT OR IGNORE INTO gauntlet_settings (key, value) VALUES ('phase_timer_end', '')")
    conn.commit()

    # Seed teams if empty
    team_count = conn.execute("SELECT COUNT(*) as cnt FROM gauntlet_teams").fetchone()['cnt']
    if team_count == 0:
        seed_default_teams(conn)

def seed_default_teams(conn):
    """Seed the 16 Jumanji animal teams into 4 pods."""
    for t in DEFAULT_TEAMS:
        conn.execute('''
            INSERT OR IGNORE INTO gauntlet_teams (team_name, access_code, pod_id, phase, is_active)
            VALUES (?, ?, ?, 'phase1_pods', 1)
        ''', (t['name'], t['code'], t['pod']))
    conn.commit()

def generate_split_keys(team_id, match_id, relic_id):
    """Generate deterministic split keys for Navigator and Cartographer."""
    nav_raw = f"{team_id}:{match_id}:{relic_id}:nav:{SECRET}"
    cart_raw = f"{team_id}:{match_id}:{relic_id}:cart:{SECRET}"
    nav_hash = hashlib.md5(nav_raw.encode()).hexdigest()[:8]
    cart_hash = hashlib.md5(cart_raw.encode()).hexdigest()[:8]
    return {
        'nav_part': f"NAV_{relic_id.upper()}_{nav_hash}",
        'cart_part': f"CART_{relic_id.upper()}_{cart_hash}",
        'nav_hash': nav_hash,
        'cart_hash': cart_hash,
        'combined_flag': f"JUMANJI{{{relic_id}_{nav_hash}_{cart_hash}}}"
    }

def get_team_for_user(conn, user_id):
    """Fetch the team and role for a given user."""
    row = conn.execute('''
        SELECT t.*, m.role, m.user_id
        FROM gauntlet_members m
        JOIN gauntlet_teams t ON m.team_id = t.id
        WHERE m.user_id = ?
    ''', (user_id,)).fetchone()
    if row:
        return dict(row)
    
    # Check if user matches admin
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if user and user['role'] == 'admin':
        # Default to Team 1 for admin testing
        t = conn.execute("SELECT * FROM gauntlet_teams ORDER BY id ASC LIMIT 1").fetchone()
        if t:
            res = dict(t)
            res['role'] = 'navigator'
            return res
    return None

def auto_assign_user_to_team(conn, user_id):
    """Automatically assign an unassigned player to a team needing a player."""
    existing = get_team_for_user(conn, user_id)
    if existing:
        return existing
        
    teams = conn.execute("SELECT * FROM gauntlet_teams ORDER BY id ASC").fetchall()
    
    # Pass 1: Try to place on a team missing a navigator
    for t in teams:
        has_nav = conn.execute("SELECT 1 FROM gauntlet_members WHERE team_id = ? AND role = 'navigator'", (t['id'],)).fetchone()
        if not has_nav:
            conn.execute("INSERT OR IGNORE INTO gauntlet_members (team_id, user_id, role) VALUES (?, ?, 'navigator')", (t['id'], user_id))
            conn.commit()
            return get_team_for_user(conn, user_id)
            
    # Pass 2: Try to place on a team missing a cartographer
    for t in teams:
        has_cart = conn.execute("SELECT 1 FROM gauntlet_members WHERE team_id = ? AND role = 'cartographer'", (t['id'],)).fetchone()
        if not has_cart:
            conn.execute("INSERT OR IGNORE INTO gauntlet_members (team_id, user_id, role) VALUES (?, ?, 'cartographer')", (t['id'], user_id))
            conn.commit()
            return get_team_for_user(conn, user_id)
            
    # Strictly capped at 32 players (16 teams of 2 players: 1 navigator, 1 cartographer)
    # If all 32 slots are filled, tournament roster is strictly full
    return None

def get_top_4_teams(conn):
    """
    Fetch the top 4 teams in the Gauntlet tournament with full member roster.
    Ranked by total score: (phase1_score + duel_score + shrine_score + lagoon_score) DESC.
    """
    teams = conn.execute('''
        SELECT 
            t.id, 
            t.team_name, 
            t.pod_id, 
            t.phase,
            t.phase1_score,
            t.duel_score,
            t.shrine_score,
            t.lagoon_score,
            (t.phase1_score + t.duel_score + t.shrine_score + t.lagoon_score) as total_gauntlet_score
        FROM gauntlet_teams t
        ORDER BY total_gauntlet_score DESC, t.id ASC
        LIMIT 4
    ''').fetchall()
    
    result = []
    for t in teams:
        td = dict(t)
        members = conn.execute('''
            SELECT m.role, u.id as user_id, u.username, u.participant_id, u.name, u.email
            FROM gauntlet_members m
            JOIN users u ON m.user_id = u.id
            WHERE m.team_id = ?
            ORDER BY m.role DESC
        ''', (t['id'],)).fetchall()
        td['members'] = [dict(m) for m in members]
        result.append(td)
    return result

def verify_relic_submission(conn, team_id, flag_input, part2=None, user_id=None):
    """
    Validate a submitted relic flag for a team.
    Supports either:
    - JUMANJI{relic_navhash_carthash}
    - JUMANJI-VICTORY-ROOT-navhash (Phase 4)
    - Two separate parts: NAV_RELIC_hash + CART_RELIC_hash
    """
    flag = str(flag_input or '').strip()
    p2 = str(part2 or '').strip() if part2 else ''

    team = conn.execute("SELECT * FROM gauntlet_teams WHERE id = ?", (team_id,)).fetchone()
    if not team:
        return {'status': 'error', 'error': 'Team not found'}

    current_phase = conn.execute("SELECT value FROM gauntlet_settings WHERE key = 'gauntlet_phase'").fetchone()['value']
    match_id = 1
    if current_phase == 'phase2_duels':
        m = conn.execute("SELECT id FROM gauntlet_matches WHERE (team_a_id = ? OR team_b_id = ?) AND status = 'active' LIMIT 1", (team_id, team_id)).fetchone()
        if m:
            match_id = m['id']

    # Handle split parts submitted together
    if (flag.startswith('NAV_') and p2.startswith('CART_')) or (flag.startswith('CART_') and p2.startswith('NAV_')):
        nav_part = flag if flag.startswith('NAV_') else p2
        cart_part = p2 if p2.startswith('CART_') else flag
        # Extract relic
        parts = nav_part.split('_')
        if len(parts) >= 3:
            relic_id = parts[1].lower()
            nav_hash = parts[2]
            cart_hash = cart_part.split('_')[-1]
            flag = f"JUMANJI{{{relic_id}_{nav_hash}_{cart_hash}}}"

    # Handle single half provided
    if flag.startswith('NAV_') and not p2:
        return {
            'status': 'split_key_required',
            'message': 'Navigator half accepted! Now obtain the Cartographer key to combine.'
        }
    if flag.startswith('CART_') and not p2:
        return {
            'status': 'split_key_required',
            'message': 'Cartographer half accepted! Now obtain the Navigator key from the terminal to combine.'
        }

    # Identify candidate relic
    identified_relic = None
    expected_keys = None

    # Check Final Roll flag
    if flag.startswith('JUMANJI-VICTORY-ROOT-'):
        target_hash = flag.replace('JUMANJI-VICTORY-ROOT-', '').strip()
        keys = generate_split_keys(team_id, match_id, 'final_jewel')
        if target_hash == keys['nav_hash']:
            identified_relic = 'final_jewel'
            expected_keys = keys

    # Check JUMANJI{relic_nav_cart} format
    if not identified_relic and flag.startswith('JUMANJI{') and flag.endswith('}'):
        inner = flag[8:-1]
        tokens = inner.split('_')
        if len(tokens) >= 3:
            r_candidate = tokens[0]
            # Handle multi-word relics like mirror_shard
            if len(tokens) == 4:
                r_candidate = f"{tokens[0]}_{tokens[1]}"
            keys = generate_split_keys(team_id, match_id, r_candidate)
            if flag == keys['combined_flag']:
                identified_relic = r_candidate
                expected_keys = keys

    if not identified_relic:
        return {'status': 'invalid_flag', 'error': 'INCORRECT RELIC CIPHER OR SPLIT KEY!'}

    # Determine points
    points = 30
    for ph_key, relics in PHASE_RELICS.items():
        if identified_relic in relics:
            points = relics[identified_relic]['points']
            break

    # Check if already solved
    already = conn.execute("SELECT 1 FROM gauntlet_solved_relics WHERE team_id = ? AND relic_id = ?", (team_id, identified_relic)).fetchone()
    if already:
        return {'status': 'already_solved', 'message': 'Relic already secured by your team.'}

    # Record solution
    now_str = get_utc_now().isoformat()
    conn.execute('''
        INSERT INTO gauntlet_solved_relics (team_id, relic_id, phase, points, solved_at, solved_by_user_id)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (team_id, identified_relic, current_phase, points, now_str, user_id))

    # Update team score
    if current_phase == 'phase1_pods':
        conn.execute("UPDATE gauntlet_teams SET phase1_score = phase1_score + ? WHERE id = ?", (points, team_id))
    elif current_phase == 'phase2_duels':
        conn.execute("UPDATE gauntlet_teams SET duel_score = duel_score + ? WHERE id = ?", (points, team_id))
        # Update match score
        m = conn.execute("SELECT * FROM gauntlet_matches WHERE (team_a_id = ? OR team_b_id = ?) AND status = 'active' LIMIT 1", (team_id, team_id)).fetchone()
        if m:
            if m['team_a_id'] == team_id:
                conn.execute("UPDATE gauntlet_matches SET score_a = score_a + 1 WHERE id = ?", (m['id'],))
            else:
                conn.execute("UPDATE gauntlet_matches SET score_b = score_b + 1 WHERE id = ?", (m['id'],))
            
            # Award random Curse Card to this team
            curse_choices = ['quicksand', 'monkeys', 'fog_of_war', 'stampede']
            awarded_curse = secrets.choice(curse_choices)
            conn.execute("INSERT INTO gauntlet_curse_inventory (team_id, curse_type) VALUES (?, ?)", (team_id, awarded_curse))
    elif current_phase == 'phase4_final':
        conn.execute("UPDATE gauntlet_teams SET phase = 'champion' WHERE id = ?", (team_id,))
    else:
        conn.execute("UPDATE gauntlet_teams SET lagoon_score = lagoon_score + ? WHERE id = ?", (points, team_id))

    conn.commit()

    # Get updated total score
    updated_team = conn.execute("SELECT * FROM gauntlet_teams WHERE id = ?", (team_id,)).fetchone()
    total = (updated_team['phase1_score'] or 0) + (updated_team['duel_score'] or 0) + (updated_team['shrine_score'] or 0) + (updated_team['lagoon_score'] or 0)

    return {
        'status': 'success',
        'relic_id': identified_relic,
        'points_awarded': points,
        'total_points': total,
        'awarded_curse': awarded_curse if current_phase == 'phase2_duels' else None
    }

def get_active_curses_for_team(conn, team_id):
    """Retrieve all currently active unexpired curses targeting a team."""
    now = get_utc_now().isoformat()
    rows = conn.execute('''
        SELECT * FROM gauntlet_curses
        WHERE to_team_id = ? AND is_active = 1 AND expires_at > ?
        ORDER BY id DESC
    ''', (team_id, now)).fetchall()
    return [dict(r) for r in rows]

def cast_curse(conn, from_team_id, curse_type, target_team_id=None):
    """Spend a Curse Card from inventory and apply it against an opponent."""
    inv = conn.execute('''
        SELECT id FROM gauntlet_curse_inventory
        WHERE team_id = ? AND curse_type = ? AND is_used = 0
        LIMIT 1
    ''', (from_team_id, curse_type)).fetchone()
    
    if not inv:
        return {'status': 'error', 'error': f'No unused {curse_type} card in team inventory.'}

    # If no target specified, find active duel opponent
    if not target_team_id:
        m = conn.execute('''
            SELECT * FROM gauntlet_matches
            WHERE (team_a_id = ? OR team_b_id = ?) AND status = 'active'
            LIMIT 1
        ''', (from_team_id, from_team_id)).fetchone()
        if m:
            target_team_id = m['team_b_id'] if m['team_a_id'] == from_team_id else m['team_a_id']
        else:
            return {'status': 'error', 'error': 'No active match opponent found to target.'}

    duration = CURSE_CONFIG.get(curse_type, {}).get('duration', 45)
    start_time = get_utc_now()
    expires_time = start_time + timedelta(seconds=duration)

    conn.execute("UPDATE gauntlet_curse_inventory SET is_used = 1 WHERE id = ?", (inv['id'],))
    conn.execute('''
        INSERT INTO gauntlet_curses (from_team_id, to_team_id, curse_type, applied_at, expires_at, is_active)
        VALUES (?, ?, ?, ?, ?, 1)
    ''', (from_team_id, target_team_id, curse_type, start_time.isoformat(), expires_time.isoformat()))
    conn.commit()

    return {
        'status': 'success',
        'curse_type': curse_type,
        'from_team_id': from_team_id,
        'to_team_id': target_team_id,
        'duration': duration,
        'expires_at': expires_time.isoformat()
    }

def advance_tournament_phase(conn, target_phase=None):
    """Transition tournament to next phase or specified phase."""
    current = conn.execute("SELECT value FROM gauntlet_settings WHERE key = 'gauntlet_phase'").fetchone()['value']
    
    if target_phase:
        next_phase = target_phase
    elif current == 'standby':
        next_phase = 'phase1_pods'
    elif current == 'phase1_pods':
        next_phase = 'phase2_duels'
    elif current == 'phase2_duels':
        next_phase = 'phase3_shrine'
    elif current == 'phase3_shrine':
        next_phase = 'phase4_final'
    else:
        next_phase = 'concluded'

    # Execute bracket promotions
    if next_phase == 'phase2_duels':
        # Select top 2 from each pod
        pods = ['pod_alpha', 'pod_bravo', 'pod_charlie', 'pod_delta']
        advanced = []
        for pod in pods:
            top_teams = conn.execute('''
                SELECT t.id FROM gauntlet_teams t
                LEFT JOIN gauntlet_solved_relics s ON t.id = s.team_id
                WHERE t.pod_id = ?
                GROUP BY t.id
                ORDER BY t.phase1_score DESC, COUNT(s.id) DESC, MIN(s.solved_at) ASC, t.id ASC
                LIMIT 2
            ''', (pod,)).fetchall()
            for r in top_teams:
                advanced.append(r['id'])
        
        # Advance top 8 to duels, remaining to lagoon
        if advanced:
            ph = ','.join(['?'] * len(advanced))
            conn.execute(f"UPDATE gauntlet_teams SET phase = 'phase2_duels' WHERE id IN ({ph})", advanced)
            conn.execute(f"UPDATE gauntlet_teams SET phase = 'lagoon' WHERE id NOT IN ({ph})", advanced)
        
        # Create 4 Quarterfinal matches
        conn.execute("DELETE FROM gauntlet_matches WHERE phase = 'phase2_duels'")
        if len(advanced) >= 8:
            matchups = [
                (advanced[0], advanced[7]), # Alpha 1 vs Delta 2
                (advanced[2], advanced[5]), # Bravo 1 vs Charlie 2
                (advanced[4], advanced[3]), # Charlie 1 vs Bravo 2
                (advanced[6], advanced[1]), # Delta 1 vs Alpha 2
            ]
            for idx, (ta, tb) in enumerate(matchups, 1):
                conn.execute('''
                    INSERT INTO gauntlet_matches (phase, match_code, team_a_id, team_b_id, status, started_at)
                    VALUES ('phase2_duels', ?, ?, ?, 'active', ?)
                ''', (f"QF_{idx}", ta, tb, get_utc_now().isoformat()))

    elif next_phase == 'phase3_shrine':
        # Advance 4 duel winners (Top 4 Teams)
        matches = conn.execute("SELECT * FROM gauntlet_matches WHERE phase = 'phase2_duels'").fetchall()
        winners = []
        for m in matches:
            w = m['winner_team_id']
            if not w:
                w = m['team_a_id'] if m['score_a'] >= m['score_b'] else m['team_b_id']
            winners.append(w)
        
        # Fallback if advancing directly or duels incomplete: choose top 4 teams by score
        if len(winners) < 4:
            top4_rows = conn.execute('''
                SELECT id FROM gauntlet_teams
                ORDER BY (phase1_score + duel_score + shrine_score + lagoon_score) DESC, id ASC
                LIMIT 4
            ''').fetchall()
            winners = [r['id'] for r in top4_rows]

        if winners:
            ph = ','.join(['?'] * len(winners))
            conn.execute(f"UPDATE gauntlet_teams SET phase = 'phase3_shrine' WHERE id IN ({ph})", winners)
            conn.execute(f"UPDATE gauntlet_teams SET phase = 'lagoon' WHERE id NOT IN ({ph})", winners)

    elif next_phase == 'phase4_final':
        # Top 2 from Shrine
        shrine_teams = conn.execute('''
            SELECT id FROM gauntlet_teams
            WHERE phase = 'phase3_shrine'
            ORDER BY shrine_score DESC, id ASC
            LIMIT 2
        ''',).fetchall()
        finalists = [r['id'] for r in shrine_teams]
        if len(finalists) >= 2:
            conn.execute("UPDATE gauntlet_teams SET phase = 'phase4_final' WHERE id IN (?, ?)", (finalists[0], finalists[1]))
            conn.execute("UPDATE gauntlet_teams SET phase = 'lagoon' WHERE phase = 'phase3_shrine' AND id NOT IN (?, ?)", (finalists[0], finalists[1]))
            conn.execute('''
                INSERT INTO gauntlet_matches (phase, match_code, team_a_id, team_b_id, status, started_at)
                VALUES ('phase4_final', 'FINAL_CHAMPIONSHIP', ?, ?, 'active', ?)
            ''', (finalists[0], finalists[1], get_utc_now().isoformat()))

    conn.execute("UPDATE gauntlet_settings SET value = ? WHERE key = 'gauntlet_phase'", (next_phase,))
    conn.commit()
    return next_phase

def record_shrine_claim(conn, access_code_or_id):
    """Update current shrine ruler."""
    team = None
    if isinstance(access_code_or_id, int) or str(access_code_or_id).isdigit():
        team = conn.execute("SELECT * FROM gauntlet_teams WHERE id = ?", (int(access_code_or_id),)).fetchone()
    else:
        team = conn.execute("SELECT * FROM gauntlet_teams WHERE access_code = ?", (str(access_code_or_id).strip(),)).fetchone()
    
    if team:
        conn.execute("UPDATE gauntlet_settings SET value = ? WHERE key = 'shrine_active_team'", (str(team['id']),))
        conn.commit()
        return team
    return None

def tick_shrine(conn):
    """Award 10 points to current shrine holding team."""
    ruler_id = conn.execute("SELECT value FROM gauntlet_settings WHERE key = 'shrine_active_team'").fetchone()['value']
    if ruler_id and ruler_id.isdigit():
        t_id = int(ruler_id)
        now_str = get_utc_now().isoformat()
        conn.execute("UPDATE gauntlet_teams SET shrine_score = shrine_score + 10 WHERE id = ?", (t_id,))
        conn.execute("INSERT INTO gauntlet_shrine_ticks (team_id, tick_time, points_awarded) VALUES (?, ?, 10)", (t_id, now_str))
        conn.commit()
        team = conn.execute("SELECT * FROM gauntlet_teams WHERE id = ?", (t_id,)).fetchone()
        return {'team_id': t_id, 'team_name': team['team_name'], 'shrine_score': team['shrine_score']}
    return None
