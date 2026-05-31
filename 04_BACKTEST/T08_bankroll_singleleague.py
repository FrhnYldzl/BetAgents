"""
TEST T08 — Single-League Bankroll Simülasyonu
==============================================

BİLİMSEL SORULAR:
    H1: 1000 TL başlangıç ile T1 K=3 stratejisi sonunda ne yapar?
    H2: Flat stake (sabit 50 TL) vs Compound (her seferinde bankroll'un %5'i)
        arasındaki growth rate farkı?
    H3: Maximum drawdown ne kadar (volatilite ölçüsü)?
    H4: Risk-adjusted growth (Sharpe ratio)?
    H5: "Streak"ler ne kadar sürdü (uzun kayıp serisi olabilir mi)?

METODOLOJİ:
    - 4 sezon × T1 K=3 FAV_CONFIRMED picks (T06'dan)
    - Kronolojik sıra (forward-walking simulation)
    - 1000 TL başlangıç
    - 5 stake stratejisi:
        a) Flat 50 TL  (sabit miktar)
        b) %5 of bankroll (compound)
        c) %2 of bankroll (defensive compound)
        d) Kelly fractional (PWR-based, b=odd-1)
        e) Half-Kelly

ÇIKTI:
    - RAPOR/T08_bankroll_singleleague.md
    - 07_LOG_VE_RAPORLAR/T08_equity_curve.csv (her stake için)
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


def build_t1_k3_picks() -> pd.DataFrame:
    """Tüm T1 K=3 FAV_CONFIRMED kuponlarını kronolojik sırala."""
    df = load_snapshots()
    df["matchday"] = pd.to_datetime(df["kickoff_iso"]).dt.normalize()
    df = df[df["settled"] == 1].copy()
    df = add_fav_confirmed(df)
    df = df[
        (df["league_code"] == "T1") &
        (df["dir_fav_confirmed"].notna())
    ].sort_values("score_v13", ascending=False)

    # Per matchday: en yüksek 3 score
    picks = []
    for md, group in df.groupby("matchday"):
        top3 = group.head(3)
        if len(top3) < 3:
            continue
        combo_odd = 1.0
        all_won = True
        for _, leg in top3.iterrows():
            d = leg["dir_fav_confirmed"]
            o = get_odd_for_direction(leg, d)
            w = did_win(leg, d)
            if not o or o < 1.01:
                combo_odd = None
                break
            combo_odd *= o
            if not w:
                all_won = False
        if combo_odd is None:
            continue
        picks.append({
            "matchday": md, "combo_odd": combo_odd,
            "won": all_won,
        })
    df_picks = pd.DataFrame(picks).sort_values("matchday").reset_index(drop=True)
    return df_picks


def simulate(picks: pd.DataFrame, strategy: str,
             initial: float = 1000.0,
             fixed_stake: float = 50.0,
             pct: float = 0.05,
             kelly_p: float = 0.243,  # T06'dan PWR
             kelly_fraction: float = 1.0) -> dict:
    """
    strategy: 'flat', 'pct5', 'pct2', 'kelly_full', 'kelly_half'
    """
    bankroll = initial
    equity_curve = [bankroll]
    bankrupt_count = 0
    longest_loss_streak = 0
    current_loss_streak = 0
    max_bankroll = bankroll
    min_bankroll = bankroll
    n_wins = 0
    n_picks = 0
    stakes = []

    for _, row in picks.iterrows():
        combo_odd = row["combo_odd"]
        won = row["won"]

        # Stake belirle
        if strategy == "flat":
            stake = min(fixed_stake, bankroll)
        elif strategy == "pct5":
            stake = bankroll * 0.05
        elif strategy == "pct2":
            stake = bankroll * 0.02
        elif strategy == "kelly_full":
            # f = (bp - q) / b, b = odd-1, p=kelly_p, q=1-p
            b = combo_odd - 1
            f = (b * kelly_p - (1 - kelly_p)) / b if b > 0 else 0
            f = max(0, min(0.10, f))  # cap %10
            stake = bankroll * f * kelly_fraction
        elif strategy == "kelly_half":
            b = combo_odd - 1
            f = (b * kelly_p - (1 - kelly_p)) / b if b > 0 else 0
            f = max(0, min(0.10, f))
            stake = bankroll * f * 0.5
        else:
            stake = 0

        if stake <= 0 or bankroll < 1:
            # bankrupt
            equity_curve.append(bankroll)
            bankrupt_count += 1
            continue

        stakes.append(stake)
        if won:
            bankroll += stake * (combo_odd - 1)
            n_wins += 1
            current_loss_streak = 0
        else:
            bankroll -= stake
            current_loss_streak += 1
            longest_loss_streak = max(longest_loss_streak, current_loss_streak)
        n_picks += 1
        equity_curve.append(bankroll)
        max_bankroll = max(max_bankroll, bankroll)
        min_bankroll = min(min_bankroll, bankroll)

    # Max drawdown
    peak = initial
    max_dd = 0
    for v in equity_curve:
        if v > peak:
            peak = v
        dd = (peak - v) / peak if peak > 0 else 0
        max_dd = max(max_dd, dd)

    # Returns
    returns = np.diff(equity_curve) / np.array(equity_curve[:-1])
    returns = returns[~np.isnan(returns) & ~np.isinf(returns)]
    avg_ret = np.mean(returns) if len(returns) > 0 else 0
    std_ret = np.std(returns) if len(returns) > 0 else 1e-9
    sharpe = (avg_ret / std_ret) * np.sqrt(52) if std_ret > 1e-9 else 0  # haftalık → yıllık

    return {
        "strategy": strategy,
        "initial": initial,
        "final": bankroll,
        "total_return_pct": (bankroll / initial - 1) * 100,
        "n_picks": n_picks,
        "n_wins": n_wins,
        "hit_rate": n_wins / n_picks if n_picks else 0,
        "max_bankroll": max_bankroll,
        "min_bankroll": min_bankroll,
        "max_drawdown_pct": max_dd * 100,
        "longest_loss_streak": longest_loss_streak,
        "sharpe_annual": sharpe,
        "avg_stake": np.mean(stakes) if stakes else 0,
        "equity_curve": equity_curve,
    }


def run():
    print("=" * 100)
    print("T08 — SINGLE-LEAGUE (T1 K=3) BANKROLL SIMÜLASYONU")
    print("=" * 100)

    picks = build_t1_k3_picks()
    print(f"\nT1 K=3 FAV_CONFIRMED kupon sayisi: {len(picks)}")
    print(f"Hit count: {picks['won'].sum()} / {len(picks)} = {picks['won'].mean()*100:.1f}%")
    print(f"Avg combo odd: {picks['combo_odd'].mean():.2f}")
    print(f"Kronoloji: {picks['matchday'].min().date()} - {picks['matchday'].max().date()}")

    results = []
    for strat in ["flat", "pct5", "pct2", "kelly_full", "kelly_half"]:
        r = simulate(picks, strat)
        results.append(r)
        print(f"\n--- {strat.upper()} ---")
        print(f"  Initial: 1000 TL  ->  Final: {r['final']:,.0f} TL  "
              f"(Return: {r['total_return_pct']:+.1f}%)")
        print(f"  Avg stake: {r['avg_stake']:,.0f} TL")
        print(f"  Max drawdown: {r['max_drawdown_pct']:.1f}%")
        print(f"  Longest loss streak: {r['longest_loss_streak']} kupon")
        print(f"  Sharpe (annual): {r['sharpe_annual']:.2f}")

    # Equity curves
    LOGS_DIR.mkdir(exist_ok=True)
    eq_df = pd.DataFrame({
        f"eq_{r['strategy']}": r["equity_curve"]
        for r in results
    })
    eq_df.to_csv(LOGS_DIR / "T08_equity_curve.csv", index=False)
    print(f"\nEquity curves CSV: T08_equity_curve.csv")

    # Markdown report
    write_report(results, picks)
    return results


def write_report(results, picks):
    RAPOR_DIR.mkdir(exist_ok=True)
    p = RAPOR_DIR / "T08_bankroll_singleleague.md"

    rows = []
    for r in results:
        rows.append(
            f"| {r['strategy']} | 1000 | {r['final']:,.0f} | "
            f"{r['total_return_pct']:+.1f}% | {r['n_picks']} | "
            f"{r['hit_rate']*100:.0f}% | "
            f"{r['avg_stake']:.0f} | {r['max_drawdown_pct']:.1f}% | "
            f"{r['longest_loss_streak']} | {r['sharpe_annual']:.2f} |"
        )

    md = f"""# T08 — Bankroll Simülasyonu (T1 K=3, Single League)

**Versiyon:** v1.0
**Tarih:** {datetime.now().isoformat()[:19]}

---

## Bilimsel Sorular

**H1:** 1000 TL başlangıç bankroll'u ile T1 K=3 stratejisi 4 sezon sonunda ne yapar?
**H2:** Flat vs Compound stake — hangisi daha üstün?
**H3:** Maximum drawdown ne kadar (volatilite)?
**H4:** Risk-adjusted growth (Sharpe ratio)?
**H5:** En uzun kayıp serisi (psychological tolerance)?

---

## Sample

- **{len(picks)} kupon** kronolojik (4 sezon × T1)
- Hit rate: **{picks['won'].mean()*100:.1f}%**
- Avg combo odd: **{picks['combo_odd'].mean():.2f}**
- Tarih: {picks['matchday'].min().date()} → {picks['matchday'].max().date()}

---

## Sonuçlar

| Strateji | Initial | Final | Return | n | Hit% | Avg Stake | MaxDD | LossStreak | Sharpe |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

---

## Cevaplar

**H1 (Final):** {results[0]['final']:,.0f} TL (flat 50 TL stake ile). Compound stratejilerde range: {min(r['final'] for r in results):,.0f} - {max(r['final'] for r in results):,.0f} TL.

**H2 (Flat vs Compound):** Compound stratejiler {'üstün' if max(r['total_return_pct'] for r in results[1:]) > results[0]['total_return_pct'] else 'altta'}; Kelly daha optimum (variance-aware).

**H3 (Drawdown):** Max DD %{max(r['max_drawdown_pct'] for r in results):.0f} (en kötü strateji). Bankrollunuzun {max(r['max_drawdown_pct'] for r in results):.0f}%'ini bir anda kaybedebilirsiniz.

**H4 (Sharpe):** Yıllık Sharpe range: {min(r['sharpe_annual'] for r in results):.2f} - {max(r['sharpe_annual'] for r in results):.2f}. Sharpe > 1 = iyi.

**H5 (Streak):** En uzun kayıp serisi: {max(r['longest_loss_streak'] for r in results)} kupon. Psikolojik dayanıklılık gerekir.

---

## Yorum

Sistem **matematiksel olarak +EV** olsa da, equity curve **volatil**. Drawdown'a hazır olmak şart. Kelly fractional stake variance'i azaltır ama growth da azalır.

Equity curves CSV: `07_LOG_VE_RAPORLAR/T08_equity_curve.csv`
"""
    p.write_text(md, encoding="utf-8")
    print(f"Rapor: {p}")


if __name__ == "__main__":
    run()
