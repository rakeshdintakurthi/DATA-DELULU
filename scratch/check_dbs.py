import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import db, org_database

con = db.connect()
orgs = con.execute("SELECT id, name, sector FROM organizations").fetchall()
print("=== Organization Database Configurations ===")
for o in orgs:
    cfg = org_database.get_org_db_config(con, o["id"])
    print(f"Org #{o['id']} [{o['name']}]:")
    print(f"  Provider: {cfg['provider']} | Host: {cfg['host']}:{cfg['port']}")
    print(f"  Database: {cfg['database_name']} | Status: {cfg['connection_status']}")
    print(f"  Record Count: {cfg['record_count']:,}")
    print(f"  Tables: {cfg['table_metadata']}")
    print("-" * 50)
