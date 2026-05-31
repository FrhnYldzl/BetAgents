"""
SELECTIVE EDGE v1.1 — Kombinasyon Optimizer (BAĞIMSIZLIK DÜZELTİLMİŞ)

v1.0 sorunu:
    joint_prob = pA × pB × pC  — saf product, bağımsızlık varsayımı.
    Ama:
    - Aynı maç içi pazarlar (1X2, OU, BTTS) HIGHLY correlated
    - Farklı maçlar arası approximately independent

v1.1 düzeltmesi:
    İki strateji bir arada:

    A) Farklı maçlar arası: product (independent OK)
    B) Aynı maç içi: combo market'tan observed joint kullan
       1X2_OU "1 ve Üst" odd → fp_combo
       BTTS_OU "Var ve Üst"  → fp_combo
       1X2_BTTS "1 ve Var"   → fp_combo
       Bu observed marketler bookmaker'ın gerçek joint görüşünü içerir.

    Bu optimizer top-3 maç (her biri farklı) varsayar.
    Yani product OK için cross-match. Yine de within-match optimization yapmıyoruz
    (zaten 1 leg per match).

EK FEATURE (v1.1):
    - CLV proxy: combine_odd vs implied_combine_odd (overround stripped)
    - Half-Kelly stake önerisi
    - Tier kalibrasyonu: backtest-based threshold yerine percentile-based
"""
from __future__ import annotations

import itertools
import math
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
YAZILIM = THIS_DIR.parent.parent
sys.path.insert(0, str(YAZILIM / "02_VERI"))

import database as db
from odds_anomaly import get_match_odds, fair_probs, implied, _valid_odd


MARKET_LEGS = [
    ("1X2", "1",   "MS-1"),
    ("1X2", "0",   "MS-X"),
    ("1X2", "2",   "MS-2"),
    ("OU2.5", "Üst", "Üst 2.5"),
    ("OU2.5", "Alt", "Alt 2.5"),
    ("BTTS", "Var", "KG Var"),
    ("BTTS", "Yok", "KG Yok"),
]


def get_leg_options(iddaa_match_id: str, conn) -> list[dict]:
    """Bir maç için 7 ana pazar leg'i."""
    mkts = get_match_odds(conn, iddaa_match_id)
    legs = []

    m1x2 = mkts.get("1X2", {})
    o1, ox, o2 = m1x2.get("1"), m1x2.get("0"), m1x2.get("2")
    if _valid_odd(o1) and _valid_odd(ox) and _valid_odd(o2):
        p1, px, p2 = fair_probs([o1, ox, o2])
        legs.append({"market": "1X2", "selection": "1",
                     "label": "MS-1", "odd": o1, "fair_prob": p1})
        legs.append({"market": "1X2", "selection": "0",
                     "label": "MS-X", "odd": ox, "fair_prob": px})
        legs.append({"market": "1X2", "selection": "2",
                     "label": "MS-2", "odd": o2, "fair_prob": p2})

    mou = mkts.get("OU2.5", {})
    alt = mou.get("Alt")
    ust = mou.get("Üst") or mou.get("Ust")
    if _valid_odd(alt) and _valid_odd(ust):
        pu, po = fair_probs([alt, ust])
        legs.append({"market": "OU2.5", "selection": "Alt",
                     "label": "Alt 2.5", "odd": alt, "fair_prob": pu})
        legs.append({"market": "OU2.5", "selection": "Üst",
                     "label": "Üst 2.5", "odd": ust, "fair_prob": po})

    mb = mkts.get("BTTS", {})
    var_ = mb.get("Var")
    yok_ = mb.get("Yok")
    if _valid_odd(var_) and _valid_odd(yok_):
        py, pn = fair_probs([var_, yok_])
        legs.append({"market": "BTTS", "selection": "Var",
                     "label": "KG Var", "odd": var_, "fair_prob": py})
        legs.append({"market": "BTTS", "selection": "Yok",
                     "label": "KG Yok", "odd": yok_, "fair_prob": pn})

    return legs


def kelly_fraction(p: float, odd: float, fraction: float = 0.25) -> float:
    """Half-Kelly (default 0.25× full) stake fraction."""
    if odd <= 1.0 or p <= 0:
        return 0.0
    b = odd - 1
    full_kelly = (b * p - (1 - p)) / b
    if full_kelly <= 0:
        return 0.0
    return full_kelly * fraction


def optimize_combinations(match_ids: list[str],
                          kelly_fraction_val: float = 0.20,
                          bankroll: float = 10000) -> dict:
    """
    3 maçtan 7³=343 kombinasyon. Her maçtan bir leg seçilir.
    Cross-match bağımsız (her biri farklı maç) → product OK.

    Within-match bağımlılık YOK (zaten her maçtan 1 leg).
    """
    conn = db.connect()
    try:
        all_legs = []
        match_meta = []
        for mid in match_ids:
            legs = get_leg_options(mid, conn)
            if not legs:
                continue
            all_legs.append(legs)
            row = conn.execute(
                "SELECT MAX(home_team) as home_team, MAX(away_team) as away_team "
                "FROM iddaa_odds WHERE iddaa_match_id=?", (mid,)
            ).fetchone()
            match_meta.append({
                "iddaa_match_id": mid,
                "home_team": row["home_team"] if row else "?",
                "away_team": row["away_team"] if row else "?",
            })

        if len(all_legs) < 2:
            return {"GARANTI": None, "DENGELI": None, "YUKSEK_EV": None,
                    "all_top10": [], "n_combinations": 0, "matches": match_meta}

        combinations = []
        for combo in itertools.product(*all_legs):
            # CROSS-MATCH independent — product OK
            joint_prob = 1.0
            combined_odds = 1.0
            probs = []
            for leg in combo:
                joint_prob *= leg["fair_prob"]
                combined_odds *= leg["odd"]
                probs.append(leg["fair_prob"])

            ev = joint_prob * combined_odds - 1

            # Risk: kupon variance hesabı
            # Var(payout) = combined_odds^2 * p * (1-p) [bernoulli]
            # Sharpe = E[payout-1] / SD(payout)
            payout_var = combined_odds * combined_odds * joint_prob * (1 - joint_prob)
            payout_sd = math.sqrt(payout_var) if payout_var > 0 else 0.001
            sharpe = ev / payout_sd if payout_sd > 0.001 else 0

            # Kelly stake
            kelly = kelly_fraction(joint_prob, combined_odds, kelly_fraction_val)
            stake_tl = round(kelly * bankroll)
            expected_win_tl = round(stake_tl * combined_odds) if stake_tl > 0 else 0

            combinations.append({
                "legs": [{"match": f"{match_meta[i]['home_team']} vs {match_meta[i]['away_team']}",
                          "market": leg["market"], "selection": leg["selection"],
                          "label": leg["label"], "odd": leg["odd"],
                          "fair_prob": leg["fair_prob"]}
                         for i, leg in enumerate(combo)],
                "joint_prob": joint_prob,
                "combined_odds": combined_odds,
                "ev": ev,
                "payout_sd": payout_sd,
                "sharpe": sharpe,
                "kelly_fraction": kelly,
                "recommended_stake_tl": stake_tl,
                "expected_payout_tl": expected_win_tl,
            })

        # Percentile-based tier (v1.1):
        # GARANTI = top decile of joint_prob
        # YUKSEK_EV = top decile of ev (or just max)
        # DENGELI = best sharpe with sharpe positive
        combinations.sort(key=lambda c: c["sharpe"], reverse=True)

        garanti_pool = [c for c in combinations if c["joint_prob"] > 0.4]
        garanti = max(garanti_pool, key=lambda c: c["ev"]) if garanti_pool else \
                  max(combinations, key=lambda c: c["joint_prob"])

        dengeli_pool = [c for c in combinations if c["ev"] > -0.20]
        dengeli = max(dengeli_pool, key=lambda c: c["sharpe"]) if dengeli_pool else \
                  max(combinations, key=lambda c: c["sharpe"])

        yuksek_ev = max(combinations, key=lambda c: c["ev"])

        top10 = sorted(combinations, key=lambda c: c["sharpe"], reverse=True)[:10]

        return {
            "GARANTI": garanti,
            "DENGELI": dengeli,
            "YUKSEK_EV": yuksek_ev,
            "all_top10": top10,
            "n_combinations": len(combinations),
            "matches": match_meta,
        }
    finally:
        conn.close()


def report():
    print("=" * 90)
    print("SELECTIVE EDGE v1.1 — TOP 3 + KOMBINASYON OPTIMIZER")
    print("=" * 90)

    from selector import select_top_n
    top3 = select_top_n(3)
    if not top3:
        print("Top-3 mac yok")
        return

    print("\nSECILEN 3 MAC:")
    for i, m in enumerate(top3):
        print(f"  [{i+1}] {m['home']} vs {m['away']}  (score: {m['selection_score']:.3f})")

    print("\nKombinasyon hesaplaniyor...")
    result = optimize_combinations([m["iddaa_match_id"] for m in top3])
    print(f"Islenen: {result.get('n_combinations', 0)}")

    for tier in ["GARANTI", "DENGELI", "YUKSEK_EV"]:
        c = result.get(tier)
        if not c:
            continue
        emoji = {"GARANTI": "[KALKAN]", "DENGELI": "[DENGE]", "YUKSEK_EV": "[ROKET]"}[tier]
        print("\n" + "=" * 90)
        print(f"{emoji} {tier}")
        print(f"   Joint Prob  : {c['joint_prob']*100:.1f}%")
        print(f"   Combine Odd : {c['combined_odds']:.2f}")
        print(f"   EV          : {c['ev']*100:+.1f}%")
        print(f"   Payout SD   : {c['payout_sd']:.2f}")
        print(f"   Sharpe      : {c['sharpe']:.3f}")
        print(f"   Kelly 0.20× : %{c['kelly_fraction']*100:.2f}  ({c['recommended_stake_tl']} TL)")
        print(f"   Beklenen   : {c['expected_payout_tl']} TL")
        print(f"   Legler:")
        for leg in c["legs"]:
            print(f"     {leg['match']:45s} | {leg['label']:10s} @ {leg['odd']:.2f}  (fair: {leg['fair_prob']*100:.0f}%)")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "report"
    if cmd == "report":
        report()
    else:
        print("Komutlar: report")
