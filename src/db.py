"""Data Delulu — Multi-Tenant SQLite Database Storage & Tenant Isolation Layer.

Design rules:
- REAL data is never stored in the database. Only SHA-256 fingerprint, counts, synthetic output,
  and differential privacy scorecards are kept.
- Strict tenant isolation: Every query for jobs, metrics, and audit records MUST be scoped
  by organization_id.
- Direct object reference (IDOR) protection: Requests for a resource from another organization
  are rejected at the database query layer.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STORAGE = ROOT / "storage"
DB_PATH = STORAGE / "datadelulu.db"
SYNTH_DIR = STORAGE / "synthetic"

SCHEMA = """
CREATE TABLE IF NOT EXISTS organizations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    sector TEXT NOT NULL,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL REFERENCES organizations(id),
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'ANALYST',
    created_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL REFERENCES organizations(id),
    created_by INTEGER REFERENCES users(id),
    dataset_name TEXT NOT NULL,
    dataset_fingerprint TEXT NOT NULL,
    target TEXT NOT NULL,
    n_rows_real INTEGER NOT NULL,
    n_rows_synth INTEGER NOT NULL,
    n_columns INTEGER NOT NULL,
    epsilon REAL NOT NULL,
    mechanism TEXT NOT NULL,
    synthetic_path TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS metrics (
    job_id INTEGER PRIMARY KEY REFERENCES jobs(id),
    organization_id INTEGER NOT NULL REFERENCES organizations(id),
    utility_pct REAL, privacy_pct REAL, guaranteed_privacy_pct REAL,
    attack_pct REAL, attack_bound_pct REAL,
    exact_copy_pct REAL, baseline_copy_pct REAL, similarity_pct REAL,
    real_acc REAL, synth_acc REAL, baseline_acc REAL,
    tests_passed INTEGER, tests_total INTEGER,
    column_similarity TEXT,
    real_metrics TEXT,
    synth_metrics TEXT
);

CREATE TABLE IF NOT EXISTS test_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES jobs(id),
    organization_id INTEGER NOT NULL REFERENCES organizations(id),
    name TEXT NOT NULL, passed INTEGER NOT NULL, detail TEXT
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL REFERENCES organizations(id),
    user_id INTEGER REFERENCES users(id),
    action TEXT NOT NULL,
    job_id INTEGER REFERENCES jobs(id),
    timestamp TEXT NOT NULL,
    metadata TEXT
);

CREATE TABLE IF NOT EXISTS secure_shares (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL REFERENCES organizations(id),
    job_id INTEGER NOT NULL REFERENCES jobs(id),
    token TEXT UNIQUE NOT NULL,
    created_by INTEGER REFERENCES users(id),
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    is_revoked INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS organization_databases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL UNIQUE REFERENCES organizations(id),
    provider TEXT NOT NULL,
    host TEXT NOT NULL,
    port INTEGER NOT NULL,
    database_name TEXT NOT NULL,
    username TEXT NOT NULL,
    encrypted_password TEXT NOT NULL,
    connection_status TEXT NOT NULL DEFAULT 'Connected',
    last_tested_at TEXT,
    record_count INTEGER NOT NULL DEFAULT 0,
    table_metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS organization_policies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL UNIQUE REFERENCES organizations(id),
    allowed_tables TEXT NOT NULL DEFAULT '[]',
    blocked_tables TEXT NOT NULL DEFAULT '[]',
    allowed_columns TEXT NOT NULL DEFAULT '[]',
    blocked_columns TEXT NOT NULL DEFAULT '[]',
    epsilon_limit REAL NOT NULL DEFAULT 5.0,
    minimum_utility REAL NOT NULL DEFAULT 80.0,
    raw_data_export INTEGER NOT NULL DEFAULT 0,
    synthetic_data_export INTEGER NOT NULL DEFAULT 1,
    approval_required INTEGER NOT NULL DEFAULT 0,
    max_records_per_job INTEGER NOT NULL DEFAULT 500000,
    retention_policy TEXT NOT NULL DEFAULT 'in-memory-only',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS organization_agents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL UNIQUE REFERENCES organizations(id),
    agent_id TEXT UNIQUE NOT NULL,
    agent_secret_hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    version TEXT NOT NULL DEFAULT '2.5.0-enclave',
    environment TEXT NOT NULL DEFAULT 'Customer Private VPC Enclave',
    last_heartbeat TEXT NOT NULL,
    raw_records_processed INTEGER NOT NULL DEFAULT 0,
    raw_records_transmitted INTEGER NOT NULL DEFAULT 0,
    raw_bytes_transmitted INTEGER NOT NULL DEFAULT 0,
    synthetic_records_generated INTEGER NOT NULL DEFAULT 0,
    jobs_executed INTEGER NOT NULL DEFAULT 0,
    jobs_blocked INTEGER NOT NULL DEFAULT 0,
    policy_violations INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def fingerprint(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()
def _migrate_schema(con: sqlite3.Connection) -> None:
    """Ensures newly added columns exist in older database files without breaking."""
    def _add_col_if_missing(table: str, col: str, col_type: str):
        try:
            cols = {r[1] for r in con.execute(f"PRAGMA table_info({table})").fetchall()}
            if col not in cols:
                con.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
                con.commit()
        except Exception:
            pass

    _add_col_if_missing("organizations", "status", "TEXT NOT NULL DEFAULT 'active'")
    _add_col_if_missing("jobs", "organization_id", "INTEGER NOT NULL DEFAULT 1")
    _add_col_if_missing("jobs", "created_by", "INTEGER REFERENCES users(id)")
    _add_col_if_missing("jobs", "release_status", "TEXT NOT NULL DEFAULT 'APPROVED'")
    _add_col_if_missing("jobs", "approved_by", "INTEGER REFERENCES users(id)")
    _add_col_if_missing("metrics", "organization_id", "INTEGER")
    _add_col_if_missing("metrics", "real_metrics", "TEXT")
    _add_col_if_missing("metrics", "synth_metrics", "TEXT")
    _add_col_if_missing("test_results", "organization_id", "INTEGER")
    try:
        con.execute(
            """UPDATE metrics 
               SET organization_id = (SELECT organization_id FROM jobs WHERE jobs.id = metrics.job_id) 
               WHERE typeof(organization_id) = 'text' OR organization_id IS NULL OR organization_id = 0"""
        )
        con.commit()
    except Exception:
        pass


def connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Connect to the Data Delulu SQLite database and ensure schema & demo tenants exist."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    _migrate_schema(con)
    _seed_demo_accounts(con)
    return con


def _seed_demo_accounts(con: sqlite3.Connection) -> None:
    """Seeds default demo organizations, securely hashed demo user accounts, and isolated DBs."""
    from src.auth import hash_password

    demo_tenants = [
        {
            "name": "SmartHire InfoTech",
            "sector": "HR & Workforce Tech",
            "users": [
                {
                    "name": "Adam Smith",
                    "email": "adam@gmail.com",
                    "password": os.getenv("DEMO_SMARTHIRE_PASSWORD", "SmartHire2026!"),
                    "role": "ADMIN"
                },
                {
                    "name": "SmartHire Admin",
                    "email": "admin@smarthire.demo",
                    "password": os.getenv("DEMO_SMARTHIRE_PASSWORD", "SmartHire2026!"),
                    "role": "ADMIN"
                }
            ]
        },
        {
            "name": "FinEdge Lending",
            "sector": "Fintech / Lending",
            "users": [
                {
                    "name": "FinEdge Admin",
                    "email": "admin@finedge.demo",
                    "password": os.getenv("DEMO_FINEDGE_PASSWORD", "FinEdge2026!"),
                    "role": "ADMIN"
                },
                {
                    "name": "FinEdge Auditor",
                    "email": "viewer@finedge.demo",
                    "password": os.getenv("DEMO_FINEDGE_PASSWORD", "FinEdge2026!"),
                    "role": "VIEWER"
                }
            ]
        },
        {
            "name": "Apex Health Systems",
            "sector": "Healthcare & Clinical",
            "users": [
                {
                    "name": "Apex Health Admin",
                    "email": "admin@healthcare.demo",
                    "password": os.getenv("DEMO_HEALTHCARE_PASSWORD", "Health2026!"),
                    "role": "ADMIN"
                }
            ]
        },
        {
            "name": "RetailX Analytics",
            "sector": "E-Commerce & Retail",
            "users": [
                {
                    "name": "RetailX Admin",
                    "email": "admin@retailx.demo",
                    "password": os.getenv("DEMO_RETAILX_PASSWORD", "RetailX2026!"),
                    "role": "ADMIN"
                }
            ]
        },
        {
            "name": "NovaBank — Demo Environment",
            "sector": "Banking / FinTech",
            "users": [
                {
                    "name": "NovaBank Admin",
                    "email": "admin@novabank.demo",
                    "password": os.getenv("DEMO_NOVABANK_PASSWORD", "NovaBank2026!"),
                    "role": "ADMIN"
                },
                {
                    "name": "NovaBank ML Analyst",
                    "email": "analyst@novabank.demo",
                    "password": os.getenv("DEMO_NOVABANK_PASSWORD", "NovaBank2026!"),
                    "role": "ANALYST"
                }
            ]
        }
    ]

    from src.org_database import _init_default_org_db_entry

    for t in demo_tenants:
        org_row = con.execute("SELECT id FROM organizations WHERE name = ?", (t["name"],)).fetchone()
        if not org_row:
            cur = con.execute(
                "INSERT INTO organizations (name, sector, created_at, status) VALUES (?, ?, ?, 'active')",
                (t["name"], t["sector"], _now())
            )
            org_id = cur.lastrowid
        else:
            org_id = org_row["id"]

        for u in t["users"]:
            pw_hash = hash_password(u["password"])
            user_row = con.execute("SELECT id FROM users WHERE email = ?", (u["email"],)).fetchone()
            if not user_row:
                con.execute(
                    """INSERT INTO users (organization_id, name, email, password_hash, role, created_at, status)
                       VALUES (?, ?, ?, ?, ?, ?, 'active')""",
                    (org_id, u["name"], u["email"], pw_hash, u["role"], _now())
                )
            else:
                con.execute("UPDATE users SET organization_id = ?, password_hash = ? WHERE id = ?", (org_id, pw_hash, user_row["id"]))

        # Ensure database configuration exists for this organization
        db_cfg = con.execute("SELECT id FROM organization_databases WHERE organization_id = ?", (org_id,)).fetchone()
        if not db_cfg:
            try:
                _init_default_org_db_entry(con, org_id, t["name"], t["sector"])
            except Exception:
                pass

        # Ensure organization policy exists
        pol_row = con.execute("SELECT id FROM organization_policies WHERE organization_id = ?", (org_id,)).fetchone()
        if not pol_row:
            from data_delulu_agent.policy_engine import OrganizationPolicy
            default_pol = OrganizationPolicy(organization_id=org_id)
            con.execute(
                """INSERT INTO organization_policies 
                   (organization_id, allowed_tables, blocked_tables, allowed_columns, blocked_columns,
                    epsilon_limit, minimum_utility, raw_data_export, synthetic_data_export,
                    approval_required, max_records_per_job, retention_policy, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?)""",
                (org_id, json.dumps(default_pol.allowed_tables), json.dumps(default_pol.blocked_tables),
                 json.dumps(default_pol.allowed_columns), json.dumps(default_pol.blocked_columns),
                 default_pol.epsilon_limit, default_pol.minimum_utility, int(default_pol.synthetic_data_export),
                 int(default_pol.approval_required), default_pol.max_records_per_job,
                 default_pol.retention_policy, _now(), _now())
            )

        # Ensure local agent registration exists
        agent_row = con.execute("SELECT id FROM organization_agents WHERE organization_id = ?", (org_id,)).fetchone()
        if not agent_row:
            agent_id = f"AGENT-ORG-{org_id:04d}"
            con.execute(
                """INSERT INTO organization_agents 
                   (organization_id, agent_id, agent_secret_hash, status, version, environment,
                    last_heartbeat, raw_records_processed, raw_records_transmitted, raw_bytes_transmitted,
                    synthetic_records_generated, jobs_executed, jobs_blocked, policy_violations, created_at, updated_at)
                   VALUES (?, ?, ?, 'ACTIVE', '2.5.0-enclave', 'Customer Private VPC Enclave', ?, 0, 0, 0, 0, 0, 0, 0, ?, ?)""",
                (org_id, agent_id, hash_password("enclave_secret_2026"), _now(), _now(), _now())
            )

    con.commit()


def add_organization(con: sqlite3.Connection, name: str, sector: str) -> int:
    name = name.strip()
    if not name:
        raise ValueError("Organization name cannot be empty.")
    cur = con.execute("INSERT INTO organizations (name, sector, created_at, status) VALUES (?, ?, ?, 'active')",
                      (name, sector, _now()))
    con.commit()
    return cur.lastrowid


def list_organizations(con: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in con.execute("SELECT * FROM organizations WHERE status = 'active' ORDER BY name")]


# --------------------------------------------------------------------------- #
# Organization Policy & Agent Management
# --------------------------------------------------------------------------- #
def get_org_policy(con: sqlite3.Connection, org_id: int) -> dict:
    """Retrieves the customer organization governance policy."""
    row = con.execute("SELECT * FROM organization_policies WHERE organization_id = ?", (org_id,)).fetchone()
    if not row:
        from data_delulu_agent.policy_engine import OrganizationPolicy
        p = OrganizationPolicy(organization_id=org_id)
        con.execute(
            """INSERT INTO organization_policies 
               (organization_id, allowed_tables, blocked_tables, allowed_columns, blocked_columns,
                epsilon_limit, minimum_utility, raw_data_export, synthetic_data_export,
                approval_required, max_records_per_job, retention_policy, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?)""",
            (org_id, json.dumps(p.allowed_tables), json.dumps(p.blocked_tables),
             json.dumps(p.allowed_columns), json.dumps(p.blocked_columns),
             p.epsilon_limit, p.minimum_utility, int(p.synthetic_data_export),
             int(p.approval_required), p.max_records_per_job, p.retention_policy, _now(), _now())
        )
        con.commit()
        row = con.execute("SELECT * FROM organization_policies WHERE organization_id = ?", (org_id,)).fetchone()

    d = dict(row)
    d["allowed_tables"] = json.loads(d.get("allowed_tables") or "[]")
    d["blocked_tables"] = json.loads(d.get("blocked_tables") or "[]")
    d["allowed_columns"] = json.loads(d.get("allowed_columns") or "[]")
    d["blocked_columns"] = json.loads(d.get("blocked_columns") or "[]")
    d["raw_data_export"] = False  # Hard invariant: ALWAYS False
    return d


def save_org_policy(con: sqlite3.Connection, org_id: int, policy_dict: dict, user_id: int | None = None) -> None:
    """Updates customer organization governance policy."""
    now_str = _now()
    con.execute(
        """INSERT INTO organization_policies 
           (organization_id, allowed_tables, blocked_tables, allowed_columns, blocked_columns,
            epsilon_limit, minimum_utility, raw_data_export, synthetic_data_export,
            approval_required, max_records_per_job, retention_policy, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(organization_id) DO UPDATE SET
            allowed_tables=excluded.allowed_tables,
            blocked_tables=excluded.blocked_tables,
            allowed_columns=excluded.allowed_columns,
            blocked_columns=excluded.blocked_columns,
            epsilon_limit=excluded.epsilon_limit,
            minimum_utility=excluded.minimum_utility,
            synthetic_data_export=excluded.synthetic_data_export,
            approval_required=excluded.approval_required,
            max_records_per_job=excluded.max_records_per_job,
            retention_policy=excluded.retention_policy,
            updated_at=excluded.updated_at""",
        (
            org_id,
            json.dumps(policy_dict.get("allowed_tables", [])),
            json.dumps(policy_dict.get("blocked_tables", [])),
            json.dumps(policy_dict.get("allowed_columns", [])),
            json.dumps(policy_dict.get("blocked_columns", [])),
            float(policy_dict.get("epsilon_limit", 5.0)),
            float(policy_dict.get("minimum_utility", 80.0)),
            int(policy_dict.get("synthetic_data_export", True)),
            int(policy_dict.get("approval_required", False)),
            int(policy_dict.get("max_records_per_job", 500_000)),
            str(policy_dict.get("retention_policy", "in-memory-only")),
            now_str, now_str
        )
    )
    from src.auth import log_audit_event
    if user_id:
        log_audit_event(con, org_id, user_id, "ORGANIZATION_POLICY_UPDATED", metadata={"epsilon_limit": policy_dict.get("epsilon_limit")})
    con.commit()


def get_org_agent(con: sqlite3.Connection, org_id: int) -> dict:
    """Retrieves local agent telemetry and kill switch state."""
    row = con.execute("SELECT * FROM organization_agents WHERE organization_id = ?", (org_id,)).fetchone()
    if not row:
        agent_id = f"AGENT-ORG-{org_id:04d}"
        from src.auth import hash_password
        con.execute(
            """INSERT INTO organization_agents 
               (organization_id, agent_id, agent_secret_hash, status, version, environment,
                last_heartbeat, raw_records_processed, raw_records_transmitted, raw_bytes_transmitted,
                synthetic_records_generated, jobs_executed, jobs_blocked, policy_violations, created_at, updated_at)
               VALUES (?, ?, ?, 'ACTIVE', '2.5.0-enclave', 'Customer Private VPC Enclave', ?, 0, 0, 0, 0, 0, 0, 0, ?, ?)""",
            (org_id, agent_id, hash_password("enclave_secret_2026"), _now(), _now(), _now())
        )
        con.commit()
        row = con.execute("SELECT * FROM organization_agents WHERE organization_id = ?", (org_id,)).fetchone()
    return dict(row)


def set_agent_status(con: sqlite3.Connection, org_id: int, is_active: bool, user_id: int | None = None) -> None:
    """Controls the local agent kill switch."""
    status_str = "ACTIVE" if is_active else "DISABLED"
    con.execute(
        "UPDATE organization_agents SET status = ?, updated_at = ? WHERE organization_id = ?",
        (status_str, _now(), org_id)
    )
    from src.auth import log_audit_event
    if user_id:
        action = "AGENT_ACTIVATED" if is_active else "AGENT_KILL_SWITCH_TRIGGERED"
        log_audit_event(con, org_id, user_id, action, metadata={"status": status_str})
    con.commit()


def update_agent_telemetry(con: sqlite3.Connection, org_id: int, raw_proc: int = 0,
                           synth_gen: int = 0, jobs_inc: int = 0, blocked_inc: int = 0,
                           violations_inc: int = 0) -> None:
    """Updates enclave telemetry counters."""
    con.execute(
        """UPDATE organization_agents SET
           raw_records_processed = raw_records_processed + ?,
           synthetic_records_generated = synthetic_records_generated + ?,
           jobs_executed = jobs_executed + ?,
           jobs_blocked = jobs_blocked + ?,
           policy_violations = policy_violations + ?,
           last_heartbeat = ?,
           updated_at = ?
           WHERE organization_id = ?""",
        (raw_proc, synth_gen, jobs_inc, blocked_inc, violations_inc, _now(), _now(), org_id)
    )
    con.commit()


def approve_job_release(con: sqlite3.Connection, org_id: int, job_id: int, user_id: int) -> None:
    """Approves a pending synthetic dataset release."""
    con.execute(
        "UPDATE jobs SET release_status = 'APPROVED', approved_by = ? WHERE id = ? AND organization_id = ?",
        (user_id, job_id, org_id)
    )
    from src.auth import log_audit_event
    log_audit_event(con, org_id, user_id, "RELEASE_APPROVED", job_id=job_id)
    con.commit()


def reject_job_release(con: sqlite3.Connection, org_id: int, job_id: int, user_id: int) -> None:
    """Rejects a pending synthetic dataset release."""
    con.execute(
        "UPDATE jobs SET release_status = 'REJECTED', approved_by = ? WHERE id = ? AND organization_id = ?",
        (user_id, job_id, org_id)
    )
    from src.auth import log_audit_event
    log_audit_event(con, org_id, user_id, "RELEASE_REJECTED", job_id=job_id)
    con.commit()


# --------------------------------------------------------------------------- #
# Organization-Scoped Job & Metrics Storage (Tenant Isolated)
# --------------------------------------------------------------------------- #
def save_job(con: sqlite3.Connection, org_id: int, dataset_name: str, dataset_fp: str,
             target: str, n_rows_real: int, synth_df, epsilon: float, accounting: dict,
             score: dict, created_by: int | None = None, release_status: str = "APPROVED",
             synth_dir: Path = SYNTH_DIR) -> int:
    """Saves a synthetic release with strict organization association."""
    cols = {r[1] for r in con.execute("PRAGMA table_info(jobs)").fetchall()}
    if "org_id" in cols and "organization_id" in cols:
        cur = con.execute(
            """INSERT INTO jobs (organization_id, org_id, created_by, dataset_name, dataset_fingerprint, target,
               n_rows_real, n_rows_synth, n_columns, epsilon, mechanism, synthetic_path, release_status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '', ?, ?)""",
            (org_id, org_id, created_by, dataset_name, dataset_fp, target, n_rows_real, len(synth_df),
             synth_df.shape[1], epsilon, accounting["mechanism"], release_status, _now())
        )
    elif "org_id" in cols:
        cur = con.execute(
            """INSERT INTO jobs (org_id, created_by, dataset_name, dataset_fingerprint, target,
               n_rows_real, n_rows_synth, n_columns, epsilon, mechanism, synthetic_path, release_status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '', ?, ?)""",
            (org_id, created_by, dataset_name, dataset_fp, target, n_rows_real, len(synth_df),
             synth_df.shape[1], epsilon, accounting["mechanism"], release_status, _now())
        )
    else:
        cur = con.execute(
            """INSERT INTO jobs (organization_id, created_by, dataset_name, dataset_fingerprint, target,
               n_rows_real, n_rows_synth, n_columns, epsilon, mechanism, synthetic_path, release_status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '', ?, ?)""",
            (org_id, created_by, dataset_name, dataset_fp, target, n_rows_real, len(synth_df),
             synth_df.shape[1], epsilon, accounting["mechanism"], release_status, _now())
        )
    job_id = cur.lastrowid
    synth_dir.mkdir(parents=True, exist_ok=True)
    path = synth_dir / f"org_{org_id}_job_{job_id}.csv"
    synth_df.to_csv(path, index=False)

    con.execute("UPDATE jobs SET synthetic_path = ? WHERE id = ?", (str(path), job_id))
    con.execute(
        """INSERT OR REPLACE INTO metrics 
           (job_id, organization_id, utility_pct, privacy_pct, guaranteed_privacy_pct,
            attack_pct, attack_bound_pct, exact_copy_pct, baseline_copy_pct, similarity_pct,
            real_acc, synth_acc, baseline_acc, tests_passed, tests_total,
            column_similarity, real_metrics, synth_metrics)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (job_id, org_id, score["utility_pct"], score["privacy_pct"], score["guaranteed_privacy_pct"],
         score["attack_pct"], score["attack_bound_pct"], score["exact_copy_pct"],
         score["baseline_copy_pct"], score["similarity_pct"], score["real_acc"], score["synth_acc"],
         score["baseline_acc"], score["tests_passed"], score["tests_total"],
         json.dumps(score.get("column_similarity", {})),
         json.dumps(score.get("real_metrics", {})),
         json.dumps(score.get("synth_metrics", {})))
    )
    con.executemany(
        "INSERT INTO test_results (job_id, organization_id, name, passed, detail) VALUES (?, ?, ?, ?, ?)",
        [(job_id, org_id, t["name"], int(t["passed"]), t["detail"]) for t in score["tests"]]
    )

    # Log audit event
    from src.auth import log_audit_event
    log_audit_event(
        con, org_id, created_by, "SYNTHETIC_DATA_GENERATED", job_id=job_id,
        metadata={"dataset_name": dataset_name, "epsilon": epsilon, "rows": len(synth_df), "release_status": release_status}
    )
    con.commit()
    return job_id


def list_jobs(con: sqlite3.Connection, org_id: int) -> list[dict]:
    """Retrieves all jobs strictly belonging to the specified organization."""
    q = """SELECT j.id, j.organization_id, j.created_at, j.dataset_name, j.target,
                  j.n_rows_real, j.n_rows_synth, j.epsilon, j.release_status,
                  COALESCE(m.guaranteed_privacy_pct, 0.0) AS guaranteed_privacy_pct,
                  COALESCE(m.privacy_pct, 0.0) AS privacy_pct,
                  COALESCE(m.utility_pct, 0.0) AS utility_pct,
                  COALESCE(m.similarity_pct, 0.0) AS similarity_pct,
                  COALESCE(m.tests_passed, 0) AS tests_passed,
                  COALESCE(m.tests_total, 7) AS tests_total
           FROM jobs j
           LEFT JOIN metrics m ON m.job_id = j.id
           WHERE j.organization_id = ? ORDER BY j.id DESC"""
    return [dict(r) for r in con.execute(q, (org_id,))]


def get_job(con: sqlite3.Connection, job_id: int, org_id: int | None = None) -> dict | None:
    """Retrieves job details with strict tenant boundary enforcement.
    
    If org_id is provided, guarantees that the job belongs to that organization.
    Returns None on IDOR / cross-tenant access attempts.
    """
    cols = {r[1] for r in con.execute("PRAGMA table_info(jobs)").fetchall()}
    org_col = "organization_id" if "organization_id" in cols else "org_id"
    if org_id is not None:
        q = f"""SELECT j.*, m.*, o.name AS org_name, o.sector FROM jobs j
               JOIN metrics m ON m.job_id = j.id
               JOIN organizations o ON o.id = j.{org_col}
               WHERE j.id = ? AND j.{org_col} = ?"""
        row = con.execute(q, (job_id, org_id)).fetchone()
    else:
        q = f"""SELECT j.*, m.*, o.name AS org_name, o.sector FROM jobs j
               JOIN metrics m ON m.job_id = j.id
               JOIN organizations o ON o.id = j.{org_col}
               WHERE j.id = ?"""
        row = con.execute(q, (job_id,)).fetchone()

    if row is None:
        return None

    job = dict(row)
    col_sim = job.get("column_similarity")
    if isinstance(col_sim, str):
        try:
            col_sim = json.loads(col_sim)
        except Exception:
            col_sim = {}
    if not isinstance(col_sim, dict):
        col_sim = {}
    job["column_similarity"] = col_sim

    real_m = job.get("real_metrics")
    if isinstance(real_m, str):
        try:
            real_m = json.loads(real_m)
        except Exception:
            real_m = {}
    if not isinstance(real_m, dict):
        real_m = {}
    job["real_metrics"] = real_m

    synth_m = job.get("synth_metrics")
    if isinstance(synth_m, str):
        try:
            synth_m = json.loads(synth_m)
        except Exception:
            synth_m = {}
    if not isinstance(synth_m, dict):
        synth_m = {}
    job["synth_metrics"] = synth_m
    
    # Strictly scoped test results
    t_rows = con.execute(
        "SELECT name, passed, detail FROM test_results WHERE job_id = ? AND organization_id = ? ORDER BY id",
        (job_id, job["organization_id"])
    ).fetchall()
    job["tests"] = [dict(r) for r in t_rows]
    return job


# --------------------------------------------------------------------------- #
# Secure Token Share Links (Tenant Isolated)
# --------------------------------------------------------------------------- #
def create_secure_share_link(con: sqlite3.Connection, org_id: int, job_id: int,
                             user_id: int, duration_days: int = 7) -> str:
    """Creates a tokenized secure link for an external researcher."""
    import secrets
    token = secrets.token_urlsafe(24)
    now = datetime.now()
    expires = now + timedelta(days=duration_days)
    con.execute(
        """INSERT INTO secure_shares (organization_id, job_id, token, created_by, created_at, expires_at, is_revoked)
           VALUES (?, ?, ?, ?, ?, ?, 0)""",
        (org_id, job_id, token, user_id, now.strftime("%Y-%m-%d %H:%M:%S"),
         expires.strftime("%Y-%m-%d %H:%M:%S"))
    )
    from src.auth import log_audit_event
    log_audit_event(
        con, org_id, user_id, "SECURE_LINK_CREATED", job_id=job_id,
        metadata={"token_prefix": token[:8] + "...", "expires_at": expires.strftime("%Y-%m-%d")}
    )
    con.commit()
    return token


def validate_secure_share(con: sqlite3.Connection, token: str) -> dict | None:
    """Validates a secure share token and returns the authorized job and organization."""
    now_str = _now()
    row = con.execute(
        """SELECT s.*, j.dataset_name, j.synthetic_path, j.epsilon, j.created_at as job_created_at,
                  o.name as org_name, o.sector as org_sector
           FROM secure_shares s
           JOIN jobs j ON s.job_id = j.id AND s.organization_id = j.organization_id
           JOIN organizations o ON s.organization_id = o.id
           WHERE s.token = ? AND s.is_revoked = 0 AND s.expires_at > ?""",
        (token, now_str)
    ).fetchone()
    return dict(row) if row else None
