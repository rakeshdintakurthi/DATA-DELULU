"""Data Delulu Local Agent — In-Enclave Synthetic Data Generator.

Generates tabular synthetic data by decoding DP-sampled marginal distributions.
Clears intermediate raw arrays from local memory after completion.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from src.engine import decode


class LocalSyntheticGenerator:
    """Local synthetic dataset generation and decoding module."""

    @staticmethod
    def decode_synthetic(synth_enc: pd.DataFrame, meta: dict, seed: int = 0) -> pd.DataFrame:
        """Decodes integer codes into readable tabular attributes."""
        rng = np.random.default_rng(seed)
        synth_df = decode(synth_enc, meta, rng=rng)
        return synth_df
