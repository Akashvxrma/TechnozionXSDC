#!/usr/bin/env python3
"""
CLI Runner: Sync Participants Directly from MongoDB to SQLite CTF Database
Usage:
    ./DAY 1/www/venv/bin/python3 sync_from_mongodb.py
"""

import sys
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WWW_DIR = os.path.join(SCRIPT_DIR, "DAY 1", "www")
sys.path.insert(0, WWW_DIR)

import mongo_sync

DB_PATH = os.path.join(WWW_DIR, "jumanji_auth.db")

def main():
    print("=" * 65)
    print(" 🚀 SDC GAMES ➔ CTF PLATFORM: DIRECT MONGODB ROSTER SYNC")
    print("=" * 65)
    
    uri, db_name = mongo_sync.get_default_mongo_config()
    print(f"[*] Target MongoDB Database: {db_name}")
    print(f"[*] Connecting to cluster...")
    
    conn_test = mongo_sync.test_mongo_connection(uri)
    if conn_test.get('status') != 'success':
        print(f"[-] ERROR: Failed to connect to MongoDB: {conn_test.get('error')}")
        sys.exit(1)
        
    print(f"[+] Successfully connected to MongoDB! Available DBs: {conn_test.get('databases')}")
    print(f"[*] Reading participants and syncing into SQLite ({DB_PATH})...")
    
    result = mongo_sync.sync_roster_from_mongodb(DB_PATH, uri, db_name)
    if result.get('status') != 'success':
        print(f"[-] ERROR: Roster sync failed: {result.get('error')}")
        sys.exit(1)
        
    print("\n" + "=" * 65)
    print(f"[+] SYNC COMPLETED SUCCESSFULLY!")
    print(f"    - Total Participants Scanned: {result['total_scanned']}")
    print(f"    - New Players Created:        {result['added']}")
    print(f"    - Existing Players Updated:   {result['updated']}")
    print("=" * 65)
    
    for r in result.get('records', []):
        act = "ADDED" if r['action'] == 'created' else "UPDATED"
        print(f"  [{act}] {r['participant_id']} -> Username: {r['username']} ({r['name']})")
    print()

if __name__ == '__main__':
    main()
