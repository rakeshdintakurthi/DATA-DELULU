"""Data Delulu Local Agent — In-Enclave Utility & ML Evaluator.

Trains and evaluates downstream ML models (Real vs Synthetic data) inside customer memory.
Exports only high-level statistical similarity metrics and classification scores.
"""
from __future__ import annotations

from typing import Any
import pandas as pd
from src.engine import evaluate_utility, column_similarity


class LocalUtilityEvaluator:
    """Evaluates machine learning utility and statistical fidelity locally."""

    @staticmethod
    def evaluate(train_enc: pd.DataFrame, test_enc: pd.DataFrame, synth_enc: pd.DataFrame,
                 meta: dict) -> dict[str, Any]:
        """Runs the complete suite of local utility evaluation benchmarks."""
        # 1. Train downstream models on Real vs Synthetic and test on held-out Real test set
        util = evaluate_utility(train_enc, test_enc, synth_enc, meta)

        # 2. Compute 1-way marginal distribution similarity
        col_sim = column_similarity(train_enc, synth_enc, meta)
        mean_sim = float(pd.Series(col_sim).mean()) if col_sim else 100.0

        real_acc = util["real_acc"]
        synth_acc = util["synth_acc"]
        utility_pct = 100.0 * synth_acc / real_acc if real_acc > 0 else 0.0

        return {
            "real_acc": round(real_acc, 4),
            "synth_acc": round(synth_acc, 4),
            "baseline_acc": round(util["baseline_acc"], 4),
            "utility_pct": round(utility_pct, 2),
            "similarity_pct": round(mean_sim, 2),
            "column_similarity": {k: round(v, 2) for k, v in col_sim.items()},
            "real_metrics": util.get("real_metrics", {}),
            "synth_metrics": util.get("synth_metrics", {}),
            "per_model": util.get("per_model", {})
        }
