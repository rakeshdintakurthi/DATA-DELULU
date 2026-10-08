"""Data Delulu — Multi-Tenant Authentication, Password Security & RBAC.

Design rules:
- Plaintext passwords are NEVER stored in the database.
- Industry standard bcrypt password hashing with salt is enforced.
- Strict tenant isolation: Every user belongs to an organization, and access is enforced
  at the backend/database query layer.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
from datetime import datetime
from typing import Any

try:
    import bcrypt

    def hash_password(password: str) -> str:
        """Securely hash a password using bcrypt."""
        salt = bcrypt.gensalt(rounds=12)
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

    def verify_password(password: str, password_hash: str) -> bool:
        """Verify a plaintext password against a stored bcrypt hash."""
        if not password or not password_hash:
            return False
        try:
            return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
        except Exception:
            return False

except ImportError:
    # Fallback to PBKDF2-HMAC-SHA256 with 100,000 rounds
    def hash_password(password: str) -> str:
        salt = secrets.token_hex(16)
        key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000)
        return f"pbkdf2:sha256:100000${salt}${key.hex()}"

    def verify_password(password: str, password_hash: str) -> bool:
        if not password or not password_hash or not password_hash.startswith("pbkdf2:"):
            return False
        try:
            _, _, rounds, salt, expected_hex = password_hash.split("$")
            key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), int(rounds))
            return secrets.compare_digest(key.hex(), expected_hex)
        except Exception:
            return False


# --------------------------------------------------------------------------- #
# Role-Based Access Control (RBAC)
# --------------------------------------------------------------------------- #
ROLE_HIERARCHY = {
    "ADMIN": 3,
    "ANALYST": 2,
    "VIEWER": 1
}


def has_role(user: dict | None, required_roles: str | list[str]) -> bool:
    """Checks if the user has one of the required roles or sufficient permission level."""
    if not user or "role" not in user:
        return False
    user_role = user.get("role", "VIEWER").upper()
    if isinstance(required_roles, str):
        required_roles = [required_roles]
    req_roles_upper = [r.upper() for r in required_roles]
    return user_role in req_roles_upper


def can_create_jobs(user: dict | None) -> bool:
    """Admins and Analysts can create synthetic data jobs."""
    return has_role(user, ["ADMIN", "ANALYST"])


def can_manage_users(user: dict | None) -> bool:
    """Only Admins can manage users and organization settings."""
    return has_role(user, "ADMIN")


def can_download_data(user: dict | None) -> bool:
    """Admins and Analysts can download synthetic datasets."""
    return has_role(user, ["ADMIN", "ANALYST"])


def can_create_share_links(user: dict | None) -> bool:
    """Admins and Analysts can create external secure share links."""
    return has_role(user, ["ADMIN", "ANALYST"])


# --------------------------------------------------------------------------- #
# Audit Logging
# --------------------------------------------------------------------------- #
def log_audit_event(con, organization_id: int, user_id: int | None, action: str,
                    job_id: int | None = None, metadata: dict | None = None) -> int:
    """Logs an audit event in the database."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    meta_json = json.dumps(metadata or {})
    cur = con.execute(
        """INSERT INTO audit_logs (organization_id, user_id, action, job_id, timestamp, metadata)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (organization_id, user_id, action, job_id, now_str, meta_json)
    )
    con.commit()
    return cur.lastrowid


def get_audit_logs(con, organization_id: int, limit: int = 100) -> list[dict]:
    """Retrieves audit logs strictly scoped to the authenticated organization."""
    rows = con.execute(
        """SELECT a.*, u.email as user_email, u.name as user_name, u.role as user_role
           FROM audit_logs a
           LEFT JOIN users u ON a.user_id = u.id
           WHERE a.organization_id = ?
           ORDER BY a.id DESC LIMIT ?""",
        (organization_id, limit)
    ).fetchall()
    results = []
    for r in rows:
        d = dict(r)
        d["metadata"] = json.loads(d.get("metadata") or "{}")
        results.append(d)
    return results


# --------------------------------------------------------------------------- #
# User Management & Authentication
# --------------------------------------------------------------------------- #
def create_user(con, organization_id: int, name: str, email: str, password: str,
                role: str = "ADMIN") -> int:
    """Creates a new user with securely hashed password."""
    name = name.strip()
    email = email.strip().lower()
    if not name or not email or not password:
        raise ValueError("Name, email, and password are required.")
    
    role = role.upper()
    if role not in ROLE_HIERARCHY:
        role = "ANALYST"

    pw_hash = hash_password(password)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cur = con.execute(
        """INSERT INTO users (organization_id, name, email, password_hash, role, created_at, status)
           VALUES (?, ?, ?, ?, ?, ?, 'active')""",
        (organization_id, name, email, pw_hash, role, now_str)
    )
    con.commit()
    user_id = cur.lastrowid
    log_audit_event(con, organization_id, user_id, "USER_CREATED", metadata={"email": email, "role": role})
    return user_id


def register_organization_and_admin(con, org_name: str, sector: str, admin_name: str,
                                    admin_email: str, password: str) -> tuple[dict, dict]:
    """Registers a new organization and its initial administrator."""
    org_name = org_name.strip()
    if not org_name:
        raise ValueError("Organization name cannot be empty.")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cur = con.execute(
        "INSERT INTO organizations (name, sector, created_at, status) VALUES (?, ?, ?, 'active')",
        (org_name, sector, now_str)
    )
    org_id = cur.lastrowid
    user_id = create_user(con, org_id, admin_name, admin_email, password, role="ADMIN")
    log_audit_event(con, org_id, user_id, "ORGANIZATION_CREATED", metadata={"org_name": org_name, "sector": sector})

    org = {"id": org_id, "name": org_name, "sector": sector, "created_at": now_str, "status": "active"}
    user = {"id": user_id, "organization_id": org_id, "name": admin_name, "email": admin_email,
            "role": "ADMIN", "created_at": now_str, "status": "active", "org_name": org_name, "org_sector": sector}
    return org, user


def authenticate_user(con, email_or_name: str, password: str) -> dict | None:
    """Authenticates a user and returns their identity with organization details."""
    query_str = email_or_name.strip().lower()
    row = con.execute(
        """SELECT u.*, o.name AS org_name, o.sector AS org_sector, o.status AS org_status
           FROM users u
           JOIN organizations o ON u.organization_id = o.id
           WHERE (LOWER(u.email) = ? OR LOWER(u.name) = ?) AND u.status = 'active'""",
        (query_str, query_str)
    ).fetchone()

    if not row:
        return None

    user = dict(row)
    if not verify_password(password, user["password_hash"]):
        log_audit_event(con, user["organization_id"], user["id"], "LOGIN_FAILURE",
                        metadata={"attempted_identifier": email_or_name})
        return None

    log_audit_event(con, user["organization_id"], user["id"], "LOGIN_SUCCESS",
                    metadata={"email": user["email"]})
    # Remove password_hash from the returned user dictionary for security
    user.pop("password_hash", None)
    return user


def get_user_organizations(con, user_id: int) -> list[dict]:
    """Returns list of organizations this user is authorized to access (for multi-org accounts)."""
    user_row = con.execute("SELECT organization_id FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user_row:
        return []
    org_id = user_row["organization_id"]
    rows = con.execute("SELECT * FROM organizations WHERE id = ? AND status = 'active'", (org_id,)).fetchall()
    return [dict(r) for r in rows]
