"""
Dixon-Coles modeli — futbol skor olasılığı tahminleyici.

Referans:
    Dixon, M. J., & Coles, S. G. (1997).
    "Modelling Association Football Scores and Inefficiencies in the
     Football Betting Market." Applied Statistics, 46(2), 265-280.

Model:
    Ev gol beklentisi:    λ = exp(α_home + β_away + γ)
    Dep gol beklentisi:   μ = exp(α_away + β_home)

    P(Home=i, Away=j) = τ(i,j) × Pois(i; λ) × Pois(j; μ)

Burada:
    α_team : takımın hücum gücü (log skala)
    β_team : takımın savunma gücü (log skala, negatif = güçlü)
    γ      : ev sahibi avantajı
    τ      : düşük skor düzeltmesi (0-0, 1-0, 0-1, 1-1)

Zaman bozulması (time decay):
    Her maça w_t = exp(-ξ × Δt_gün) ağırlığı verilir.
    ξ = 0.0019 (haftalık ~%1.4 bozulma) Dixon-Coles'un önerisi.

Çıktı:
    score_matrix[i, j] = P(home=i, away=j)
    Bundan türetilir:
        - 1X2: P(Home Win), P(Draw), P(Away Win)
        - Alt/Üst N.5: P(home + away > N) etc.
        - KG (BTTS): P(home >= 1 AND away >= 1)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

import numpy as np
from scipy.optimize import minimize
from scipy.stats import poisson

# ============================================================
# DÜŞÜK SKOR DÜZELTMESİ (τ)
# ============================================================

def tau(i: int, j: int, lam: float, mu: float, rho: float) -> float:
    """
    Dixon-Coles düşük skor düzeltme fonksiyonu.
    Sadece (0,0), (1,0), (0,1), (1,1) skorlarını etkiler.
    """
    if i == 0 and j == 0:
        return 1.0 - lam * mu * rho
    if i == 0 and j == 1:
        return 1.0 + lam * rho
    if i == 1 and j == 0:
        return 1.0 + mu * rho
    if i == 1 and j == 1:
        return 1.0 - rho
    return 1.0


def tau_matrix(lam: float, mu: float, rho: float, max_goals: int = 10) -> np.ndarray:
    """4x4 alt köşede τ'lar, geri kalan = 1."""
    T = np.ones((max_goals + 1, max_goals + 1))
    T[0, 0] = 1.0 - lam * mu * rho
    T[0, 1] = 1.0 + lam * rho
    T[1, 0] = 1.0 + mu * rho
    T[1, 1] = 1.0 - rho
    return T


# ============================================================
# OLASILIK MATRİSİ
# ============================================================

def score_matrix(
    lam: float,
    mu: float,
    rho: float = -0.1,
    max_goals: int = 10,
) -> np.ndarray:
    """
    Verilen λ (ev), μ (dep), ρ parametreleri için
    P(home=i, away=j) matrisi döndürür.
    Boyut: (max_goals+1, max_goals+1)
    """
    i = np.arange(max_goals + 1)
    home_pmf = poisson.pmf(i, lam)  # P(i goal)
    away_pmf = poisson.pmf(i, mu)
    M = np.outer(home_pmf, away_pmf)  # M[i, j] = home_pmf[i] * away_pmf[j]
    M *= tau_matrix(lam, mu, rho, max_goals)
    # Numerik düzeltme — negatif probability'leri 0'a clip
    M = np.clip(M, 0, None)
    # Toplam ≈ 1 (max_goals truncation nedeniyle hafif eksik)
    return M


# ============================================================
# PARAMETRELER VE LIKELIHOOD
# ============================================================

@dataclass
class DCParams:
    """Eğitilmiş Dixon-Coles parametreleri."""
    teams: list[str]
    attack: dict[str, float]   # α_team
    defence: dict[str, float]  # β_team
    home_adv: float            # γ
    rho: float                 # düşük skor düzeltme
    xi: float                  # zaman bozulma faktörü

    def expected_goals(self, home: str, away: str) -> tuple[float, float]:
        """Belli bir maç için (λ, μ) — gol beklentileri."""
        a_h = self.attack.get(home, 0.0)
        b_h = self.defence.get(home, 0.0)
        a_a = self.attack.get(away, 0.0)
        b_a = self.defence.get(away, 0.0)
        lam = np.exp(a_h + b_a + self.home_adv)
        mu = np.exp(a_a + b_h)
        return float(lam), float(mu)

    def score_matrix_for(self, home: str, away: str, max_goals: int = 10) -> np.ndarray:
        lam, mu = self.expected_goals(home, away)
        return score_matrix(lam, mu, self.rho, max_goals)


def _negative_log_likelihood(
    params: np.ndarray,
    home_idx: np.ndarray,
    away_idx: np.ndarray,
    home_goals: np.ndarray,
    away_goals: np.ndarray,
    weights: np.ndarray,
    n_teams: int,
) -> float:
    """
    Negatif log-likelihood (minimize edilecek).

    params yapısı:
        [α_1, ..., α_{n-1}, β_1, ..., β_n, γ, ρ]
    α'nın son elemanı kısıt için tutulur: Σα = 0.
    """
    attack = np.empty(n_teams)
    attack[:-1] = params[: n_teams - 1]
    attack[-1] = -np.sum(attack[:-1])  # Σα = 0 kısıtı (identifiability)

    defence = params[n_teams - 1 : 2 * n_teams - 1]
    home_adv = params[-2]
    rho = params[-1]

    a_h = attack[home_idx]
    b_h = defence[home_idx]
    a_a = attack[away_idx]
    b_a = defence[away_idx]

    lam = np.exp(a_h + b_a + home_adv)
    mu = np.exp(a_a + b_h)

    # log P(home_goals, away_goals)
    log_p_home = home_goals * np.log(lam + 1e-12) - lam
    log_p_away = away_goals * np.log(mu + 1e-12) - mu

    # τ düzeltmesi sadece düşük skorlar için
    # vektörize edilmiş tau hesabı
    tau_vec = np.ones_like(lam)
    mask00 = (home_goals == 0) & (away_goals == 0)
    mask01 = (home_goals == 0) & (away_goals == 1)
    mask10 = (home_goals == 1) & (away_goals == 0)
    mask11 = (home_goals == 1) & (away_goals == 1)
    tau_vec[mask00] = np.clip(1 - lam[mask00] * mu[mask00] * rho, 1e-9, None)
    tau_vec[mask01] = np.clip(1 + lam[mask01] * rho, 1e-9, None)
    tau_vec[mask10] = np.clip(1 + mu[mask10] * rho, 1e-9, None)
    tau_vec[mask11] = np.clip(1 - rho, 1e-9, None)

    log_lik = log_p_home + log_p_away + np.log(tau_vec)

    # Ağırlıklı (time decay)
    weighted = weights * log_lik
    return -np.sum(weighted)


# ============================================================
# EĞİTİM (FIT)
# ============================================================

def fit_dixon_coles(
    home_teams: Sequence[str],
    away_teams: Sequence[str],
    home_goals_arr: Sequence[int],
    away_goals_arr: Sequence[int],
    match_dates: Sequence[datetime],
    reference_date: datetime | None = None,
    xi: float = 0.0019,
    verbose: bool = False,
) -> DCParams:
    """
    Dixon-Coles modelini fit eder.

    Args:
        home_teams, away_teams: takım adları (string list)
        home_goals, away_goals: gol sayıları
        match_dates: maç tarihleri (datetime)
        reference_date: referans tarih (default: en son maç). Bundan önceki
                        maçlar exp(-xi * days_diff) ile zayıflatılır.
        xi: zaman bozulma faktörü. 0.0019 = haftada %1.4 azalış.
        verbose: optimizasyon adımlarını yazdır.

    Returns:
        DCParams nesnesi.
    """
    home_goals_arr = np.asarray(home_goals_arr, dtype=float)
    away_goals_arr = np.asarray(away_goals_arr, dtype=float)
    match_dates = list(match_dates)
    n_games = len(home_teams)

    if reference_date is None:
        reference_date = max(match_dates)

    # Tüm takımları topla (ev ve dep)
    all_teams = sorted(set(home_teams) | set(away_teams))
    team_to_idx = {t: i for i, t in enumerate(all_teams)}
    n_teams = len(all_teams)

    home_idx = np.array([team_to_idx[t] for t in home_teams])
    away_idx = np.array([team_to_idx[t] for t in away_teams])

    # Time decay ağırlıkları
    days_diff = np.array(
        [(reference_date - d).days for d in match_dates], dtype=float
    )
    weights = np.exp(-xi * days_diff)

    # İlk tahmin: nötr (0) hücum/savunma, ev avantajı 0.3, ρ -0.1
    x0 = np.concatenate([
        np.zeros(n_teams - 1),   # attack (n-1 free)
        np.zeros(n_teams),       # defence
        [0.30],                  # home_adv
        [-0.10],                 # rho
    ])

    # Sınırlar (rho için kısıtlı)
    bounds = (
        [(-3.0, 3.0)] * (n_teams - 1) +  # attack
        [(-3.0, 3.0)] * n_teams +        # defence
        [(-1.0, 1.0)] +                  # home_adv
        [(-0.20, 0.20)]                  # rho
    )

    result = minimize(
        _negative_log_likelihood,
        x0,
        args=(home_idx, away_idx, home_goals_arr, away_goals_arr, weights, n_teams),
        method="L-BFGS-B",
        bounds=bounds,
        options={"maxiter": 500, "disp": verbose},
    )

    if not result.success and verbose:
        print(f"  uyari: optimizasyon yakinsayamadi: {result.message}")

    # Parametreleri ayrıştır
    attack_arr = np.empty(n_teams)
    attack_arr[:-1] = result.x[: n_teams - 1]
    attack_arr[-1] = -np.sum(attack_arr[:-1])

    defence_arr = result.x[n_teams - 1 : 2 * n_teams - 1]
    home_adv = float(result.x[-2])
    rho = float(result.x[-1])

    attack = {t: float(attack_arr[i]) for t, i in team_to_idx.items()}
    defence = {t: float(defence_arr[i]) for t, i in team_to_idx.items()}

    return DCParams(
        teams=all_teams,
        attack=attack,
        defence=defence,
        home_adv=home_adv,
        rho=rho,
        xi=xi,
    )


# ============================================================
# CLI TEST (örnek)
# ============================================================

if __name__ == "__main__":
    """Hızlı sanity check — tek sezon Süper Lig fit + tahmin örneği."""
    import sys
    from pathlib import Path

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    import pandas as pd

    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
    data_path = PROJECT_ROOT / "02_VERI" / "processed" / "matches.csv"

    if not data_path.exists():
        print(f"Veri yok: {data_path}")
        print("Önce: python ../../02_VERI/scrapers/football_data_downloader.py")
        sys.exit(1)

    df = pd.read_csv(data_path, parse_dates=["match_date"])
    sl = df[df["league"] == "T1"].dropna(subset=["home_goals", "away_goals"]).copy()
    print(f"Süper Lig veri: {len(sl)} maç, {sl['match_date'].min().date()} -> {sl['match_date'].max().date()}")

    print("\nDixon-Coles fit ediliyor (bu 5-30 saniye sürebilir)...")
    params = fit_dixon_coles(
        home_teams=sl["home_team"].tolist(),
        away_teams=sl["away_team"].tolist(),
        home_goals_arr=sl["home_goals"].astype(int).tolist(),
        away_goals_arr=sl["away_goals"].astype(int).tolist(),
        match_dates=sl["match_date"].dt.to_pydatetime().tolist(),
        verbose=False,
    )

    print(f"\nFit tamamlandi.")
    print(f"  Takim sayisi: {len(params.teams)}")
    print(f"  Ev sahibi avantaji (gamma): {params.home_adv:.3f}")
    print(f"  Dusuk skor duzeltmesi (rho): {params.rho:.3f}")

    # En guclu/zayif takimlar (hucum)
    sorted_attack = sorted(params.attack.items(), key=lambda x: -x[1])
    print("\nEn iyi 5 hucum (alpha):")
    for t, v in sorted_attack[:5]:
        print(f"  {t:25s} alpha={v:+.3f}")
    print("\nEn iyi 5 savunma (negatif beta):")
    sorted_def = sorted(params.defence.items(), key=lambda x: x[1])
    for t, v in sorted_def[:5]:
        print(f"  {t:25s} beta={v:+.3f}")

    # Ornek tahmin: Galatasaray vs Fenerbahce
    if "Galatasaray" in params.teams and "Fenerbahce" in params.teams:
        M = params.score_matrix_for("Galatasaray", "Fenerbahce")
        lam, mu = params.expected_goals("Galatasaray", "Fenerbahce")
        print(f"\nOrnek: Galatasaray (ev) vs Fenerbahce")
        print(f"  Beklenen gol: ev={lam:.2f}, dep={mu:.2f}")
        # En olası 5 skor
        flat = [(M[i, j], i, j) for i in range(M.shape[0]) for j in range(M.shape[1])]
        flat.sort(reverse=True)
        print("  En olasi 5 skor:")
        for p, i, j in flat[:5]:
            print(f"    {i}-{j}: %{p*100:.2f}")
