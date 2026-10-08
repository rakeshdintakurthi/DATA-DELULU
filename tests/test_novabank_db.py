import sys
from pathlib import Path
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from data.make_novabank_data import generate_novabank_dataset
from src.novabank_db import init_novabank_database, connect_novabank_database, fetch_novabank_dataset
from src.engine import preprocess, synthesize, evaluate_utility, attribute_inference_attack, scorecard


def test_novabank_dataset_generation():
    df = generate_novabank_dataset(n=1000)
    assert len(df) == 1000
    expected_cols = [
        "customer_id", "age", "gender", "city", "income", "account_type",
        "account_balance", "transaction_count", "average_transaction_amount",
        "credit_score", "loan_status", "loan_amount", "repayment_status",
        "transaction_category", "transaction_frequency", "fraud_flag"
    ]
    for col in expected_cols:
        assert col in df.columns


def test_novabank_database_init_and_fetch(tmp_path):
    test_db = tmp_path / "novabank_test.db"
    res = init_novabank_database(db_path=test_db, n_records=500)
    assert res["status"] == "success"
    assert res["records_seeded"] == 500

    info = connect_novabank_database(db_path=test_db)
    assert info["connected"] is True
    assert info["records_available"] == 500

    fetched = fetch_novabank_dataset(db_path=test_db)
    assert len(fetched) == 500
    assert "loan_status" in fetched.columns
    assert "customer_id" in fetched.columns


def test_end_to_end_synthesis_on_novabank_data(tmp_path):
    df = generate_novabank_dataset(n=600)
    features_only = [c for c in df.columns if not c.lower().endswith("_id")]
    enc, meta = preprocess(df[features_only], "loan_status")
    
    synth_enc, acc = synthesize(enc, meta, epsilon=1.0)
    assert len(synth_enc) == len(enc)
    
    train = enc.iloc[:400]
    test = enc.iloc[400:]
    synth_train = synth_enc.iloc[:400]
    
    u = evaluate_utility(train, test, synth_train, meta)
    assert "real_acc" in u
    assert "synth_acc" in u
    assert "real_metrics" in u
    assert "synth_metrics" in u
    
    sc = scorecard(train, test, synth_train, meta, acc, epsilon=1.0)
    assert sc["tests_total"] == 7
    assert sc["utility_pct"] > 0
