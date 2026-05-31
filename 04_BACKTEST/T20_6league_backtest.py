"""
TEST T20 — 6-Lig Backtest (T1+E0+D1+SP1+I1+F1)
================================================

SP1, I1, F1 ingest sonrası 6-lig multi-league strateji testi.

NOT: SP1/I1/F1 DC modeli YOK → dir_model None, sadece anomaly+xG+form ile
FAV_CONFIRMED hesaplanır (≥1 confirmer).

KARŞILAŞTIRMA:
    - 3-lig (önceki +81K)
    - 6-lig (yeni)
    - Per-lig kırılım
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
YAZILIM = THIS_DIR.parent
RAPOR_DIR = YAZILIM / "RAPOR"
LOGS_DIR = YAZILIM / "07_LOG_VE_RAPORLAR"

sys.path.insert(0, str(THIS_DIR))
from T11_flat1000 import simulate_flat


def build_kupons_extended(K: int, leagues: list) -> pd.DataFrame:
    """Tüm signal_snapshots'tan FAV_CONFIRMED K-leg kuponları."""
    import sqlite3
    db_path = YAZILIM / "02_VERI" / "bahis_agent.db"
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query(
        "SELECT * FROM signal_snapshots WHERE source='football_data' AND settled=1",
        conn
    )
    conn.close()

    def normalize_dir(d):
        if d in ("HOME", "H", "1"): return "HOME"
        if d in ("AWAY", "A", "2"): return "AWAY"
        if d in ("DRAW", "D", "X"): return "DRAW"
        return d

    def fav_confirmed(r):
        fav = r.get("dir_favorite")
        if not fav: return None
        fav_n = normalize_dir(fav)
        sigs = [r.get("dir_anomaly"), r.get("dir_model"),
                r.get("dir_xg"), r.get("dir_form")]
        agreeing = [s for s in sigs if s and normalize_dir(s) == fav_n]
        return fav if len(agreeing) >= 1 else None

    df["dir_fav_confirmed"] = df.apply(fav_confirmed, axis=1)
    df = df[df["dir_fav_confirmed"].notna() & df["league_code"].isin(leagues)]
    df["matchday"] = pd.to_datetime(df["kickoff_iso"]).dt.normalize()
    df = df.sort_values("score_v13", ascending=False)

    kupons = []
    for (md, lg), group in df.groupby(["matchday", "league_code"]):
        topK = group.head(K)
        if len(topK) < K: continue
        combo_odd = 1.0; all_won = True
        for _, leg in topK.iterrows():
            d = leg["dir_fav_confirmed"]
            if d in ("HOME","H","1"): o, w = leg["odd_1"], leg["result_1x2"] == "H"
            elif d in ("AWAY","A","2"): o, w = leg["odd_2"], leg["result_1x2"] == "A"
            elif d in ("DRAW","D","X"): o, w = leg["odd_X"], leg["result_1x2"] == "D"
            else: o = w = None
            if not o or o < 1.01:
                combo_odd = None; break
            combo_odd *= o
            if not w: all_won = False
        if combo_odd is None: continue
        kupons.append({
            "matchday": md, "league": lg,
            "combo_odd": combo_odd, "won": all_won,
        })
    return pd.DataFrame(kupons).sort_values("matchday").reset_index(drop=True)


def run():
    print("=" * 100)
    print("T20 — 6-LIG BACKTEST (T1+E0+D1+SP1+I1+F1)")
    print("=" * 100)

    # Per-lig
    print(f"\n{'LIG':5s} {'n':>4s} {'won':>4s} {'hit%':>5s} {'hacim':>9s} {'pnl':>10s} {'ROI':>6s} {'yıllık':>9s}")
    print("-" * 80)
    all_results = []
    for lg in ["T1", "E0", "D1", "SP1", "I1", "F1"]:
        kp = build_kupons_extended(3, [lg])
        if len(kp) == 0:
            print(f"  {lg:4s} (0 kupon)")
            continue
        r = simulate_flat(kp, stake=1000.0)
        r["league"] = lg
        all_results.append(r)
        print(f"  {lg:4s} {r['n']:>4d} {r['n_won']:>4d} {r['hit_rate']*100:>4.0f}% "
              f"{r['total_stake']:>8,.0f} {r['total_pnl']:>+9,.0f} {r['roi_pct']:>+5.1f}% "
              f"{r['annual_pnl']:>+8,.0f}")

    # Total 6-lig
    if all_results:
        n_tot = sum(r["n"] for r in all_results)
        won_tot = sum(r["n_won"] for r in all_results)
        stake_tot = sum(r["total_stake"] for r in all_results)
        pnl_tot = sum(r["total_pnl"] for r in all_results)
        annual_tot = sum(r["annual_pnl"] for r in all_results)
        print(f"\n  6-LIG TOPLAM:")
        print(f"    n: {n_tot}, won: {won_tot} ({won_tot/n_tot*100:.0f}%)")
        print(f"    Hacim: {stake_tot:,.0f}, PnL: {pnl_tot:+,.0f}")
        print(f"    ROI: {pnl_tot/stake_tot*100:+.1f}%, Yıllık: {annual_tot:+,.0f}")

    # 3-lig vs 6-lig karşılaştırma
    print(f"\n=== 3-LIG vs 6-LIG ===")
    three = [r for r in all_results if r["league"] in ("T1", "E0", "D1")]
    six = all_results
    if three and six:
        t3_pnl = sum(r["total_pnl"] for r in three)
        t3_n = sum(r["n"] for r in three)
        t6_pnl = sum(r["total_pnl"] for r in six)
        t6_n = sum(r["n"] for r in six)
        print(f"  3-lig (T1+E0+D1): n={t3_n}, PnL={t3_pnl:+,.0f}, yıllık={sum(r['annual_pnl'] for r in three):+,.0f}")
        print(f"  6-lig (+SP1+I1+F1): n={t6_n}, PnL={t6_pnl:+,.0f}, yıllık={sum(r['annual_pnl'] for r in six):+,.0f}")
        print(f"  Fark (ek 3 lig'ten): n+={t6_n-t3_n}, PnL+={t6_pnl-t3_pnl:+,.0f}")

    write_report(all_results)


def write_report(results):
    RAPOR_DIR.mkdir(exist_ok=True)
    p = RAPOR_DIR / "T20_6league_backtest.md"

    rows = []
    for r in results:
        rows.append(
            f"| {r['league']} | {r['n']} | {r['n_won']} | "
            f"{r['hit_rate']*100:.0f}% | {r['avg_combo_odd']:.2f} | "
            f"{r['total_stake']:,.0f} | {r['total_pnl']:+,.0f} | "
            f"{r['roi_pct']:+.1f}% | {r['annual_pnl']:+,.0f} |"
        )

    n_tot = sum(r["n"] for r in results)
    pnl_tot = sum(r["total_pnl"] for r in results)
    stake_tot = sum(r["total_stake"] for r in results)
    annual_tot = sum(r["annual_pnl"] for r in results)

    md = f"""# T20 — 6-Lig Backtest (T1+E0+D1+SP1+I1+F1)

**Versiyon:** v1.0
**Tarih:** {datetime.now().isoformat()[:19]}

---

## Bilimsel Soru

SP1 (La Liga), I1 (Serie A), F1 (Ligue 1) eklenince 6-lig multi-league
strateji 3-lig'den daha karlı mı?

NOT: SP1/I1/F1 için DC modeli YOK → sadece anomaly+xG+form sinyalleri.
FAV_CONFIRMED ≥1 confirmer.

---

## Per-Lig Sonuçlar (K=3 FAV_CONFIRMED Flat 1000 TL)

| Lig | n | Won | Hit% | Avg Odd | Hacim | Net PnL | ROI | Yıllık |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

---

## 6-Lig Toplam

- **Toplam kupon:** {n_tot}
- **Toplam hacim:** {stake_tot:,.0f} TL
- **Toplam NET PnL:** {pnl_tot:+,.0f} TL
- **ROI:** {pnl_tot/stake_tot*100:+.1f}% (eğer hacim > 0)
- **Yıllık ortalama:** {annual_tot:+,.0f} TL

---

## Yorum

6-lig vs 3-lig: ek 3 lig (SP1+I1+F1) toplam PnL'ye nasıl etki etti?

Eğer her lig pozitif → diversifikasyon iyi, daha çok lig daha çok kar.
Eğer bazı lig negatif → o lig stratejinin dışına alınmalı (D1 örneği gibi).
"""
    p.write_text(md, encoding="utf-8")
    print(f"\nRapor: {p}")


if __name__ == "__main__":
    run()
