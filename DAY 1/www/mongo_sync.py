"""
Direct MongoDB Roster Synchronization Module for Technozion SDC CTF
Connects directly to the SDC Games MongoDB instance (Atlas or Local)
to fetch participants and sync them into the CTF SQLite database.
Zero HTTP bridge dependencies.
"""

import os
import json
import sqlite3
import secrets
from typing import Dict, Any, Optional

try:
    import pymongo
except ImportError:
    pymongo = None


def load_ctf_env():
    """Load configuration from DAY 1/www/.env if present."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if os.path.exists(env_path):
        try:
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        k, v = line.split('=', 1)
                        os.environ.setdefault(k.strip(), v.strip())
        except Exception:
            pass

load_ctf_env()


def get_default_mongo_config():
    """Retrieve MongoDB config from environment."""
    load_ctf_env()
    uri = os.environ.get('SDC_MONGODB_URI', '')
    db_name = os.environ.get('SDC_MONGODB_DB_NAME', 'test')
    return uri, db_name


def test_mongo_connection(uri: Optional[str] = None, timeout_ms: int = 5000) -> Dict[str, Any]:
    """Test connectivity to MongoDB and return available databases."""
    if pymongo is None:
        return {'status': 'error', 'error': 'pymongo is not installed in the current environment.'}
    
    uri = uri or get_default_mongo_config()[0]
    if not uri:
        return {'status': 'error', 'error': 'SDC_MONGODB_URI is not set in environment or .env.'}
        
    try:
        client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=timeout_ms)
        dbs = client.list_database_names()
        client.close()
        return {'status': 'success', 'databases': dbs}
    except Exception as e:
        return {'status': 'error', 'error': str(e)}


def sync_roster_from_mongodb(db_path: str, uri: Optional[str] = None, db_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Connects directly to MongoDB, reads participants, users, and priorities,
    and non-destructively upserts them into SQLite jumanji_auth.db.
    """
    if pymongo is None:
        return {'status': 'error', 'error': 'pymongo is not installed.'}
        
    env_uri, env_db = get_default_mongo_config()
    uri = uri or env_uri
    db_name = db_name or env_db or 'test'
    
    if not uri:
        return {'status': 'error', 'error': 'SDC_MONGODB_URI is not configured.'}
        
    try:
        # 1. Connect to MongoDB Atlas / Local
        client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=5000)
        mongo_db = client[db_name]
        
        # 2. Fetch raw collections
        participants = list(mongo_db.participants.find())
        users = list(mongo_db.users.find())
        priorities = list(mongo_db.priorities.find())
        client.close()
        
        user_map = {str(u['_id']): u for u in users if '_id' in u}
        priority_map = {str(p.get('participantId')): p for p in priorities if 'participantId' in p}
        
        # 3. Connect to SQLite
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        
        added_count = 0
        updated_count = 0
        synced_records = []
        
        for p in participants:
            pid = p.get('participantId')
            if not pid:
                continue
                
            contact = p.get('contact', {}) or {}
            email = contact.get('email', '')
            name = p.get('name', '')
            
            # Lookup linked user
            u_id = str(p.get('userId', ''))
            user = user_map.get(u_id)
            if user:
                if not email and user.get('email'):
                    email = user.get('email')
                if not name and user.get('name'):
                    name = user.get('name')
                google_id = user.get('providerUserId', '')
            else:
                google_id = ''
                
            # Determine authorized levels from priorities
            p_oid = str(p.get('_id', ''))
            priority = priority_map.get(p_oid)
            choices = priority.get('choices', []) if priority else []
            
            has_l2 = any(c.get('roundNumber') == 2 and c.get('domainId') == 'cybersecurity' for c in choices)
            has_l3 = any(c.get('roundNumber') == 3 and c.get('domainId') == 'cybersecurity' for c in choices)
            
            # If explicit choices submitted, grant selected; otherwise default to both [2, 3]
            auth_levels = []
            if has_l2:
                auth_levels.append(2)
            if has_l3:
                auth_levels.append(3)
            if not auth_levels:
                auth_levels = [2, 3]
                
            auth_levels_json = json.dumps(auth_levels)
            
            # Check existing player in SQLite
            existing = None
            if pid:
                existing = conn.execute("SELECT * FROM users WHERE participant_id = ?", (pid,)).fetchone()
            if not existing and email:
                existing = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
                
            if not existing:
                # Generate clean unique username
                base_username = pid.lower().replace('-', '_')
                username = base_username
                suffix = 1
                while conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
                    username = f"{base_username}_{suffix}"
                    suffix += 1
                    
                unusable_pw = f"!OAUTH_ONLY!_{secrets.token_hex(16)}"
                conn.execute('''
                    INSERT INTO users (
                        username, password, role, points, level2_points, level3_points,
                        status, level2_status, level3_status, has_seen_intro, has_seen_l2_intro, has_seen_l3_intro,
                        participant_id, authorized_levels, email, name, google_id
                    )
                    VALUES (?, ?, 'player', 0, 0, 0, 'active', 'active', 'active', 0, 0, 0, ?, ?, ?, ?, ?)
                ''', (username, unusable_pw, pid, auth_levels_json, email, name, google_id))
                added_count += 1
                synced_records.append({'participant_id': pid, 'username': username, 'name': name, 'action': 'created'})
            else:
                # Update metadata non-destructively and ensure password login is deactivated
                update_fields = []
                update_values = []
                
                # Revoke legacy default password if present
                if existing['password'] == 'ShadowDrop2026!' or existing['password'].startswith('ShadowDrop'):
                    update_fields.append("password = ?")
                    update_values.append(f"!OAUTH_ONLY!_{secrets.token_hex(16)}")
                
                if pid:
                    update_fields.append("participant_id = ?")
                    update_values.append(pid)
                if auth_levels_json:
                    update_fields.append("authorized_levels = ?")
                    update_values.append(auth_levels_json)
                if email:
                    update_fields.append("email = COALESCE(NULLIF(email, ''), ?)")
                    update_values.append(email)
                if name:
                    update_fields.append("name = COALESCE(NULLIF(name, ''), ?)")
                    update_values.append(name)
                if google_id:
                    update_fields.append("google_id = COALESCE(NULLIF(google_id, ''), ?)")
                    update_values.append(google_id)
                    
                update_values.append(existing['id'])
                conn.execute(f"UPDATE users SET {', '.join(update_fields)} WHERE id = ?", update_values)
                updated_count += 1
                synced_records.append({'participant_id': pid, 'username': existing['username'], 'name': name, 'action': 'updated'})
                
        conn.commit()
        conn.close()
        
        return {
            'status': 'success',
            'database': db_name,
            'total_scanned': len(participants),
            'added': added_count,
            'updated': updated_count,
            'records': synced_records
        }
    except Exception as e:
        return {'status': 'error', 'error': str(e)}
