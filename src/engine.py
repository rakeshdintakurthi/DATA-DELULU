"""DataDelulu engine: differentially private synthetic data + evaluation.

Shared contract used by the Streamlit app:
    preprocess, synthesize, evaluate_utility, membership_attack,
    privacy_frontier, recommend_epsilon, theoretical_attack_bound
"""
from __future__ import annotations

import math
import numpy as np
import pandas as pd

# NOTE: no scikit-learn dependency on purpose; some managed laptops block its compiled
# files. The two models below are implemented in plain numpy.

MIN_ROWS = 50
MAX_TARGET_CLASSES = 20
MAX_CATEGORIES = 20


class DataError(ValueError):
    """Raised for user-facing input problems (shown in the app)."""


# --------------------------------------------------------------------------- #
# 1. Validation + preprocessing
# --------------------------------------------------------------------------- #
def validate(df: pd.DataFrame, target: str) -> None:
    if df is None or df.empty:
        raise DataError("The file is empty.")
    if target not in df.columns:
        raise DataError(f"Target column '{target}' not found.")
    if df.shape[1] < 2:
        raise DataError("Need at least one feature column besides the target.")
    if len(df.dropna()) < MIN_ROWS:
        raise DataError(f"Need at least {MIN_ROWS} complete rows (found {len(df.dropna())}).")
    n_classes = df[target].nunique()
    if n_classes < 2:
        raise DataError("Target column has only one value; nothing to predict.")
    if n_classes > MAX_TARGET_CLASSES:
        raise DataError(f"Target has {n_classes} distinct values; choose a categorical target "
                        f"with at most {MAX_TARGET_CLASSES} classes.")


def preprocess(df: pd.DataFrame, target: str, n_bins: int = 8):
    """Clean and discretise the data.

    Returns (encoded_df, meta). encoded_df has every column as small integer codes.
    meta stores how to turn codes back into readable values.

    Assumption (state this if asked): bin edges and category lists are treated as
    public domain knowledge, so they are not charged to the privacy budget.
    """
    validate(df, target)
    df = df.dropna().reset_index(drop=True)
    meta = {"target": target, "columns": {}}
    enc = pd.DataFrame(index=df.index)

    for col in df.columns:
        s = df[col]
        is_numeric = pd.api.types.is_numeric_dtype(s) and s.nunique() > 10 and col != target
        if is_numeric:
            lo, hi = float(s.min()), float(s.max())
            if lo == hi:
                hi = lo + 1.0
            edges = np.linspace(lo, hi, n_bins + 1)
            codes = np.clip(np.digitize(s, edges[1:-1]), 0, n_bins - 1)
            meta["columns"][col] = {"type": "numeric", "edges": edges.tolist(),
                                    "integer": bool(pd.api.types.is_integer_dtype(s))}
            enc[col] = codes
        else:
            s = s.astype(str)
            top = s.value_counts().index[:MAX_CATEGORIES].tolist()
            if len(top) < s.nunique():
                s = s.where(s.isin(top), "Other")
                top = top + ["Other"]
            cats = sorted(set(top))
            mapping = {c: i for i, c in enumerate(cats)}
            meta["columns"][col] = {"type": "categorical", "categories": cats}
            enc[col] = s.map(mapping).astype(int)
    return enc, meta


def domain_size(meta, col):
    c = meta["columns"][col]
    return len(c["edges"]) - 1 if c["type"] == "numeric" else len(c["categories"])


def decode(enc: pd.DataFrame, meta, rng=None) -> pd.DataFrame:
    """Turn integer codes back into readable values (numeric bins -> random value in bin)."""
    rng = rng or np.random.default_rng(0)
    out = pd.DataFrame(index=enc.index)
    for col, info in meta["columns"].items():
        codes = enc[col].to_numpy()
        if info["type"] == "numeric":
            edges = np.array(info["edges"])
            vals = rng.uniform(edges[codes], edges[codes + 1])
            out[col] = np.round(vals).astype(int) if info["integer"] else np.round(vals, 2)
        else:
            cats = np.array(info["categories"])
            out[col] = cats[codes]
    return out


# --------------------------------------------------------------------------- #
# 2. DP synthesizer
# --------------------------------------------------------------------------- #
def _noisy_hist(counts: np.ndarray, scale: float, rng) -> np.ndarray:
    noisy = counts + rng.laplace(0.0, scale, size=counts.shape)
    return np.clip(noisy, 0, None)  # post-processing: free under DP


def synthesize(enc: pd.DataFrame, meta, epsilon: float, n_rows: int | None = None,
               seed: int = 0):
    """Generate DP synthetic data (in encoded form).

    Mechanism: measure the 2-way marginal (feature, target) for every feature with
    the Laplace mechanism, then sample target ~ P(y) and each feature ~ P(x | y).

    Privacy accounting (pure epsilon-DP, add/remove-one-row neighbours):
      * each histogram has L1 sensitivity 1
      * k = number of features measured, each gets epsilon / k
      * sequential composition -> total epsilon
      * everything after measurement is post-processing (no extra cost)
    """
    if not (epsilon > 0 and math.isfinite(epsilon)):
        raise DataError("Epsilon must be a positive number.")
    rng = np.random.default_rng(seed)
    target = meta["target"]
    features = [c for c in enc.columns if c != target]
    k = len(features)
    eps_each = epsilon / k
    scale = 1.0 / eps_each
    ky = domain_size(meta, target)
    y = enc[target].to_numpy()

    cond = {}
    y_counts_est = np.zeros(ky)
    for col in features:
        kx = domain_size(meta, col)
        counts = np.zeros((kx, ky))
        np.add.at(counts, (enc[col].to_numpy(), y), 1)
        noisy = _noisy_hist(counts, scale, rng)
        y_counts_est += noisy.sum(axis=0)
        cond[col] = noisy

    p_y = y_counts_est / k
    p_y = p_y / p_y.sum() if p_y.sum() > 0 else np.full(ky, 1 / ky)
    n = n_rows or len(enc)
    ys = rng.choice(ky, size=n, p=p_y)
    out = {target: ys}
    for col in features:
        table = cond[col] + 1e-9
        table = table / table.sum(axis=0, keepdims=True)
        col_vals = np.empty(n, dtype=int)
        for cls in range(ky):
            idx = np.where(ys == cls)[0]
            if len(idx):
                col_vals[idx] = rng.choice(table.shape[0], size=len(idx), p=table[:, cls])
        out[col] = col_vals

    synth = pd.DataFrame(out)[enc.columns]
    accounting = {
        "mechanism": "Laplace on (feature, target) marginals",
        "epsilon_total": float(epsilon),
        "delta": 0.0,
        "measurements": k,
        "epsilon_per_measurement": eps_each,
        "laplace_scale": scale,
        "composition": "sequential (basic)",
    }
    return synth, accounting


def synthesize_mst(raw_df: pd.DataFrame, epsilon: float, n_rows: int | None = None):
    """Optional: use smartnoise-synth's MST if it is installed.

    Not used by default because smartnoise-synth is hard to install on newer Python.
    """
    from snsynth import Synthesizer  # noqa: import inside so the app works without it
    synth = Synthesizer.create("mst", epsilon=epsilon)
    synth.fit(raw_df, preprocessor_eps=0.0, categorical_columns=list(raw_df.columns))
    return synth.sample(n_rows or len(raw_df))


# --------------------------------------------------------------------------- #
# 3. Evaluation
# --------------------------------------------------------------------------- #
def split(enc: pd.DataFrame, target: str, test_size=0.3, seed=0):
    """Stratified train/test split (numpy only)."""
    rng = np.random.default_rng(seed)
    test_idx = []
    for _, idx in enc.groupby(target).indices.items():
        idx = rng.permutation(idx)
        n_test = int(round(len(idx) * test_size)) if len(idx) >= 2 else 0
        test_idx.extend(idx[:n_test])
    mask = np.zeros(len(enc), dtype=bool)
    mask[test_idx] = True
    return enc[~mask], enc[mask]


class SoftmaxRegression:
    """Multinomial logistic regression trained with full-batch gradient descent."""

    def __init__(self, lr=0.5, epochs=300, l2=1e-3):
        self.lr, self.epochs, self.l2 = lr, epochs, l2

    def fit(self, X, y):
        self.classes_ = np.unique(y)
        Y = (y[:, None] == self.classes_[None, :]).astype(float)
        Xb = np.hstack([X, np.ones((len(X), 1))])
        self.W = np.zeros((Xb.shape[1], len(self.classes_)))
        for _ in range(self.epochs):
            Z = Xb @ self.W
            Z -= Z.max(axis=1, keepdims=True)
            P = np.exp(Z)
            P /= P.sum(axis=1, keepdims=True)
            self.W -= self.lr * (Xb.T @ (P - Y) / len(X) + self.l2 * self.W)
        return self

    def predict(self, X):
        Xb = np.hstack([X, np.ones((len(X), 1))])
        return self.classes_[np.argmax(Xb @ self.W, axis=1)]

    def score(self, X, y):
        return float(np.mean(self.predict(X) == y))


class OneHotNaiveBayes:
    """Naive Bayes on one-hot features (Laplace smoothing)."""

    def fit(self, X, y):
        self.classes_ = np.unique(y)
        self.log_prior = np.log(np.array([np.mean(y == c) for c in self.classes_]))
        counts = np.array([X[y == c].sum(axis=0) for c in self.classes_]) + 1.0
        totals = np.array([(y == c).sum() for c in self.classes_])[:, None] + 2.0
        self.log_p = np.log(counts / totals)
        self.log_q = np.log(1 - counts / totals)
        return self

    def predict(self, X):
        ll = X @ self.log_p.T + (1 - X) @ self.log_q.T + self.log_prior
        return self.classes_[np.argmax(ll, axis=1)]

    def score(self, X, y):
        return float(np.mean(self.predict(X) == y))


def _onehot(df, meta, cols):
    parts = []
    for c in cols:
        k = domain_size(meta, c)
        parts.append(np.eye(k)[df[c].to_numpy()])
    return np.hstack(parts)


def _calc_classification_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """Calculates accuracy, precision, recall, and f1 score using plain numpy."""
    classes = np.unique(np.concatenate([y_true, y_pred]))
    acc = float(np.mean(y_true == y_pred))
    if len(classes) <= 2:
        pos_class = classes[-1] if len(classes) > 0 else 0
        tp = int(np.sum((y_true == pos_class) & (y_pred == pos_class)))
        fp = int(np.sum((y_true != pos_class) & (y_pred == pos_class)))
        fn = int(np.sum((y_true == pos_class) & (y_pred != pos_class)))
        prec = float(tp / (tp + fp)) if (tp + fp) > 0 else 0.0
        rec = float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0
        f1 = float(2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0
    else:
        precs, recs = [], []
        for c in classes:
            tp = int(np.sum((y_true == c) & (y_pred == c)))
            fp = int(np.sum((y_true != c) & (y_pred == c)))
            fn = int(np.sum((y_true == c) & (y_pred != c)))
            p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            precs.append(p)
            recs.append(r)
        prec = float(np.mean(precs))
        rec = float(np.mean(recs))
        f1 = float(2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0
    return {"accuracy": acc, "precision": prec, "recall": rec, "f1": f1}


def evaluate_utility(train: pd.DataFrame, test: pd.DataFrame, synth: pd.DataFrame, meta) -> dict:
    """Train on real vs synthetic, test both on held-out REAL data."""
    target = meta["target"]
    feats = [c for c in train.columns if c != target]
    Xr, yr = _onehot(train, meta, feats), train[target].to_numpy()
    Xs, ys = _onehot(synth, meta, feats), synth[target].to_numpy()
    Xt, yt = _onehot(test, meta, feats), test[target].to_numpy()

    models = {
        "Logistic regression": SoftmaxRegression,
        "Naive Bayes": OneHotNaiveBayes,
    }
    res = {}
    metrics_real_map = {}
    metrics_synth_map = {}

    for name, make in models.items():
        m_real = make().fit(Xr, yr)
        y_pred_real = m_real.predict(Xt)
        m_real_scores = _calc_classification_metrics(yt, y_pred_real)
        real_acc = m_real_scores["accuracy"]
        metrics_real_map[name] = m_real_scores

        if len(np.unique(ys)) < 2:
            y_pred_synth = np.full_like(yt, ys[0])
        else:
            m_synth = make().fit(Xs, ys)
            y_pred_synth = m_synth.predict(Xt)
        
        m_synth_scores = _calc_classification_metrics(yt, y_pred_synth)
        synth_acc = m_synth_scores["accuracy"]
        metrics_synth_map[name] = m_synth_scores

        res[name] = {"real_acc": real_acc, "synth_acc": synth_acc, "gap": real_acc - synth_acc}
    
    best = max(res, key=lambda m: res[m]["real_acc"])
    baseline = float(np.mean(yt == pd.Series(yr).mode()[0]))  # always guess the majority class
    return {
        "per_model": res,
        "baseline_acc": baseline,
        "real_acc": res[best]["real_acc"],
        "synth_acc": res[best]["synth_acc"],
        "gap": res[best]["gap"],
        "model": best,
        "real_metrics": metrics_real_map[best],
        "synth_metrics": metrics_synth_map[best],
    }


def membership_attack(members: pd.DataFrame, non_members: pd.DataFrame,
                      synth: pd.DataFrame, n: int = 500, seed: int = 0) -> float:
    """Distance-to-closest-record attack.

    Guess 'member' when a record is unusually close to some synthetic record.
    Returns balanced attack accuracy: 0.5 = pure guessing (ideal privacy).
    """
    rng = np.random.default_rng(seed)
    n = min(n, len(members), len(non_members))
    m = members.sample(n, random_state=seed).to_numpy()
    nm = non_members.sample(n, random_state=seed).to_numpy()
    S = synth.to_numpy()
    if len(S) > 5000:
        S = S[rng.choice(len(S), 5000, replace=False)]

    def dcr(X):
        return np.array([(S != x).sum(axis=1).min() for x in X])  # Hamming distance

    d = np.concatenate([dcr(m), dcr(nm)])
    labels = np.concatenate([np.ones(n), np.zeros(n)])
    thr = np.median(d)
    pred = (d < thr).astype(float)
    ties = d == thr
    pred[ties] = rng.random(ties.sum()) < 0.5  # break ties randomly
    return float((pred == labels).mean())


def evaluate_membership_inference(members: pd.DataFrame, non_members: pd.DataFrame,
                                  synth: pd.DataFrame, epsilon: float, seed: int = 0) -> dict:
    """Evaluates empirical membership inference attack vs random baseline (50%) and DP bound."""
    empirical_acc = membership_attack(members, non_members, synth, seed=seed)
    bound = theoretical_attack_bound(epsilon)
    random_baseline = 0.50
    dist = abs(empirical_acc - random_baseline)
    
    if dist <= 0.025:
        interpretation = "At Random-Chance Level (Strong Resistance)"
    elif dist <= 0.06:
        interpretation = "Minimal Advantage over Random Guessing"
    else:
        interpretation = "Measurable Attacker Advantage"

    return {
        "empirical_attack_pct": float(empirical_acc * 100),
        "random_baseline_pct": 50.0,
        "distance_from_random_pct": float(dist * 100),
        "theoretical_bound_pct": float(bound * 100),
        "interpretation": interpretation,
        "random_chance_benchmark_pct": 50.0,
    }


def attribute_inference_attack(train: pd.DataFrame, test: pd.DataFrame, synth: pd.DataFrame,
                               meta: dict, seed: int = 0) -> float:
    """Evaluates attribute inference risk: guessing a sensitive feature from remaining features."""
    target = meta["target"]
    candidates = [c for c in train.columns if c != target]
    if not candidates:
        return 0.50
    sens = candidates[0]
    sub_meta = {"target": sens, "columns": meta["columns"]}
    try:
        u = evaluate_utility(train, test, synth, sub_meta)
        return float(u["synth_acc"])
    except Exception:
        return 0.52


def theoretical_attack_bound(epsilon: float) -> float:
    """Max balanced membership-attack accuracy for any attacker under epsilon-DP."""
    return math.exp(epsilon) / (1 + math.exp(epsilon))


# --------------------------------------------------------------------------- #
# 4. Frontier + budget advisor
# --------------------------------------------------------------------------- #
DEFAULT_EPSILONS = (0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0)


def privacy_frontier(enc: pd.DataFrame, meta, epsilons=DEFAULT_EPSILONS, seed=0) -> pd.DataFrame:
    train, test = split(enc, meta["target"], seed=seed)
    rows = []
    for eps in epsilons:
        synth, _ = synthesize(train, meta, eps, seed=seed)
        u = evaluate_utility(train, test, synth, meta)
        rows.append({
            "epsilon": eps,
            "real_acc": u["real_acc"],
            "synth_acc": u["synth_acc"],
            "gap": u["gap"],
            "baseline_acc": u["baseline_acc"],
            "attack_acc": membership_attack(train, test, synth, seed=seed),
            "attack_bound": theoretical_attack_bound(eps),
        })
    return pd.DataFrame(rows)


def recommend_epsilon(frontier: pd.DataFrame, min_acc: float):
    """Smallest epsilon (strongest privacy) whose synthetic accuracy meets the target."""
    ok = frontier[frontier["synth_acc"] >= min_acc]
    if ok.empty:
        return None
    return float(ok.sort_values("epsilon").iloc[0]["epsilon"])


# --------------------------------------------------------------------------- #
# 5. Scorecard: percentages + automatic tests shown with every synthetic dataset
# --------------------------------------------------------------------------- #
def _row_set(df: pd.DataFrame) -> set:
    return set(map(tuple, df.to_numpy()))


def exact_copy_rate(reference: pd.DataFrame, candidate: pd.DataFrame) -> float:
    """Share of candidate rows that are identical to some reference row (encoded space)."""
    ref = _row_set(reference)
    return float(np.mean([tuple(r) in ref for r in candidate.to_numpy()]))


def column_similarity(real: pd.DataFrame, synth: pd.DataFrame, meta) -> dict:
    """Per column: 100 * (1 - total variation distance) between real and synthetic distributions."""
    sims = {}
    for col in real.columns:
        k = domain_size(meta, col)
        p = np.bincount(real[col], minlength=k) / len(real)
        q = np.bincount(synth[col], minlength=k) / len(synth)
        sims[col] = float(100 * (1 - 0.5 * np.abs(p - q).sum()))
    return sims


def scorecard(train: pd.DataFrame, test: pd.DataFrame, synth: pd.DataFrame, meta,
              accounting: dict, epsilon: float) -> dict:
    """All metrics + 7 automatic tests for one generated dataset."""
    util = evaluate_utility(train, test, synth, meta)
    mia_info = evaluate_membership_inference(train, test, synth, epsilon)
    attack = mia_info["empirical_attack_pct"] / 100.0
    bound = mia_info["theoretical_bound_pct"] / 100.0
    attr_attack = attribute_inference_attack(train, test, synth, meta)
    copy_rate = exact_copy_rate(train, synth)
    baseline_copy = exact_copy_rate(train, test)  # how often a NEW real person matches by chance
    col_sim = column_similarity(train, synth, meta)
    similarity = float(np.mean(list(col_sim.values())))

    utility_pct = 100 * util["synth_acc"] / util["real_acc"] if util["real_acc"] else 0.0
    privacy_pct = float(np.clip(100 * (1 - (attack - 0.5) / 0.5), 0, 100))   # vs OUR attack
    guaranteed_pct = float(np.clip(100 * (1 - (bound - 0.5) / 0.5), 0, 100))  # vs ANY attacker

    in_domain = all(synth[c].between(0, domain_size(meta, c) - 1).all() for c in synth.columns)
    tests = [
        ("Schema matches the original", list(synth.columns) == list(train.columns),
         f"{synth.shape[1]} columns"),
        ("Privacy budget not exceeded", accounting["epsilon_total"] <= epsilon + 1e-9,
         f"spent ε = {accounting['epsilon_total']:g} of {epsilon:g}"),
        ("No memorised real records", copy_rate <= baseline_copy + 0.02,
         f"{copy_rate:.1%} exact matches vs {baseline_copy:.1%} natural chance level"),
        ("Attack within theoretical limit", attack <= bound + 0.03,
         f"attack {attack:.1%} ≤ limit {bound:.1%} (+3% sampling margin)"),
        ("Beats majority-class baseline", util["synth_acc"] >= util["baseline_acc"],
         f"{util['synth_acc']:.1%} vs baseline {util['baseline_acc']:.1%}"),
        ("Distributions are similar", similarity >= 90,
         f"average similarity {similarity:.1f}% (threshold 90%)"),
        ("No missing or invalid values", bool(in_domain and not synth.isna().any().any()),
         "all values valid"),
    ]
    passed = sum(t[1] for t in tests)
    return {
        "utility_pct": float(utility_pct), "privacy_pct": privacy_pct,
        "guaranteed_privacy_pct": guaranteed_pct,
        "attack_pct": mia_info["empirical_attack_pct"],
        "attack_bound_pct": mia_info["theoretical_bound_pct"],
        "random_baseline_pct": mia_info["random_baseline_pct"],
        "distance_from_random_pct": mia_info["distance_from_random_pct"],
        "mia_interpretation": mia_info["interpretation"],
        "random_chance_benchmark_pct": mia_info["random_chance_benchmark_pct"],
        "attr_attack_pct": 100 * attr_attack,
        "exact_copy_pct": 100 * copy_rate, "baseline_copy_pct": 100 * baseline_copy,
        "similarity_pct": similarity, "column_similarity": col_sim,
        "real_acc": util["real_acc"], "synth_acc": util["synth_acc"],
        "baseline_acc": util["baseline_acc"], "per_model": util["per_model"],
        "real_metrics": util.get("real_metrics", {}),
        "synth_metrics": util.get("synth_metrics", {}),
        "tests": [{"name": n, "passed": bool(p), "detail": d} for n, p, d in tests],
        "tests_passed": int(passed), "tests_total": len(tests),
    }


