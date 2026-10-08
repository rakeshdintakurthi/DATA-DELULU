"""Generates distinct, realistic organizational datasets for different industry domains.

Organizations:
1. SmartHire InfoTech (HR & Tech Workforce) -> 8,420 records
2. FinEdge Lending (Fintech & Lending) -> 23,750 records
3. Apex Health Systems / HealthNova (Healthcare & Clinical) -> 5,280 records
4. RetailX Analytics (E-Commerce & Retail) -> 41,200 records
5. NovaBank — Demo Environment (Banking & Risk) -> 12,500 records
6. Generic / Custom Organization -> 5,000 records
"""
from pathlib import Path
import numpy as np
import pandas as pd


def generate_smarthire_dataset(n: int = 8420, seed: int = 101) -> pd.DataFrame:
    """SmartHire InfoTech: HR & Workforce analytics dataset."""
    rng = np.random.default_rng(seed)
    emp_ids = [f"SH-{20000 + i}" for i in range(n)]
    ages = rng.integers(22, 62, n)
    depts = rng.choice(
        ["Engineering", "Product & Design", "Sales & Marketing", "Customer Success", "Operations", "Finance"],
        n, p=[0.38, 0.16, 0.20, 0.12, 0.08, 0.06]
    )
    experience = np.clip(np.round((ages - 21) * rng.uniform(0.3, 0.9, n)), 0, 35).astype(int)
    education = rng.choice(["Bachelors", "Masters", "PhD", "Bootcamp / Associate"], n, p=[0.55, 0.30, 0.05, 0.10])
    
    dept_salary_mult = pd.Series(depts).map({
        "Engineering": 1.25, "Product & Design": 1.15, "Sales & Marketing": 1.05,
        "Customer Success": 0.85, "Operations": 0.90, "Finance": 1.10
    }).to_numpy()
    
    base_sal = (48000 + 4200 * experience + rng.normal(0, 8000, n)) * dept_salary_mult
    salary = np.clip(np.round(base_sal, -2), 38000, 240000).astype(int)
    
    ratings = rng.choice([1, 2, 3, 4, 5], n, p=[0.06, 0.14, 0.48, 0.24, 0.08])
    projects = np.clip(np.round(rng.normal(6 + experience * 0.4, 2.5, n)), 1, 25).astype(int)
    remote_ratio = rng.choice([0.0, 0.5, 0.8, 1.0], n, p=[0.15, 0.35, 0.20, 0.30])
    promotions = np.where(rng.random(n) < (0.10 + 0.05 * (ratings >= 4)), "Yes", "No")
    satisfaction = np.clip(np.round(rng.normal(3.4 + 0.3 * (ratings - 3) + 0.4 * remote_ratio, 0.8, n), 1), 1.0, 5.0)
    commute = np.clip(np.round(rng.exponential(12, n)), 1, 65).astype(int)
    training = np.clip(np.round(rng.normal(24, 12, n)), 4, 90).astype(int)
    hiring_src = rng.choice(["LinkedIn", "Employee Referral", "Campus Recruitment", "Direct Inbound", "Agency"], n, p=[0.35, 0.28, 0.15, 0.14, 0.08])
    
    # Attrition Risk target
    attr_logit = (
        -0.8 * (satisfaction - 3.0)
        - 0.000015 * (salary - 80000)
        + 0.02 * commute
        - 0.6 * (promotions == "Yes")
        + 0.4 * (ratings <= 2)
        - 1.2
    )
    attr_prob = 1.0 / (1.0 + np.exp(-attr_logit))
    attrition = np.where(rng.random(n) < attr_prob, "High Risk", "Retained")

    return pd.DataFrame({
        "employee_id": emp_ids,
        "age": ages,
        "department": depts,
        "years_experience": experience,
        "education_level": education,
        "salary": salary,
        "performance_rating": ratings,
        "projects_completed": projects,
        "remote_work_ratio": remote_ratio,
        "promotion_last_3years": promotions,
        "satisfaction_score": satisfaction,
        "commute_distance_km": commute,
        "training_hours_annual": training,
        "hiring_source": hiring_src,
        "attrition_risk": attrition
    })


def generate_finedge_dataset(n: int = 23750, seed: int = 202) -> pd.DataFrame:
    """FinEdge Lending: Fintech and consumer credit dataset."""
    rng = np.random.default_rng(seed)
    b_ids = [f"FE-{500000 + i}" for i in range(n)]
    ages = rng.integers(21, 70, n)
    emp_types = rng.choice(["Full-Time Salaried", "Self-Employed", "Gig Economy / Contract", "Retired"], n, p=[0.62, 0.22, 0.11, 0.05])
    
    income = np.clip(np.round(rng.lognormal(10.9, 0.48, n), -2), 24000, 290000).astype(int)
    credit_scores = np.clip(np.round(rng.normal(635 + (income / 3500) + (ages - 21) * 0.8, 55, n)), 450, 850).astype(int)
    
    purposes = rng.choice(
        ["Debt Consolidation", "Home Improvement", "Small Business", "Medical Expenses", "Major Purchase", "Auto Loan"],
        n, p=[0.42, 0.18, 0.14, 0.10, 0.09, 0.07]
    )
    req_amt = np.clip(np.round(rng.uniform(0.15, 0.85, n) * income, -2), 2500, 85000).astype(int)
    dti = np.clip(np.round(rng.normal(26 + (req_amt / income) * 20, 9, n), 1), 4.0, 65.0)
    open_lines = np.clip(np.round(rng.normal(9, 4, n)), 1, 28).astype(int)
    delinq = np.clip(np.round(rng.exponential(0.4, n)), 0, 8).astype(int)
    
    # Interest rate based on credit score
    rate = np.clip(np.round(24.5 - (credit_scores - 450) * 0.038 + (dti > 40) * 2.5 + rng.normal(0, 0.8, n), 2), 5.5, 29.9)
    term = rng.choice([24, 36, 48, 60], n, p=[0.15, 0.45, 0.25, 0.15])
    collateral = rng.choice(["Unsecured", "Vehicle", "Property Equity", "Savings Certificate"], n, p=[0.68, 0.16, 0.11, 0.05])
    
    risk_tier = np.where(credit_scores >= 740, "Tier A (Prime)",
                np.where(credit_scores >= 660, "Tier B (Near Prime)",
                np.where(credit_scores >= 580, "Tier C (Subprime)", "Tier D (High Risk)")))

    default_logit = (
        -0.015 * (credit_scores - 620)
        + 0.045 * (dti - 25)
        + 0.35 * delinq
        + 0.08 * (rate - 12)
        - 1.8
    )
    def_prob = 1.0 / (1.0 + np.exp(-default_logit))
    default_flag = np.where(rng.random(n) < def_prob, "Defaulted", "Current / Paid")

    return pd.DataFrame({
        "borrower_id": b_ids,
        "age": ages,
        "employment_type": emp_types,
        "annual_income": income,
        "credit_score": credit_scores,
        "loan_purpose": purposes,
        "requested_amount": req_amt,
        "debt_to_income": dti,
        "open_credit_lines": open_lines,
        "delinquencies_2yr": delinq,
        "interest_rate_pct": rate,
        "loan_term_months": term,
        "collateral_type": collateral,
        "risk_tier": risk_tier,
        "loan_default": default_flag
    })


def generate_apexhealth_dataset(n: int = 5280, seed: int = 303) -> pd.DataFrame:
    """Apex Health Systems / HealthNova: Clinical research and patient outcomes."""
    rng = np.random.default_rng(seed)
    p_ids = [f"PT-{100000 + i}" for i in range(n)]
    ages = rng.integers(18, 88, n)
    genders = rng.choice(["Female", "Male", "Other"], n, p=[0.52, 0.46, 0.02])
    
    bp_systolic = np.clip(np.round(rng.normal(122 + (ages - 18) * 0.35, 14, n)), 90, 195).astype(int)
    cholesterol = np.clip(np.round(rng.normal(195 + (ages - 18) * 0.5, 32, n)), 120, 340).astype(int)
    bmi = np.clip(np.round(rng.normal(27.2, 5.2, n), 1), 16.5, 48.0)
    smoker = rng.choice(["Never", "Former", "Current"], n, p=[0.58, 0.26, 0.16])
    
    conditions = np.clip(np.round(rng.poisson(0.4 + (ages / 35), n)), 0, 7).astype(int)
    adm_type = rng.choice(["Emergency", "Elective", "Urgent", "Outpatient Referral"], n, p=[0.42, 0.28, 0.18, 0.12])
    los = np.clip(np.round(rng.exponential(3.8 + conditions * 0.8, n)), 1, 28).astype(int)
    labs = np.clip(np.round(rng.normal(14 + los * 1.5, 6, n)), 2, 55).astype(int)
    meds = np.clip(np.round(rng.normal(4 + conditions * 1.2, 2.5, n)), 1, 18).astype(int)
    ins = rng.choice(["Medicare", "Commercial HMO", "Commercial PPO", "Medicaid", "Self-Pay"], n, p=[0.38, 0.26, 0.22, 0.10, 0.04])
    
    diagnosis = rng.choice(
        ["Cardiovascular", "Respiratory / Pulmonary", "Metabolic & Diabetes", "Orthopedic", "Neurology", "General Surgery"],
        n, p=[0.30, 0.22, 0.18, 0.14, 0.09, 0.07]
    )

    readm_logit = (
        0.03 * (ages - 50)
        + 0.35 * conditions
        + 0.06 * (los - 4)
        + 0.4 * (adm_type == "Emergency")
        - 0.3 * (ins == "Commercial PPO")
        - 1.7
    )
    readm_prob = 1.0 / (1.0 + np.exp(-readm_logit))
    readmission = np.where(rng.random(n) < readm_prob, "Readmitted (30d)", "No Readmission")

    return pd.DataFrame({
        "patient_id": p_ids,
        "age": ages,
        "gender": genders,
        "blood_pressure_systolic": bp_systolic,
        "cholesterol_mg_dl": cholesterol,
        "bmi": bmi,
        "smoking_status": smoker,
        "chronic_conditions_count": conditions,
        "admission_type": adm_type,
        "length_of_stay_days": los,
        "lab_procedures_count": labs,
        "prescribed_medications_count": meds,
        "insurance_plan": ins,
        "diagnosis_category": diagnosis,
        "readmission_30d": readmission
    })


def generate_retailx_dataset(n: int = 41200, seed: int = 404) -> pd.DataFrame:
    """RetailX Analytics: E-commerce and omni-channel customer analytics."""
    rng = np.random.default_rng(seed)
    c_ids = [f"RX-{800000 + i}" for i in range(n)]
    ages = rng.integers(18, 72, n)
    genders = rng.choice(["Female", "Male", "Unspecified"], n, p=[0.51, 0.45, 0.04])
    cities = rng.choice(["New York", "Los Angeles", "Chicago", "Dallas", "Miami", "Atlanta", "Seattle", "Denver"], n)
    
    tier = rng.choice(["Bronze", "Silver", "Gold", "Platinum VIP"], n, p=[0.50, 0.30, 0.15, 0.05])
    tier_mult = pd.Series(tier).map({"Bronze": 1.0, "Silver": 2.2, "Gold": 4.5, "Platinum VIP": 8.0}).to_numpy()
    
    orders = np.clip(np.round(rng.exponential(4, n) * tier_mult), 1, 120).astype(int)
    aov = np.clip(np.round(rng.normal(55 + tier_mult * 15, 22, n), 2), 12.0, 480.0)
    annual_spend = np.round(orders * aov, 2)
    
    category = rng.choice(["Apparel & Fashion", "Electronics", "Beauty & Personal", "Home & Kitchen", "Sports & Fitness"], n)
    loyalty_pts = np.clip(np.round(annual_spend * 1.5 + rng.normal(0, 100, n)), 0, 50000).astype(int)
    ret_rate = np.clip(np.round(rng.beta(2, 8, n) * 100, 1), 0.0, 45.0)
    email_open = np.clip(np.round(rng.beta(3, 5, n) * 100, 1), 0.0, 95.0)
    app_user = np.where(rng.random(n) < (0.35 + 0.15 * (ages < 35)), "Yes", "No")
    payment = rng.choice(["Credit Card", "Digital Wallet (Apple/Google)", "Debit Card", "Buy-Now-Pay-Later"], n, p=[0.45, 0.32, 0.15, 0.08])
    
    churn_logit = (
        -0.03 * (orders - 4)
        - 0.02 * (email_open - 30)
        + 0.04 * (ret_rate - 15)
        - 0.5 * (app_user == "Yes")
        - 0.8
    )
    churn_prob = 1.0 / (1.0 + np.exp(-churn_logit))
    churn = np.where(rng.random(n) < churn_prob, "Churned", "Active")

    return pd.DataFrame({
        "customer_id": c_ids,
        "age": ages,
        "gender": genders,
        "city": cities,
        "membership_tier": tier,
        "annual_spend": annual_spend,
        "orders_placed": orders,
        "average_order_value": aov,
        "preferred_category": category,
        "loyalty_points": loyalty_pts,
        "return_rate_pct": ret_rate,
        "email_open_rate_pct": email_open,
        "mobile_app_user": app_user,
        "payment_method": payment,
        "churn_flag": churn
    })


def generate_custom_org_dataset(org_name: str, sector: str, n: int = 5000, seed: int = 505) -> pd.DataFrame:
    """Generates an initial isolated dataset for newly registered custom organizations."""
    sector_lower = sector.lower()
    if "health" in sector_lower:
        return generate_apexhealth_dataset(n=n, seed=seed)
    elif "fintech" in sector_lower or "lend" in sector_lower:
        return generate_finedge_dataset(n=n, seed=seed)
    elif "hr" in sector_lower or "recruit" in sector_lower or "tech" in sector_lower:
        return generate_smarthire_dataset(n=n, seed=seed)
    elif "retail" in sector_lower or "commerce" in sector_lower:
        return generate_retailx_dataset(n=n, seed=seed)
    else:
        from data.make_novabank_data import generate_novabank_dataset
        return generate_novabank_dataset(n=n, seed=seed)
