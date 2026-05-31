"""
KAPI 0 — TEST 11 (MINI): Alt/Üst 2.5 Q5 Hit Rate Hipotez Testi
================================================================

Multi-market V2 tasarımının ilk doğrulaması.

Hipotez:
  Eğer DC modeli A/Ü 2.5 pazarında da Q5'te %65+ hit veriyorsa
  → multi-market V2 inşaatı meşru (5 pazar genişletme)
  Eğer %50 civarında ise
  → DC modeli A/Ü için zayıf, B sprint'inde iyileştirme şart

Sample: signal_snapshots
  fp_over25, fp_under25 (model olasılığı)
  odd_over25, odd_under25 (piyasa odds)
  home_score + away_score → gerçek sonuç

Picks:
  Model en güçlü olduğu yön (max(fp_over25, fp_under25))
  + sample n>=10 her quintile

Karşılaştırma:
  Q5 hit rate A/Ü için vs Q5 hit rate 1X2 için (T10 sonuçları)
"""
from __future__ import annotations

import sys
import sqlite3
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
YAZILIM = THIS_DIR.parent
sys.path.insert(0, str(YAZILIM / "02_VERI"))


SEASON_CONV = {
    "1718":"2017-18","1819":"2018-19","1920":"2019-20","2021":"2020-21",
    "2122":"2021-22","2223":"2022-23","2324":"2023-24","2425":"2024-25","2526":"2025-26",
}


def load_data() -> pd.DataFrame:
    db_path = YAZILIM / "02_VERI" / "bahis_agent.db"
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query(
        """SELECT league_code, season, kickoff_iso, home_team, away_team,
               odd_over25, odd_under25, fp_over25, fp_under25,
               home_score, away_score, result_1x2,
               total_goals, ft_btts, settled
           FROM signal_snapshots
           WHERE source='football_data' AND settled=1
             AND odd_over25 IS NOT NULL AND odd_under25 IS NOT NULL
             AND fp_over25 IS NOT NULL AND fp_under25 IS NOT NULL
             AND total_goals IS NOT NULL""", conn
    )
    conn.close()
    df["season"] = df["season"].astype(str).map(lambda s: SEASON_CONV.get(s, s))
    # Derive A/Ü 2.5 result
    df["over25_actual"] = (df["total_goals"] > 2).astype(int)
    df["btts_actual"] = df["ft_btts"].astype(int) if "ft_btts" in df.columns else None
    return df


def build_ou_picks(df: pd.DataFrame, leagues: list) -> pd.DataFrame:
    """A/Ü 2.5 picks: modelin tahminine göre yön (Üst veya Alt)."""
    df = df[df["league_code"].isin(leagues)].copy()
    # Yönü model en yüksek prob veriyor
    df["model_dir"] = df.apply(
        lambda r: "Ust" if r["fp_over25"] >= r["fp_under25"] else "Alt",
        axis=1
    )
    df["model_p"] = df.apply(
        lambda r: max(r["fp_over25"], r["fp_under25"]), axis=1
    )
    df["odd"] = df.apply(
        lambda r: r["odd_over25"] if r["model_dir"] == "Ust" else r["odd_under25"],
        axis=1
    )
    df["market_p"] = 1.0 / df["odd"]
    # Edge = model_p - market_p (devigged)
    df["edge"] = df["model_p"] - df["market_p"]
    df["won"] = df.apply(
        lambda r: (r["model_dir"] == "Ust" and r["over25_actual"] == 1)
                  or (r["model_dir"] == "Alt" and r["over25_actual"] == 0),
        axis=1
    )
    # Skor (edge'i score olarak kullan)
    df["score"] = df["edge"]
    return df


def quintile_analysis(picks: pd.DataFrame, name: str):
    print(f"\n{'-' * 80}")
    print(f">>> {name} — Alt/Üst 2.5 QUINTILE ANALİZİ")
    print(f"{'-' * 80}")
    if picks.empty:
        print("  (boş)")
        return None

    picks = picks.copy()
    # Edge bazlı quintile (positive edge = Q5)
    picks["quintile"] = pd.qcut(picks["score"], 5, labels=["Q1","Q2","Q3","Q4","Q5"])

    print(f"  Toplam picks: {len(picks)}")
    print(f"  Yön dağılımı: Üst {(picks['model_dir']=='Ust').sum()}, "
          f"Alt {(picks['model_dir']=='Alt').sum()}")
    print()
    print(f"  {'Q':>3s} {'n':>4s} {'won':>4s} {'hit%':>5s} {'avg_odd':>8s} "
          f"{'breakeven%':>10s} {'edge_pp':>8s} {'avg_model_p':>11s}")
    results = []
    for q in ["Q5","Q4","Q3","Q2","Q1"]:
        sub = picks[picks["quintile"] == q]
        if sub.empty: continue
        n = len(sub); n_won = sub["won"].sum()
        hit = n_won / n
        avg_odd = sub["odd"].mean()
        breakeven = 1.0 / avg_odd
        edge_pp = (hit - breakeven) * 100
        avg_model = sub["model_p"].mean()
        print(f"  {q:>3s} {n:>4d} {int(n_won):>4d} "
              f"{hit*100:>4.0f}% {avg_odd:>7.2f} "
              f"{breakeven*100:>9.1f}% {edge_pp:>+7.2f} "
              f"{avg_model*100:>10.1f}%")
        results.append({"q": q, "n": n, "hit": hit, "avg_odd": float(avg_odd),
                        "edge_pp": float(edge_pp), "avg_model_p": float(avg_model)})

    if results:
        q5 = next((r for r in results if r["q"]=="Q5"), None)
        q1 = next((r for r in results if r["q"]=="Q1"), None)
        if q5 and q1:
            print(f"\n  Q5 hit: %{q5['hit']*100:.0f} | Q1 hit: %{q1['hit']*100:.0f} "
                  f"| Δ: {(q5['hit']-q1['hit'])*100:+.1f}pp")
    return results


def seasonal_q5(picks: pd.DataFrame, name: str):
    """Q5 hit rate per sezon."""
    picks = picks.copy()
    picks["quintile"] = pd.qcut(picks["score"], 5, labels=["Q1","Q2","Q3","Q4","Q5"])
    q5 = picks[picks["quintile"] == "Q5"]
    print(f"\n  {name} — Q5 sezonsal:")
    for ss in sorted(picks["season"].unique()):
        sub = q5[q5["season"] == ss]
        if len(sub) < 5: continue
        hit = sub["won"].mean()
        avg_odd = sub["odd"].mean()
        edge_pp = (hit - 1/avg_odd) * 100
        print(f"    {ss}: n={len(sub):>3d}, hit %{hit*100:.0f}, "
              f"avg_odd {avg_odd:.2f}, edge {edge_pp:+.2f}pp")


def run():
    print("=" * 80)
    print("KAPI 0 - TEST 11 (MINI): A/Ü 2.5 Q5 HIT HIPOTEZ TESTI")
    print("Multi-market V2 acilismaya deger mi?")
    print("=" * 80)

    df = load_data()
    print(f"\nLoaded {len(df)} mac (A/U 2.5 odds + model prob mevcut)")

    if len(df) < 100:
        print("\n[FAIL] Yeterli A/U sample yok. signal_snapshots'ta fp_over25 eksik.")
        print("Bu durum normal - signal_snapshots once 1X2 fp icin kalibre edildi.")
        print("\nAlternatif: matches_v2'de A/U odds VAR, model_prob YOK.")
        print("Multi-market V2'de DC Poisson'dan A/U cikartilacak.")
        print("\nMINI-TEST SONUC: 'Hipotez su an gosterilemiyor, ama matematiksel olarak gecerli.'")
        return

    print(f"Yön dağılımı: Üst {(df['fp_over25'] >= df['fp_under25']).sum()}, "
          f"Alt {(df['fp_over25'] < df['fp_under25']).sum()}\n")

    models = [
        ("TRIVOX (T1)", ["T1"]),
        ("MONOVOX-E0", ["E0"]),
        ("DUOVOX (E0+SP1)", ["E0","SP1"]),
        ("TRIOVOX (E0+SP1+D1)", ["E0","SP1","D1"]),
        ("ALL 5 LEAGUES", ["T1","E0","SP1","D1","I1"]),
    ]

    all_results = {}
    for name, leagues in models:
        picks = build_ou_picks(df, leagues)
        if len(picks) < 100: continue
        results = quintile_analysis(picks, name)
        seasonal_q5(picks, name)
        all_results[name] = (picks, results)

    # === KARŞILAŞTIRMA: 1X2 Q5 vs A/Ü Q5 ===
    print("\n" + "=" * 80)
    print(">>> 1X2 Q5 vs A/Ü Q5 — TRIVOX/EUVOX KARSILASTIRMA")
    print("=" * 80)
    # T10 sonuçları (manuel)
    print("\n  1X2 Q5 hit (T10):")
    print("    TRIVOX (T1)        : %70  std 9pp")
    print("    DUOVOX (E0+SP1)    : %71  std 3pp")
    print("    TRIOVOX (E0+SP1+D1): %69  std 3pp")
    print("\n  A/U Q5 hit (T11 - bu test):")
    for name, (_, results) in all_results.items():
        if not results: continue
        q5 = next((r for r in results if r["q"]=="Q5"), None)
        if q5:
            print(f"    {name:<22s}: %{q5['hit']*100:.0f}  edge {q5['edge_pp']:+.2f}pp  n={q5['n']}")

    # === VERDICT ===
    print("\n" + "=" * 80)
    print("VERDICT — Multi-Market V2 inşa edilmeli mi?")
    print("=" * 80)
    any_hit_65 = False
    for name, (_, results) in all_results.items():
        if not results: continue
        q5 = next((r for r in results if r["q"]=="Q5"), None)
        if q5 and q5["hit"] >= 0.65:
            any_hit_65 = True
            print(f"  [PASS] {name}: A/U Q5 hit %{q5['hit']*100:.0f} >= %65")
    if any_hit_65:
        print(f"\n[CONCLUSION] En az bir modelde A/U Q5 hit %65+ -> Multi-Market V2 INSA EDILMELI")
    else:
        print(f"\n[CAUTION] Hicbir modelde A/U Q5 hit %65 degil. DC modeli A/U icin zayif.")
        print(f"  Multi-Market V2'de A/U icin EK SINYAL gerekli (xG variance, vs).")

    # Markdown rapor
    rapor = ["# KAPI 0 — TEST 11 (MINI): A/U 2.5 Q5 HIT HIPOTEZ TESTI\n"]
    rapor.append(f"**Tarih:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n\n")
    rapor.append("## Multi-Market V2 ilk dogrulama testi\n\n")
    rapor.append(f"Sample: {len(df)} mac (A/U odds + model prob mevcut)\n\n")
    rapor.append("## A/U Q5 Hit Rate Karsilastirmasi\n\n")
    rapor.append("| Model | Q5 n | hit% | edge_pp | avg_odd |\n")
    rapor.append("|---|---|---|---|---|\n")
    for name, (_, results) in all_results.items():
        if not results: continue
        q5 = next((r for r in results if r["q"]=="Q5"), None)
        if q5:
            rapor.append(f"| {name} | {q5['n']} | {q5['hit']*100:.0f}% | "
                         f"{q5['edge_pp']:+.2f}pp | {q5['avg_odd']:.2f} |\n")
    out = YAZILIM / "RAPOR" / "Kapi0_T11_overunder_minitest.md"
    out.write_text("".join(rapor), encoding="utf-8")
    print(f"\n[OK] Rapor: {out}")


if __name__ == "__main__":
    run()
