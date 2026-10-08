import os
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import auth
from src import db
from src.engine import preprocess, synthesize, scorecard, decode
from data.make_novabank_data import generate_novabank_dataset


@pytest.fixture
def test_db(tmp_path):
    database_file = tmp_path / "test_datadelulu.db"
    con = db.connect(database_file)
    return con


def test_password_hashing_and_security(test_db):
    """TEST 10: Verify passwords are NEVER stored in plaintext in the database."""
    # Check seeded users
    users = test_db.execute("SELECT email, password_hash FROM users").fetchall()
    assert len(users) > 0
    for u in users:
        # Must not be plaintext
        assert u["password_hash"] != "NovaBank2026!"
        assert u["password_hash"] != "FinEdge2026!"
        assert u["password_hash"] != "Health2026!"
        # Must start with bcrypt or pbkdf2 hash signature
        assert u["password_hash"].startswith("$2b$") or u["password_hash"].startswith("$2a$") or u["password_hash"].startswith("pbkdf2:")


def test_authentication_success_and_failure(test_db):
    """Verify login authentication logic and audit logging."""
    # Valid login
    user = auth.authenticate_user(test_db, "admin@finedge.demo", "FinEdge2026!")
    assert user is not None
    assert user["email"] == "admin@finedge.demo"
    assert user["role"] == "ADMIN"
    assert "password_hash" not in user  # Strip hash from returned session dict

    # Invalid password
    bad_login = auth.authenticate_user(test_db, "admin@finedge.demo", "WrongPassword123")
    assert bad_login is None

    # Check audit logs for failed and successful logins
    logs = auth.get_audit_logs(test_db, user["organization_id"])
    actions = [l["action"] for l in logs]
    assert "LOGIN_SUCCESS" in actions
    assert "LOGIN_FAILURE" in actions


def test_tenant_isolation_and_idor_prevention(test_db, tmp_path):
    """TEST 1, 2, 3, 4, 7: Cross-tenant access and IDOR protection."""
    # Find FinEdge and NovaBank org IDs
    finedge_org = test_db.execute("SELECT id FROM organizations WHERE name = 'FinEdge Lending'").fetchone()["id"]
    novabank_org = test_db.execute("SELECT id FROM organizations WHERE name LIKE '%NovaBank%'").fetchone()["id"]
    assert finedge_org != novabank_org

    # Create synthetic dataset for NovaBank
    df = generate_novabank_dataset(n=200)
    features = [c for c in df.columns if not c.lower().endswith("_id")]
    enc, meta = preprocess(df[features], "loan_status")
    synth_enc, acc = synthesize(enc, meta, epsilon=1.0)
    train = enc.iloc[:100]
    test = enc.iloc[100:]
    synth_train = synth_enc.iloc[:100]
    sc = scorecard(train, test, synth_train, meta, acc, 1.0)
    
    nova_admin = auth.authenticate_user(test_db, "admin@novabank.demo", "NovaBank2026!")
    nova_job_id = db.save_job(
        test_db, novabank_org, "novabank_dataset.csv", "fp_nova", "loan_status",
        100, decode(synth_train, meta), 1.0, acc, sc, created_by=nova_admin["id"],
        synth_dir=tmp_path
    )

    # 1. NovaBank user can access their own job
    nova_job = db.get_job(test_db, nova_job_id, org_id=novabank_org)
    assert nova_job is not None
    assert nova_job["id"] == nova_job_id

    # 2. FinEdge user tries to access NovaBank job -> IDOR test
    finedge_user = auth.authenticate_user(test_db, "admin@finedge.demo", "FinEdge2026!")
    assert finedge_user["organization_id"] == finedge_org
    
    # Database query enforces organization_id == current_user.organization_id
    idor_attempt = db.get_job(test_db, nova_job_id, org_id=finedge_org)
    assert idor_attempt is None  # MUST RETURN NONE / ACCESS DENIED

    # 3. FinEdge user listing jobs must only see FinEdge jobs (0 NovaBank jobs)
    finedge_jobs = db.list_jobs(test_db, finedge_org)
    assert not any(j["id"] == nova_job_id for j in finedge_jobs)


def test_registration_creates_isolated_tenant(test_db):
    """TEST 8: Registering a custom organization creates isolated partition."""
    org, admin = auth.register_organization_and_admin(
        test_db, "Quantum BioTech", "Healthcare", "Dr. Jane Doe", "jane@quantumbio.com", "SecurePass2026!"
    )
    assert org["id"] is not None
    assert admin["organization_id"] == org["id"]
    assert admin["role"] == "ADMIN"

    # Authenticate new admin
    auth_user = auth.authenticate_user(test_db, "jane@quantumbio.com", "SecurePass2026!")
    assert auth_user is not None
    assert auth_user["organization_id"] == org["id"]

    # Brand new tenant has zero jobs
    jobs = db.list_jobs(test_db, org["id"])
    assert len(jobs) == 0


def test_secure_share_link_validation(test_db, tmp_path):
    """TEST 9: Secure share links are tokenized and validated."""
    novabank_org = test_db.execute("SELECT id FROM organizations WHERE name LIKE '%NovaBank%'").fetchone()["id"]
    nova_admin = auth.authenticate_user(test_db, "admin@novabank.demo", "NovaBank2026!")

    # Generate dummy job
    df = generate_novabank_dataset(n=100)
    features = [c for c in df.columns if not c.lower().endswith("_id")]
    enc, meta = preprocess(df[features], "loan_status")
    synth_enc, acc = synthesize(enc, meta, epsilon=1.0)
    sc = scorecard(enc.iloc[:50], enc.iloc[50:], synth_enc.iloc[:50], meta, acc, 1.0)
    job_id = db.save_job(
        test_db, novabank_org, "share_test.csv", "fp_share", "loan_status",
        50, decode(synth_enc.iloc[:50], meta), 1.0, acc, sc, created_by=nova_admin["id"],
        synth_dir=tmp_path
    )

    token = db.create_secure_share_link(test_db, novabank_org, job_id, nova_admin["id"], duration_days=7)
    assert token is not None

    # Valid token
    share_data = db.validate_secure_share(test_db, token)
    assert share_data is not None
    assert share_data["job_id"] == job_id
    assert share_data["organization_id"] == novabank_org

    # Invalid token
    invalid_share = db.validate_secure_share(test_db, "invalid_fake_token_123")
    assert invalid_share is None
