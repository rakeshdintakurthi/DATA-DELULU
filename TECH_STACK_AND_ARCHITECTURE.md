# Data Delulu — Tech Stack & Complete Architecture Guide

> **Core Architectural Principle:** *"The software goes to the data. The data does not go to the software."*

---

## 1. Complete Technology Stack

| Layer | Technologies Used | Description & Purpose |
| :--- | :--- | :--- |
| **Core Language & Runtime** | **Python 3.11+ / 3.14** | Core execution runtime for backend logic, data processing, cryptographic operations, and privacy engines. |
| **Frontend & UI Framework** | **Streamlit (v1.45+)** | Reactive web application framework providing multi-page UI, session management, and state reactivity. |
| **Visual Styling & 3D Depth** | **Vanilla CSS3 & Modern HTML5** | Isometric 3D card tilts (`perspective: 1000px`), keyframe animations (`ddCorePulse`, `ddRingRotate`), glassmorphism, and responsive layout tokens. |
| **Interactive Data Visualization** | **Altair (v5.0+) / Vega-Lite** | Declarative statistical data visualization for feature distributions, correlations, privacy–utility trade-off frontiers, and attack bounds. |
| **Data Processing & Analytics** | **Pandas (v2.0+) & NumPy (v1.26+)** | High-performance in-memory tabular manipulation, marginal frequency encoding, discretization, and statistical calculations. |
| **Differential Privacy Engine** | **Pure Differential Privacy ($\varepsilon$-DP)** | Laplace perturbation mechanism on 1-way & 2-way marginal contingency tables with zero data leakage. |
| **Attacks & Security Evaluation** | **Scikit-Learn / Custom NumPy** | Shadow-model Membership Inference Attacks (MIA), Attribute Inference Attacks, and Memorization / Exact Duplication detectors. |
| **Database & Persistence** | **SQLite3 (with WAL mode & Row Factory)** | Multi-tenant tenant-isolated metadata storage (`storage/datadelulu.db`) and isolated per-organization database enclaves (`storage/tenant_dbs/*.db`). |
| **Security & Authentication** | **PBKDF2-HMAC-SHA256 & Secrets** | Cryptographically salted password hashing, organization-scoped Role-Based Access Control (RBAC), and tokenized secure link generation. |
| **Containerization & Deployment** | **Docker & Docker Compose** | Multi-container setup separating Cloud Control Plane (`Dockerfile`) and Customer Enclave Agent (`Dockerfile.agent`). |
| **Testing & Quality Assurance** | **Pytest (v7.0+) & AsyncIO** | 48 automated test suites covering isolation, IDOR prevention, DP mathematical correctness, and connector interfaces. |

---

## 2. Directory & File-by-File Breakdown

### 📁 Root Configuration & Infrastructure Files

- **`requirements.txt`**: Defines top-level dependencies (`streamlit`, `pandas`, `numpy`, `altair`, `pytest`).
- **`Dockerfile`**: Production Docker container for the Data Delulu Control Plane / Web Application.
- **`Dockerfile.agent`**: Isolated container image for the customer-side Local Enclave Agent.
- **`docker-compose.yml`**: Orchestration file running the Control Plane and simulated customer VPC agent environments.
- **`.env.example`**: Environment variable template for secrets, database paths, and demo credentials.

---

### 📁 `app/` — Frontend & Presentation Layer

- **`app/streamlit_app.py`**:
  - Main application router and view controller.
  - Multi-tenant login & registration workflow.
  - **Enterprise Dashboard**: Enclave status, live telemetry (`Raw Data Egress: 0 Records`), and categorized Data Source cards.
  - **New Job**: Source connector selector, target feature picker, $\varepsilon$-privacy budget slider, and in-enclave job launcher.
  - **Results & Evaluation**: Release inspection, 7 quality checks, ML comparison charts, synthetic data previews, and download bundles (CSV, Privacy Certificate, Audit Bundle).
  - **Architecture & Security**: In-enclave architecture visualizer and cryptographic proofs.
  - **Audit History**: Tenant-isolated compliance audit trail.

- **`app/ui.py`**:
  - Custom CSS design system, dark-mode tokens, 3D cards, badges, and status pills.
  - **`render_3d_pipeline_core()`**: Isometric 3D visualization of Customer Database $\rightarrow$ Glowing Privacy Core $\rightarrow$ Synthetic Dataset.
  - Chart theme configuration for Altair visualizations.

---

### 📁 `data_delulu_agent/` — Local Customer Enclave Agent (Data Plane)

> *Runs inside the customer's private infrastructure. Enforces zero raw data egress.*

- **`data_delulu_agent/agent.py`**:
  - `DataDeluluAgent`: Main coordinator inside the customer VPC.
  - Executes jobs locally: loads data $\rightarrow$ checks policies $\rightarrow$ runs DP synthesis $\rightarrow$ evaluates privacy & utility $\rightarrow$ verifies release gate $\rightarrow$ produces sanitized release manifest.

- **`data_delulu_agent/db_connector.py`**:
  - `DataSourceConnector` / `DatabaseConnector`: Unified abstract base class.
  - **13 Database & Storage Connectors**:
    1. *PostgreSQLConnector* (Connected / Live Executable)
    2. *MySQLConnector* (Available / Executable)
    3. *SQLServerConnector* (Available / Demo & Config)
    4. *OracleConnector* (Available / Demo & Config)
    5. *SnowflakeConnector* (Available / Demo & Config)
    6. *BigQueryConnector* (Available / Demo & Config)
    7. *RedshiftConnector* (Available / Demo & Config)
    8. *S3Connector* (Available / Demo & Config)
    9. *AzureBlobConnector* (Available / Demo & Config)
    10. *GCSConnector* (Available / Demo & Config)
    11. *CSVConnector* (Available / Live Ingestion)
    12. *ParquetConnector* (Available / Live Ingestion)
    13. *MongoDBConnector* (Available / Demo & Config)
  - `list_supported_connectors()`: Catalog metadata for UI configuration.

- **`data_delulu_agent/dp_engine.py`**:
  - `LocalDPEngine`: In-enclave Differential Privacy calculation using Laplace perturbation on tabular marginals.

- **`data_delulu_agent/synthetic_generator.py`**:
  - `LocalSyntheticGenerator`: Samples high-fidelity synthetic tabular records strictly from noisy marginal probability distributions.

- **`data_delulu_agent/privacy_evaluator.py`**:
  - `LocalPrivacyEvaluator`: Runs automated shadow Membership Inference Attacks (MIA), attribute inference attacks, and exact record copy checks.

- **`data_delulu_agent/utility_evaluator.py`**:
  - `LocalUtilityEvaluator`: Trains real vs. synthetic classification models and computes accuracy, precision, recall, F1, and Total Variation Distance.

- **`data_delulu_agent/policy_engine.py`**:
  - `PolicyEngine`: Enforces tenant-level constraints (blocked tables, blocked columns, maximum $\varepsilon$, minimum utility floor).

- **`data_delulu_agent/release_gate.py`**:
  - `ReleaseGate`: Evaluates 7 automated quality and security checks before approving a dataset for release.

- **`data_delulu_agent/egress_controller.py`**:
  - `EgressController`: Network egress firewall verifying that raw records never leave the customer enclave (`0 Raw Records Transmitted`).

- **`data_delulu_agent/audit.py`**:
  - `LocalAgentAuditLogger`: Immutable in-enclave audit logger.

- **`data_delulu_agent/config.py`**:
  - `AgentConfig`: Dataclass holding agent configuration, database credentials, and kill-switch state.

---

### 📁 `src/` — Control Plane & Core Mathematical Libraries

- **`src/db.py`**:
  - Central SQLite schema, connection management, schema migrations, and demo tenant seeders.
  - Job management (`save_job`, `list_jobs`, `get_job`), secure token sharing (`create_secure_share_link`, `validate_secure_share`), and telemetry updates.

- **`src/auth.py`**:
  - PBKDF2 password hashing & verification.
  - Tenant authentication, session token issuance, and organization audit logging.

- **`src/engine.py`**:
  - Core mathematical Differential Privacy algorithms: `preprocess`, `synthesize`, `evaluate_utility`, `membership_inference_attack`, `scorecard`, and `privacy_frontier`.

- **`src/org_database.py`**:
  - Multi-tenant SQLite database provisioning (`storage/tenant_dbs/<org_id>.db`).
  - Isolated dataset querying and connector dispatching.

- **`src/novabank_db.py`**:
  - Mock organizational banking dataset generator and database seeder for NovaBank demo environment.

---

### 📁 `data/` — Dataset Synthesizers & Seeds

- **`data/make_novabank_data.py`**: Generates 5,000 realistic synthetic banking records with 16 financial features (`income`, `credit_score`, `loan_status`, `fraud_flag`, etc.).
- **`data/make_tenant_datasets.py`**: Domain-specific mock generators for HR (SmartHire), Healthcare (Apex Health), FinTech (FinEdge), and E-Commerce (RetailX).
- **`data/make_demo_data.py`**: Generates lending dataset baseline.

---

### 📁 `tests/` — Automated Test Suite (48 Test Cases)

- **`tests/test_auth_and_isolation.py`**: Verifies password hashing, multi-tenant workspace isolation, and IDOR prevention.
- **`tests/test_customer_data_plane.py`**: Verifies the 13 data source connectors, local agent execution, policy engine, and zero-egress invariants.
- **`tests/test_engine.py`**: Verifies pure $\varepsilon$-Differential Privacy noise addition, utility preservation, and MIA accuracy bounds.
- **`tests/test_novabank_db.py`**: Tests NovaBank dataset generation and tenant database initialization.
- **`tests/test_org_database.py`**: Tests end-to-end synthesis across multiple industry verticals.

---

## 3. End-to-End Workflow Architecture

```
                       CUSTOMER ENCLAVE / DATA PLANE
┌────────────────────────────────────────────────────────────────────────┐
│                                                                        │
│   Enterprise Data Source (PostgreSQL / Snowflake / S3 / CSV)           │
│                             │                                          │
│                             ▼                                          │
│                   Unified Connector Layer                              │
│                             │                                          │
│                             ▼                                          │
│                In-Memory Common DataFrame                              │
│                             │                                          │
│                             ▼                                          │
│         Local Organization Governance Policy Enforcement               │
│                             │                                          │
│                             ▼                                          │
│            Local Differential Privacy (Laplace ε-DP)                   │
│                             │                                          │
│                             ▼                                          │
│                   Synthetic Data Generator                             │
│                             │                                          │
│                             ▼                                          │
│              Local Privacy & Utility Evaluator Gate                    │
│           (MIA Attack ≤ Bound, Fidelity ≥ Floor, 7/7 Checks)           │
│                             │                                          │
│                             ▼                                          │
│            Egress Controller (0 Raw Records Egress)                    │
│                                                                        │
└─────────────────────────────┬──────────────────────────────────────────┘
                              │
                    Approved Release & Metrics Only
                              │
                              ▼
                   DATA DELULU CONTROL PLANE
┌────────────────────────────────────────────────────────────────────────┐
│                                                                        │
│   • Multi-Tenant SQLite Database (`storage/datadelulu.db`)             │
│   • Results & Evaluation Dashboard (`http://localhost:8503`)           │
│   • Privacy Certificate & Audit Bundle Downloader                      │
│   • Cryptographic Tokenized Secure Share Links                         │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```
