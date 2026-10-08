"""Data Delulu Local Agent — Configuration & Environment Secrets.

Stores local agent identity, security settings, and runtime parameters.
Database credentials and customer secrets remain strictly local to this process.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AgentConfig:
    """Customer-side agent runtime configuration."""
    organization_id: int = 1
    organization_name: str = "Customer Organization"
    agent_id: str = "AGENT-LOCAL-001"
    agent_secret: str = "sec_enclave_local_secret_key"
    environment: str = "Customer Private VPC Enclave"
    version: str = "2.5.0-enclave"
    is_active: bool = True
    
    # Local paths
    agent_data_dir: Path = field(default_factory=lambda: Path(os.getenv("AGENT_DATA_DIR", "./storage/agent_local")))
    audit_log_path: Path = field(default_factory=lambda: Path(os.getenv("AGENT_AUDIT_LOG", "./storage/agent_local/audit.jsonl")))
    
    # Customer-owned Database credentials (stored strictly local in memory / env vars)
    db_provider: str = "SQLite"
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "customer_private_db"
    db_user: str = "datadelulu_reader"
    db_password: str = ""
    db_sqlite_path: str = ""

    # Security boundaries & constraints
    max_memory_records: int = 500_000
    allow_raw_egress: bool = False  # NEVER True — Hard enforced by EgressController

    @property
    def database_type(self) -> str:
        """Alias for db_provider."""
        return self.db_provider

    @property
    def database_file_path(self) -> str:
        """Alias for db_sqlite_path."""
        return self.db_sqlite_path

    @classmethod
    def from_env(cls, organization_id: int = 1) -> AgentConfig:
        """Constructs an AgentConfig using customer environment variables."""
        return cls(
            organization_id=organization_id,
            organization_name=os.getenv("DATA_DELULU_ORG_NAME", f"Organization #{organization_id}"),
            agent_id=os.getenv("DATA_DELULU_AGENT_ID", f"AGENT-ORG-{organization_id:04d}"),
            agent_secret=os.getenv("DATA_DELULU_AGENT_SECRET", "enclave_agent_secret_key"),
            environment=os.getenv("DATA_DELULU_ENVIRONMENT", "Customer Private VPC Enclave"),
            is_active=os.getenv("DATA_DELULU_AGENT_ACTIVE", "true").lower() in ("true", "1", "yes"),
            db_provider=os.getenv("CUSTOMER_DB_PROVIDER", "PostgreSQL"),
            db_host=os.getenv("CUSTOMER_DB_HOST", "localhost"),
            db_port=int(os.getenv("CUSTOMER_DB_PORT", "5432")),
            db_name=os.getenv("CUSTOMER_DB_NAME", "customer_data"),
            db_user=os.getenv("CUSTOMER_DB_USER", "datadelulu_reader"),
            db_password=os.getenv("CUSTOMER_DB_PASSWORD", ""),
        )
