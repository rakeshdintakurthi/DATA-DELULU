"""Data Delulu Local Agent — In-Enclave Privacy & Attack Evaluator.

Executes empirical attacks (Membership Inference Attack, Attribute Inference, Exact Copy)
strictly inside customer memory. Only sanitized percentages and test outcomes are exported.
"""
from __future__ import annotations

from typing import Any
import numpy as np
import pandas as pd
from src.engine import (
    membership_attack, exact_copy_rate, theoretical_attack_bound,
    attribute_inference_attack
)


class LocalPrivacyEvaluator:
    """Evaluates empirical and theoretical privacy metrics locally."""

    @staticmethod
    def evaluate(train_enc: pd.DataFrame, test_enc: pd.DataFrame, synth_enc: pd.DataFrame,
                 meta: dict, epsilon: float) -> dict[str, Any]:
        """Runs the complete suite of local privacy tests."""
        # 1. Membership Inference Attack (empirical red-team attacker)
        mia_acc = membership_attack(train_enc, test_enc, synth_enc)
        attack_bound = theoretical_attack_bound(epsilon)
        guaranteed_priv = float(np.clip(100 * (1 - (attack_bound - 0.5) / 0.5), 0, 100))

        # 2. Attribute inference attack
        attr_acc = attribute_inference_attack(train_enc, test_enc, synth_enc, meta)

        # 3. Exact Duplication / Memorization check
        exact_copy = exact_copy_rate(train_enc, synth_enc)
        baseline_copy = exact_copy_rate(train_enc, test_enc)

        # 4. Privacy % (empirical resistance)
        emp_privacy_pct = max(0.0, min(100.0, 100.0 * (1.0 - 2.0 * max(0.0, mia_acc - 0.50))))

        return {
            "attack_pct": round(mia_acc * 100.0, 2),
            "attack_bound_pct": round(attack_bound * 100.0, 2),
            "guaranteed_privacy_pct": round(guaranteed_priv, 2),
            "privacy_pct": round(emp_privacy_pct, 2),
            "attr_attack_pct": round(attr_acc * 100.0, 2),
            "exact_copy_pct": round(exact_copy * 100.0, 3),
            "baseline_copy_pct": round(baseline_copy * 100.0, 3),
            "memorization_detected": bool(exact_copy > max(0.05, baseline_copy + 0.02)),
        }
