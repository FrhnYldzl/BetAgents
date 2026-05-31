"""
EUVOX FAZ II — DC Eğitim (SP1, I1, F1)
========================================

Football-Data CSV'lerini kullanarak SP1, I1, F1 için DC modeli eğit ve
06_PRODUCTION/models/dc_params_{LG}.json olarak kaydet.

Eğitim verisi: 2021-22 + 2022-23 (out-of-sample 2324, 2425, 2526 için).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
YAZILIM = THIS_DIR.parent.parent
MODELS_DIR = YAZILIM / "06_PRODUCTION" / "models"
RAW_DIR = YAZILIM / "02_VERI" / "raw"

sys.path.insert(0, str(YAZILIM / "03_MODELLER"))
from base.dixon_coles import fit_dixon_coles


TRAIN_SEASONS = ["2122", "2223"]  # train
LEAGUES = ["SP1", "I1", "F1"]


def train_one(league: str) -> dict:
    """Bir lig için DC fit + JSON kaydet."""
    print(f"\n[{league}] eğitim başlıyor...")
    dfs = []
    for ss in TRAIN_SEASONS:
        fn = RAW_DIR / f"{league}_{ss}.csv"
        if not fn.exists():
            continue
        df = pd.read_csv(fn, encoding="latin-1")
        df["Date"] = pd.to_datetime(df["Date"], format="%d/%m/%Y", errors="coerce")
        df = df.dropna(subset=["Date", "FTHG", "FTAG", "HomeTeam", "AwayTeam"])
        dfs.append(df)
    if not dfs:
        return {"league": league, "error": "no_data"}
    full = pd.concat(dfs, ignore_index=True).sort_values("Date").reset_index(drop=True)
    print(f"  {len(full)} maç (2 sezon)")

    # DC fit
    params = fit_dixon_coles(
        home_teams=full["HomeTeam"].tolist(),
        away_teams=full["AwayTeam"].tolist(),
        home_goals_arr=full["FTHG"].astype(int).tolist(),
        away_goals_arr=full["FTAG"].astype(int).tolist(),
        match_dates=full["Date"].tolist(),
        xi=0.0019,
        verbose=False,
    )

    # JSON kaydet
    out = MODELS_DIR / f"dc_params_{league}.json"
    out.write_text(json.dumps({
        "teams": params.teams,
        "attack": params.attack,
        "defence": params.defence,
        "home_adv": params.home_adv,
        "rho": params.rho,
        "xi": params.xi,
    }), encoding="utf-8")
    print(f"  {len(params.teams)} takim, rho={params.rho:.3f}, home_adv={params.home_adv:.3f}")
    print(f"  Kaydedildi: {out}")
    return {
        "league": league, "n_matches": len(full),
        "n_teams": len(params.teams),
        "rho": params.rho, "home_adv": params.home_adv,
    }


def run():
    print("=" * 80)
    print("EUVOX FAZ II — DC Eğitim (SP1, I1, F1)")
    print("=" * 80)

    results = []
    for lg in LEAGUES:
        r = train_one(lg)
        results.append(r)

    print("\n=== ÖZET ===")
    for r in results:
        if "error" in r:
            print(f"  {r['league']}: HATA {r['error']}")
        else:
            print(f"  {r['league']}: {r['n_matches']} maç, {r['n_teams']} takım, "
                  f"home_adv={r['home_adv']:.2f}")

    print("\n[OK] 3 yeni DC modeli üretildi. signal_snapshots'ı şimdi yeniden hesapla.")


if __name__ == "__main__":
    run()
