"""Generates the simulated organizational source dataset for NovaBank.

Organization: NovaBank — Demo Environment
Domain: Banking / FinTech
Records: 12,500 (10,000+)

Fields:
- customer_id
- age
- gender
- city
- income
- account_type
- account_balance
- transaction_count
- average_transaction_amount
- credit_score
- loan_status
- loan_amount
- repayment_status
- transaction_category
- transaction_frequency
- fraud_flag

NOTE: This is SIMULATED / DEMO organizational data. It represents sensitive
internal bank data for the hackathon demonstration. It does NOT belong to real people.
"""
from pathlib import Path
import numpy as np
import pandas as pd


def generate_novabank_dataset(n: int = 12500, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    # 1. Customer Demographics
    customer_ids = [f"NB-{10001 + i}" for i in range(n)]
    ages = rng.integers(21, 76, n)
    genders = rng.choice(["Female", "Male", "Non-Binary"], n, p=[0.49, 0.48, 0.03])
    cities = rng.choice(
        ["New York", "San Francisco", "Austin", "Chicago", "Boston", "Seattle", "Charlotte"],
        n,
        p=[0.24, 0.18, 0.14, 0.15, 0.11, 0.10, 0.08]
    )

    # City income modifiers
    city_income_boost = pd.Series(cities).map({
        "New York": 1.25, "San Francisco": 1.35, "Austin": 1.10,
        "Chicago": 1.05, "Boston": 1.18, "Seattle": 1.20, "Charlotte": 0.95
    }).to_numpy()

    # 2. Financial Attributes
    base_income = rng.lognormal(11.0, 0.45, n) * city_income_boost
    income = np.clip(np.round(base_income, -2), 30000, 280000).astype(int)

    account_types = rng.choice(
        ["Checking", "Savings", "Premium Wealth", "Business"],
        n,
        p=[0.42, 0.36, 0.14, 0.08]
    )
    type_wealth_mult = pd.Series(account_types).map({
        "Checking": 0.15, "Savings": 0.45, "Premium Wealth": 1.8, "Business": 1.2
    }).to_numpy()

    account_balance = np.clip(
        np.round(rng.uniform(0.05, 0.65, n) * income * type_wealth_mult, 2),
        500.0, 350000.0
    )

    # Credit Score (300 - 850)
    credit_noise = rng.normal(0, 45, n)
    credit_score = np.clip(
        np.round(560 + 0.0009 * income + 1.2 * (ages - 21) + credit_noise),
        420, 850
    ).astype(int)

    # 3. Transactions & Activity
    transaction_categories = rng.choice(
        ["Retail & Grocery", "Travel & Dining", "Electronics & Tech", "Healthcare", "Investments"],
        n,
        p=[0.38, 0.24, 0.16, 0.12, 0.10]
    )
    transaction_frequencies = rng.choice(
        ["Daily", "Weekly", "Bi-Weekly", "Monthly"],
        n,
        p=[0.45, 0.35, 0.14, 0.06]
    )
    transaction_count = np.clip(
        np.round(rng.normal(90, 40, n) + (ages < 40) * 35),
        10, 380
    ).astype(int)

    avg_tx_amt = np.clip(
        np.round(rng.exponential(45, n) + (income / 1500) + (account_types == "Business") * 120, 2),
        8.50, 950.0
    )

    # 4. Lending & Risk
    loan_amount = np.where(
        rng.random(n) < 0.68,
        np.clip(np.round(rng.uniform(0.2, 1.4, n) * income, -2), 3000, 120000).astype(int),
        0
    )

    # Logistic approval / status formula
    approval_logit = (
        0.016 * (credit_score - 640)
        + 0.000015 * (income - 60000)
        + 0.00002 * (account_balance - 15000)
        - 0.000025 * loan_amount
        - 0.8
    )
    approval_prob = 1.0 / (1.0 + np.exp(-approval_logit))

    has_loan = loan_amount > 0
    approved_mask = has_loan & (rng.random(n) < approval_prob)
    rejected_mask = has_loan & (~approved_mask)

    loan_status = np.where(
        approved_mask, "Approved",
        np.where(rejected_mask, "Rejected", "No Loan")
    )

    repayment_status = []
    for i in range(n):
        if not approved_mask[i]:
            repayment_status.append("N/A")
        else:
            c_score = credit_score[i]
            if c_score >= 720:
                repayment_status.append(rng.choice(["On-Time", "Delayed 30d"], p=[0.94, 0.06]))
            elif c_score >= 600:
                repayment_status.append(rng.choice(["On-Time", "Delayed 30d", "Delayed 60d+", "Defaulted"], p=[0.74, 0.16, 0.07, 0.03]))
            else:
                repayment_status.append(rng.choice(["On-Time", "Delayed 30d", "Delayed 60d+", "Defaulted"], p=[0.48, 0.24, 0.16, 0.12]))

    # Fraud flag (realistic 3.2% anomaly rate)
    fraud_risk_score = (
        (avg_tx_amt > 400) * 1.8
        + (transaction_count > 250) * 1.2
        + (pd.Series(repayment_status) == "Defaulted").to_numpy() * 2.5
        + rng.normal(0, 1.0, n)
    )
    fraud_flag = np.where(fraud_risk_score > 3.2, "Flagged", "Normal")

    df = pd.DataFrame({
        "customer_id": customer_ids,
        "age": ages,
        "gender": genders,
        "city": cities,
        "income": income,
        "account_type": account_types,
        "account_balance": account_balance,
        "transaction_count": transaction_count,
        "average_transaction_amount": avg_tx_amt,
        "credit_score": credit_score,
        "loan_status": loan_status,
        "loan_amount": loan_amount,
        "repayment_status": repayment_status,
        "transaction_category": transaction_categories,
        "transaction_frequency": transaction_frequencies,
        "fraud_flag": fraud_flag,
    })
    return df


if __name__ == "__main__":
    out_dir = Path(__file__).resolve().parent
    df = generate_novabank_dataset(12500)
    out_path = out_dir / "novabank_demo.csv"
    df.to_csv(out_path, index=False)
    print(f"Generated NovaBank simulated dataset with {len(df):,} records and {df.shape[1]} columns at {out_path}")
