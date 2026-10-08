"""Data Delulu Local Agent — In-Enclave Differential Privacy Engine.

Executes calibrated Laplace mechanisms and privacy budget accounting strictly inside
the customer environment. Raw counting queries never leave customer memory.
"""
from __future__ import annotations

import math
from typing import Any
import numpy as np
import pandas as pd
from src.engine import preprocess, synthesize, split, decode, recommend_epsilon, privacy_frontier, theoretical_attack_bound, DataError


class LocalDPEngine:
    """Customer-side Differential Privacy Engine."""

    def __init__(self, default_epsilon: float = 1.0):
        self.default_epsilon = default_epsilon

    def process_and_synthesize(self, df: pd.DataFrame, target: str, epsilon: float,
                               n_rows: int | None = None, seed: int = 0) -> dict[str, Any]:
        """Preprocesses raw dataset in-memory, splits, adds calibrated Laplace noise,
        and generates differentially private encoded synthetic data.
        """
        if epsilon <= 0:
            raise DataError("Privacy budget ε must be positive.")

        # 1. In-memory preprocessing and discretization
        enc_df, meta = preprocess(df, target)
        train_enc, test_enc = split(enc_df, target, test_size=0.3, seed=seed)

        # 2. Add calibrated Laplace noise and sample synthetic records
        target_n_rows = n_rows if n_rows is not None else len(train_enc)
        synth_enc, accounting = synthesize(train_enc, meta, epsilon, n_rows=target_n_rows, seed=seed)

        return {
            "meta": meta,
            "train_enc": train_enc,
            "test_enc": test_enc,
            "synth_enc": synth_enc,
            "accounting": accounting,
            "epsilon": epsilon,
            "n_rows_real": len(train_enc),
            "n_rows_synth": len(synth_enc),
            "target": target,
        }

    @staticmethod
    def get_theoretical_attack_bound(epsilon: float) -> float:
        """Computes mathematical worst-case Membership Inference Attack bound."""
        return theoretical_attack_bound(epsilon)
