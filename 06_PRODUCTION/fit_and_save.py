"""
fit_and_save.py — En güncel veriyle Dixon-Coles + Platt kalibrasyonu fit eder,
parametreleri JSON olarak diske kaydeder.

Kullanım:
    python fit_and_save.py

Çıktı:
    06_PRODUCTION/models/dc_params_<league>.json
    06_PRODUCTION/models/platt_params_<league>.json
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
YAZILIM_DIR = THIS_DIR.parent
sys.path.insert(0, str(YAZILIM_DIR / "03_MODELLER"))

from base.dixon_coles import fit_dixon_coles  # noqa: E402
from base.markets import prob_over_under, prob_btts  # noqa: E402
from calibration.platt_scaling import fit_platt  # noqa: E402

MODELS_DIR = THIS_DIR / "models"
MODELS_DIR.mkdir(exist_ok=True, parents=True)

MATCHES_PATH = YAZILIM_DIR / "02_VERI" / "processed" / "matches.csv"


LEAGUE_NAMES = {
    "T1": "Türkiye Süper Lig",
    "E0": "Premier League",
    "D1": "Bundesliga",
}


def fit_for_league(df: pd.DataFrame, league: str) -> None:
    sub = df[df["league"] == league].sort_values("match_date").reset_index(drop=True)
    if len(sub) < 200:
        print(f"  [{league}] yetersiz veri ({len(sub)} mac), atlandi")
        return

    print(f"\n[{league}] {LEAGUE_NAMES.get(league, league)}")
    print(f"  Veri      : {len(sub)} mac ({sub.match_date.min().date()} -> {sub.match_date.max().date()})")

    # Dixon-Coles fit
    print("  Dixon-Coles fit ediliyor...")
    params = fit_dixon_coles(
        home_teams=sub["home_team"].tolist(),
        away_teams=sub["away_team"].tolist(),
        home_goals_arr=sub["home_goals"].astype(int).tolist(),
        away_goals_arr=sub["away_goals"].astype(int).tolist(),
        match_dates=sub["match_date"].dt.to_pydatetime().tolist(),
        xi=0.0019,
        verbose=False,
    )

    # Platt kalibrasyonu için Over 2.5 üzerinden p_raw vs actual topla
    # Son 800 maçı holdout, ondan önce her bir maç için model fit ile yapılırdı
    # Basitleştirilmiş: mevcut tam-fit modelle son 600 maçın "in-sample" tahminlerini al
    # (gerçek production'da rolling fit olmalı, ama MVP için yeterli)
    print("  Platt kalibrasyon hazirlaniyor (Over 2.5 uzerinden)...")
    calib_set = sub.tail(600).copy()
    p_raws = []
    actuals = []
    for _, r in calib_set.iterrows():
        try:
            M = params.score_matrix_for(r["home_team"], r["away_team"], max_goals=10)
            p_over = prob_over_under(M, 2.5)["over"]
            actual_over = int((r["home_goals"] + r["away_goals"]) > 2.5)
            p_raws.append(p_over)
            actuals.append(actual_over)
        except Exception:
            continue
    p_raws = np.array(p_raws)
    actuals = np.array(actuals)

    platt = fit_platt(p_raws, actuals)
    print(f"  Platt fit : a={platt.a:.4f}, b={platt.b:.4f}, n={platt.n_train_samples}")

    # DC params serialize
    dc_dict = {
        "league": league,
        "league_name": LEAGUE_NAMES.get(league, league),
        "trained_at": datetime.now().isoformat(),
        "reference_date": sub["match_date"].max().isoformat(),
        "n_matches": len(sub),
        "teams": params.teams,
        "attack": params.attack,
        "defence": params.defence,
        "home_adv": params.home_adv,
        "rho": params.rho,
        "xi": params.xi,
    }
    dc_path = MODELS_DIR / f"dc_params_{league}.json"
    dc_path.write_text(json.dumps(dc_dict, indent=2, ensure_ascii=False), encoding="utf-8")

    platt_dict = {
        "league": league,
        "a": platt.a,
        "b": platt.b,
        "n_train_samples": platt.n_train_samples,
    }
    platt_path = MODELS_DIR / f"platt_params_{league}.json"
    platt_path.write_text(json.dumps(platt_dict, indent=2, ensure_ascii=False), encoding="utf-8")

    # En guclu 5 takim (attack - defence)
    print("  En guclu 5 takim (net guc):")
    strength = {t: params.attack.get(t, 0) - params.defence.get(t, 0) for t in params.teams}
    for t, s in sorted(strength.items(), key=lambda x: -x[1])[:5]:
        print(f"    {t:25s}  attack={params.attack[t]:+.3f}  defence={params.defence[t]:+.3f}  net={s:+.3f}")

    print(f"  Kaydedildi: {dc_path.name}, {platt_path.name}")


def main() -> None:
    print("=" * 70)
    print("BAHIS AGENT - Model Egitimi ve Kaydi")
    print("=" * 70)
    print(f"Calismakta olan tarih: {datetime.now().date()}")

    df = pd.read_csv(MATCHES_PATH, parse_dates=["match_date"])
    print(f"Toplam veri: {len(df):,} mac, {df.league.nunique()} lig")

    for lg in sorted(df["league"].unique()):
        fit_for_league(df, lg)

    print("\nTamamlandi.")
    print(f"Modeller: {MODELS_DIR}")


if __name__ == "__main__":
    main()
