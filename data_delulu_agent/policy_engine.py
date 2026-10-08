"""Data Delulu Local Agent — Organization Policy Engine.

Enforces customer-defined data access and egress governance.
Evaluates authorization decisions entirely inside the customer security perimeter.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any
import pandas as pd


class PolicyViolationError(Exception):
    """Raised when an operation or job instruction violates organization data policy."""
    pass


@dataclass
class OrganizationPolicy:
    """Customer-controlled data access and differential privacy governance policy."""
    organization_id: int
    allowed_tables: list[str] = field(default_factory=list)  # Empty means all non-blocked tables allowed
    blocked_tables: list[str] = field(default_factory=lambda: [
        "executive_compensation", "ssn_vault", "admin_audit_keys", "secret_tokens"
    ])
    allowed_columns: list[str] = field(default_factory=list)  # Empty means all except blocked
    blocked_columns: list[str] = field(default_factory=lambda: [
        "ssn", "social_security_number", "password", "password_hash", "credit_card_number",
        "passport_num", "national_id", "secret_key", "api_key"
    ])
    epsilon_limit: float = 5.0
    minimum_utility: float = 80.0
    raw_data_export: bool = False       # ALWAYS False — Zero Raw Data Egress Guarantee
    synthetic_data_export: bool = True
    approval_required: bool = False
    max_records_per_job: int = 500_000
    retention_policy: str = "in-memory-only"

    def to_dict(self) -> dict[str, Any]:
        return {
            "organization_id": self.organization_id,
            "allowed_tables": self.allowed_tables,
            "blocked_tables": self.blocked_tables,
            "allowed_columns": self.allowed_columns,
            "blocked_columns": self.blocked_columns,
            "epsilon_limit": self.epsilon_limit,
            "minimum_utility": self.minimum_utility,
            "raw_data_export": self.raw_data_export,
            "synthetic_data_export": self.synthetic_data_export,
            "approval_required": self.approval_required,
            "max_records_per_job": self.max_records_per_job,
            "retention_policy": self.retention_policy,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OrganizationPolicy:
        return cls(
            organization_id=data.get("organization_id", 1),
            allowed_tables=data.get("allowed_tables") if isinstance(data.get("allowed_tables"), list) else json.loads(data.get("allowed_tables") or "[]"),
            blocked_tables=data.get("blocked_tables") if isinstance(data.get("blocked_tables"), list) else json.loads(data.get("blocked_tables") or "[]"),
            allowed_columns=data.get("allowed_columns") if isinstance(data.get("allowed_columns"), list) else json.loads(data.get("allowed_columns") or "[]"),
            blocked_columns=data.get("blocked_columns") if isinstance(data.get("blocked_columns"), list) else json.loads(data.get("blocked_columns") or "[]"),
            epsilon_limit=float(data.get("epsilon_limit", 5.0)),
            minimum_utility=float(data.get("minimum_utility", 80.0)),
            raw_data_export=False,  # Enforce False regardless of stored value
            synthetic_data_export=bool(data.get("synthetic_data_export", True)),
            approval_required=bool(data.get("approval_required", False)),
            max_records_per_job=int(data.get("max_records_per_job", 500_000)),
            retention_policy=str(data.get("retention_policy", "in-memory-only")),
        )


class PolicyEngine:
    """Evaluates and enforces data access rules inside the customer environment."""

    def __init__(self, policy: OrganizationPolicy):
        self.policy = policy

    def can_access_table(self, table_name: str) -> bool:
        """Determines if a table can be queried according to organization policy."""
        if not table_name:
            return True
        t_clean = table_name.lower().strip()
        for b in self.policy.blocked_tables:
            if b.lower().strip() == t_clean:
                return False
        return True

    def can_access_column(self, column_name: str) -> bool:
        """Determines if a column is authorized for differential privacy modeling."""
        c_clean = column_name.lower().strip()
        for b in self.policy.blocked_columns:
            if b.lower().strip() == c_clean:
                return False

        if not self.policy.allowed_columns:
            return True

        return any(a.lower().strip() == c_clean for a in self.policy.allowed_columns)

    def can_use_epsilon(self, requested_epsilon: float) -> bool:
        """Validates requested DP budget against organization upper bound."""
        if requested_epsilon <= 0:
            return False
        return requested_epsilon <= self.policy.epsilon_limit

    def can_export_raw_data(self) -> bool:
        """Raw data export is mathematically and architecturally prohibited."""
        return False

    def can_export_synthetic_data(self) -> bool:
        """Checks if organization permits synthetic data release."""
        return self.policy.synthetic_data_export

    def requires_admin_approval(self) -> bool:
        """Checks if release requires explicit Organization Admin sign-off."""
        return self.policy.approval_required

    def validate_job_instruction(self, job_spec: dict) -> None:
        """Validates incoming control plane job instruction against local policy."""
        table = job_spec.get("dataset", "org_source_view")
        if not self.can_access_table(table):
            raise PolicyViolationError(f"Access to table '{table}' is blocked by organization policy.")

        eps = float(job_spec.get("epsilon", 1.0))
        if not self.can_use_epsilon(eps):
            raise PolicyViolationError(
                f"Requested ε = {eps} exceeds organization privacy budget limit of ε = {self.policy.epsilon_limit}."
            )

    def filter_authorized_dataset(self, df: pd.DataFrame, target: str) -> tuple[pd.DataFrame, list[str]]:
        """Strips unauthorized/blocked columns from dataset and ensures target is authorized."""
        if not self.can_access_column(target):
            raise PolicyViolationError(f"Target feature '{target}' is on the organization blocked columns list.")

        removed_cols = []
        keep_cols = []
        for col in df.columns:
            if col.lower().endswith("_id") and col != target:
                continue
            if not self.can_access_column(col):
                removed_cols.append(col)
            else:
                keep_cols.append(col)

        if not keep_cols:
            raise PolicyViolationError("No authorized columns remaining after applying organization policy.")

        if target not in keep_cols:
            keep_cols.append(target)

        return df[keep_cols].copy(), removed_cols
