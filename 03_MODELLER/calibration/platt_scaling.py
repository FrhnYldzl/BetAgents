"""
Platt Scaling — olasılık kalibrasyonu.

Referans:
    Platt, J. (1999). "Probabilistic outputs for support vector machines
    and comparisons to regularized likelihood methods."

Modelin ham olasılıkları (p_raw) gerçek frekansa kalibre edilir:
    p_calibrated = 1 / (1 + exp(A * p_raw + B))

A ve B parametreleri, validation seti üzerinde maximum likelihood ile bulunur.

Pratik kullanım:
    1. Eğit: model tahminleri + gerçek outcome'larla fit_platt()
    2. Tahmin: yeni model çıktısı için apply_platt()
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize


@dataclass
class PlattParams:
    """Platt scaling parametreleri."""
    a: float
    b: float
    n_train_samples: int

    def apply(self, p_raw: np.ndarray | float) -> np.ndarray | float:
        """Ham olasılığı kalibre et."""
        p_raw = np.asarray(p_raw)
        # Sigmoid(a * p + b), ama p_raw zaten olasılık olduğu için
        # logit(p_raw)'a uygulanır (standard Platt)
        # Numerik stabil logit
        eps = 1e-7
        p_clip = np.clip(p_raw, eps, 1.0 - eps)
        logit = np.log(p_clip / (1.0 - p_clip))
        z = self.a * logit + self.b
        # Sigmoid
        return 1.0 / (1.0 + np.exp(-z))


def _platt_nll(params: np.ndarray, logits: np.ndarray, y: np.ndarray) -> float:
    """Negatif log-likelihood (logistic regression)."""
    a, b = params
    z = a * logits + b
    # log(1 + exp(-z)) için stabil hesap
    nll = np.where(z >= 0,
                   np.log1p(np.exp(-z)) + (1 - y) * z,
                   np.log1p(np.exp(z)) - y * z)
    return float(np.sum(nll))


def fit_platt(p_raw: np.ndarray, y: np.ndarray) -> PlattParams:
    """
    Platt scaling parametrelerini fit eder.

    Args:
        p_raw: modelin ham tahmin olasılıkları, shape (n,)
        y: gerçek outcome (0 veya 1), shape (n,)

    Returns:
        PlattParams.
    """
    p_raw = np.asarray(p_raw, dtype=float)
    y = np.asarray(y, dtype=float)

    if len(p_raw) < 20:
        # Çok az veri → identity (kalibre etme)
        return PlattParams(a=1.0, b=0.0, n_train_samples=len(p_raw))

    eps = 1e-7
    p_clip = np.clip(p_raw, eps, 1.0 - eps)
    logits = np.log(p_clip / (1.0 - p_clip))

    # Hedef sayısı: positive/negative dengesizliği için Platt'ın orijinal düzeltmesi
    n_pos = float(np.sum(y == 1))
    n_neg = float(np.sum(y == 0))
    if n_pos == 0 or n_neg == 0:
        # Tek sınıf → kalibre edilemez, identity dön
        return PlattParams(a=1.0, b=0.0, n_train_samples=len(p_raw))

    # Platt'ın smoothed targets:
    t = np.where(y == 1, (n_pos + 1) / (n_pos + 2), 1.0 / (n_neg + 2))

    # Initial guess
    x0 = np.array([1.0, 0.0])
    result = minimize(
        _platt_nll, x0, args=(logits, t),
        method="L-BFGS-B",
        bounds=[(-10, 10), (-10, 10)],
        options={"maxiter": 200},
    )

    a, b = float(result.x[0]), float(result.x[1])
    return PlattParams(a=a, b=b, n_train_samples=len(p_raw))


def apply_platt(params: PlattParams, p_raw: np.ndarray | float) -> np.ndarray | float:
    return params.apply(p_raw)


# ============================================================
# CLI test
# ============================================================

if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    # Sentetik test: aşırı özgüvenli bir model (true rate %50 ama model %30/%70 söylüyor)
    rng = np.random.default_rng(42)
    n = 1000
    true_p = 0.5
    y = (rng.random(n) < true_p).astype(int)
    # Model tahmini: çok özgüvenli (uçlara yakın)
    p_raw = np.where(y == 1,
                     rng.uniform(0.55, 0.95, n),
                     rng.uniform(0.05, 0.45, n))

    print("=== Kalibrasyon oncesi ===")
    # 10 bin'e böl, her bin'in ortalama tahmin vs gerçek frekans
    bins = np.linspace(0, 1, 11)
    for i in range(10):
        mask = (p_raw >= bins[i]) & (p_raw < bins[i + 1])
        if mask.sum() > 0:
            avg_pred = p_raw[mask].mean()
            avg_real = y[mask].mean()
            print(f"  bin [{bins[i]:.1f},{bins[i+1]:.1f}): n={mask.sum():3d} "
                  f"avg_pred={avg_pred:.3f} avg_real={avg_real:.3f} "
                  f"diff={avg_pred - avg_real:+.3f}")

    params = fit_platt(p_raw, y)
    print(f"\nPlatt params: a={params.a:.3f}, b={params.b:.3f}")

    p_cal = apply_platt(params, p_raw)

    print("\n=== Kalibrasyon sonrasi ===")
    for i in range(10):
        mask = (p_cal >= bins[i]) & (p_cal < bins[i + 1])
        if mask.sum() > 0:
            avg_pred = p_cal[mask].mean()
            avg_real = y[mask].mean()
            print(f"  bin [{bins[i]:.1f},{bins[i+1]:.1f}): n={mask.sum():3d} "
                  f"avg_pred={avg_pred:.3f} avg_real={avg_real:.3f} "
                  f"diff={avg_pred - avg_real:+.3f}")

    # Brier score karşılaştırması
    from numpy import mean
    brier_raw = float(mean((p_raw - y) ** 2))
    brier_cal = float(mean((p_cal - y) ** 2))
    print(f"\nBrier score:  ham={brier_raw:.4f}  kalibre={brier_cal:.4f}  (dusuk = daha iyi)")
