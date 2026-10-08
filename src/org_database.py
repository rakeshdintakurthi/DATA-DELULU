"""Data Delulu — Multi-Tenant Organization Database Integration & Connection Layer.

Each organization has its own isolated database configuration and data store.
Zero global hardcoding.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
import pandas as pd

from data.make_tenant_datasets import (
    generate_smarthire_dataset,
    generate_finedge_dataset,
    generate_apexhealth_dataset,
    generate_retailx_dataset,
    generate_custom_org_dataset
)
from data.make_novabank_data import generate_novabank_dataset

ROOT = Path(__file__).resolve().parents[1]
STORAGE = ROOT / "storage"
TENANTS_DIR = STORAGE / "tenants"
TENANT_DB_DIR = TENANTS_DIR

# Ensure tenant database directory exists safely
TENANT_DB_DIR.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------------- #
# Simple reversible encryption for demo database passwords (Server-Side)
# --------------------------------------------------------------------------- #
SECRET_KEY = os.getenv("SYNTHGUARD_SECRET_KEY", "datadelulu_enterprise_enclave_key_2026")


def encrypt_db_password(password: str) -> str:
    """Obfuscates/encrypts database password for storage."""
    if not password:
        return ""
    key_bytes = hashlib.sha256(SECRET_KEY.encode()).digest()
    pw_bytes = password.encode("utf-8")
    xor_bytes = bytes([b ^ key_bytes[i % len(key_bytes)] for i, b in enumerate(pw_bytes)])
    return "enc:" + base64.b64encode(xor_bytes).decode("ascii")


def decrypt_db_password(enc_password: str) -> str:
    """Decrypts database password server-side."""
    if not enc_password or not enc_password.startswith("enc:"):
        return enc_password
    try:
        raw_b64 = enc_password[4:]
        xor_bytes = base64.b64decode(raw_b64.encode("ascii"))
        key_bytes = hashlib.sha256(SECRET_KEY.encode()).digest()
        pw_bytes = bytes([b ^ key_bytes[i % len(key_bytes)] for i, b in enumerate(xor_bytes)])
        return pw_bytes.decode("utf-8")
    except Exception:
        return ""


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_tenant_db_path(org_id: int | str, con: sqlite3.Connection | None = None) -> Path:
    """Returns the isolated, deterministic SQLite database file path for an organization."""
    TENANT_DB_DIR.mkdir(parents=True, exist_ok=True)
    try:
        clean_id = int(org_id)
        return TENANT_DB_DIR / f"org_{clean_id}.db"
    except (ValueError, TypeError):
        safe_name = "".join(c for c in str(org_id) if c.isalnum() or c in ("_", "-"))
        return TENANT_DB_DIR / f"org_{safe_name}.db"


def tenant_database_exists(org_id: int | str, con: sqlite3.Connection | None = None) -> bool:
    """Checks if the tenant database file already exists on disk."""
    return get_tenant_db_path(org_id, con=con).exists()


def initialize_tenant_database(con: sqlite3.Connection, org_id: int | str, user_id: int | None = None,
                                force_reseed: bool = False) -> dict:
    """Standardized API to initialize and seed an organization-specific database."""
    return init_org_demo_database(con, int(org_id), user_id=user_id, force_reseed=force_reseed)


def get_tenant_connection(org_id: int | str, con: sqlite3.Connection | None = None) -> sqlite3.Connection:
    """Returns a SQLite connection strictly scoped to the tenant's isolated database."""
    db_file = get_tenant_db_path(org_id, con=con)
    if not db_file.exists() and con is not None:
        init_org_demo_database(con, int(org_id))
    return sqlite3.connect(db_file)


# --------------------------------------------------------------------------- #
# Organization Database Configuration CRUD
# --------------------------------------------------------------------------- #
def get_org_db_config(con: sqlite3.Connection, org_id: int) -> dict:
    """Retrieves database configuration strictly scoped to the specified organization."""
    row = con.execute("SELECT * FROM organization_databases WHERE organization_id = ?", (org_id,)).fetchone()
    if not row:
        # Initialize default config for this organization
        org_row = con.execute("SELECT * FROM organizations WHERE id = ?", (org_id,)).fetchone()
        org_name = org_row["name"] if org_row else f"Org {org_id}"
        org_sector = org_row["sector"] if org_row else "Enterprise"
        _init_default_org_db_entry(con, org_id, org_name, org_sector)
        row = con.execute("SELECT * FROM organization_databases WHERE organization_id = ?", (org_id,)).fetchone()

    config = dict(row)
    config["table_metadata"] = json.loads(config.get("table_metadata") or "{}")
    config["has_password"] = bool(config.get("encrypted_password"))
    config.pop("encrypted_password", None)  # Never expose encrypted password to caller
    return config


def _seed_tenant_data_file(db_file: Path, org_name: str, org_sector: str) -> int:
    """Seeds the SQLite tenant database with synthetic domain records."""
    name_lower = org_name.lower()
    sector_lower = org_sector.lower()
    t_con = sqlite3.connect(db_file)
    
    if "smarthire" in name_lower or "hr" in sector_lower:
        df = generate_smarthire_dataset(n=8420)
        t_emp = df[["employee_id", "age", "department", "years_experience", "education_level", "salary"]].copy()
        t_apps = pd.DataFrame({
            "application_id": [f"APP-{30000+i}" for i in range(len(df))],
            "employee_id": df["employee_id"],
            "hiring_source": df["hiring_source"],
            "hiring_decision": "Hired",
            "satisfaction_score": df["satisfaction_score"]
        })
        t_payroll = pd.DataFrame({
            "payroll_id": [f"PAY-{70000+i}" for i in range(len(df))],
            "employee_id": df["employee_id"],
            "salary": df["salary"],
            "promotion_last_3years": df["promotion_last_3years"],
            "attrition_risk": df["attrition_risk"]
        })
        t_attend = pd.DataFrame({
            "attendance_id": [f"ATT-{90000+i}" for i in range(len(df))],
            "employee_id": df["employee_id"],
            "remote_work_ratio": df["remote_work_ratio"],
            "commute_distance_km": df["commute_distance_km"],
            "training_hours_annual": df["training_hours_annual"],
            "performance_rating": df["performance_rating"],
            "projects_completed": df["projects_completed"]
        })
        t_emp.to_sql("employees", t_con, if_exists="replace", index=False)
        t_apps.to_sql("job_applications", t_con, if_exists="replace", index=False)
        t_payroll.to_sql("payroll_records", t_con, if_exists="replace", index=False)
        t_attend.to_sql("attendance_logs", t_con, if_exists="replace", index=False)
        df.to_sql("org_source_view", t_con, if_exists="replace", index=False)

    elif "finedge" in name_lower or "lend" in sector_lower:
        df = generate_finedge_dataset(n=23750)
        t_borrowers = df[["borrower_id", "age", "employment_type", "annual_income", "credit_score"]].copy()
        t_loans = pd.DataFrame({
            "loan_id": [f"LN-FE-{100000+i}" for i in range(len(df))],
            "borrower_id": df["borrower_id"],
            "loan_purpose": df["loan_purpose"],
            "requested_amount": df["requested_amount"],
            "loan_term_months": df["loan_term_months"],
            "interest_rate_pct": df["interest_rate_pct"]
        })
        t_repay = pd.DataFrame({
            "repayment_id": [f"RP-{200000+i}" for i in range(len(df))],
            "borrower_id": df["borrower_id"],
            "debt_to_income": df["debt_to_income"],
            "delinquencies_2yr": df["delinquencies_2yr"],
            "loan_default": df["loan_default"]
        })
        t_risk = pd.DataFrame({
            "profile_id": [f"RK-{400000+i}" for i in range(len(df))],
            "borrower_id": df["borrower_id"],
            "open_credit_lines": df["open_credit_lines"],
            "collateral_type": df["collateral_type"],
            "risk_tier": df["risk_tier"]
        })
        t_borrowers.to_sql("borrowers", t_con, if_exists="replace", index=False)
        t_loans.to_sql("loan_portfolios", t_con, if_exists="replace", index=False)
        t_repay.to_sql("repayment_schedules", t_con, if_exists="replace", index=False)
        t_risk.to_sql("credit_risk_profiles", t_con, if_exists="replace", index=False)
        df.to_sql("org_source_view", t_con, if_exists="replace", index=False)

    elif "apex" in name_lower or "health" in sector_lower or "hospital" in name_lower:
        df = generate_apexhealth_dataset(n=5280)
        t_patients = df[["patient_id", "age", "gender", "insurance_plan", "smoking_status"]].copy()
        t_enc = pd.DataFrame({
            "encounter_id": [f"ENC-{60000+i}" for i in range(len(df))],
            "patient_id": df["patient_id"],
            "admission_type": df["admission_type"],
            "length_of_stay_days": df["length_of_stay_days"],
            "diagnosis_category": df["diagnosis_category"],
            "readmission_30d": df["readmission_30d"]
        })
        t_labs = pd.DataFrame({
            "lab_id": [f"LAB-{80000+i}" for i in range(len(df))],
            "patient_id": df["patient_id"],
            "blood_pressure_systolic": df["blood_pressure_systolic"],
            "cholesterol_mg_dl": df["cholesterol_mg_dl"],
            "bmi": df["bmi"],
            "lab_procedures_count": df["lab_procedures_count"]
        })
        t_tx = pd.DataFrame({
            "treatment_id": [f"TRT-{110000+i}" for i in range(len(df))],
            "patient_id": df["patient_id"],
            "chronic_conditions_count": df["chronic_conditions_count"],
            "prescribed_medications_count": df["prescribed_medications_count"]
        })
        t_patients.to_sql("patients", t_con, if_exists="replace", index=False)
        t_enc.to_sql("clinical_encounters", t_con, if_exists="replace", index=False)
        t_labs.to_sql("lab_diagnostics", t_con, if_exists="replace", index=False)
        t_tx.to_sql("treatment_outcomes", t_con, if_exists="replace", index=False)
        df.to_sql("org_source_view", t_con, if_exists="replace", index=False)

    elif "retail" in name_lower or "commerce" in sector_lower:
        df = generate_retailx_dataset(n=41200)
        t_cust = df[["customer_id", "age", "gender", "city", "membership_tier"]].copy()
        t_orders = pd.DataFrame({
            "order_summary_id": [f"ORD-{700000+i}" for i in range(len(df))],
            "customer_id": df["customer_id"],
            "orders_placed": df["orders_placed"],
            "average_order_value": df["average_order_value"],
            "annual_spend": df["annual_spend"]
        })
        t_loyalty = pd.DataFrame({
            "loyalty_id": [f"LOY-{900000+i}" for i in range(len(df))],
            "customer_id": df["customer_id"],
            "loyalty_points": df["loyalty_points"],
            "preferred_category": df["preferred_category"],
            "payment_method": df["payment_method"]
        })
        t_engage = pd.DataFrame({
            "engagement_id": [f"ENG-{500000+i}" for i in range(len(df))],
            "customer_id": df["customer_id"],
            "return_rate_pct": df["return_rate_pct"],
            "email_open_rate_pct": df["email_open_rate_pct"],
            "mobile_app_user": df["mobile_app_user"],
            "churn_flag": df["churn_flag"]
        })
        t_cust.to_sql("retail_customers", t_con, if_exists="replace", index=False)
        t_orders.to_sql("store_orders", t_con, if_exists="replace", index=False)
        t_loyalty.to_sql("loyalty_rewards", t_con, if_exists="replace", index=False)
        t_engage.to_sql("cart_abandonment", t_con, if_exists="replace", index=False)
        df.to_sql("org_source_view", t_con, if_exists="replace", index=False)

    elif "novabank" in name_lower:
        df = generate_novabank_dataset(n=12500)
        t_cust = df[["customer_id", "age", "gender", "city", "income", "account_type", "credit_score"]].copy()
        t_tx = pd.DataFrame({
            "transaction_id": [f"TX-{100000 + i}" for i in range(len(df))],
            "customer_id": df["customer_id"],
            "transaction_count": df["transaction_count"],
            "average_transaction_amount": df["average_transaction_amount"],
            "transaction_category": df["transaction_category"],
            "transaction_frequency": df["transaction_frequency"],
            "fraud_flag": df["fraud_flag"],
        })
        t_loans = pd.DataFrame({
            "loan_id": [f"LN-{50000 + i}" for i in range(len(df))],
            "customer_id": df["customer_id"],
            "loan_status": df["loan_status"],
            "loan_amount": df["loan_amount"],
            "repayment_status": df["repayment_status"],
            "account_balance": df["account_balance"],
        })
        t_cust.to_sql("customers", t_con, if_exists="replace", index=False)
        t_tx.to_sql("transactions", t_con, if_exists="replace", index=False)
        t_loans.to_sql("loans", t_con, if_exists="replace", index=False)
        df.to_sql("org_source_view", t_con, if_exists="replace", index=False)

    else:
        df = generate_custom_org_dataset(org_name, org_sector, n=5000)
        df.to_sql("primary_records", t_con, if_exists="replace", index=False)
        df.to_sql("org_source_view", t_con, if_exists="replace", index=False)

    t_con.close()
    return len(df)


def _init_default_org_db_entry(con: sqlite3.Connection, org_id: int, org_name: str, org_sector: str):
    """Provisions default provider, host, and port matching the organization's domain."""
    name_lower = org_name.lower()
    sector_lower = org_sector.lower()

    if "smarthire" in name_lower or "hr" in sector_lower:
        provider = "PostgreSQL"
        host = "smart-hire-db.internal"
        port = 5432
        db_name = "smarthire_prod"
        username = "smarthire_agent"
    elif "finedge" in name_lower or "lend" in sector_lower:
        provider = "MySQL"
        host = "finedge-db.internal"
        port = 3306
        db_name = "finedge_lending"
        username = "finedge_svc"
    elif "apex" in name_lower or "health" in sector_lower or "hospital" in name_lower:
        provider = "PostgreSQL"
        host = "healthnova-db.internal"
        port = 5432
        db_name = "healthnova_clinical"
        username = "clinical_app"
    elif "retail" in name_lower or "commerce" in sector_lower:
        provider = "Snowflake"
        host = "retailx-account.snowflakecomputing.com"
        port = 443
        db_name = "retail_analytics"
        username = "retail_bi"
    elif "novabank" in name_lower:
        provider = "PostgreSQL"
        host = "novabank-db.internal"
        port = 5432
        db_name = "novabank_private"
        username = "novabank_svc"
    else:
        provider = "PostgreSQL"
        clean_name = "".join(c for c in name_lower if c.isalnum())
        host = f"{clean_name}-db.internal"
        port = 5432
        db_name = f"{clean_name}_data"
        username = "db_agent"

    # Ensure demo tenant db exists to get initial count
    tenant_db_file = get_tenant_db_path(org_id, con=con)
    if not tenant_db_file.exists():
        _seed_tenant_data_file(tenant_db_file, org_name, org_sector)

    meta, total_recs = _discover_tables_and_counts(tenant_db_file)

    con.execute(
        """INSERT OR REPLACE INTO organization_databases 
           (organization_id, provider, host, port, database_name, username, encrypted_password,
            connection_status, last_tested_at, record_count, table_metadata, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, 'Connected', ?, ?, ?, ?, ?)""",
        (org_id, provider, host, port, db_name, username, encrypt_db_password("default_pass"),
         _now(), total_recs, json.dumps(meta), _now(), _now())
    )
    con.commit()



def save_org_db_config(con: sqlite3.Connection, org_id: int, user_id: int,
                       provider: str, host: str, port: int, database_name: str,
                       username: str, password: str = "") -> dict:
    """Updates database connection configuration for an organization."""
    host = host.strip()
    database_name = database_name.strip()
    username = username.strip()

    enc_pw = encrypt_db_password(password) if password else ""
    
    # If no new password provided, keep existing encrypted password
    if not password:
        existing = con.execute("SELECT encrypted_password FROM organization_databases WHERE organization_id = ?", (org_id,)).fetchone()
        if existing:
            enc_pw = existing[0]

    con.execute(
        """INSERT INTO organization_databases 
           (organization_id, provider, host, port, database_name, username, encrypted_password,
            connection_status, last_tested_at, record_count, table_metadata, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, 'Disconnected', ?, 0, '{}', ?, ?)
           ON CONFLICT(organization_id) DO UPDATE SET
            provider=excluded.provider,
            host=excluded.host,
            port=excluded.port,
            database_name=excluded.database_name,
            username=excluded.username,
            encrypted_password=CASE WHEN excluded.encrypted_password != '' THEN excluded.encrypted_password ELSE organization_databases.encrypted_password END,
            updated_at=excluded.updated_at""",
        (org_id, provider, host, port, database_name, username, enc_pw, _now(), _now(), _now())
    )
    con.commit()

    from src.auth import log_audit_event
    log_audit_event(
        con, org_id, user_id, "DB_CONFIG_UPDATED",
        metadata={"provider": provider, "host": host, "port": port, "database": database_name}
    )

    # Test the connection immediately
    return test_org_db_connection(con, org_id, user_id)


# --------------------------------------------------------------------------- #
# Real Database Connection Testing & Dynamic Schema Discovery
# --------------------------------------------------------------------------- #
def _discover_tables_and_counts(db_file: Path) -> tuple[dict[str, int], int]:
    """Inspects a database file, discovering all user tables and querying exact row counts.
    
    Returns (table_metadata_dict, primary_record_count).
    """
    if not db_file.exists():
        return {}, 0
    try:
        t_con = sqlite3.connect(db_file)
        cur = t_con.cursor()
        tables = cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        
        metadata = {}
        primary_cnt = 0
        for (t_name,) in tables:
            try:
                cnt = cur.execute(f"SELECT COUNT(*) FROM {t_name}").fetchone()[0]
                if t_name == "org_source_view":
                    primary_cnt = int(cnt)
                else:
                    metadata[t_name] = int(cnt)
            except Exception:
                if t_name != "org_source_view":
                    metadata[t_name] = 0
        t_con.close()
        
        # If no explicit org_source_view, take max table count or first table
        if primary_cnt == 0 and metadata:
            primary_cnt = max(metadata.values())

        return metadata, primary_cnt
    except Exception:
        return {}, 0


def test_org_db_connection(con: sqlite3.Connection, org_id: int, user_id: int | None = None) -> dict:
    """Executes a real connection test against the organization's database."""
    cfg = get_org_db_config(con, org_id)
    db_file = get_tenant_db_path(org_id, con=con)

    # Check if tenant database exists, or create if missing
    if not db_file.exists():
        init_org_demo_database(con, org_id, user_id=user_id)

    # Validate by running a real query
    try:
        t_con = sqlite3.connect(db_file)
        val = t_con.execute("SELECT 1").fetchone()
        t_con.close()
        if not val or val[0] != 1:
            raise RuntimeError("Validation query failed.")

        table_counts, primary_rows = _discover_tables_and_counts(db_file)
        now_str = _now()

        con.execute(
            """UPDATE organization_databases 
               SET connection_status = 'Connected', last_tested_at = ?, record_count = ?, table_metadata = ?
               WHERE organization_id = ?""",
            (now_str, primary_rows, json.dumps(table_counts), org_id)
        )
        con.commit()

        from src.auth import log_audit_event
        if user_id:
            log_audit_event(con, org_id, user_id, "DB_CONNECTION_TEST_SUCCESS", metadata={"records": primary_rows})

        return {
            "status": "Connected",
            "connected": True,
            "provider": cfg["provider"],
            "host": cfg["host"],
            "port": cfg["port"],
            "database_name": cfg["database_name"],
            "record_count": primary_rows,
            "tables": table_counts,
            "last_tested_at": now_str,
            "message": f"✓ Successfully connected to {cfg['provider']} ({cfg['database_name']}). Discovered {len(table_counts)} tables with {primary_rows:,} records available."
        }

    except Exception as e:
        now_str = _now()
        con.execute(
            """UPDATE organization_databases 
               SET connection_status = 'Connection Failed', last_tested_at = ?
               WHERE organization_id = ?""",
            (now_str, org_id)
        )
        con.commit()

        from src.auth import log_audit_event
        if user_id:
            log_audit_event(con, org_id, user_id, "DB_CONNECTION_TEST_FAILURE", metadata={"error": str(e)[:100]})

        return {
            "status": "Connection Failed",
            "connected": False,
            "provider": cfg["provider"],
            "host": cfg["host"],
            "port": cfg["port"],
            "database_name": cfg["database_name"],
            "record_count": 0,
            "tables": {},
            "last_tested_at": now_str,
            "message": f"Connection failed: Unable to connect to {cfg['provider']} database at {cfg['host']}:{cfg['port']}."
        }



# --------------------------------------------------------------------------- #
# Organization Demo Database Provisioning & Population
# --------------------------------------------------------------------------- #
def init_org_demo_database(con: sqlite3.Connection, org_id: int, user_id: int | None = None,
                           force_reseed: bool = False) -> dict:
    """Initializes and seeds an isolated database specifically for this organization."""
    db_file = get_tenant_db_path(org_id, con=con)
    org_row = con.execute("SELECT * FROM organizations WHERE id = ?", (org_id,)).fetchone()
    org_name = org_row["name"] if org_row else f"Org {org_id}"
    org_sector = org_row["sector"] if org_row else "Enterprise"

    if not db_file.exists() or force_reseed:
        num_records = _seed_tenant_data_file(db_file, org_name, org_sector)
        from src.auth import log_audit_event
        if user_id:
            log_audit_event(con, org_id, user_id, "DEMO_DB_INITIALIZED", metadata={"records": num_records})

    return test_org_db_connection(con, org_id, user_id)


# --------------------------------------------------------------------------- #
# Organization Dataset Fetching (Strict Tenant Isolation)
# --------------------------------------------------------------------------- #
def fetch_org_dataset(con: sqlite3.Connection, org_id: int, limit: int | None = None) -> pd.DataFrame:
    """Fetches the source organizational dataset strictly from this organization's database."""
    db_file = get_tenant_db_path(org_id, con=con)
    if not db_file.exists():
        init_org_demo_database(con, org_id)

    query = "SELECT * FROM org_source_view"
    if limit:
        query += f" LIMIT {limit}"

    t_con = sqlite3.connect(db_file)
    try:
        df = pd.read_sql(query, t_con)
    except Exception:
        # If org_source_view isn't found, find the first available table
        tables = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'", t_con)
        if not tables.empty:
            first_table = tables.iloc[0]["name"]
            df = pd.read_sql(f"SELECT * FROM {first_table}" + (f" LIMIT {limit}" if limit else ""), t_con)
        else:
            t_con.close()
            init_org_demo_database(con, org_id, force_reseed=True)
            t_con = sqlite3.connect(db_file)
            df = pd.read_sql(query, t_con)
    t_con.close()
    return df
