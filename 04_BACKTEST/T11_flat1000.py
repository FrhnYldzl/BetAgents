"""
TEST T11 — Her Hafta 1000 TL Flat Risk Simülasyonu
====================================================

BİLİMSEL SORU:
    H1: Her kuponda 1000 TL flat stake — 4 sezon sonunda NET ne kalır?
    H2: Toplam yatırım (hacim) ne kadar, getiri yüzdesi?
    H3: En kötü hafta? En iyi hafta? En uzun kayıp serisi?
    H4: Aylık ortalama PnL? Yıllık ortalama?
    H5: Multi-league yapsak — her ligten ayrı 1000 TL kupon — toplam ne olur?

METODOLOJİ:
    Stake = 1000 TL (sabit, compound DEĞİL)
    Win  = +1000 × (combo_odd - 1)
    Loss = -1000

    Configs:
        a) T1 K=3 (anchor)
        b) E0 K=3
        c) D1 K=3
        d) T1 K=2
        e) ALL leagues K=3 (her lig kupon paralel)
        f) E0+T1 K=3 paralel

ÇIKTI:
    - RAPOR/T11_flat1000.md
    - 07_LOG_VE_RAPORLAR/T11_weekly.csv
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


STAKE = 1000.0


def build_kupons(K: int, leagues: list) -> pd.DataFrame:
    """Belirli lig(ler) için K-leg FAV_CONFIRMED kuponları, kronolojik."""
    df = load_snapshots()
    df["matchday"] = pd.to_datetime(df["kickoff_iso"]).dt.normalize()
    df = df[df["settled"] == 1].copy()
    df = add_fav_confirmed(df)
    df = df[df["dir_fav_confirmed"].notna() & df["league_code"].isin(leagues)]
    df = df.sort_values("score_v13", ascending=False)

    kupons = []
    # Group by (matchday, league) — her lig için ayrı kupon
    for (md, lg), group in df.groupby(["matchday", "league_code"]):
        topK = group.head(K)
        if len(topK) < K:
            continue
        combo_odd = 1.0
        all_won = True
        for _, leg in topK.iterrows():
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
        kupons.append({
            "matchday": md, "league": lg,
            "combo_odd": combo_odd, "won": all_won,
        })
    return pd.DataFrame(kupons).sort_values("matchday").reset_index(drop=True)


def simulate_flat(kupons: pd.DataFrame, stake: float = STAKE) -> dict:
    """Flat stake simülasyonu."""
    n = len(kupons)
    if n == 0:
        return {"n": 0}

    pnls = []
    for _, r in kupons.iterrows():
        if r["won"]:
            pnls.append(stake * (r["combo_odd"] - 1))
        else:
            pnls.append(-stake)

    n_won = sum(1 for p in pnls if p > 0)
    total_stake = stake * n
    total_pnl = sum(pnls)
    roi = total_pnl / total_stake * 100

    # Streak
    longest_loss = 0; current_loss = 0
    longest_win = 0; current_win = 0
    for p in pnls:
        if p < 0:
            current_loss += 1; current_win = 0
            longest_loss = max(longest_loss, current_loss)
        else:
            current_win += 1; current_loss = 0
            longest_win = max(longest_win, current_win)

    # Cumulative PnL
    cum = np.cumsum(pnls)
    max_high = max(cum) if len(cum) > 0 else 0
    max_low = min(cum) if len(cum) > 0 else 0
    # Maximum drawdown (cumulative bazlı, başlangıç 0)
    peak = 0; max_dd = 0
    for c in cum:
        peak = max(peak, c)
        dd = peak - c
        max_dd = max(max_dd, dd)

    # Aylık ve yıllık ortalama
    if n > 0 and "matchday" in kupons:
        days = (kupons["matchday"].max() - kupons["matchday"].min()).days
        years = max(days / 365.25, 0.5)
        annual_pnl = total_pnl / years
        monthly_pnl = annual_pnl / 12
    else:
        annual_pnl = monthly_pnl = 0

    best_week = max(pnls)
    worst_week = min(pnls)

    return {
        "n": n,
        "n_won": n_won,
        "hit_rate": n_won / n,
        "total_stake": total_stake,
        "total_pnl": total_pnl,
        "roi_pct": roi,
        "best_week": best_week,
        "worst_week": worst_week,
        "longest_loss_streak": longest_loss,
        "longest_win_streak": longest_win,
        "max_drawdown_tl": max_dd,
        "cumulative_high": max_high,
        "cumulative_low": max_low,
        "avg_combo_odd": kupons["combo_odd"].mean(),
        "annual_pnl": annual_pnl,
        "monthly_pnl": monthly_pnl,
        "pnls": pnls,
        "weekly_data": list(zip(
            kupons["matchday"].astype(str).tolist(),
            kupons["league"].tolist(),
            kupons["combo_odd"].tolist(),
            kupons["won"].tolist(),
            pnls,
        )),
    }


def run():
    print("=" * 100)
    print("T11 — HER HAFTA 1000 TL FLAT RISK SIMULASYONU")
    print("=" * 100)

    configs = [
        ("T1 K=3 (anchor)", 3, ["T1"]),
        ("T1 K=2", 2, ["T1"]),
        ("T1 K=1", 1, ["T1"]),
        ("E0 K=3", 3, ["E0"]),
        ("D1 K=3", 3, ["D1"]),
        ("ALL K=3 (her lig paralel)", 3, ["E0", "D1", "T1"]),
        ("E0+T1 K=3", 3, ["E0", "T1"]),
        ("E0+T1 K=2", 2, ["E0", "T1"]),
    ]

    results = []
    print(f"\n{'STRATEJI':30s} {'n':>4s} {'hit%':>5s} {'hacim':>10s} {'pnl':>10s} {'ROI':>6s} {'best':>7s} {'worst':>7s} {'maxDD':>8s} {'aylik':>9s}")
    print("-" * 110)
    for name, K, leagues in configs:
        kp = build_kupons(K, leagues)
        r = simulate_flat(kp)
        r["name"] = name
        results.append(r)
        if r["n"] == 0:
            print(f"  {name:28s} (0 kupon)")
            continue
        print(f"  {name:28s} {r['n']:>4d} {r['hit_rate']*100:>4.0f}% "
              f"{r['total_stake']:>9,.0f} {r['total_pnl']:>+9,.0f} "
              f"{r['roi_pct']:>+5.1f}% "
              f"{r['best_week']:>+6,.0f} {r['worst_week']:>+6,.0f} "
              f"{r['max_drawdown_tl']:>7,.0f} "
              f"{r['monthly_pnl']:>+8,.0f}")

    # CSV — weekly detail (T1 K=3 anchor)
    LOGS_DIR.mkdir(exist_ok=True)
    anchor = next(r for r in results if r["name"] == "T1 K=3 (anchor)")
    weekly_df = pd.DataFrame(anchor["weekly_data"],
                            columns=["matchday", "league", "combo_odd", "won", "pnl"])
    weekly_df.to_csv(LOGS_DIR / "T11_weekly_t1_k3.csv", index=False)
    print(f"\nWeekly CSV (T1 K=3): T11_weekly_t1_k3.csv")

    write_report(results)
    return results


def write_report(results):
    RAPOR_DIR.mkdir(exist_ok=True)
    p = RAPOR_DIR / "T11_flat1000.md"

    rows = []
    for r in results:
        if r["n"] == 0:
            continue
        rows.append(
            f"| {r['name']} | {r['n']} | {r['hit_rate']*100:.0f}% | "
            f"{r['avg_combo_odd']:.2f} | "
            f"{r['total_stake']:,.0f} | {r['total_pnl']:+,.0f} | "
            f"{r['roi_pct']:+.1f}% | "
            f"{r['best_week']:+,.0f} | {r['worst_week']:+,.0f} | "
            f"{r['longest_loss_streak']} | {r['max_drawdown_tl']:,.0f} | "
            f"{r['monthly_pnl']:+,.0f} | {r['annual_pnl']:+,.0f} |"
        )

    anchor = next((r for r in results if r["name"] == "T1 K=3 (anchor)"), None)
    portfolio = next((r for r in results if "ALL K=3" in r["name"]), None)

    md = f"""# T11 — Her Hafta 1000 TL Flat Risk

**Versiyon:** v1.0
**Tarih:** {datetime.now().isoformat()[:19]}

---

## Bilimsel Soru

**H1:** Her kuponda 1000 TL flat → 4 sezon sonunda NET PnL nedir?

Hiç compound yok, hiç Kelly yok. Sabit risk → sade matematik.

---

## Sonuçlar

| Strateji | n | Hit% | Avg Odd | Hacim | Net PnL | ROI | Best | Worst | LossStreak | MaxDD | Aylık | Yıllık |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

---

## Yorum

### T1 K=3 (Anchor)
{f'''- **{anchor['n']} kupon** oynanmış, **{anchor['n_won']} tanesi tutmuş** ({anchor['hit_rate']*100:.0f}%)
- Toplam yatırım: **{anchor['total_stake']:,.0f} TL** (hacim)
- Net kazanç: **{anchor['total_pnl']:+,.0f} TL**
- ROI: **{anchor['roi_pct']:+.1f}%**
- En iyi hafta: **+{anchor['best_week']:,.0f} TL** (combo {anchor['best_week']/1000+1:.2f}× tuttu)
- En kötü hafta: **{anchor['worst_week']:+,.0f} TL** (kupon kaybetti)
- En uzun kayıp serisi: **{anchor['longest_loss_streak']} hafta**
- Max drawdown: **{anchor['max_drawdown_tl']:,.0f} TL** (peak'ten aşağı)
- Aylık ortalama: **{anchor['monthly_pnl']:+,.0f} TL**
- Yıllık ortalama: **{anchor['annual_pnl']:+,.0f} TL**''' if anchor else ''}

### ALL K=3 paralel (Her ligten kupon)
{f'''- Hacim: **{portfolio['total_stake']:,.0f} TL** ({portfolio['n']} kupon × 1000 TL)
- Net: **{portfolio['total_pnl']:+,.0f} TL**, ROI **{portfolio['roi_pct']:+.1f}%**
- T1-only ile karşılaştırma: ROI **{portfolio['roi_pct'] - anchor['roi_pct']:+.1f} pp fark**''' if portfolio and anchor else ''}

---

## Pratik Çıkarımlar

1. **Aylık ~+{anchor['monthly_pnl']/1000:.1f}K TL** (T1 K=3) — küçük ama tutarlı
2. **En kötü hafta -1000 TL** (kupon kaybetti) — ama kazanan kupon ~+5000-8000 TL
3. **{anchor['longest_loss_streak']} hafta arka arkaya kayıp** olabilir — sabır gerekir
4. Toplam hacim: ~{anchor['total_stake']/1000:.0f}K TL → kullanıcı 4 sezon boyunca bu hacimde stake'lemeye razı mı?

Weekly detail CSV: `07_LOG_VE_RAPORLAR/T11_weekly_t1_k3.csv`
"""
    p.write_text(md, encoding="utf-8")
    print(f"Rapor: {p}")


if __name__ == "__main__":
    run()
