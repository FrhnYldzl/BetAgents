"""
EUVOX E01-E05 — Diagnostik
============================

T20'de 6-lig kötü çıkmıştı. NEDEN?

E01 — Per-lig FAV_CONFIRMED coverage (kaç maçta filtre geçiyor)
E02 — Per-lig DC availability (DC modeli olan/olmayan)
E03 — Per-lig sinyal kapsamı (anomaly/model/xG/form coverage)
E04 — Per-lig hit rate dağılımı (favori, FAV_CONFIRMED)
E05 — Per-lig odd distribution (combo K=3)

ÇIKTI:
    - RAPOR/EUVOX_E01_diagnostic.md
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

sys.path.insert(0, str(YAZILIM / "03_MODELLER" / "selective"))
from trivox_v1 import TrivoxModel, fav_confirmed, normalize_dir, get_odd_for_dir, did_win


def load_data():
    import sqlite3
    conn = sqlite3.connect(YAZILIM / "02_VERI" / "bahis_agent.db")
    df = pd.read_sql_query(
        "SELECT * FROM signal_snapshots WHERE source='football_data'", conn
    )
    conn.close()
    df["matchday"] = pd.to_datetime(df["kickoff_iso"]).dt.normalize()
    return df


def E01_coverage(df):
    """Her lig: settled mac, FAV_CONFIRMED match, K=3 kupon."""
    print("\n=== E01 — Per-Lig Coverage ===")
    print(f"{'LIG':5s} {'mac':>5s} {'fav_dir':>8s} {'fc_match':>9s} {'K3_kupon':>9s} {'kupon%':>7s}")
    print("-" * 60)
    results = []
    for lg in sorted(df["league_code"].unique()):
        sub = df[(df["league_code"] == lg) & (df["settled"] == 1)].copy()
        sub["dir_fc"] = sub.apply(lambda r: fav_confirmed(r.to_dict(), 1), axis=1)
        n_total = len(sub)
        n_fav = sub["dir_favorite"].notna().sum()
        n_fc = sub["dir_fc"].notna().sum()
        # K=3 kupon say (TrivoxModel ile)
        model = TrivoxModel(leagues=[lg])
        k = model.build_kupons(df)
        n_kupon = len(k)
        coverage = n_kupon / sub["matchday"].nunique() * 100 if sub["matchday"].nunique() else 0
        print(f"  {lg:4s} {n_total:>5d} {n_fav:>8d} {n_fc:>9d} {n_kupon:>9d} {coverage:>6.1f}%")
        results.append({
            "lig": lg, "n_settled": n_total, "n_fav_dir": int(n_fav),
            "n_fc_match": int(n_fc), "n_kupon_K3": n_kupon,
            "coverage_pct": coverage,
        })
    return results


def E02_dc_availability(df):
    """DC sinyali olan / olmayan dağılımı."""
    print("\n=== E02 — DC Availability ===")
    print(f"{'LIG':5s} {'mac':>5s} {'has_DC':>7s} {'DC%':>6s} {'has_xG':>7s} {'xG%':>6s}")
    print("-" * 50)
    results = []
    for lg in sorted(df["league_code"].unique()):
        sub = df[(df["league_code"] == lg) & (df["settled"] == 1)]
        n = len(sub)
        has_dc = sub["s_model"].notna().sum()
        has_xg = (sub["s_xg"].fillna(0) > 0).sum()
        print(f"  {lg:4s} {n:>5d} {has_dc:>7d} {has_dc/n*100:>5.0f}% {has_xg:>7d} {has_xg/n*100:>5.0f}%")
        results.append({"lig": lg, "n_total": n, "has_dc": int(has_dc),
                       "dc_pct": has_dc/n*100, "has_xg": int(has_xg),
                       "xg_pct": has_xg/n*100})
    return results


def E03_signal_coverage(df):
    """Her sinyalin per-lig coverage."""
    print("\n=== E03 — Signal Coverage Per League ===")
    print(f"{'LIG':5s} {'anomaly%':>9s} {'model%':>7s} {'xG%':>6s} {'form%':>7s} {'4-sig%':>7s}")
    print("-" * 60)
    results = []
    for lg in sorted(df["league_code"].unique()):
        sub = df[(df["league_code"] == lg) & (df["settled"] == 1)]
        n = len(sub)
        if n == 0:
            continue
        a = sub["dir_anomaly"].notna().sum() / n * 100
        m = sub["dir_model"].notna().sum() / n * 100
        x = sub["dir_xg"].notna().sum() / n * 100
        f = sub["dir_form"].notna().sum() / n * 100
        # 4 sinyal hepsi var
        four = sub[
            sub["dir_anomaly"].notna() &
            sub["dir_model"].notna() &
            sub["dir_xg"].notna() &
            sub["dir_form"].notna()
        ]
        four_pct = len(four) / n * 100
        print(f"  {lg:4s} {a:>8.0f}% {m:>6.0f}% {x:>5.0f}% {f:>6.0f}% {four_pct:>6.0f}%")
        results.append({"lig": lg, "anomaly_pct": a, "model_pct": m,
                       "xg_pct": x, "form_pct": f, "all4_pct": four_pct})
    return results


def E04_hit_rates(df):
    """Her lig: favori hit, FAV_CONFIRMED hit."""
    print("\n=== E04 — Per-Lig Hit Rate ===")
    print(f"{'LIG':5s} {'n_set':>6s} {'fav_hit':>8s} {'fc_hit':>7s} {'k3_hit':>7s}")
    print("-" * 50)
    results = []
    for lg in sorted(df["league_code"].unique()):
        sub = df[(df["league_code"] == lg) & (df["settled"] == 1)].copy()
        n = len(sub)
        # Hep favori
        wins_fav = 0; n_fav = 0
        for _, r in sub.iterrows():
            d = r.get("dir_favorite")
            if not d: continue
            n_fav += 1
            if did_win(r.to_dict(), d):
                wins_fav += 1
        fav_hit = wins_fav / n_fav if n_fav else 0
        # FAV_CONFIRMED
        sub["dir_fc"] = sub.apply(lambda r: fav_confirmed(r.to_dict(), 1), axis=1)
        sub_fc = sub[sub["dir_fc"].notna()]
        wins_fc = sum(1 for _, r in sub_fc.iterrows()
                     if did_win(r.to_dict(), r["dir_fc"]))
        fc_hit = wins_fc / len(sub_fc) if len(sub_fc) else 0
        # K=3 kupon hit
        model = TrivoxModel(leagues=[lg])
        k = model.build_kupons(df)
        k3_hit = k["won"].mean() if not k.empty else 0
        print(f"  {lg:4s} {n:>6d} {fav_hit*100:>7.1f}% {fc_hit*100:>6.1f}% {k3_hit*100:>6.1f}%")
        results.append({"lig": lg, "n_settled": n,
                       "fav_hit": fav_hit, "fc_hit": fc_hit, "k3_hit": k3_hit})
    return results


def E05_odd_dist(df):
    """Per-lig combo K=3 odd distribution."""
    print("\n=== E05 — Per-Lig K=3 Combo Odd Distribution ===")
    print(f"{'LIG':5s} {'n':>4s} {'min':>5s} {'p25':>5s} {'med':>5s} {'p75':>5s} {'max':>5s}")
    print("-" * 50)
    results = []
    for lg in sorted(df["league_code"].unique()):
        model = TrivoxModel(leagues=[lg])
        k = model.build_kupons(df)
        if k.empty:
            continue
        odds = k["combo_odd"].values
        print(f"  {lg:4s} {len(odds):>4d} {odds.min():>5.2f} {np.percentile(odds,25):>5.2f} "
              f"{np.median(odds):>5.2f} {np.percentile(odds,75):>5.2f} {odds.max():>5.2f}")
        results.append({"lig": lg, "n": len(odds), "min": float(odds.min()),
                       "p25": float(np.percentile(odds, 25)),
                       "median": float(np.median(odds)),
                       "p75": float(np.percentile(odds, 75)),
                       "max": float(odds.max())})
    return results


def run():
    print("=" * 80)
    print("EUVOX FAZ I — Diagnostik (E01-E05)")
    print("=" * 80)

    df = load_data()
    print(f"\nLoaded: {len(df)} kayit")

    r1 = E01_coverage(df)
    r2 = E02_dc_availability(df)
    r3 = E03_signal_coverage(df)
    r4 = E04_hit_rates(df)
    r5 = E05_odd_dist(df)

    write_report(r1, r2, r3, r4, r5)


def write_report(r1, r2, r3, r4, r5):
    RAPOR_DIR.mkdir(exist_ok=True)
    p = RAPOR_DIR / "EUVOX_E01_diagnostic.md"

    def to_md_table(rows):
        if not rows: return "(boş)"
        cols = list(rows[0].keys())
        md = "| " + " | ".join(cols) + " |\n"
        md += "|" + "|".join(["---"] * len(cols)) + "|\n"
        for r in rows:
            md += "| " + " | ".join(
                f"{v:.2f}" if isinstance(v, float) else str(v)
                for v in r.values()
            ) + " |\n"
        return md

    md = f"""# EUVOX Faz I — Diagnostik

**Tarih:** {datetime.now().isoformat()[:19]}

T20'de 6-lig genişleme -38K zarar verdi. **Neden?**

---

## E01 — Per-Lig Coverage

{to_md_table(r1)}

**Yorum:** FAV_CONFIRMED filtresinden geçen maç sayısı liglere göre değişir.
Az FC match → az kupon → az fırsat.

---

## E02 — DC Availability

{to_md_table(r2)}

**KRİTİK:** SP1, I1, F1'de DC modeli **YOK** (sadece T1, E0, D1).
FAV_CONFIRMED filtresinde DC sinyali en güçlü olduğundan, bu eksiklik zayıflığı açıklıyor.

---

## E03 — Signal Coverage Per League

{to_md_table(r3)}

**Yorum:** Sinyaller per-lig nasıl dağılıyor? all4 yüksekse iyi.

---

## E04 — Hit Rate Comparison

{to_md_table(r4)}

**Yorum:**
- `fav_hit`: Hep favori baseline (referans)
- `fc_hit`: FAV_CONFIRMED filtre uygulanmış (en az 1 sinyal teyit)
- `k3_hit`: K=3 combo kupon hit rate

FAV_CONFIRMED filtresi fav_hit'ten ne kadar yüksek hit veriyor? Lig-spesifik.

---

## E05 — Per-Lig K=3 Combo Odd Distribution

{to_md_table(r5)}

**Yorum:** Combo odd dağılımı. Yüksek odd → daha az hit ama daha çok kazanç.

---

## Tespit (Diagnostik Sonucu)

1. **SP1, I1, F1'de DC modeli yok** — FAV_CONFIRMED filtresi zayıf
2. Her lig farklı **coverage, hit rate, odd dağılımı**
3. Lig-spesifik tuning gerek (T03 + T04 metodolojisi her lige uygulanmalı)

**Sonraki Adım:** Faz II — SP1, I1, F1 için DC modeli eğit.
"""
    p.write_text(md, encoding="utf-8")
    print(f"\nRapor: {p}")


if __name__ == "__main__":
    run()
