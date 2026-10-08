"""Database Initialization and Seed Script for Data Delulu Demo.

Initializes NovaBank's demo tables (customers, transactions, loans)
with 12,500 simulated organizational records.

Run:
  python scripts/init_demo_db.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.novabank_db import init_novabank_database, connect_novabank_database


def main():
    print("==================================================")
    print(" Data Delulu — NovaBank Demo Database Setup")
    print("==================================================")

    print("Target Environment: NovaBank — Demo Environment (Banking / FinTech)")
    print("Initializing simulated organizational tables (customers, transactions, loans)...")

    res = init_novabank_database(n_records=12500)
    print(f"\n[OK] Database initialized successfully!")
    print(f"     Backend Engine: {res['backend']}")
    print(f"     Records Seeded: {res['records_seeded']:,}")
    print(f"     Tables: {', '.join(res['tables'])}")

    info = connect_novabank_database()
    print("\n--- Connection Verification ---")
    print(f"     Status: Connected (Active)")
    print(f"     Customers Table: {info['customers_count']:,} records")
    print(f"     Transactions Table: {info['transactions_count']:,} records")
    print(f"     Loans Table: {info['loans_count']:,} records")
    print(f"     Host: {info['host']}")
    print(f"     Isolation: {info['isolation']}")
    print("==================================================")


if __name__ == "__main__":
    main()
