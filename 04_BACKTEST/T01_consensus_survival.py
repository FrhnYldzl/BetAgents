"""
TEST T01 — Haftalık Konsensüs Survival
======================================

ODAK: "3 bağımsız ses aynı şeyi söylediğinde, bu duyulması gereken sestir."

HİPOTEZ:
    Her hafta için: en az 3 sinyal mevcut + en az 2'si aynı yönü gösteren
    maçlardan en yüksek score'lu PICK et.
    Bu strateji HER HAFTA pozitif olur mu?

BAŞARI ÖLÇÜTÜ:
    Positive Weeks Ratio (PWR) = (kazanç eden hafta sayısı) / (toplam hafta)
    Hedef: PWR > %50

VERİ:
    signal_snapshots tablosu (4188 maç, 4 sezon × 3 lig)

ÇIKTI:
    - RAPOR/T01_consensus_survival.md (bilimsel rapor)
    - 07_LOG_VE_RAPORLAR/T01_picks.csv (haftalık picks)
"""
from __future__ import annotations

import sqlite3
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
YAZILIM = THIS_DIR.parent
RAPOR_DIR = YAZILIM / "RAPOR"
LOGS_DIR = YAZILIM / "07_LOG_VE_RAPORLAR"
DB_PATH = YAZILIM / "02_VERI" / "bahis_agent.db"


def load_snapshots() -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        "SELECT * FROM signal_snapshots WHERE source='football_data'", conn
    )
    conn.close()
    return df


def compute_pnl(row, direction: str) -> float | None:
    """Verilen direction için bu maçın PnL'i (1 birim stake)."""
    if not row.get("settled"):
        return None
    odd = None
    won = False
    ftr = row.get("result_1x2")
    tg = row.get("total_goals")
    if direction in ("HOME", "H", "1"):
        odd = row.get("odd_1"); won = ftr == "H"
    elif direction in ("AWAY", "A", "2"):
        odd = row.get("odd_2"); won = ftr == "A"
    elif direction in ("DRAW", "D", "X"):
        odd = row.get("odd_X"); won = ftr == "D"
    elif direction == "Over":
        odd = row.get("odd_over25"); won = tg is not None and tg > 2.5
    elif direction == "Under":
        odd = row.get("odd_under25"); won = tg is not None and tg < 2.5
    if not odd or odd < 1.01:
        return None
    return (odd - 1) if won else -1


def run_t01() -> dict:
    print("=" * 80)
    print("T01 — HAFTALIK KONSENSÜS SURVIVAL")
    print("=" * 80)

    df = load_snapshots()
    df["matchday"] = pd.to_datetime(df["kickoff_iso"]).dt.normalize()

    # Filter: en az 3 sinyal + ≥2 agree
    candidates = df[
        (df["signal_count"] >= 3) &
        (df["agree_count"] >= 2) &
        (df["dir_consensus"].notna()) &
        (df["settled"] == 1)
    ].copy()

    print(f"Toplam settled mac: {(df['settled']==1).sum()}")
    print(f"Konsensüs adayı (sig>=3, agree>=2): {len(candidates)}")

    # Her matchday için en yüksek score'lu maçı pick
    candidates = candidates.sort_values("score_v13", ascending=False)
    weekly_picks = candidates.groupby("matchday").first().reset_index()
    print(f"Haftalık pick sayısı: {len(weekly_picks)}")

    # PnL hesabı
    weekly_picks["pnl"] = weekly_picks.apply(
        lambda r: compute_pnl(r, r["dir_consensus"]), axis=1
    )
    valid = weekly_picks[weekly_picks["pnl"].notna()].copy()
    print(f"Geçerli (odd+sonuç) pick: {len(valid)}")

    if len(valid) == 0:
        return {"n": 0, "error": "valid picks=0"}

    # METRIKLER
    n = len(valid)
    n_won = (valid["pnl"] > 0).sum()
    n_pos = (valid["pnl"] > 0).sum()  # pozitif hafta = kazanan pick olan hafta
    pwr = n_pos / n  # Positive Weeks Ratio
    total_pnl = valid["pnl"].sum()
    roi = total_pnl / n
    hit_rate = n_won / n

    # Bootstrap CI
    rng = np.random.RandomState(42)
    boot = [rng.choice(valid["pnl"].values, size=n, replace=True).mean()
            for _ in range(2000)]
    ci_low, ci_high = float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))

    # Per-season breakdown
    valid["season"] = valid["season"].astype(str)
    season_stats = []
    for season, sub in valid.groupby("season"):
        sn = len(sub); shit = (sub["pnl"] > 0).sum()
        season_stats.append({
            "season": season, "n": sn, "wins": int(shit),
            "hit_rate": shit / sn, "roi": sub["pnl"].mean(),
            "pwr": shit / sn,
        })

    # Per-league breakdown
    league_stats = []
    for lg, sub in valid.groupby("league_code"):
        sn = len(sub); shit = (sub["pnl"] > 0).sum()
        league_stats.append({
            "league": lg, "n": sn, "wins": int(shit),
            "hit_rate": shit / sn, "roi": sub["pnl"].mean(),
        })

    # Avg odd
    valid["odd_used"] = valid.apply(
        lambda r: (r.get("odd_1") if r["dir_consensus"] in ("HOME","H","1")
                   else r.get("odd_2") if r["dir_consensus"] in ("AWAY","A","2")
                   else r.get("odd_X") if r["dir_consensus"] in ("DRAW","D","X")
                   else r.get("odd_over25") if r["dir_consensus"] == "Over"
                   else r.get("odd_under25") if r["dir_consensus"] == "Under"
                   else None),
        axis=1
    )
    avg_odd = valid["odd_used"].mean()

    # Picks CSV
    LOGS_DIR.mkdir(exist_ok=True)
    valid_export = valid[["matchday","league_code","season","home_team","away_team",
                          "score_v13","agree_count","signal_count","dir_consensus",
                          "odd_used","result_1x2","pnl"]]
    csv_path = LOGS_DIR / "T01_picks.csv"
    valid_export.to_csv(csv_path, index=False)
    print(f"Picks CSV: {csv_path.name}")

    result = {
        "n": int(n),
        "n_wins": int(n_won),
        "hit_rate": float(hit_rate),
        "roi": float(roi),
        "pwr": float(pwr),
        "ci_low": ci_low,
        "ci_high": ci_high,
        "avg_odd": float(avg_odd),
        "total_pnl": float(total_pnl),
        "season_stats": season_stats,
        "league_stats": league_stats,
        "edge_positive": ci_low > 0,
    }
    return result


def write_report(r: dict):
    """Kısa bilimsel rapor."""
    RAPOR_DIR.mkdir(exist_ok=True)
    p = RAPOR_DIR / "T01_consensus_survival.md"
    edge_verdict = "✅ POZİTİF EDGE" if r.get("edge_positive") else "⚠️ BELİRSİZ"
    season_lines = "\n".join([
        f"| {s['season']} | {s['n']} | {s['hit_rate']*100:.0f}% | {s['roi']*100:+.2f}% |"
        for s in r.get("season_stats", [])
    ])
    league_lines = "\n".join([
        f"| {l['league']} | {l['n']} | {l['hit_rate']*100:.0f}% | {l['roi']*100:+.2f}% |"
        for l in r.get("league_stats", [])
    ])
    md = f"""# T01 — Haftalık Konsensüs Survival

**Versiyon:** v1.0
**Tarih:** {datetime.now().isoformat()[:19]}
**Veri:** 4 sezon × 3 lig × signal_snapshots tablosundan

---

## Hipotez

Her hafta için: en az 3 sinyal mevcut + en az 2'si aynı yön konsensüsü oluşturmuş maçlardan **en yüksek score'lu olanı** pick et.

Başarı ölçütü: **Positive Weeks Ratio (PWR)** > %50.

---

## Sonuçlar

| Metrik | Değer |
|---|---|
| Toplam hafta pick | **{r['n']}** |
| Kazanan pick | {r['n_wins']} |
| Hit rate | **{r['hit_rate']*100:.1f}%** |
| ROI (per pick) | **{r['roi']*100:+.2f}%** |
| **PWR (positive weeks)** | **{r['pwr']*100:.1f}%** |
| Avg odd | {r['avg_odd']:.2f} |
| Bootstrap CI95 | [{r['ci_low']*100:+.1f}%, {r['ci_high']*100:+.1f}%] |
| Toplam PnL (1 birim/hafta) | {r['total_pnl']:+.2f} |
| Verdikt | **{edge_verdict}** |

## Per-Sezon

| Sezon | n | Hit% | ROI |
|---|---:|---:|---:|
{season_lines}

## Per-Lig

| Lig | n | Hit% | ROI |
|---|---:|---:|---:|
{league_lines}

---

## Yorum

- **PWR {r['pwr']*100:.0f}%** → {'%50 üstü, başarılı' if r['pwr'] > 0.5 else '%50 altı, hedefe ulaşılmadı'}
- **CI95 [{r['ci_low']*100:+.1f}%, {r['ci_high']*100:+.1f}%]** → {'sıfır üstü = gerçek edge' if r['ci_low'] > 0 else 'sıfırı içeriyor = belirsiz'}

**Picks CSV:** `07_LOG_VE_RAPORLAR/T01_picks.csv`
"""
    p.write_text(md, encoding="utf-8")
    print(f"\nRapor: {p}")


if __name__ == "__main__":
    r = run_t01()
    print("\n=== T01 SONUÇ ===")
    for k, v in r.items():
        if k not in ("season_stats", "league_stats"):
            print(f"  {k}: {v}")
    write_report(r)
