"""
Multi-league bilimsel validasyon — E0, T1, D1 birlikte.

Hedef:
    - Mevcut walk-forward backtest motorunu 3 ligde çalıştır
    - n=1800+ sample size (statistical power için yeterli)
    - Birleştirilmiş bilimsel test (t-test, bootstrap, CLV)
    - Net hüküm: edge VAR mı YOK mu?

Çıktı:
    - 07_LOG_VE_RAPORLAR/multi_league_bets.csv
    - 07_LOG_VE_RAPORLAR/scientific_verdict.md
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

THIS_DIR = Path(__file__).resolve().parent
YAZILIM_DIR = THIS_DIR.parent

sys.path.insert(0, str(THIS_DIR / "engine"))
sys.path.insert(0, str(YAZILIM_DIR / "03_MODELLER" / "base"))
sys.path.insert(0, str(YAZILIM_DIR / "03_MODELLER" / "calibration"))

import improved_backtest as ibt


LEAGUES_TO_TEST = ["E0", "T1", "D1"]
TEST_SEASONS = ["2324", "2425"]  # son 2 sezon (2526 hala devam edebilir)


def run_league(df: pd.DataFrame, league: str) -> pd.DataFrame:
    """Bir lig için backtest çalıştır, bet records DataFrame döndür."""
    config = dict(ibt.CONFIG)
    config["league"] = league
    config["test_seasons"] = TEST_SEASONS

    print(f"\n{'=' * 70}")
    print(f"  {league}")
    print(f"{'=' * 70}")

    result = ibt.run_backtest(df, config)

    # BetRecord -> dict
    bets = []
    for b in result.bets:
        bets.append({
            "league": league,
            "match_date": b.match_date,
            "home": b.home,
            "away": b.away,
            "score": f"{b.home_goals}-{b.away_goals}",
            "selection": b.selection,
            "p_raw": b.model_prob_raw,
            "p_calibrated": b.model_prob_calibrated,
            "market_odds": b.market_odds,
            "closing_odds": b.closing_odds,
            "edge_pct": b.edge_pct,
            "stake": b.stake,
            "won": b.won,
            "pnl": b.pnl,
            "bankroll_after": b.bankroll_after,
            "clv_pct": b.clv_pct,
        })
    return pd.DataFrame(bets)


def scientific_verdict(all_bets: pd.DataFrame) -> str:
    """Birleştirilmiş bilimsel test."""
    n = len(all_bets)
    if n == 0:
        return "Hiç bahis yok."

    roi_per_bet = all_bets["pnl"] / all_bets["stake"]
    mean_roi = roi_per_bet.mean()
    std_roi = roi_per_bet.std()
    se = std_roi / np.sqrt(n)
    t_stat = mean_roi / se
    p_value = 2 * (1 - stats.t.cdf(abs(t_stat), n - 1))
    ci = stats.t.interval(0.95, n - 1, loc=mean_roi, scale=se)

    # Bootstrap
    np.random.seed(42)
    boot = []
    for _ in range(2000):
        s = roi_per_bet.sample(n, replace=True)
        boot.append(s.mean())
    boot = np.array(boot)

    # CLV
    clv = all_bets["clv_pct"]
    mean_clv = clv.mean()
    clv_se = clv.std() / np.sqrt(n)
    t_clv = mean_clv / clv_se if clv_se > 0 else 0
    p_clv = 2 * (1 - stats.t.cdf(abs(t_clv), n - 1)) if clv_se > 0 else 1.0
    ci_clv = stats.t.interval(0.95, n - 1, loc=mean_clv, scale=clv_se) if clv_se > 0 else (0, 0)

    # Sharpe-equivalent (annualized değil, per-bet)
    sharpe = mean_roi / std_roi * np.sqrt(252) if std_roi > 0 else 0

    # Drawdown
    starting = ibt.CONFIG["starting_bankroll"] * len(LEAGUES_TO_TEST)  # her lig 10K → toplam 30K
    cum_pnl = all_bets["pnl"].cumsum()
    bk = starting + cum_pnl
    peak = bk.cummax()
    dd = (peak - bk) / peak
    max_dd = float(dd.max() * 100)

    # Per league
    per_lg = []
    for lg in all_bets["league"].unique():
        sub = all_bets[all_bets["league"] == lg]
        per_lg.append({
            "lig": lg,
            "n": len(sub),
            "win_pct": float(sub["won"].mean() * 100),
            "roi_pct": float(sub["pnl"].sum() / sub["stake"].sum() * 100) if sub["stake"].sum() > 0 else 0,
            "clv_pct": float(sub["clv_pct"].mean()),
        })

    out = []
    out.append("# Bilimsel Validasyon Raporu")
    out.append(f"\n**Tarih:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    out.append(f"**Ligler:** {', '.join(LEAGUES_TO_TEST)}")
    out.append(f"**Test Sezonları:** {', '.join(TEST_SEASONS)}")
    out.append(f"**Bahis tipi:** Over 2.5 (Toplam Gol Üst 2.5)")
    out.append(f"**Model:** Dixon-Coles + Platt scaling")
    out.append(f"**Stake:** 0.20× Kelly, max %3 bankroll")

    out.append("\n## 1. Birleşik Sample")
    out.append(f"\n| Metrik | Değer |")
    out.append(f"|---|---|")
    out.append(f"| Toplam bahis (n) | **{n}** |")
    out.append(f"| Kazanan | {int(all_bets['won'].sum())} ({all_bets['won'].mean()*100:.1f}%) |")
    out.append(f"| Toplam stake | {all_bets['stake'].sum():,.0f} ₺ |")
    out.append(f"| Toplam P&L | **{all_bets['pnl'].sum():+,.0f} ₺** |")
    out.append(f"| Genel ROI | **{all_bets['pnl'].sum() / all_bets['stake'].sum() * 100:+.2f}%** |")

    out.append("\n## 2. Lig Bazlı Performans\n")
    out.append("| Lig | n | Win % | ROI % | CLV % | Durum |")
    out.append("|---|---|---|---|---|---|")
    for r in per_lg:
        durum = ("✅ Pozitif edge" if r["clv_pct"] > 0
                 else "⚠️ Şüpheli (CLV<0)")
        out.append(f"| {r['lig']} | {r['n']} | {r['win_pct']:.1f} | {r['roi_pct']:+.2f} | {r['clv_pct']:+.2f} | {durum} |")

    out.append("\n## 3. İstatistiksel Test (One-sample t-test, H₀: ROI=0)\n")
    out.append("| Metrik | Değer |")
    out.append("|---|---|")
    out.append(f"| Mean ROI | **{mean_roi*100:+.3f}%** per bet |")
    out.append(f"| Std | {std_roi*100:.2f}% |")
    out.append(f"| Standard Error | {se*100:.4f}% |")
    out.append(f"| t-statistic | {t_stat:.3f} |")
    out.append(f"| **p-value** | **{p_value:.4f}** |")
    out.append(f"| 95% CI | [{ci[0]*100:+.2f}%, {ci[1]*100:+.2f}%] |")
    sig = "✅ İSTATİSTİKSEL ANLAMLI EDGE" if p_value < 0.05 else "❌ ANLAMSIZ — şans olabilir"
    out.append(f"| **Sonuç** | {sig} |")

    out.append("\n## 4. Bootstrap Analizi (2000 resampling)\n")
    out.append(f"- Bootstrap median ROI: **{np.median(boot)*100:+.2f}%**")
    out.append(f"- Bootstrap 95% CI: [{np.percentile(boot,2.5)*100:+.2f}%, {np.percentile(boot,97.5)*100:+.2f}%]")
    out.append(f"- P(ROI > 0) ampirik: **{(boot > 0).mean()*100:.1f}%**")
    boot_ok = (boot > 0).mean() > 0.95 and np.percentile(boot,2.5) > 0
    out.append(f"- {'✅ Tutarlı pozitif' if boot_ok else '❌ Sıfırı içeriyor — emin değiliz'}")

    out.append("\n## 5. CLV (Closing Line Value) — KRİTİK\n")
    out.append("| Metrik | Değer |")
    out.append("|---|---|")
    out.append(f"| Mean CLV | **{mean_clv:+.3f}%** |")
    out.append(f"| CLV > 0 oran | {(clv > 0).mean()*100:.1f}% ({(clv>0).sum()}/{n}) |")
    out.append(f"| t-statistic | {t_clv:.3f} |")
    out.append(f"| p-value | **{p_clv:.4f}** |")
    out.append(f"| 95% CI | [{ci_clv[0]:+.2f}%, {ci_clv[1]:+.2f}%] |")
    clv_ok = mean_clv > 0 and p_clv < 0.05
    clv_sig_neg = mean_clv < 0 and p_clv < 0.05
    if clv_ok:
        out.append(f"\n✅ **CLV anlamlı şekilde POZİTİF — güçlü edge sinyali**")
    elif clv_sig_neg:
        out.append(f"\n❌ **CLV anlamlı şekilde NEGATİF — Pinnacle bizden daha doğru. ROI varsa şans.**")
    else:
        out.append(f"\n⚠️ **CLV sıfır civarında, anlamlı değil — emin olamayız**")

    out.append("\n## 6. Risk Metrikleri\n")
    out.append(f"- Sharpe-equivalent (252-day annualized): **{sharpe:.2f}**")
    out.append(f"- Maksimum drawdown: **%{max_dd:.2f}**")

    out.append("\n## 7. Sample Power Analizi\n")
    out.append(f"Mevcut sample (n={n}). Gerçek edge tespit etmek için gereken:")
    sigma = std_roi
    z_a, z_b = 1.96, 0.84  # alpha=0.05, power=0.80
    for true_roi in [0.02, 0.03, 0.05, 0.08]:
        n_req = int(((z_a + z_b) * sigma / true_roi) ** 2)
        status = "✓ yeterli" if n >= n_req else f"❌ yetersiz ({n_req - n} daha gerek)"
        out.append(f"- %{true_roi*100:.0f} edge için: **{n_req:,}** bahis ({status})")

    out.append("\n## 8. NİHAİ BİLİMSEL HÜKÜM\n")
    cond_p = p_value < 0.05
    cond_clv = mean_clv > 0
    cond_n = n >= 500
    cond_boot = boot_ok

    if cond_p and cond_clv and cond_n and cond_boot:
        out.append("# ✅ EDGE KANITLANDI")
        out.append("\nGerçek bahis için bilimsel temel sağlam:")
        out.append("- ROI istatistiksel olarak anlamlı")
        out.append("- CLV pozitif")
        out.append("- Sample yeterli")
        out.append("- Bootstrap tutarlı")
        out.append("\n**Karar: PAPER TRADING'e geçilebilir, sonra gerçek bahis.**")
    else:
        out.append("# ❌ EDGE KANITLANMADI")
        out.append("\nGerçek bahis için bilimsel kanıt yok. Sorunlar:")
        if not cond_p:
            out.append(f"- ❌ t-test p={p_value:.3f} (>0.05) — ROI anlamsız")
        if not cond_clv:
            out.append(f"- ❌ CLV ortalaması {mean_clv:+.2f}% — negatif, gerçek edge yok")
        if not cond_n:
            out.append(f"- ❌ Sample yetersiz (n={n}, 500+ gerek)")
        if not cond_boot:
            out.append(f"- ❌ Bootstrap güvenilir değil")
        out.append("\n**Karar: PARA YATIRMA. Model iyileştirme gerekli (Sprint 2.3 LLM augmentation).**")

    return "\n".join(out)


def main():
    print("=" * 70)
    print("MULTI-LEAGUE BİLİMSEL VALİDASYON")
    print("=" * 70)

    matches_path = YAZILIM_DIR / "02_VERI" / "processed" / "matches.csv"
    df = pd.read_csv(matches_path, parse_dates=["match_date"])
    print(f"Toplam veri: {len(df):,} mac, {df.league.nunique()} lig")

    all_bets_list = []
    for lg in LEAGUES_TO_TEST:
        bets_df = run_league(df, lg)
        all_bets_list.append(bets_df)

    all_bets = pd.concat(all_bets_list, ignore_index=True)
    print(f"\n{'=' * 70}")
    print(f"TOPLAM BAHİS: {len(all_bets)}")
    print(f"{'=' * 70}")

    # Kaydet
    out_csv = YAZILIM_DIR / "07_LOG_VE_RAPORLAR" / "multi_league_bets.csv"
    all_bets.to_csv(out_csv, index=False)
    print(f"Bet log: {out_csv.name}")

    # Bilimsel rapor
    report = scientific_verdict(all_bets)
    report_path = YAZILIM_DIR / "07_LOG_VE_RAPORLAR" / "scientific_verdict.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"Rapor : {report_path.name}")

    # Konsola özet
    print("\n" + "=" * 70)
    print("ÖZET")
    print("=" * 70)
    for line in report.split("\n"):
        if line.startswith("#") or line.startswith("|") or line.startswith("-") or line.startswith("✅") or line.startswith("❌") or line.startswith("⚠️"):
            print(line)


if __name__ == "__main__":
    main()
