"""Data Delulu — Automated Test Suite for Organization Database Isolation & Connections.
Tests cover:
- Organization-specific database engines & configs (PostgreSQL, MySQL, Snowflake, etc.)
- Dynamic table & record count discovery
- Tenant isolation & cross-tenant security
- Connection testing & failure handling
- Password encryption & masking
- Ingesting organization-specific source datasets
"""
import os
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import auth, db, org_database


@pytest.fixture
def test_db(tmp_path):
    database_file = tmp_path / "test_datadelulu.db"
    con = db.connect(database_file)
    return con


def test_smarthire_database_configuration_and_counts(test_db):
    """TEST 1: SmartHire InfoTech has PostgreSQL, smart-hire-db.internal, 8,420 records."""
    org = test_db.execute("SELECT id FROM organizations WHERE name = 'SmartHire InfoTech'").fetchone()
    assert org is not None
    org_id = org["id"]

    cfg = org_database.get_org_db_config(test_db, org_id)
    assert cfg["provider"] == "PostgreSQL"
    assert "smart-hire-db" in cfg["host"]
    assert cfg["port"] == 5432
    assert cfg["database_name"] == "smarthire_prod"
    assert cfg["record_count"] == 8420
    assert "employees" in cfg["table_metadata"]
    assert "payroll_records" in cfg["table_metadata"]
    assert cfg["table_metadata"]["employees"] == 8420


def test_finedge_database_configuration_and_counts(test_db):
    """TEST 2: FinEdge Lending has MySQL, finedge-db.internal, 23,750 records."""
    org = test_db.execute("SELECT id FROM organizations WHERE name = 'FinEdge Lending'").fetchone()
    assert org is not None
    org_id = org["id"]

    cfg = org_database.get_org_db_config(test_db, org_id)
    assert cfg["provider"] == "MySQL"
    assert "finedge-db" in cfg["host"]
    assert cfg["port"] == 3306
    assert cfg["database_name"] == "finedge_lending"
    assert cfg["record_count"] == 23750
    assert "borrowers" in cfg["table_metadata"]
    assert "loan_portfolios" in cfg["table_metadata"]
    assert cfg["table_metadata"]["borrowers"] == 23750


def test_apexhealth_and_retailx_database_configurations(test_db):
    """TEST 3 & 4: Apex Health (PostgreSQL 5,280) and RetailX (Snowflake 41,200)."""
    # Apex Health
    health_org = test_db.execute("SELECT id FROM organizations WHERE name LIKE '%Apex Health%'").fetchone()
    assert health_org is not None
    h_cfg = org_database.get_org_db_config(test_db, health_org["id"])
    assert h_cfg["provider"] == "PostgreSQL"
    assert h_cfg["record_count"] == 5280
    assert "patients" in h_cfg["table_metadata"]

    # RetailX
    retail_org = test_db.execute("SELECT id FROM organizations WHERE name LIKE '%RetailX%'").fetchone()
    assert retail_org is not None
    r_cfg = org_database.get_org_db_config(test_db, retail_org["id"])
    assert r_cfg["provider"] == "Snowflake"
    assert r_cfg["record_count"] == 41200
    assert "retail_customers" in r_cfg["table_metadata"]


def test_record_counts_differ_between_tenants(test_db):
    """TEST 5: Distinct tenants have genuine distinct record counts."""
    counts = {}
    for org_row in test_db.execute("SELECT id, name FROM organizations").fetchall():
        cfg = org_database.get_org_db_config(test_db, org_row["id"])
        counts[org_row["name"]] = cfg["record_count"]

    assert counts["SmartHire InfoTech"] == 8420
    assert counts["FinEdge Lending"] == 23750
    assert counts["Apex Health Systems"] == 5280
    assert counts["RetailX Analytics"] == 41200
    assert counts["NovaBank — Demo Environment"] == 12500
    # Ensure they are distinct
    assert len(set(counts.values())) == len(counts)


def test_connection_testing_and_live_status(test_db):
    """TEST 6, 7, 8: Test Connection executes real validation query and reports status."""
    org = test_db.execute("SELECT id FROM organizations WHERE name = 'SmartHire InfoTech'").fetchone()
    org_id = org["id"]

    res = org_database.test_org_db_connection(test_db, org_id)
    assert res["connected"] is True
    assert res["status"] == "Connected"
    assert res["record_count"] == 8420
    assert "smarthire_prod" in res["message"]


def test_save_and_update_database_configuration(test_db):
    """TEST 9: Updating database configuration works and saves server-side."""
    org = test_db.execute("SELECT id FROM organizations WHERE name = 'SmartHire InfoTech'").fetchone()
    user = auth.authenticate_user(test_db, "adam@gmail.com", "SmartHire2026!")

    res = org_database.save_org_db_config(
        test_db, org["id"], user["id"],
        provider="PostgreSQL",
        host="smart-hire-custom.cloud",
        port=5433,
        database_name="smarthire_enterprise",
        username="adam_admin",
        password="SuperSecretPassword123!"
    )
    assert res["connected"] is True

    # Retrieve config
    cfg = org_database.get_org_db_config(test_db, org["id"])
    assert cfg["host"] == "smart-hire-custom.cloud"
    assert cfg["port"] == 5433
    assert cfg["database_name"] == "smarthire_enterprise"
    assert cfg["username"] == "adam_admin"
    assert cfg["has_password"] is True


def test_passwords_never_exposed_or_stored_plaintext(test_db):
    """TEST 10, 11: Passwords encrypted with server-side key, never returned in config."""
    org = test_db.execute("SELECT id FROM organizations WHERE name = 'FinEdge Lending'").fetchone()
    user = auth.authenticate_user(test_db, "admin@finedge.demo", "FinEdge2026!")

    org_database.save_org_db_config(
        test_db, org["id"], user["id"],
        provider="MySQL",
        host="finedge-db.internal",
        port=3306,
        database_name="finedge_lending",
        username="finedge_svc",
        password="MySecretMySQLPassword!"
    )

    # 1. Raw database check
    raw_row = test_db.execute("SELECT encrypted_password FROM organization_databases WHERE organization_id = ?", (org["id"],)).fetchone()
    assert "MySecretMySQLPassword!" not in raw_row["encrypted_password"]
    assert raw_row["encrypted_password"].startswith("enc:")

    # 2. Config getter check
    cfg = org_database.get_org_db_config(test_db, org["id"])
    assert "encrypted_password" not in cfg
    assert "password" not in cfg
    assert cfg["has_password"] is True


def test_tenant_dataset_fetching_isolation(test_db):
    """TEST 12: Ingesting dataset produces organization-specific columns and records."""
    # SmartHire
    smarthire_org = test_db.execute("SELECT id FROM organizations WHERE name = 'SmartHire InfoTech'").fetchone()["id"]
    df_smart = org_database.fetch_org_dataset(test_db, smarthire_org)
    assert len(df_smart) == 8420
    assert "salary" in df_smart.columns or "employee_id" in df_smart.columns

    # FinEdge
    finedge_org = test_db.execute("SELECT id FROM organizations WHERE name = 'FinEdge Lending'").fetchone()["id"]
    df_finedge = org_database.fetch_org_dataset(test_db, finedge_org)
    assert len(df_finedge) == 23750
    assert "credit_score" in df_finedge.columns or "borrower_id" in df_finedge.columns

    # Apex Health
    apex_org = test_db.execute("SELECT id FROM organizations WHERE name LIKE '%Apex Health%'").fetchone()["id"]
    df_apex = org_database.fetch_org_dataset(test_db, apex_org)
    assert len(df_apex) == 5280
    assert "patient_id" in df_apex.columns or "admission_type" in df_apex.columns

    # RetailX
    retail_org = test_db.execute("SELECT id FROM organizations WHERE name LIKE '%RetailX%'").fetchone()["id"]
    df_retail = org_database.fetch_org_dataset(test_db, retail_org)
    assert len(df_retail) == 41200
    assert "annual_spend" in df_retail.columns or "membership_tier" in df_retail.columns


def test_end_to_end_synthesis_for_smarthire_and_finedge(test_db, tmp_path):
    """TEST 13: End-to-end synthesis on SmartHire (HR) and FinEdge (Lending) datasets."""
    from src.engine import preprocess, synthesize, scorecard, split, decode

    # 1. SmartHire
    smart_org = test_db.execute("SELECT id FROM organizations WHERE name = 'SmartHire InfoTech'").fetchone()["id"]
    smart_user = auth.authenticate_user(test_db, "adam@gmail.com", "SmartHire2026!")
    smart_df = org_database.fetch_org_dataset(test_db, smart_org, limit=500)
    feat_smart = [c for c in smart_df.columns if not c.lower().endswith("_id")]
    enc_s, meta_s = preprocess(smart_df[feat_smart], "performance_rating")
    tr_s, te_s = split(enc_s, "performance_rating")
    synth_s, acc_s = synthesize(tr_s, meta_s, epsilon=1.0, n_rows=500)
    sc_s = scorecard(tr_s, te_s, synth_s, meta_s, acc_s, 1.0)
    
    smart_job_id = db.save_job(
        test_db, smart_org, "smarthire_workforce.csv", "fp_smart", "performance_rating",
        len(tr_s), decode(synth_s, meta_s), 1.0, acc_s, sc_s,
        created_by=smart_user["id"], synth_dir=tmp_path
    )
    assert smart_job_id > 0
    job_record = db.get_job(test_db, smart_job_id, org_id=smart_org)
    assert job_record is not None
    assert job_record["org_name"] == "SmartHire InfoTech"
    assert job_record["target"] == "performance_rating"
    assert job_record["tests_passed"] >= 4
    assert job_record["tests_total"] == 7


def test_tenant_db_dir_constant_and_path_resolution():
    """TEST 1, 2, 3, 4: TENANT_DB_DIR exists and resolves isolated paths per organization."""
    assert hasattr(org_database, "TENANT_DB_DIR")
    assert isinstance(org_database.TENANT_DB_DIR, Path)
    assert org_database.TENANT_DB_DIR.exists()

    path_1 = org_database.get_tenant_db_path(1)
    path_2 = org_database.get_tenant_db_path(2)
    path_str_1 = org_database.get_tenant_db_path("1")

    assert path_1 == path_str_1
    assert path_1 != path_2
    assert "org_1.db" in str(path_1)
    assert "org_2.db" in str(path_2)


def test_tenant_database_api_lifecycle(test_db):
    """TEST 5: tenant_database_exists, initialize_tenant_database, and get_tenant_connection."""
    org = test_db.execute("SELECT id FROM organizations WHERE name = 'SmartHire InfoTech'").fetchone()
    org_id = org["id"]

    # Initialize tenant DB
    res = org_database.initialize_tenant_database(test_db, org_id)
    assert res["connected"] is True
    assert org_database.tenant_database_exists(org_id) is True

    # Connect to tenant DB directly
    t_con = org_database.get_tenant_connection(org_id, con=test_db)
    cur = t_con.cursor()
    row = cur.execute("SELECT COUNT(*) FROM employees").fetchone()
    assert row[0] == 8420
    t_con.close()


def test_local_agent_connections_to_distinct_tenants(test_db):
    """TEST 6, 7, 8: Local Agent can connect to org 1 and org 2 databases separately."""
    from data_delulu_agent import DataDeluluAgent, AgentConfig, OrganizationPolicy

    org1 = test_db.execute("SELECT id, name FROM organizations WHERE name = 'SmartHire InfoTech'").fetchone()
    org2 = test_db.execute("SELECT id, name FROM organizations WHERE name = 'FinEdge Lending'").fetchone()

    # Agent 1
    p1 = org_database.get_tenant_db_path(org1["id"])
    org_database.initialize_tenant_database(test_db, org1["id"])
    cfg1 = AgentConfig(
        organization_id=org1["id"],
        organization_name=org1["name"],
        db_provider="SQLite",
        db_sqlite_path=str(p1)
    )
    agent1 = DataDeluluAgent(cfg1)
    tables1 = agent1.connector.list_tables()
    assert "employees" in tables1
    assert "borrowers" not in tables1

    # Agent 2
    p2 = org_database.get_tenant_db_path(org2["id"])
    org_database.initialize_tenant_database(test_db, org2["id"])
    cfg2 = AgentConfig(
        organization_id=org2["id"],
        organization_name=org2["name"],
        db_provider="SQLite",
        db_sqlite_path=str(p2)
    )
    agent2 = DataDeluluAgent(cfg2)
    tables2 = agent2.connector.list_tables()
    assert "borrowers" in tables2
    assert "employees" not in tables2


def test_nri_university_registration_and_tenant_db(test_db):
    """TEST 9, 10: New organizations like NRI University initialize isolated databases seamlessly."""
    # Register new organization
    org, user = auth.register_organization_and_admin(
        test_db,
        org_name="NRI University",
        sector="Education / Research",
        admin_name="Dr. Sharma",
        admin_email="admin@nri.edu",
        password="NriPassword2026!"
    )
    assert org["id"] > 0
    assert org["name"] == "NRI University"

    # Tenant DB path and initialization
    db_path = org_database.get_tenant_db_path(org["id"])
    assert f"org_{org['id']}.db" in str(db_path)

    init_res = org_database.initialize_tenant_database(test_db, org["id"], user_id=user["id"])
    assert init_res["connected"] is True
    assert db_path.exists()

    df = org_database.fetch_org_dataset(test_db, org["id"])
    assert len(df) == 5000
    assert org_database.tenant_database_exists(org["id"]) is True

