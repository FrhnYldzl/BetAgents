"""
Market olasılığı türetici.

Dixon-Coles skor matrisinden iddaa pazarlarının olasılıklarını çıkarır:
    - 1X2 (Maç Sonucu)
    - Alt/Üst (Toplam Gol 0.5 / 1.5 / 2.5 / 3.5 / 4.5)
    - KG (Karşılıklı Gol / BTTS)
    - Çifte Şans
    - Toplam Gol Tek/Çift

Her pazarın fair odds'u: 1 / p.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


# ============================================================
# 1X2 — Maç Sonucu
# ============================================================

def prob_1x2(M: np.ndarray) -> dict[str, float]:
    """
    Maç sonucu olasılıkları.

    M[i, j] = P(home=i, away=j)
    Home Win:  i > j   (alt üçgen, diagonal hariç)
    Draw:      i == j
    Away Win:  i < j

    Returns:
        {"1": P(home), "X": P(draw), "2": P(away)}
    """
    n = M.shape[0]
    # Maskleri tek seferde oluştur
    i_idx, j_idx = np.indices((n, n))
    home = M[i_idx > j_idx].sum()
    draw = M[i_idx == j_idx].sum()
    away = M[i_idx < j_idx].sum()
    total = home + draw + away
    return {
        "1": float(home / total),
        "X": float(draw / total),
        "2": float(away / total),
    }


# ============================================================
# Alt/Üst — Toplam Gol
# ============================================================

def prob_over_under(M: np.ndarray, threshold: float) -> dict[str, float]:
    """
    Toplam gol alt/üst.

    Üst threshold: home + away > threshold
    Alt threshold: home + away < threshold
    (threshold yarım olduğu için eşitlik durumu yok)

    Returns:
        {"over": P(>threshold), "under": P(<threshold)}
    """
    n = M.shape[0]
    i_idx, j_idx = np.indices((n, n))
    total_goals = i_idx + j_idx
    over = M[total_goals > threshold].sum()
    under = M[total_goals < threshold].sum()
    # Eşitlik durumu (tam sayı threshold için) — sadece bilgi amaçlı
    eq = M[total_goals == threshold].sum()
    norm = over + under + eq
    return {
        "over": float(over / norm),
        "under": float(under / norm),
        "push": float(eq / norm),  # threshold yarım ise 0
    }


# ============================================================
# KG — Karşılıklı Gol (BTTS — Both Teams To Score)
# ============================================================

def prob_btts(M: np.ndarray) -> dict[str, float]:
    """
    Karşılıklı gol (KG).

    KG Var:  home >= 1 AND away >= 1
    KG Yok:  home == 0 OR away == 0

    Returns:
        {"yes": P(KG var), "no": P(KG yok)}
    """
    n = M.shape[0]
    # i >= 1 ve j >= 1 alanı (alt-sağ)
    yes = M[1:, 1:].sum()
    # i == 0 veya j == 0 (üst-sol L şekli)
    no = M[0, :].sum() + M[:, 0].sum() - M[0, 0]
    total = yes + no
    return {"yes": float(yes / total), "no": float(no / total)}


# ============================================================
# Çifte Şans — iddaa Madde 14/6
# ============================================================

def prob_double_chance(M: np.ndarray) -> dict[str, float]:
    """
    Çifte Şans:
        1X = home win VEYA draw
        12 = home win VEYA away win
        X2 = draw VEYA away win
    """
    p = prob_1x2(M)
    return {
        "1X": p["1"] + p["X"],
        "12": p["1"] + p["2"],
        "X2": p["X"] + p["2"],
    }


# ============================================================
# Tek/Çift — Toplam Gol
# ============================================================

def prob_odd_even(M: np.ndarray) -> dict[str, float]:
    """
    Toplam Gol Tek/Çift.
    0-0 → çift (iddaa Madde 14/23-b: "0-0 sonuçlanan bir müsabaka çift gol sayısı olarak değerlendirmeye alınır")
    """
    n = M.shape[0]
    i_idx, j_idx = np.indices((n, n))
    total = i_idx + j_idx
    even = M[total % 2 == 0].sum()
    odd = M[total % 2 == 1].sum()
    norm = even + odd
    return {"even": float(even / norm), "odd": float(odd / norm)}


# ============================================================
# Maç Skoru (Top N en olası)
# ============================================================

def top_n_scores(M: np.ndarray, n: int = 10) -> list[tuple[int, int, float]]:
    """En olası N skoru döndürür. Liste: [(home, away, prob), ...]"""
    flat = []
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            flat.append((i, j, float(M[i, j])))
    flat.sort(key=lambda x: -x[2])
    return flat[:n]


# ============================================================
# Beklenen değer (EV) ve edge
# ============================================================

@dataclass
class ValueBet:
    market: str
    selection: str
    model_prob: float
    fair_odds: float
    market_odds: float
    edge_pct: float       # (market_odds * model_prob - 1) * 100
    kelly_frac: float     # tam Kelly (kullanırken 0.25x uygula)


def compute_edge(model_prob: float, market_odds: float) -> tuple[float, float, float]:
    """
    Returns:
        fair_odds: 1 / model_prob
        edge_pct: (market_odds * model_prob - 1) * 100
        kelly_frac: tam Kelly fraction (= (b*p - q) / b)
    """
    if model_prob <= 0 or market_odds <= 1.0:
        return float("inf"), -100.0, 0.0
    fair = 1.0 / model_prob
    edge = (market_odds * model_prob - 1.0) * 100.0
    b = market_odds - 1.0
    q = 1.0 - model_prob
    kelly = max(0.0, (b * model_prob - q) / b)
    return fair, edge, kelly


def find_value_bets(
    market_probs: dict[str, float],
    market_odds: dict[str, float],
    min_edge_pct: float = 3.0,
    market_name: str = "1X2",
) -> list[ValueBet]:
    """
    Bir pazarda value bet'leri tespit eder.

    Args:
        market_probs: modelin olasılıkları {"1": 0.55, "X": 0.25, "2": 0.20}
        market_odds: piyasa oranları (iddaa) {"1": 1.95, "X": 3.40, "2": 4.50}
        min_edge_pct: edge eşiği (% cinsinden)

    Returns:
        Edge eşiğini geçen value bet'lerin listesi.
    """
    bets = []
    for selection, p in market_probs.items():
        if selection not in market_odds:
            continue
        odds = market_odds[selection]
        if odds is None or odds <= 1.0:
            continue
        fair, edge, kelly = compute_edge(p, odds)
        if edge >= min_edge_pct:
            bets.append(ValueBet(
                market=market_name,
                selection=selection,
                model_prob=p,
                fair_odds=fair,
                market_odds=odds,
                edge_pct=edge,
                kelly_frac=kelly,
            ))
    return bets


# ============================================================
# Handikaplı Sonuç (iddaa Madde 14/13)
# ============================================================

def prob_handicap(M: np.ndarray, handicap: float) -> dict[str, float]:
    """
    Handikaplı maç sonucu.

    Handicap, ev sahibinin lehine (+) veya aleyhine (-) ek gol farkı.
    Örnek: handicap = -1 → ev sahibi 1 gol farkıyla kazanmalı.
           handicap = +1.5 → deplasman 2+ gol farkıyla kazanırsa H, 0-1
                              veya beraberlik ev sahibi kazanır.

    Ondalıklı handicap (.5'li) → eşitlik mümkün değil
    Tam handicap (integer) → eşitlik (push/iade) mümkün

    Returns:
        {"1": P(ev kazanır), "X": P(handicap eşit, push), "2": P(dep kazanır)}
    """
    n = M.shape[0]
    i_idx, j_idx = np.indices((n, n))
    # Ev sahibi efektif skoru = i + handicap
    home_eff = i_idx + handicap
    away = j_idx

    home_win = M[home_eff > away].sum()
    push = M[np.isclose(home_eff, away)].sum() if handicap == int(handicap) else 0.0
    away_win = M[home_eff < away].sum()

    total = home_win + push + away_win
    if total <= 0:
        return {"1": 0.0, "X": 0.0, "2": 0.0}
    return {
        "1": float(home_win / total),
        "X": float(push / total),
        "2": float(away_win / total),
    }


# ============================================================
# İlk Yarı 1X2 (iddaa Madde 14/3)
# ============================================================

def score_matrix_half(lam_full: float, mu_full: float, rho: float,
                      half_fraction: float = 0.45,
                      max_goals: int = 6) -> np.ndarray:
    """
    İlk yarı için skor matrisi.

    Heuristik: İlk yarı gol oranı ~ 0.45 × full match.
    (Akademik literatürde first-half goals %42-48 of full match)

    Returns: ilk yarı skor matrisi (max_goals küçük çünkü ilk yarıda az gol)
    """
    from scipy.stats import poisson
    lam_h = lam_full * half_fraction
    mu_h = mu_full * half_fraction
    i = np.arange(max_goals + 1)
    home_pmf = poisson.pmf(i, lam_h)
    away_pmf = poisson.pmf(i, mu_h)
    M = np.outer(home_pmf, away_pmf)

    # Dixon-Coles τ düzeltmesi sadece tam maç için anlamlı.
    # İlk yarıda da uygulayabiliriz ama düşük λ'da etkisi az.
    return np.clip(M, 0, None)


def prob_first_half_1x2(lam: float, mu: float, rho: float = -0.1,
                         half_fraction: float = 0.45) -> dict[str, float]:
    """İlk yarı sonucu olasılıkları."""
    Mh = score_matrix_half(lam, mu, rho, half_fraction)
    return prob_1x2(Mh)


def prob_first_half_over_under(lam: float, mu: float, threshold: float = 0.5,
                                 rho: float = -0.1,
                                 half_fraction: float = 0.45) -> dict[str, float]:
    """İlk yarı toplam gol alt/üst."""
    Mh = score_matrix_half(lam, mu, rho, half_fraction)
    return prob_over_under(Mh, threshold)


# ============================================================
# İY/MS Kombine (iddaa Madde 14/5)
# ============================================================

def prob_ht_ft(lam: float, mu: float, rho: float = -0.1,
                half_fraction: float = 0.45,
                max_goals: int = 8) -> dict[str, float]:
    """
    İlk Yarı / Maç Sonucu kombine.

    9 olası kombinasyon: 1/1, 1/X, 1/2, X/1, X/X, X/2, 2/1, 2/X, 2/2.

    Hesap: ilk yarı skor matrisini bağımsız Poisson'la simüle,
    sonra ikinci yarı için (1 - half_fraction) × full ile yine bağımsız.
    Joint = P(HT_score) × P(FT_score | HT_score).
    """
    from scipy.stats import poisson

    half_2 = 1.0 - half_fraction
    lam_1 = lam * half_fraction
    mu_1 = mu * half_fraction
    lam_2 = lam * half_2
    mu_2 = mu * half_2

    # İlk yarı ev / dep gol PMF
    pmf_h1 = poisson.pmf(np.arange(max_goals + 1), lam_1)
    pmf_a1 = poisson.pmf(np.arange(max_goals + 1), mu_1)
    pmf_h2 = poisson.pmf(np.arange(max_goals + 1), lam_2)
    pmf_a2 = poisson.pmf(np.arange(max_goals + 1), mu_2)

    # 9 kombinasyon
    probs = {k: 0.0 for k in ["1/1", "1/X", "1/2",
                                "X/1", "X/X", "X/2",
                                "2/1", "2/X", "2/2"]}

    for h1 in range(max_goals + 1):
        for a1 in range(max_goals + 1):
            p_ht = pmf_h1[h1] * pmf_a1[a1]
            if p_ht < 1e-9:
                continue
            if h1 > a1: ht = "1"
            elif h1 < a1: ht = "2"
            else: ht = "X"

            for h2 in range(max_goals + 1):
                for a2 in range(max_goals + 1):
                    p_2h = pmf_h2[h2] * pmf_a2[a2]
                    if p_2h < 1e-9:
                        continue
                    H = h1 + h2; A = a1 + a2
                    if H > A: ft = "1"
                    elif H < A: ft = "2"
                    else: ft = "X"
                    probs[f"{ht}/{ft}"] += p_ht * p_2h

    # Normalize (truncation due to max_goals)
    total = sum(probs.values())
    if total > 0:
        for k in probs:
            probs[k] /= total
    return probs


# ============================================================
# Komple pazar dökümü (rapor için)
# ============================================================

def all_markets(M: np.ndarray,
                 lam: float | None = None, mu: float | None = None,
                 rho: float = -0.1,
                 half_fraction: float = 0.45) -> dict[str, dict[str, float]]:
    """
    Tüm pazarların olasılıklarını tek dict olarak verir.
    İlk yarı pazarları için lam ve mu (DC expected goals) gerekir.
    """
    out = {
        "1X2": prob_1x2(M),
        "Double Chance": prob_double_chance(M),
        "BTTS": prob_btts(M),
        "Over/Under 0.5": prob_over_under(M, 0.5),
        "Over/Under 1.5": prob_over_under(M, 1.5),
        "Over/Under 2.5": prob_over_under(M, 2.5),
        "Over/Under 3.5": prob_over_under(M, 3.5),
        "Over/Under 4.5": prob_over_under(M, 4.5),
        "Odd/Even": prob_odd_even(M),
        # Handicap (3 popüler handikap)
        "Handicap -1": prob_handicap(M, -1),
        "Handicap +1": prob_handicap(M, +1),
        "Handicap -2": prob_handicap(M, -2),
    }
    if lam is not None and mu is not None:
        out["FirstHalf 1X2"] = prob_first_half_1x2(lam, mu, rho, half_fraction)
        out["FirstHalf O/U 0.5"] = prob_first_half_over_under(lam, mu, 0.5, rho, half_fraction)
        out["FirstHalf O/U 1.5"] = prob_first_half_over_under(lam, mu, 1.5, rho, half_fraction)
        out["HT/FT"] = prob_ht_ft(lam, mu, rho, half_fraction)
    return out


# ============================================================
# CLI Test
# ============================================================

if __name__ == "__main__":
    import sys
    from pathlib import Path

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    # Bu dosyanın bulunduğu dizinden ana modülü import et
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from dixon_coles import score_matrix

    # Test: λ=1.5, μ=1.2, ρ=-0.1 (tipik bir maç)
    M = score_matrix(lam=1.5, mu=1.2, rho=-0.1, max_goals=10)
    print(f"Skor matrisi toplam: {M.sum():.4f}  (1.0'a yakin olmali)")
    print()

    print("=== Pazar olasiliklari (lam=1.5, mu=1.2, rho=-0.1) ===")
    for market, probs in all_markets(M).items():
        print(f"  {market}:")
        for sel, p in probs.items():
            fair = 1 / p if p > 0 else float("inf")
            print(f"    {sel:10s} p={p:.4f}  fair={fair:.2f}")

    print()
    print("=== En olasi 5 skor ===")
    for i, j, p in top_n_scores(M, 5):
        print(f"  {i}-{j}: {p*100:.2f}%")

    # Value bet örnek
    print()
    print("=== Value bet ornegi ===")
    model_p = prob_over_under(M, 2.5)
    iddaa_odds = {"over": 1.95, "under": 1.85}  # ornek iddaa oranlari
    bets = find_value_bets(
        market_probs={"Üst": model_p["over"], "Alt": model_p["under"]},
        market_odds={"Üst": 1.95, "Alt": 1.85},
        min_edge_pct=3.0,
        market_name="Toplam Gol 2.5",
    )
    if bets:
        for b in bets:
            print(f"  ✓ {b.market} -> {b.selection}")
            print(f"    Model p: {b.model_prob:.4f}  Fair: {b.fair_odds:.2f}  Piyasa: {b.market_odds}")
            print(f"    Edge: %{b.edge_pct:.2f}  Kelly (0.25x): %{b.kelly_frac*25:.2f}")
    else:
        print("  (bu ornekte value bet yok)")
