"""Data Delulu — Customer-Controlled Private Data Plane Agent.

"The software goes to the data. The data does not go to the software."

This package executes entirely inside the customer's private infrastructure (VPC/Enclave/On-Prem).
Raw customer data never crosses the security boundary.
"""
from __future__ import annotations

from .agent import DataDeluluAgent, AgentDisabledError
from .config import AgentConfig
from .db_connector import (
    DatabaseConnector,
    DataSourceConnector,
    PostgreSQLConnector,
    MySQLConnector,
    SQLServerConnector,
    OracleConnector,
    SnowflakeConnector,
    BigQueryConnector,
    RedshiftConnector,
    S3Connector,
    AzureBlobConnector,
    GCSConnector,
    CSVConnector,
    ParquetConnector,
    MongoDBConnector,
    SQLiteConnector,
    get_connector,
    list_supported_connectors,
)
from .policy_engine import OrganizationPolicy, PolicyEngine, PolicyViolationError
from .dp_engine import LocalDPEngine
from .synthetic_generator import LocalSyntheticGenerator
from .privacy_evaluator import LocalPrivacyEvaluator
from .utility_evaluator import LocalUtilityEvaluator
from .release_gate import ReleaseGate, ReleaseGateResult, ReleaseStatus
from .egress_controller import EgressController, EgressBlockedError
from .audit import LocalAgentAuditLogger

InEnclaveAuditLogger = LocalAgentAuditLogger

__all__ = [
    "DataDeluluAgent",
    "AgentDisabledError",
    "AgentConfig",
    "DatabaseConnector",
    "DataSourceConnector",
    "PostgreSQLConnector",
    "MySQLConnector",
    "SQLServerConnector",
    "OracleConnector",
    "SnowflakeConnector",
    "BigQueryConnector",
    "RedshiftConnector",
    "S3Connector",
    "AzureBlobConnector",
    "GCSConnector",
    "CSVConnector",
    "ParquetConnector",
    "MongoDBConnector",
    "SQLiteConnector",
    "get_connector",
    "list_supported_connectors",
    "OrganizationPolicy",
    "PolicyEngine",
    "PolicyViolationError",
    "LocalDPEngine",
    "LocalSyntheticGenerator",
    "LocalPrivacyEvaluator",
    "LocalUtilityEvaluator",
    "ReleaseGate",
    "ReleaseGateResult",
    "ReleaseStatus",
    "EgressController",
    "EgressBlockedError",
    "LocalAgentAuditLogger",
    "InEnclaveAuditLogger",
]

