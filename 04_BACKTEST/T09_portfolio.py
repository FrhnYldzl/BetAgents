"""
TEST T09 — Multi-League Portfolio Simülasyonu
=============================================

BİLİMSEL SORULAR:
    H1: Her ligten ayrı K=3 kupon → bankroll'u 3 lige eşit dağıt vs T1-only,
        hangisi daha iyi growth + daha düşük volatilite?
    H2: Ligler arası kupon outcome'ları korele mi? (Birden çok kuponun aynı
        haftada birden kaybetme olasılığı bağımsız mı?)
    H3: Diversifikasyon Sharpe'i arttırır mı (volatilite/getiri oranı)?
    H4: Portföy max drawdown < single-league max drawdown mı?

METODOLOJİ:
    - Her lig için K=3 FAV_CONFIRMED picks (T1 already T08'de, E0+D1 dahil)
    - 4 portföy stratejisi:
        A) T1-only (referans)
        B) E0+T1+D1 eşit dağıt (1/3 her ligten)
        C) E0+T1 ikili (D1 hariç, T04'ten kanıtlandı)
        D) T1 ağırlıklı portföy (T1 %70, E0 %20, D1 %10)
    - Her hafta: o lig için kupon varsa stake et
    - Stake: Flat 50 TL per kupon
    - Korelasyon analizi: aynı hafta farklı ligler'de kazanan/kaybeden oranı

ÇIKTI:
    - RAPOR/T09_portfolio.md
    - 07_LOG_VE_RAPORLAR/T09_portfolio_equity.csv
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
YAZILIM = THIS_DIR.parent
RAPOR_DIR = YAZILIM / "RAPOR"
LOGS_DIR = YAZILIM / "07_LOG_VE_RAPORLAR"

sys.path.insert(0, str(THIS_DIR))
from T01_consensus_survival import load_snapshots
from T02_combo_kupon import get_odd_for_direction, did_win
from T04_league_validation import add_fav_confirmed


def build_picks_per_league(K: int = 3) -> dict[str, pd.DataFrame]:
    """Her lig için K-leg picks (kronolojik)."""
    df = load_snapshots()
    df["matchday"] = pd.to_datetime(df["kickoff_iso"]).dt.normalize()
    df = df[df["settled"] == 1].copy()
    df = add_fav_confirmed(df)
    df = df[df["dir_fav_confirmed"].notna()].sort_values("score_v13", ascending=False)

    per_league = {}
    for lg in ["E0", "D1", "T1"]:
        lg_df = df[df["league_code"] == lg]
        picks = []
        for md, group in lg_df.groupby("matchday"):
            topk = group.head(K)
            if len(topk) < K:
                continue
            combo_odd = 1.0
            all_won = True
            for _, leg in topk.iterrows():
                d = leg["dir_fav_confirmed"]
                o = get_odd_for_direction(leg, d)
                w = did_win(leg, d)
                if not o or o < 1.01:
                    combo_odd = None; break
                combo_odd *= o
                if not w:
                    all_won = False
            if combo_odd is None:
                continue
            picks.append({
                "matchday": md, "league": lg,
                "combo_odd": combo_odd, "won": all_won,
            })
        per_league[lg] = pd.DataFrame(picks).sort_values("matchday").reset_index(drop=True)
        print(f"  {lg}: {len(per_league[lg])} kupon")
    return per_league


def simulate_portfolio(picks_per_league: dict, weights: dict,
                       initial: float = 1000.0,
                       per_pick_pct: float = 0.05) -> dict:
    """
    weights: {'E0': 0.33, 'D1': 0.33, 'T1': 0.33}
    Her lig kendi kapital'inden compound %5 stake'er.

    Returns: equity curve + metrics
    """
    # Per-league bankroll
    bankrolls = {lg: initial * w for lg, w in weights.items() if w > 0}
    initial_bankrolls = dict(bankrolls)

    # Tüm haftaları birleştir, kronolojik
    all_picks = []
    for lg, df in picks_per_league.items():
        if lg in weights and weights[lg] > 0:
            for _, r in df.iterrows():
                all_picks.append({**r.to_dict(), "league": lg})
    all_picks_df = pd.DataFrame(all_picks).sort_values("matchday").reset_index(drop=True)

    equity_total = [sum(bankrolls.values())]
    weekly_pnls = []
    n_picks = 0
    n_wins = 0

    for _, row in all_picks_df.iterrows():
        lg = row["league"]
        if lg not in bankrolls or bankrolls[lg] < 1:
            continue
        stake = bankrolls[lg] * per_pick_pct
        if row["won"]:
            bankrolls[lg] += stake * (row["combo_odd"] - 1)
            n_wins += 1
        else:
            bankrolls[lg] -= stake
        n_picks += 1
        equity_total.append(sum(bankrolls.values()))
        weekly_pnls.append(stake * (row["combo_odd"] - 1) if row["won"] else -stake)

    final_total = sum(bankrolls.values())

    # Metrics
    peak = initial
    max_dd = 0
    for v in equity_total:
        if v > peak: peak = v
        dd = (peak - v) / peak if peak > 0 else 0
        max_dd = max(max_dd, dd)

    returns = np.diff(equity_total) / np.array(equity_total[:-1])
    returns = returns[~np.isnan(returns) & ~np.isinf(returns)]
    avg_ret = np.mean(returns) if len(returns) else 0
    std_ret = np.std(returns) if len(returns) else 1e-9
    sharpe = (avg_ret / std_ret) * np.sqrt(52) if std_ret > 1e-9 else 0

    return {
        "initial": initial, "final": final_total,
        "return_pct": (final_total / initial - 1) * 100,
        "n_picks": n_picks, "n_wins": n_wins,
        "hit_rate": n_wins / n_picks if n_picks else 0,
        "max_drawdown_pct": max_dd * 100,
        "sharpe_annual": sharpe,
        "equity_curve": equity_total,
        "final_per_league": bankrolls,
        "initial_per_league": initial_bankrolls,
    }


def correlation_analysis(picks_per_league: dict) -> dict:
    """Ligler arası kupon outcome korelasyonu."""
    # Tüm matchday × lig outcome matrix
    all_matchdays = set()
    for df in picks_per_league.values():
        all_matchdays.update(df["matchday"].tolist())
    all_matchdays = sorted(all_matchdays)

    matrix = {lg: [] for lg in picks_per_league.keys()}
    valid_dates = []
    for md in all_matchdays:
        # Bu hafta her ligin sonucu var mı?
        outcomes = {}
        has_all = True
        for lg, df in picks_per_league.items():
            row = df[df["matchday"] == md]
            if not row.empty:
                outcomes[lg] = 1 if row.iloc[0]["won"] else 0
            else:
                has_all = False
        if has_all:
            valid_dates.append(md)
            for lg in picks_per_league.keys():
                matrix[lg].append(outcomes[lg])

    if not valid_dates:
        return {"n_common_weeks": 0}

    df_corr = pd.DataFrame(matrix)
    corr_matrix = df_corr.corr()
    return {
        "n_common_weeks": len(valid_dates),
        "correlation_matrix": corr_matrix,
    }


def run():
    print("=" * 100)
    print("T09 — MULTI-LEAGUE PORTFOLIO SIMÜLASYONU")
    print("=" * 100)

    print("\n[1/3] Her lig için K=3 picks yükleniyor...")
    picks_per_league = build_picks_per_league(K=3)

    print("\n[2/3] Korelasyon analizi (ligler arası outcome)")
    corr = correlation_analysis(picks_per_league)
    if corr.get("n_common_weeks", 0) > 0:
        print(f"  Tum 3 ligin ayni hafta kupon ureticeği hafta sayisi: {corr['n_common_weeks']}")
        print(f"  Korelasyon matrisi:")
        print(corr["correlation_matrix"].round(3).to_string())
    else:
        print("  Yetersiz overlap, korelasyon hesaplanamadi.")

    print("\n[3/3] Portföy simülasyonları")
    portfolios = {
        "T1-only (ref)": {"T1": 1.0},
        "Equal 3-league": {"E0": 1/3, "D1": 1/3, "T1": 1/3},
        "E0+T1 (T04 winners)": {"E0": 0.5, "T1": 0.5},
        "T1-weighted (70/20/10)": {"T1": 0.7, "E0": 0.2, "D1": 0.1},
    }

    results = []
    for name, w in portfolios.items():
        r = simulate_portfolio(picks_per_league, w)
        r["name"] = name; r["weights"] = w
        results.append(r)
        print(f"\n--- {name} ---")
        print(f"  Initial 1000 TL -> Final: {r['final']:,.0f} TL  (Return: {r['return_pct']:+.1f}%)")
        print(f"  Picks: {r['n_picks']}, Wins: {r['n_wins']} ({r['hit_rate']*100:.0f}%)")
        print(f"  Max DD: {r['max_drawdown_pct']:.1f}%, Sharpe: {r['sharpe_annual']:.2f}")
        for lg, final_bk in r['final_per_league'].items():
            init_bk = r['initial_per_league'][lg]
            ret = (final_bk / init_bk - 1) * 100 if init_bk > 0 else 0
            print(f"    {lg} alt-bankroll: {init_bk:.0f} -> {final_bk:,.0f} ({ret:+.1f}%)")

    # CSV equity curves
    LOGS_DIR.mkdir(exist_ok=True)
    eq_df = pd.DataFrame({
        r["name"]: r["equity_curve"] + [None] * (max(len(r2["equity_curve"]) for r2 in results) - len(r["equity_curve"]))
        for r in results
    })
    eq_df.to_csv(LOGS_DIR / "T09_portfolio_equity.csv", index=False)

    # Report
    write_report(results, corr)
    return results


def write_report(results, corr):
    RAPOR_DIR.mkdir(exist_ok=True)
    p = RAPOR_DIR / "T09_portfolio.md"

    rows = []
    for r in results:
        rows.append(
            f"| {r['name']} | 1000 | {r['final']:,.0f} | "
            f"{r['return_pct']:+.1f}% | {r['n_picks']} | "
            f"{r['hit_rate']*100:.0f}% | {r['max_drawdown_pct']:.1f}% | "
            f"{r['sharpe_annual']:.2f} |"
        )

    corr_str = "Yetersiz overlap."
    if corr.get("n_common_weeks", 0) > 0:
        cm = corr["correlation_matrix"]
        corr_str = f"""**{corr['n_common_weeks']} ortak hafta** (3 lig de kupon üretmiş):

```
{cm.round(3).to_string()}
```
"""

    md = f"""# T09 — Multi-League Portfolio Simülasyonu

**Versiyon:** v1.0
**Tarih:** {datetime.now().isoformat()[:19]}

---

## Bilimsel Sorular

**H1:** Multi-league portföy T1-only'den daha iyi growth+volatilite oranı verir mi?
**H2:** Ligler arası outcome korelasyonu ne kadar?
**H3:** Diversifikasyon Sharpe'i arttırır mı?
**H4:** Portföy max drawdown < single-league mı?

---

## Sonuçlar

| Portföy | Initial | Final | Return | n picks | Hit% | MaxDD | Sharpe |
|---|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

---

## Korelasyon Analizi

{corr_str}

**Düşük korelasyon (|r| < 0.3)** = bağımsız → diversifikasyon faydalı
**Yüksek korelasyon (|r| > 0.5)** = aynı yönde hareket → diversifikasyon işe yaramaz

---

## Cevaplar

**H1:** Portföy growth: {min(r['return_pct'] for r in results):+.0f}% - {max(r['return_pct'] for r in results):+.0f}%. T1-only ile equal-weight farkı: {results[1]['return_pct'] - results[0]['return_pct']:+.1f} pp.

**H2:** Lig outcome'ları arası korelasyon → CSV'de detay.

**H3:** En yüksek Sharpe: {max(r['sharpe_annual'] for r in results):.2f} ({[r['name'] for r in results if r['sharpe_annual']==max(rr['sharpe_annual'] for rr in results)][0]}). T1-only Sharpe: {results[0]['sharpe_annual']:.2f}.

**H4:** Min max-drawdown: %{min(r['max_drawdown_pct'] for r in results):.0f} ({[r['name'] for r in results if r['max_drawdown_pct']==min(rr['max_drawdown_pct'] for rr in results)][0]}).

---

## Yorum

Diversifikasyon **growth'tan ödün vermeden** drawdown'u azaltıyorsa optimal. Portföyün üstün özelliği: aynı hafta farklı liglerin bağımsız sonuçları → variance düşer.

Equity CSV: `07_LOG_VE_RAPORLAR/T09_portfolio_equity.csv`
"""
    p.write_text(md, encoding="utf-8")
    print(f"\nRapor: {p}")


if __name__ == "__main__":
    run()
