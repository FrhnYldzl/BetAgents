"""
DD — Live 2025-26 Hafta-Hafta Prediction Test
=================================================

Acquirer'ın en kritik sorusu:
    "Bu yıl maçları aldın. Hafta hafta tahmin yapabilir misin?"

Test:
    - 2526 sezonu (devam ediyor)
    - Hafta hafta TRIVOX + EUVOX prediction
    - Her tahmin: model picks
    - Settled olanların sonucu ile karşılaştır
    - Bu hafta gerçek out-of-sample

ÇIKTI:
    - RAPOR/DD_live_prediction_2526.md
    - 07_LOG_VE_RAPORLAR/dd_predictions.csv
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

sys.path.insert(0, str(YAZILIM / "03_MODELLER" / "selective"))
from trivox_v1 import TrivoxModel
from euvox_v1 import EuvoxModel


def load_2526():
    import sqlite3
    conn = sqlite3.connect(YAZILIM / "02_VERI" / "bahis_agent.db")
    df = pd.read_sql_query(
        "SELECT * FROM signal_snapshots WHERE source='football_data' AND season='2526'",
        conn
    )
    conn.close()
    df["matchday"] = pd.to_datetime(df["kickoff_iso"]).dt.normalize()
    return df


def week_by_week(df_2526: pd.DataFrame, model, model_name: str):
    """Her matchday için kupon üret + outcome."""
    weeks = sorted(df_2526["matchday"].unique())
    print(f"\n=== {model_name} — 2526 Hafta-Hafta ===")
    print(f"{'matchday':>12s} {'lig':>4s} {'kupon':>5s} {'leg':>3s} {'odd':>5s} {'tutusu':>9s} {'pnl':>10s}")
    print("-" * 80)
    weekly_results = []
    cumulative_pnl = 0
    n_total = 0; n_won = 0

    for wk in weeks:
        df_wk = df_2526[df_2526["matchday"] == wk]
        if df_wk["settled"].sum() == 0:
            continue
        kupons = model.build_kupons(df_wk)
        if kupons.empty:
            continue
        for _, k in kupons.iterrows():
            n_total += 1
            won_count = sum(1 for leg in k["legs"] if leg["won"])
            total_legs = len(k["legs"])
            status = "TUTTU" if k["won"] else f"{won_count}/{total_legs}"
            pnl = k["pnl_gross"]
            cumulative_pnl += pnl
            if k["won"]: n_won += 1
            print(f"  {wk.strftime('%Y-%m-%d'):>12s} {k['league']:>4s} "
                  f"{k['K']:>5d}-leg {total_legs:>3d} {k['combo_odd']:>5.2f} "
                  f"{status:>9s} {pnl:>+9,.0f}")
            weekly_results.append({
                "matchday": wk, "league": k["league"], "K": k["K"],
                "combo_odd": k["combo_odd"], "won": k["won"],
                "pnl": pnl, "cumulative": cumulative_pnl,
            })

    print(f"\n  TOPLAM: n={n_total}, won={n_won} ({n_won/max(n_total,1)*100:.0f}%), "
          f"PnL: {cumulative_pnl:+,.0f}")
    return weekly_results, cumulative_pnl, n_total, n_won


def run():
    print("=" * 90)
    print("DD — Live 2025-26 Sezon Hafta-Hafta Prediction Test")
    print("=" * 90)

    df = load_2526()
    print(f"\n2526 sezonu data:")
    for lg in sorted(df["league_code"].unique()):
        sub = df[df["league_code"] == lg]
        settled = sub["settled"].sum()
        print(f"  {lg}: {len(sub)} mac, {settled} settled, "
              f"{sub['matchday'].min().date()} - {sub['matchday'].max().date()}")

    # TRIVOX (T1 only)
    print("\n" + "=" * 90)
    print("MODEL 1: TRIVOX (T1-only)")
    print("=" * 90)
    df_t1 = df[df["league_code"] == "T1"]
    trivox = TrivoxModel(leagues=["T1"])
    t_results, t_pnl, t_n, t_won = week_by_week(df_t1, trivox, "TRIVOX")

    # EUVOX (6-lig)
    print("\n" + "=" * 90)
    print("MODEL 2: EUVOX (6-lig)")
    print("=" * 90)
    euvox = EuvoxModel()
    e_results, e_pnl, e_n, e_won = week_by_week(df, euvox, "EUVOX")

    # Karşılaştırma
    print("\n" + "=" * 90)
    print("KARSILASTIRMA — 2526 Sezonu Performans")
    print("=" * 90)
    print(f"  TRIVOX: n={t_n:>3} kupon, {t_won} tutmuş ({t_won/max(t_n,1)*100:.0f}%), "
          f"PnL: {t_pnl:+,.0f} TL")
    print(f"  EUVOX:  n={e_n:>3} kupon, {e_won} tutmuş ({e_won/max(e_n,1)*100:.0f}%), "
          f"PnL: {e_pnl:+,.0f} TL")

    # Save
    LOGS_DIR.mkdir(exist_ok=True)
    pd.DataFrame(t_results).to_csv(LOGS_DIR / "dd_trivox_2526.csv", index=False)
    pd.DataFrame(e_results).to_csv(LOGS_DIR / "dd_euvox_2526.csv", index=False)

    write_report(t_results, t_pnl, t_n, t_won, e_results, e_pnl, e_n, e_won)


def write_report(t_results, t_pnl, t_n, t_won, e_results, e_pnl, e_n, e_won):
    RAPOR_DIR.mkdir(exist_ok=True)
    p = RAPOR_DIR / "DD_live_prediction_2526.md"

    t_rows = []
    for r in t_results:
        status = "TUTTU" if r["won"] else "❌"
        t_rows.append(
            f"| {r['matchday'].strftime('%Y-%m-%d')} | T1 | "
            f"K={r['K']} | {r['combo_odd']:.2f} | {status} | "
            f"{r['pnl']:+,.0f} | {r['cumulative']:+,.0f} |"
        )

    e_rows = []
    for r in e_results:
        status = "TUTTU" if r["won"] else "❌"
        e_rows.append(
            f"| {r['matchday'].strftime('%Y-%m-%d')} | {r['league']} | "
            f"K={r['K']} | {r['combo_odd']:.2f} | {status} | "
            f"{r['pnl']:+,.0f} | {r['cumulative']:+,.0f} |"
        )

    t_hit = t_won / max(t_n, 1) * 100
    t_roi = t_pnl / max(t_n * 1000, 1) * 100
    e_hit = e_won / max(e_n, 1) * 100
    e_roi = e_pnl / max(e_n * 1000, 1) * 100

    md = f"""# DD — Live 2025-26 Sezon Hafta-Hafta Prediction Test

**Tarih:** {datetime.now().isoformat()[:19]}
**Soru:** Acquirer "bu yıl maçları aldın, hafta-hafta tahmin?"
**Cevap:** 2526 sezonu mevcut + devam eden = gerçek out-of-sample test

---

## TRIVOX 2526 (T1-only)

| Matchday | Lig | K | Combo Odd | Sonuç | PnL | Kümülatif |
|---|:---:|:---:|---:|:---:|---:|---:|
{chr(10).join(t_rows) if t_rows else "**(0 kupon, sample yetersiz)**"}

**TOPLAM TRIVOX 2526:** n={t_n}, hit={t_won}/{t_n} ({t_hit:.0f}%), PnL={t_pnl:+,.0f}, ROI={t_roi:+.1f}%

---

## EUVOX 2526 (6-lig)

| Matchday | Lig | K | Combo Odd | Sonuç | PnL | Kümülatif |
|---|:---:|:---:|---:|:---:|---:|---:|
{chr(10).join(e_rows) if e_rows else "**(0 kupon)**"}

**TOPLAM EUVOX 2526:** n={e_n}, hit={e_won}/{e_n} ({e_hit:.0f}%), PnL={e_pnl:+,.0f}, ROI={e_roi:+.1f}%

---

## KARŞILAŞTIRMA Tablosu

| Model | n kupon | Hit | Hit% | PnL | ROI |
|---|---:|---:|---:|---:|---:|
| TRIVOX | {t_n} | {t_won} | {t_hit:.0f}% | {t_pnl:+,.0f} | {t_roi:+.1f}% |
| EUVOX | {e_n} | {e_won} | {e_hit:.0f}% | {e_pnl:+,.0f} | {e_roi:+.1f}% |

---

## YORUM (Acquirer perspektifi)

### Bu test ne kanıtlar?

Modellerin **bilmediği** sezonda (2526 devam eden) performansını gösterir.

### Sınırlamalar

1. Sezon ortası — sample {max(t_n, e_n)} kupon (full sezon yarısına denk)
2. Closing odds bazı maçlarda eksik
3. Live shadow run değil — sonradan analizmiş gibi

### Acquirer sorusu cevapları

- **"Edge canlı sezonda devam ediyor mu?"** → Tabloya bak.
- **"Tutarlılık?"** → Hafta-hafta dağılım dosyada.
- **"Bu hafta öneri?"** → Son matchday'in pick'leri yukarıda.

Detay CSV: `07_LOG_VE_RAPORLAR/dd_trivox_2526.csv`, `dd_euvox_2526.csv`
"""
    p.write_text(md, encoding="utf-8")
    print(f"\nRapor: {p}")


if __name__ == "__main__":
    run()
