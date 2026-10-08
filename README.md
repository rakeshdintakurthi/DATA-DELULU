# DATA DELULU — Privacy Infrastructure for AI

> *"The software goes to the data. The data does not go to the software."*

**Data Delulu** transforms synthetic data generation into a **Customer-Controlled Private Data Plane** architecture. Raw organizational data remains strictly inside the customer's private environment (VPC, secure enclave, or on-premises server). The Data Delulu Cloud control plane orchestrates jobs, manages governance policies, and visualizes safe mathematical metrics—without receiving a single raw record.

---

## 🏗️ Target Architecture & Security Perimeter

```
                    DATA DELULU CLOUD
                 ┌──────────────────────┐
                 │     CONTROL PLANE    │
                 │                      │
                 │ Authentication       │
                 │ Organizations        │
                 │ Users / RBAC         │
                 │ Policies             │
                 │ Job Management       │
                 │ Audit METADATA       │
                 │ Privacy Metrics      │
                 │ Utility Metrics      │
                 └──────────┬───────────┘
                            │
                      Secure Control API
                            │
================================================
              CUSTOMER SECURITY BOUNDARY
================================================
                            │
                 ┌──────────▼──────────┐
                 │ DATA DELULU AGENT   │
                 │                      │
                 │ Policy Engine        │
                 │ DB Connector         │
                 │ DP Engine            │
                 │ Synthetic Generator  │
                 │ Privacy Tests        │
                 │ Utility Tests        │
                 │ Egress Controller    │
                 └──────────┬───────────┘
                            │
                            ▼
                 ┌────────────────────┐
                 │ CUSTOMER DATABASE  │
                 │                    │
                 │ RAW DATA           │
                 └────────────────────┘
```

---

## 🛡️ Core Security Guarantees & Invariants

1. **Zero Raw Data Egress:** Server-side firewall (`EgressController`) guarantees `raw_records_transmitted = 0` and `raw_bytes_transmitted = 0`.
2. **Least-Privilege Database Access:** Local agent connects using read-only accounts (`SELECT` queries only).
3. **Customer Policy Enforcement:** Organization admins configure allowed/blocked tables, blocked columns (PII/secrets), epsilon ceilings ($\varepsilon$), and minimum utility floors.
4. **Local Differential Privacy:** Pure $\varepsilon$-DP ($\delta = 0$) Laplace mechanism executes entirely inside customer memory.
5. **In-Enclave Attack Auditing:** Membership Inference Attacks (MIA), Attribute Inference, and Exact Copy Memorization tests execute locally.
6. **Fail-Closed Release Gate:** If utility, privacy, or policy checks fail, synthetic data egress is blocked immediately (`ReleaseStatus.BLOCKED`).
7. **Emergency Agent Kill Switch:** Organizations can immediately disable their local agent from their environment, terminating database access and telemetry.
8. **Multi-Tenant Isolation:** Central control plane enforces strict `organization_id` isolation across all queries and API responses.

---

## 📦 Package Layout

```
datadelulu/
├── app/
│   ├── streamlit_app.py        # Control Plane Web Dashboard & RBAC UI
│   └── ui.py                   # Reusable UI components, cards, & styles
├── data_delulu_agent/          # Customer-Controlled Data Plane Agent
│   ├── __init__.py             # Agent exports & types
│   ├── agent.py                # Agent runtime & CLI orchestrator
│   ├── config.py               # Local enclave configuration & secrets
│   ├── db_connector.py         # Extensible DB connectors (Postgres, MySQL, SQLite, CSV)
│   ├── policy_engine.py        # Organization Policy model & enforcement engine
│   ├── dp_engine.py            # In-enclave Differential Privacy Laplace engine
│   ├── synthetic_generator.py  # In-enclave tabular synthetic decoder
│   ├── privacy_evaluator.py    # Local MIA & attribute attack evaluator
│   ├── utility_evaluator.py    # Local ML utility & TVD statistical evaluator
│   ├── release_gate.py         # Multi-check Release Gate (Approved / Blocked / Pending)
│   ├── egress_controller.py    # Outbound egress firewall (0 raw records guaranteed)
│   └── audit.py                # Local sanitized JSONL audit logger
├── src/
│   ├── auth.py                 # Multi-tenant auth, bcrypt hashing, RBAC
│   ├── db.py                   # Control plane database schema, policies, and telemetry
│   ├── engine.py               # Core mathematical algorithms & ML benchmarking
│   └── org_database.py         # Multi-tenant isolated database routing
├── Dockerfile                  # Control Plane container build
├── Dockerfile.agent            # Customer Data Plane Agent container build
├── docker-compose.yml          # Multi-tenant simulated deployment
└── tests/
    ├── test_customer_data_plane.py # Comprehensive 20-point security test suite
    ├── test_auth_and_isolation.py  # RBAC & tenant boundary tests
    ├── test_engine.py              # DP math & attack tests
    ├── test_novabank_db.py         # NovaBank isolated data tests
    └── test_org_database.py        # Isolated DB configuration tests
```

---

## 🚀 Getting Started

### 1. Local Development Simulation
```bash
# Terminal 1: Run Control Plane Dashboard
python -m streamlit run app/streamlit_app.py

# Terminal 2: Run Customer A Data Delulu Agent (NovaBank Enclave)
python -m data_delulu_agent.agent --org-id 5 --db-type sqlite --target loan_status

# Terminal 3: Run Customer B Data Delulu Agent (FinEdge Enclave)
python -m data_delulu_agent.agent --org-id 2 --db-type sqlite --target loan_default
```

### 2. Docker Compose Deployment
```bash
docker compose up --build
```
- **Control Plane:** `http://localhost:8501`
- **Agent NovaBank:** Container on isolated `novabank-private-vpc`
- **Agent FinEdge:** Container on isolated `finedge-private-vpc`

### 3. Demo Credentials
| Organization | Email | Role | Password |
|---|---|---|---|
| **SmartHire InfoTech** | `adam@gmail.com` | ADMIN | `SmartHire2026!` |
| **NovaBank** | `admin@novabank.demo` | ADMIN | `NovaBank2026!` |
| **FinEdge Lending** | `admin@finedge.demo` | ADMIN | `FinEdge2026!` |
| **FinEdge Lending** | `viewer@finedge.demo` | VIEWER | `FinEdge2026!` |
| **Apex Health Systems** | `admin@healthcare.demo` | ADMIN | `Health2026!` |
| **RetailX Analytics** | `admin@retailx.demo` | ADMIN | `RetailX2026!` |

---

## 🧪 Automated Security Test Suite

Run the full automated test suite (41/41 tests passing):
```bash
python -m pytest -v
```
Verifies all 20 required security invariants:
- [x] Raw data never reaches control plane
- [x] Raw data is never written to central database
- [x] Raw data & credentials never appear in central logs
- [x] Customer A cannot access Customer B data
- [x] Customer A agent cannot access Customer B database
- [x] Blocked columns (PII/secrets) are stripped before modeling
- [x] Blocked tables are rejected at the policy engine
- [x] Raw data export is ALWAYS denied
- [x] Synthetic export strictly follows organization policy
- [x] Agent kill switch immediately halts local processing
- [x] Database credentials never appear in API responses
- [x] Database credentials never appear in logs
- [x] Failed policy check blocks job execution
- [x] Failed privacy check blocks dataset release
- [x] Failed utility check blocks release
- [x] Agent processes data locally with 0 raw egress
- [x] Session & logout isolation enforced
- [x] Differential Privacy mathematical bounds verified
- [x] Downstream ML utility tests verified
- [x] Tenant RBAC isolation verified
