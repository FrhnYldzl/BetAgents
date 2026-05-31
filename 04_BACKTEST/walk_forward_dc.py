"""
SELECTIVE EDGE v1.4 — Walk-Forward DC Training

Sorun:
    Mevcut DC modelleri (dc_params_T1, _E0, _D1.json) sabit, 2023-24 sezonuna
    eğitildi. Backtest aynı sezonda → in-sample bias. 2022-23 → DC görmedi
    ama 2021-22'de görmedi → OK.

Çözüm:
    Walk-forward: her matchday için sadece o tarihten ÖNCE oynanmış maçları
    kullanarak DC fit et. Bunu önceden hesapla, signal_snapshots'a DC tahminlerini
    yaz.

Performans:
    Her matchday için fit ~5-10 saniye. 350 matchday × 3 lig × 4 sezon = ~4200 fit.
    Toplam ~10-15 saat. Sınırlama: her hafta sadece bir fit kullanılacak (rolling).

Optimizasyon:
    - Önce her LIG için MATCHDAY'leri grupla
    - Her matchday için "tüm prior maçlar" → DC fit → tüm o gün maçları için tahmin
    - Tahmin ve params cache'le

Bu modül offline çalıştırılır, signal_snapshots'a sonuç yazar.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
YAZILIM = THIS_DIR.parent
sys.path.insert(0, str(YAZILIM / "03_MODELLER"))
sys.path.insert(0, str(YAZILIM / "03_MODELLER" / "selective"))
sys.path.insert(0, str(YAZILIM / "02_VERI"))

from base.dixon_coles import DCParams, fit_dixon_coles, score_matrix
from base.markets import prob_1x2, prob_over_under
from selective_backtest import load_week


LEAGUES = ["E0", "D1", "T1"]
SEASONS = ["2122", "2223", "2324", "2425"]


def build_match_history(league: str) -> pd.DataFrame:
    """Tüm sezonları birleştir, kronolojik sıra."""
    dfs = []
    for ss in SEASONS:
        try:
            df = load_week(league, ss)
            df["season"] = ss
            dfs.append(df)
        except FileNotFoundError:
            continue
    if not dfs:
        return pd.DataFrame()
    combined = pd.concat(dfs, ignore_index=True)
    combined = combined.dropna(subset=["FTHG", "FTAG"])
    combined = combined.sort_values("Date").reset_index(drop=True)
    return combined


def walk_forward_fit_one(history_so_far: pd.DataFrame,
                         xi: float = 0.0019) -> DCParams | None:
    """Bir noktadaki tüm prior maçlardan DC fit."""
    if len(history_so_far) < 30:
        return None
    try:
        params = fit_dixon_coles(
            home_teams=history_so_far["HomeTeam"].tolist(),
            away_teams=history_so_far["AwayTeam"].tolist(),
            home_goals_arr=history_so_far["FTHG"].astype(int).tolist(),
            away_goals_arr=history_so_far["FTAG"].astype(int).tolist(),
            match_dates=history_so_far["Date"].tolist(),
            xi=xi,
            verbose=False,
        )
        return params
    except Exception as e:
        print(f"  fit ERR: {e}")
        return None


def run_league_walk_forward(league: str, min_history_days: int = 60,
                            refit_every: int = 7) -> pd.DataFrame:
    """
    Tüm maçlar için walk-forward DC tahminleri.
    refit_every: her N gün bir kez fit et (perf optimizasyonu).
    """
    history = build_match_history(league)
    if history.empty:
        print(f"[{league}] history boş")
        return pd.DataFrame()
    print(f"[{league}] toplam {len(history)} maç, kronoloji {history['Date'].min().date()} - {history['Date'].max().date()}")

    results = []
    last_fit_date = None
    cached_params = None
    n_fits = 0

    for i, match in history.iterrows():
        match_date = match["Date"]
        # min_history_days yeterli mi?
        days_in_history = (match_date - history["Date"].min()).days
        if days_in_history < min_history_days:
            continue

        # Refit gerekli mi?
        need_refit = (
            cached_params is None or
            last_fit_date is None or
            (match_date - last_fit_date).days >= refit_every
        )
        if need_refit:
            prior = history.iloc[:i]
            cached_params = walk_forward_fit_one(prior)
            last_fit_date = match_date
            n_fits += 1
            if n_fits % 10 == 0:
                print(f"  [{n_fits} fits, match #{i}/{len(history)}]")

        if cached_params is None:
            continue

        # Bu maç için tahmin
        h = match["HomeTeam"]; a = match["AwayTeam"]
        if h not in cached_params.teams or a not in cached_params.teams:
            continue
        try:
            lam, mu = cached_params.expected_goals(h, a)
            M = score_matrix(lam, mu, cached_params.rho, max_goals=10)
            p1x2 = prob_1x2(M)
            ou25 = prob_over_under(M, 2.5)
            results.append({
                "league": league,
                "season": match["season"],
                "date": match_date.strftime("%Y-%m-%d"),
                "home": h,
                "away": a,
                "wf_p_1": p1x2["1"],
                "wf_p_X": p1x2["X"],
                "wf_p_2": p1x2["2"],
                "wf_p_over25": ou25["over"],
                "wf_p_under25": ou25["under"],
                "wf_lam_h": lam,
                "wf_lam_a": mu,
                "ftr": match["FTR"],
                "fthg": match["FTHG"],
                "ftag": match["FTAG"],
            })
        except Exception as e:
            continue

    print(f"  Toplam {n_fits} fit, {len(results)} tahmin")
    return pd.DataFrame(results)


def evaluate(df_pred: pd.DataFrame, strategy: str = "model_dir") -> dict:
    """Walk-forward tahminlerle ROI hesabı (Pinnacle closing'e gir)."""
    pnls = []
    # Need closing odds — load from Football-Data
    from selective_backtest import load_week
    odds_cache = {}
    for season in df_pred["season"].unique():
        for lg in df_pred["league"].unique():
            try:
                wkdf = load_week(lg, season)
                for _, r in wkdf.iterrows():
                    key = (lg, str(r["Date"])[:10], r["HomeTeam"], r["AwayTeam"])
                    odds_cache[key] = r
            except FileNotFoundError:
                continue

    for _, r in df_pred.iterrows():
        key = (r["league"], r["date"], r["home"], r["away"])
        oc = odds_cache.get(key)
        if oc is None:
            continue
        # Pick: en yüksek WF prob
        probs = {"H": r["wf_p_1"], "D": r["wf_p_X"], "A": r["wf_p_2"]}
        best_dir = max(probs, key=probs.get)
        # Bu yön için Pinnacle closing
        if best_dir == "H": odd = oc.get("PSCH")
        elif best_dir == "A": odd = oc.get("PSCA")
        else: odd = oc.get("PSCD")
        if not odd or odd < 1.01:
            continue
        # Sonuç
        won = r["ftr"] == best_dir
        pnls.append((odd - 1) if won else -1)

    if not pnls:
        return {"n": 0}
    n = len(pnls)
    roi = sum(pnls) / n
    return {
        "n": n,
        "hit_rate": sum(1 for p in pnls if p > 0) / n,
        "roi": roi,
    }


def run():
    print("=" * 100)
    print("WALK-FORWARD DC — leak-free DC tahminleri")
    print("=" * 100)
    all_preds = []
    for lg in LEAGUES:
        df = run_league_walk_forward(lg)
        all_preds.append(df)
    combined = pd.concat(all_preds, ignore_index=True)

    print(f"\nToplam tahmin: {len(combined)}")
    # Persistence — CSV
    out = YAZILIM / "07_LOG_VE_RAPORLAR" / "walk_forward_dc_preds.csv"
    combined.to_csv(out, index=False)
    print(f"Kaydedildi: {out.name}")

    # Eval
    ev = evaluate(combined)
    print(f"\nWalk-forward model_dir ROI: {ev.get('roi',0)*100:+.2f}%  hit={ev.get('hit_rate',0)*100:.0f}%  n={ev.get('n',0)}")


if __name__ == "__main__":
    run()
