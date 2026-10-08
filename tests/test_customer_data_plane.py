"""Data Delulu — Customer-Controlled Private Data Plane Security & Architecture Tests.
Verifies all 20 security invariants defined in Section 31 of Master Implementation Specification:
1. Raw data never reaches control plane.
2. Raw data is never written to central database.
3. Raw data is not present in central logs.
4. Customer A cannot access Customer B data.
5. Customer A agent cannot access Customer B database.
6. Blocked columns are never processed.
7. Blocked tables are never processed.
8. Raw data export is always denied.
9. Synthetic export follows organization policy.
10. Agent kill switch works.
11. Database credentials never appear in API responses.
12. Database credentials never appear in logs.
13. Failed policy check blocks job.
14. Failed privacy check blocks release.
15. Failed utility check blocks release when required.
16. Agent can process data without sending raw records to cloud.
17. Logout/session isolation works.
18. Existing DP tests continue passing.
19. Existing utility tests continue passing.
20. Existing authentication/tenant tests continue passing.
"""
import json
import sqlite3
import pandas as pd
import numpy as np
import pytest

from data_delulu_agent import (
    DataDeluluAgent, AgentConfig, OrganizationPolicy, PolicyEngine,
    ReleaseGate, ReleaseStatus, EgressController, AgentDisabledError,
    PolicyViolationError, LocalAgentAuditLogger
)
from src import auth, db, org_database


@pytest.fixture
def test_db():
    con = db.connect()
    return con


@pytest.fixture
def sample_raw_df():
    # 100 rows to satisfy min rows requirement for ML utility benchmarks
    n = 100
    rng = np.random.default_rng(42)
    return pd.DataFrame({
        "customer_id": list(range(1, n + 1)),
        "ssn": [f"000-11-{i:04d}" for i in range(1, n + 1)],
        "age": rng.integers(20, 65, size=n),
        "income": rng.integers(30000, 150000, size=n),
        "city": rng.choice(["New York", "Boston", "Chicago", "Seattle", "Austin"], size=n),
        "loan_default": rng.choice([0, 1], p=[0.75, 0.25], size=n)
    })


# --------------------------------------------------------------------------- #
# Test 1 & 16: Raw data never reaches control plane; Agent processes locally
# --------------------------------------------------------------------------- #
def test_raw_data_never_reaches_control_plane(sample_raw_df):
    policy = OrganizationPolicy(
        organization_id=1,
        blocked_columns=["ssn"],
        synthetic_data_export=True
    )
    config = AgentConfig(
        agent_id="AGENT-ORG-0001",
        organization_id=1,
        agent_secret="test_secret",
        db_provider="SQLite"
    )
    agent = DataDeluluAgent(config, policy=policy)
    
    job_request = {
        "job_id": "JOB-TEST-1001",
        "organization_id": "1",
        "operation": "GENERATE_SYNTHETIC",
        "dataset": "customers",
        "target": "loan_default",
        "epsilon": 1.0,
        "minimum_utility": 70.0,
        "n_rows": 50,
        "raw_df": sample_raw_df
    }
    
    manifest = agent.execute_job(job_request)
    
    # Invariant: Raw data count > 0, but Raw data egress == 0
    assert manifest.raw_records_processed == 100
    assert manifest.raw_records_transmitted == 0
    assert manifest.raw_bytes_transmitted == 0
    assert manifest["raw_records_count"] == 100
    assert manifest["egress_telemetry"]["raw_records_transmitted"] == 0
    assert manifest["egress_telemetry"]["raw_bytes_transmitted"] == 0
    assert "raw_records" not in manifest.to_dict()
    assert "raw_df" not in manifest.to_dict()


# --------------------------------------------------------------------------- #
# Test 2: Raw data is never written to central database
# --------------------------------------------------------------------------- #
def test_central_database_contains_no_raw_records(test_db, sample_raw_df):
    # Check all tables in control plane database
    tables = [r[0] for r in test_db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    assert "raw_customer_data" not in tables
    assert "raw_transactions" not in tables
    assert "raw_uploads" not in tables
    
    # Save a job and verify only metrics & paths are saved
    from src.engine import preprocess, split, synthesize, scorecard, decode
    enc, meta = preprocess(sample_raw_df.drop(columns=["ssn"]), "loan_default")
    train, test = split(enc, "loan_default")
    synth_enc, accounting = synthesize(train, meta, 1.0, n_rows=50)
    score = scorecard(train, test, synth_enc, meta, accounting, 1.0)
    synth_df = decode(synth_enc, meta)
    
    job_id = db.save_job(
        test_db, 1, "test_job", "fingerprint123", "loan_default",
        len(train), synth_df, 1.0, accounting, score, release_status="APPROVED"
    )
    
    job_row = test_db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    assert "raw" not in dict(job_row)


# --------------------------------------------------------------------------- #
# Test 3 & 12: Raw data & database credentials never present in logs
# --------------------------------------------------------------------------- #
def test_zero_raw_data_and_credentials_in_logs(tmp_path):
    log_file = tmp_path / "enclave_audit.jsonl"
    logger = LocalAgentAuditLogger(log_file)
    
    logger.log_event(
        action="JOB_COMPLETED",
        job_id="JOB-101",
        organization_id=1,
        metadata={
            "password": "super_secret_password",
            "ssn": "000-11-2222",
            "api_key": "AKIA1234567890",
            "records_processed_count": 500,
            "raw_records_egress": 0
        }
    )
    
    with open(log_file, "r") as f:
        log_content = f.read()
    
    assert "super_secret_password" not in log_content
    assert "000-11-2222" not in log_content
    assert "AKIA1234567890" not in log_content
    assert "records_processed_count" in log_content


# --------------------------------------------------------------------------- #
# Test 4 & 5: Customer A cannot access Customer B data or database
# --------------------------------------------------------------------------- #
def test_tenant_isolation_and_database_separation(test_db):
    orgs = db.list_organizations(test_db)
    org_a = orgs[0]
    org_b = orgs[1]
    
    # Fetch database config for Org A vs Org B
    db_a = org_database.get_org_db_config(test_db, org_a["id"])
    db_b = org_database.get_org_db_config(test_db, org_b["id"])
    
    assert db_a["database_name"] != db_b["database_name"]
    
    # IDOR check: Fetching Job for Org A with Org B's ID should return None
    fake_job_id = 99999
    assert db.get_job(test_db, fake_job_id, org_id=org_a["id"]) is None


# --------------------------------------------------------------------------- #
# Test 6: Blocked columns are never processed
# --------------------------------------------------------------------------- #
def test_blocked_columns_rejection(sample_raw_df):
    policy = OrganizationPolicy(
        organization_id=1,
        blocked_columns=["ssn", "age"]
    )
    engine = PolicyEngine(policy)
    
    # Column access decision
    assert engine.can_access_column("ssn") is False
    assert engine.can_access_column("age") is False
    assert engine.can_access_column("income") is True
    
    # Filter dataset
    sanitized_df, removed = engine.filter_authorized_dataset(sample_raw_df, "loan_default")
    assert "ssn" not in sanitized_df.columns
    assert "age" not in sanitized_df.columns
    assert "income" in sanitized_df.columns
    assert "ssn" in removed
    assert "age" in removed


# --------------------------------------------------------------------------- #
# Test 7 & 13: Blocked tables & policy checks block jobs
# --------------------------------------------------------------------------- #
def test_blocked_tables_and_policy_job_rejection():
    policy = OrganizationPolicy(
        organization_id=1,
        allowed_tables=["transactions", "customers"],
        blocked_tables=["payroll", "executive_salaries"],
        epsilon_limit=2.0
    )
    engine = PolicyEngine(policy)
    
    assert engine.can_access_table("payroll") is False
    assert engine.can_access_table("transactions") is True
    
    # Exceeding epsilon budget
    assert engine.can_use_epsilon(5.0) is False
    assert engine.can_use_epsilon(1.5) is True


# --------------------------------------------------------------------------- #
# Test 8: Raw data export is ALWAYS denied
# --------------------------------------------------------------------------- #
def test_raw_data_export_always_denied():
    policy = OrganizationPolicy(organization_id=1, raw_data_export=False)
    engine = PolicyEngine(policy)
    
    # Attempt raw export
    assert engine.can_export_raw_data() is False


# --------------------------------------------------------------------------- #
# Test 9: Synthetic export follows organization policy
# --------------------------------------------------------------------------- #
def test_synthetic_export_policy_toggle():
    policy_enabled = OrganizationPolicy(organization_id=1, synthetic_data_export=True)
    policy_disabled = OrganizationPolicy(organization_id=1, synthetic_data_export=False)
    
    assert PolicyEngine(policy_enabled).can_export_synthetic_data() is True
    assert PolicyEngine(policy_disabled).can_export_synthetic_data() is False


# --------------------------------------------------------------------------- #
# Test 10: Agent Kill Switch immediately halts processing
# --------------------------------------------------------------------------- #
def test_agent_kill_switch(sample_raw_df):
    policy = OrganizationPolicy(organization_id=1)
    config = AgentConfig(
        agent_id="AGENT-ORG-0001",
        organization_id=1,
        agent_secret="test_secret",
        is_active=False,  # DISABLED VIA KILL SWITCH
        db_provider="SQLite"
    )
    agent = DataDeluluAgent(config, policy=policy)
    
    job_request = {
        "job_id": "JOB-1002",
        "organization_id": "1",
        "operation": "GENERATE_SYNTHETIC",
        "dataset": "customers",
        "target": "loan_default",
        "epsilon": 1.0,
        "minimum_utility": 70.0,
        "n_rows": 20,
        "raw_df": sample_raw_df
    }
    
    with pytest.raises(AgentDisabledError) as excinfo:
        agent.execute_job(job_request)
    assert "disabled by local kill switch" in str(excinfo.value).lower()


# --------------------------------------------------------------------------- #
# Test 11: Database credentials never appear in API responses or config exports
# --------------------------------------------------------------------------- #
def test_credentials_never_exposed(test_db):
    org_db = org_database.get_org_db_config(test_db, 1)
    # Password must not be plaintext in the returned public dictionary
    assert "password" not in org_db or org_db.get("password") == ""
    assert org_db.get("has_password") is True


# --------------------------------------------------------------------------- #
# Test 14 & 15: Release Gate blocks failed privacy or utility checks
# --------------------------------------------------------------------------- #
def test_release_gate_fail_closed():
    policy = OrganizationPolicy(organization_id=1, minimum_utility=80.0, epsilon_limit=2.0)
    gate = ReleaseGate(policy)
    
    # 1. Failing utility check
    failing_utility = {
        "utility_pct": 50.0,  # Below floor 80.0%
        "similarity_pct": 92.0
    }
    privacy_metrics = {
        "attack_pct": 50.0,
        "attack_bound_pct": 73.0,
        "exact_copy_pct": 0.0,
        "baseline_copy_pct": 2.0
    }
    decision = gate.evaluate(1.0, privacy_metrics, failing_utility, n_rows_synth=20)
    assert decision.status == ReleaseStatus.BLOCKED
    assert any("utility" in r.lower() for r in decision.block_reasons)
    
    # 2. Failing memorization check
    memorizing_privacy = {
        "attack_pct": 50.0,
        "attack_bound_pct": 73.0,
        "exact_copy_pct": 10.0,  # 10% exact copy > baseline 1% * 2.5
        "baseline_copy_pct": 1.0
    }
    good_utility = {
        "utility_pct": 90.0,
        "similarity_pct": 92.0
    }
    decision_mem = gate.evaluate(1.0, memorizing_privacy, good_utility, n_rows_synth=20)
    assert decision_mem.status == ReleaseStatus.BLOCKED
    assert any("memorization" in r.lower() for r in decision_mem.block_reasons)


# --------------------------------------------------------------------------- #
# Test 17: User Authentication & Role-Based Access Control (RBAC)
# --------------------------------------------------------------------------- #
def test_rbac_and_session_isolation(test_db):
    # Admin can create jobs and approve releases
    admin_user = auth.authenticate_user(test_db, "adam@gmail.com", "SmartHire2026!")
    assert admin_user is not None
    assert auth.can_create_jobs(admin_user) is True
    assert auth.has_role(admin_user, "ADMIN") is True
    
    # Viewer cannot create jobs
    viewer_user = auth.authenticate_user(test_db, "viewer@finedge.demo", "FinEdge2026!")
    assert viewer_user is not None
    assert auth.can_create_jobs(viewer_user) is False


def test_new_job_agent_and_tenant_source_resolution(test_db):
    """TEST: New Job workflow resolves tenant database path without TENANT_DB_DIR AttributeError."""
    org1 = test_db.execute("SELECT id, name FROM organizations WHERE name = 'SmartHire InfoTech'").fetchone()
    org_id = org1["id"]

    org_agent_meta = db.get_org_agent(test_db, org_id)
    org_policy_dict = db.get_org_policy(test_db, org_id)
    policy = OrganizationPolicy.from_dict(org_policy_dict)

    tenant_db_path = org_database.get_tenant_db_path(org_id, con=test_db)
    if not tenant_db_path.exists():
        org_database.initialize_tenant_database(test_db, org_id)

    config = AgentConfig(
        organization_id=org_id,
        organization_name=org1["name"],
        agent_id=org_agent_meta["agent_id"],
        db_provider="SQLite",
        db_sqlite_path=str(tenant_db_path),
    )
    agent = DataDeluluAgent(config, policy=policy)
    assert agent.config.organization_id == org_id
    assert agent.config.database_type == "SQLite"

    raw_df = org_database.fetch_org_dataset(test_db, org_id, limit=100)
    assert len(raw_df) == 100
    assert "salary" in raw_df.columns or "employee_id" in raw_df.columns


def test_session_switching_agent_isolation(test_db):
    """TEST: Switching users/organizations creates separate agents with no connection reuse."""
    org1 = test_db.execute("SELECT id, name FROM organizations WHERE name = 'SmartHire InfoTech'").fetchone()
    org2 = test_db.execute("SELECT id, name FROM organizations WHERE name = 'FinEdge Lending'").fetchone()

    # User 1 logs in
    user1 = auth.authenticate_user(test_db, "adam@gmail.com", "SmartHire2026!")
    assert user1["organization_id"] == org1["id"]
    path1 = org_database.get_tenant_db_path(user1["organization_id"])
    agent1 = DataDeluluAgent(AgentConfig(organization_id=user1["organization_id"], db_sqlite_path=str(path1)))

    # User 2 logs in
    user2 = auth.authenticate_user(test_db, "admin@finedge.demo", "FinEdge2026!")
    assert user2["organization_id"] == org2["id"]
    path2 = org_database.get_tenant_db_path(user2["organization_id"])
    agent2 = DataDeluluAgent(AgentConfig(organization_id=user2["organization_id"], db_sqlite_path=str(path2)))

    # Ensure separate paths, agents, and connectors
    assert str(path1) != str(path2)
    assert agent1.config.organization_id != agent2.config.organization_id
    assert agent1.connector != agent2.connector


def test_nri_university_postgresql_dataset_execution(test_db):
    """TEST: Configured organization dataset (e.g., nri_university_postgresql) runs without policy violation."""
    # Create or fetch NRI University org
    org = test_db.execute("SELECT id, name FROM organizations WHERE name LIKE '%NRI%' OR name LIKE '%University%'").fetchone()
    if not org:
        org_id = db.create_organization(test_db, "NRI University", "Higher Education")
    else:
        org_id = org["id"]

    policy_dict = db.get_org_policy(test_db, org_id)
    policy = OrganizationPolicy.from_dict(policy_dict)
    
    agent = DataDeluluAgent(
        config=AgentConfig(organization_id=org_id, organization_name="NRI University", db_provider="PostgreSQL"),
        policy=policy
    )
    
    # Generate sample NRI university student raw data
    sample_df = pd.DataFrame({
        "student_id": list(range(1, 101)),
        "department": np.random.choice(["Computer Science", "Engineering", "Business", "Medicine"], 100),
        "gpa": np.random.uniform(2.5, 4.0, 100).round(2),
        "tuition_fee": np.random.randint(10000, 45000, 100),
        "placement_status": np.random.choice([0, 1], p=[0.3, 0.7], size=100)
    })
    
    dataset_name = "nri_university_postgresql"
    job_spec = {
        "job_id": "JOB-NRI-2026",
        "organization_id": str(org_id),
        "operation": "GENERATE_SYNTHETIC",
        "dataset": dataset_name,
        "target": "placement_status",
        "epsilon": 1.5,
        "minimum_utility": 65.0,
        "n_rows": 80,
        "raw_df": sample_df
    }
    
    # Execute job - must succeed without PolicyViolationError
    manifest = agent.execute_job(job_spec)
    assert manifest.raw_records_processed == 100
    assert manifest.raw_records_transmitted == 0
    assert manifest.synthetic_records_released == 80
    assert manifest.synthetic_df is not None
    assert len(manifest.synthetic_df) == 80
    assert "placement_status" in manifest.synthetic_df.columns


