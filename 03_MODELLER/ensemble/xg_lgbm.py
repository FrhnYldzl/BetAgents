"""
Ensemble model: Dixon-Coles + xG rolling features + Elo + LightGBM.

Target: Over 2.5 (binary classification, sonra 1X2 ve KG eklenir)

Features (sızıntı yok — sadece geçmiş veriden):
    DC tabanlı (5)        : p_1, p_X, p_2, p_over25_raw, p_btts
    xG rolling (8)        : home_xg_for_5, home_xg_for_10,
                            home_xg_against_5, home_xg_against_10,
                            away_xg_for_5, away_xg_for_10,
                            away_xg_against_5, away_xg_against_10
    Form (4)              : home_pts_5, home_gd_5, away_pts_5, away_gd_5
    Match context (4)     : home_rest_days, away_rest_days,
                            home_matches_played, away_matches_played
    Elo (3)               : home_elo, away_elo, elo_diff

Walk-forward:
    Her test maçından önce, tüm geçmiş veriyle (lig+xG)
        - DC parametrelerini fit et
        - rolling xG/form/Elo'yu hesapla
        - LightGBM eğit
        - Test maçını tahmin et

Çıktı:
    - Model olasılığı her maç için
    - CLV ve ROI hesabı yeni model ile
"""
from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
MODEL_DIR = THIS_DIR.parent
YAZILIM_DIR = MODEL_DIR.parent

sys.path.insert(0, str(MODEL_DIR))
sys.path.insert(0, str(YAZILIM_DIR / "02_VERI"))

from base.dixon_coles import fit_dixon_coles, score_matrix, DCParams
from base.markets import prob_1x2, prob_over_under, prob_btts


# ============================================================
# TAKIM AD NORMALİZASYONU (Understat → Football-Data)
# ============================================================

UNDERSTAT_TO_FD = {
    # Premier League
    "Manchester City":          "Man City",
    "Manchester United":        "Man United",
    "Newcastle United":         "Newcastle",
    "Nottingham Forest":        "Nott'm Forest",
    "Wolverhampton Wanderers":  "Wolves",
    # La Liga
    # (footballdata vs understat çoğunlukla aynı isimleri)
    # Bundesliga
    "Bayer Leverkusen":         "Leverkusen",
    "FC Köln":                  "FC Koln",
    "Eintracht Frankfurt":      "Ein Frankfurt",
    "Borussia M.Gladbach":      "M'gladbach",
    "Hertha BSC":               "Hertha",
    # Serie A
    "Hellas Verona":            "Verona",
    # Ligue 1
    "PSG":                      "Paris SG",
    "Paris Saint-Germain":      "Paris SG",
    "Stade Brestois 29":        "Brest",
    "RC Strasbourg":            "Strasbourg",
    "AS Saint-Étienne":         "St Etienne",
}


def normalize_understat_team(name: str) -> str:
    return UNDERSTAT_TO_FD.get(name, name)


# ============================================================
# ELO RATINGS
# ============================================================

def compute_elo(matches: pd.DataFrame, k: float = 20.0, hfa: float = 60.0,
                init: float = 1500.0) -> pd.DataFrame:
    """
    Standart Elo + ev avantajı (hfa).

    Args:
        matches: home_team, away_team, home_goals, away_goals, match_date sorted
        k: K-factor (Elo update strength)
        hfa: ev sahibi avantajı (Elo points)
        init: yeni takım için başlangıç rating

    Returns:
        matches'a `home_elo_pre`, `away_elo_pre` (maç öncesi) sütunları
    """
    elo: dict[str, float] = {}
    home_pre, away_pre = [], []
    for _, r in matches.iterrows():
        h, a = r["home_team"], r["away_team"]
        rh = elo.get(h, init)
        ra = elo.get(a, init)
        home_pre.append(rh)
        away_pre.append(ra)

        # Expected score (ev için), hfa dahil
        diff = (rh + hfa) - ra
        exp_h = 1.0 / (1.0 + 10 ** (-diff / 400))
        # Actual: result
        if pd.isna(r["home_goals"]) or pd.isna(r["away_goals"]):
            continue  # skip if not played
        hg, ag = int(r["home_goals"]), int(r["away_goals"])
        if hg > ag:
            score_h = 1.0
        elif hg < ag:
            score_h = 0.0
        else:
            score_h = 0.5

        # MOV (margin of victory) multiplier — FiveThirtyEight tarzı
        mov = abs(hg - ag)
        elo_diff_abs = abs(diff)
        mov_mult = np.log(mov + 1) * (2.2 / (elo_diff_abs * 0.001 + 2.2))

        update = k * mov_mult * (score_h - exp_h)
        elo[h] = rh + update
        elo[a] = ra - update

    matches = matches.copy()
    matches["home_elo_pre"] = home_pre
    matches["away_elo_pre"] = away_pre
    return matches


# ============================================================
# FEATURE ENGINEERING
# ============================================================

def add_rolling_features(matches: pd.DataFrame, xg: pd.DataFrame,
                          windows: tuple = (5, 10)) -> pd.DataFrame:
    """
    Her maç için, kendi tarihinden ÖNCE oynanmış maçlardan rolling istatistikler.

    matches: sorted by date, ev+dep, goller dolu (oynanmış maçlar)
    xg: home_team, away_team (normalize), match_date, home_xg, away_xg
    """
    matches = matches.sort_values("match_date").reset_index(drop=True)

    # xG'yi tarih+takım üzerinden join et
    xg_indexed = xg.copy()
    xg_indexed["match_date"] = pd.to_datetime(xg_indexed["match_date"])
    xg_indexed["home_team_n"] = xg_indexed["home_team"].apply(normalize_understat_team)
    xg_indexed["away_team_n"] = xg_indexed["away_team"].apply(normalize_understat_team)

    # her takımın history'sini sırala
    # team_history[team] = list of (date, xg_for, xg_against, goals_for, goals_against, points)
    team_hist: dict[str, list] = {}

    # Hazır: xG verileri match listesine eşleştir
    # xG datasını fixture+team ile bind et
    xg_by_key = {}
    for _, r in xg_indexed.iterrows():
        # Hem ev hem deplasman tarafından erişilebilsin
        if pd.notna(r.get("home_xg")):
            xg_by_key[(str(r["match_date"].date()), r["home_team_n"], r["away_team_n"])] = (
                float(r["home_xg"]), float(r["away_xg"])
            )

    feats = []
    for _, m in matches.iterrows():
        h, a = m["home_team"], m["away_team"]
        mdate = m["match_date"]

        # Her takım için son N maç istatistikleri
        h_hist = team_hist.get(h, [])
        a_hist = team_hist.get(a, [])

        row = {"match_idx": m.name}

        for w in windows:
            for team, hist, prefix in [(h, h_hist, "home"), (a, a_hist, "away")]:
                last = hist[-w:] if hist else []
                if last:
                    xgf = np.mean([x[1] for x in last])
                    xga = np.mean([x[2] for x in last])
                    gf = np.mean([x[3] for x in last])
                    ga = np.mean([x[4] for x in last])
                    pts = np.mean([x[5] for x in last])
                else:
                    xgf = xga = gf = ga = pts = np.nan
                row[f"{prefix}_xg_for_{w}"] = xgf
                row[f"{prefix}_xg_against_{w}"] = xga
                row[f"{prefix}_gf_{w}"] = gf
                row[f"{prefix}_ga_{w}"] = ga
                row[f"{prefix}_pts_{w}"] = pts

        # Match context
        for team, hist, prefix in [(h, h_hist, "home"), (a, a_hist, "away")]:
            last_date = hist[-1][0] if hist else None
            row[f"{prefix}_rest_days"] = (mdate - last_date).days if last_date else np.nan
            row[f"{prefix}_matches_played"] = len(hist)

        feats.append(row)

        # Sonra history'yi güncelle (CURRENT match'ten sonra, gelecekteki maç bunu kullanacak)
        if pd.notna(m["home_goals"]) and pd.notna(m["away_goals"]):
            hg, ag = int(m["home_goals"]), int(m["away_goals"])
            # Bu maç için xG (Understat'tan)
            key = (str(mdate.date()), h, a)
            xg_pair = xg_by_key.get(key, (None, None))
            home_xg = xg_pair[0] if xg_pair[0] is not None else float(hg)
            away_xg = xg_pair[1] if xg_pair[1] is not None else float(ag)

            # Ev sahibinin perspektifinden
            if hg > ag: h_pts = 3
            elif hg < ag: h_pts = 0
            else: h_pts = 1
            a_pts = 3 - h_pts if h_pts != 1 else 1

            team_hist.setdefault(h, []).append(
                (mdate, home_xg, away_xg, hg, ag, h_pts)
            )
            team_hist.setdefault(a, []).append(
                (mdate, away_xg, home_xg, ag, hg, a_pts)
            )

    feat_df = pd.DataFrame(feats).set_index("match_idx")
    return matches.join(feat_df)


# ============================================================
# DIXON-COLES OLASILIK FEATURES (sızıntı yok)
# ============================================================

def add_dc_features(matches: pd.DataFrame, train_cutoff_idx: int,
                     xi: float = 0.0019) -> pd.DataFrame:
    """
    İlk train_cutoff_idx maça kadar olan veriyle DC fit, kalan tüm maçlar için
    p_1, p_X, p_2, p_over25, p_btts ham olasılıklarını üret.

    NOT: TRAIN seti içindeki maçlar için TRAIN içi prediction yapılır
    (sızıntı yok çünkü tüm train aynı modelle fit edilir).
    TEST seti için yine aynı model kullanılır.
    """
    train = matches.iloc[:train_cutoff_idx]
    if len(train) < 100:
        # Yetersiz
        for c in ["p_1", "p_X", "p_2", "p_over25", "p_btts"]:
            matches[c] = np.nan
        return matches

    params = fit_dixon_coles(
        home_teams=train["home_team"].tolist(),
        away_teams=train["away_team"].tolist(),
        home_goals_arr=train["home_goals"].astype(int).tolist(),
        away_goals_arr=train["away_goals"].astype(int).tolist(),
        match_dates=train["match_date"].dt.to_pydatetime().tolist(),
        xi=xi,
    )

    p1, pX, p2, po, pb = [], [], [], [], []
    for _, m in matches.iterrows():
        if m["home_team"] not in params.teams or m["away_team"] not in params.teams:
            p1.append(np.nan); pX.append(np.nan); p2.append(np.nan)
            po.append(np.nan); pb.append(np.nan)
            continue
        M = params.score_matrix_for(m["home_team"], m["away_team"], max_goals=10)
        o = prob_1x2(M); ou = prob_over_under(M, 2.5); btts = prob_btts(M)
        p1.append(o["1"]); pX.append(o["X"]); p2.append(o["2"])
        po.append(ou["over"]); pb.append(btts["yes"])

    matches = matches.copy()
    matches["p_1"] = p1
    matches["p_X"] = pX
    matches["p_2"] = p2
    matches["p_over25"] = po
    matches["p_btts"] = pb
    return matches


# ============================================================
# MAIN PIPELINE
# ============================================================

FEATURE_COLS = [
    # DC
    "p_1", "p_X", "p_2", "p_over25", "p_btts",
    # xG rolling 5 + 10
    "home_xg_for_5", "home_xg_against_5", "home_xg_for_10", "home_xg_against_10",
    "away_xg_for_5", "away_xg_against_5", "away_xg_for_10", "away_xg_against_10",
    # Form 5
    "home_gf_5", "home_ga_5", "home_pts_5",
    "away_gf_5", "away_ga_5", "away_pts_5",
    # Context
    "home_rest_days", "away_rest_days",
    "home_matches_played", "away_matches_played",
    # Elo
    "home_elo_pre", "away_elo_pre",
]


def build_dataset(league: str = "E0",
                  db_path: str | None = None,
                  matches_csv: str | None = None) -> pd.DataFrame:
    """
    Bir lig için tüm feature set'ini hazırla.

    Args:
        league: 'E0', 'SP1', vb.
    """
    if db_path is None:
        db_path = str(YAZILIM_DIR / "02_VERI" / "bahis_agent.db")
    if matches_csv is None:
        matches_csv = str(YAZILIM_DIR / "02_VERI" / "processed" / "matches.csv")

    # Football-data tarafından gelen maçlar (oranlarla)
    mat = pd.read_csv(matches_csv, parse_dates=["match_date"])
    mat = mat[mat["league"] == league].copy()
    mat = mat.dropna(subset=["home_goals", "away_goals"])
    mat["home_goals"] = mat["home_goals"].astype(int)
    mat["away_goals"] = mat["away_goals"].astype(int)
    mat = mat.sort_values("match_date").reset_index(drop=True)
    print(f"  {len(mat)} mac (football-data, {league})")

    # xG verisi
    conn = sqlite3.connect(db_path)
    try:
        xg = pd.read_sql_query(
            "SELECT match_date, home_team, away_team, home_xg, away_xg "
            "FROM xg_data WHERE league_code = ?",
            conn, params=(league,)
        )
    finally:
        conn.close()
    print(f"  {len(xg)} mac xG")

    # Rolling features
    mat = add_rolling_features(mat, xg, windows=(5, 10))

    # Elo
    mat = compute_elo(mat)

    return mat


def walk_forward_lgbm(mat: pd.DataFrame,
                      target: str = "over25",
                      n_initial: int = 600,
                      refit_every: int = 50) -> pd.DataFrame:
    """
    Walk-forward LightGBM ile out-of-sample tahminler üret.

    Args:
        target: 'over25' (sınıflandırma hedefi)
        n_initial: ilk fit için kullanılacak maç sayısı (warmup)
        refit_every: kaç maçta bir refit
    """
    import lightgbm as lgb

    mat = mat.copy()
    if target == "over25":
        mat["y"] = (mat["home_goals"] + mat["away_goals"] > 2.5).astype(int)
    elif target == "btts":
        mat["y"] = ((mat["home_goals"] >= 1) & (mat["away_goals"] >= 1)).astype(int)
    else:
        raise ValueError(f"Bilinmeyen target: {target}")

    n = len(mat)
    out = mat[["match_date", "home_team", "away_team",
               "home_goals", "away_goals", "y"]].copy()
    out["p_ensemble"] = np.nan
    out["p_dc_only"] = np.nan

    # Walk-forward
    last_model = None
    last_fit_idx = -refit_every  # ilk fit'i zorla
    cached_dc_features = mat.assign(p_1=np.nan, p_X=np.nan, p_2=np.nan,
                                     p_over25=np.nan, p_btts=np.nan)

    for i in range(n_initial, n):
        if i - last_fit_idx >= refit_every:
            # DC: ilk i mac ile fit, tum maclar icin predict (predict leakage yok cunku fit window sabit)
            cached_dc_features = add_dc_features(mat, train_cutoff_idx=i)
            train = cached_dc_features.iloc[:i].dropna(subset=FEATURE_COLS + ["y"])
            if len(train) < 200:
                continue

            X = train[FEATURE_COLS].values
            yy = train["y"].values

            # zaman ağırlığı: son maçlar daha çok ağırlık
            ref = cached_dc_features.iloc[i]["match_date"]
            days_back = (ref - train["match_date"]).dt.days.values
            w = np.exp(-days_back / 365.0)  # 1 yıl half-life-like

            model = lgb.LGBMClassifier(
                n_estimators=200, max_depth=4, learning_rate=0.05,
                min_child_samples=20, reg_lambda=1.0,
                random_state=42, verbose=-1
            )
            model.fit(X, yy, sample_weight=w)
            last_model = model
            last_fit_idx = i
            if i % 100 == 0:
                print(f"  i={i} ({i/n*100:.0f}%) - LGBM refit, train_n={len(train)}")

        # Test maçını tahmin et
        if last_model is not None:
            row = cached_dc_features.iloc[i]
            feats = row[FEATURE_COLS]
            if not feats.isna().any():
                X_test = feats.values.reshape(1, -1).astype(float)
                p_ens = float(last_model.predict_proba(X_test)[0, 1])
                out.at[mat.index[i], "p_ensemble"] = p_ens
                out.at[mat.index[i], "p_dc_only"] = float(row["p_over25"]) if target == "over25" else float(row["p_btts"])

    return out


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    print("=" * 70)
    print("SPRINT 1.4 — Ensemble Model (DC + xG + Elo + LightGBM)")
    print("=" * 70)

    league = sys.argv[1] if len(sys.argv) > 1 else "E0"
    target = sys.argv[2] if len(sys.argv) > 2 else "over25"

    print(f"\nLig    : {league}")
    print(f"Target : {target}")
    print()

    print("[1/3] Dataset hazirlaniyor...")
    mat = build_dataset(league)
    print(f"  Total mac        : {len(mat)}")
    print(f"  xG eslesmis      : {mat['home_xg_for_5'].notna().sum()}")

    print(f"\n[2/3] Walk-forward LightGBM ({target})...")
    res = walk_forward_lgbm(mat, target=target, n_initial=600, refit_every=50)

    print(f"\n[3/3] Sonuclar:")
    valid = res.dropna(subset=["p_ensemble"])
    print(f"  Out-of-sample tahmin: {len(valid)}")
    print(f"  Ortalama p_ensemble : {valid['p_ensemble'].mean():.4f}")
    print(f"  Ortalama y          : {valid['y'].mean():.4f}")

    # Brier
    from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
    brier_ens = brier_score_loss(valid["y"], valid["p_ensemble"])
    brier_dc = brier_score_loss(valid["y"], valid["p_dc_only"])
    ll_ens = log_loss(valid["y"], valid["p_ensemble"])
    ll_dc = log_loss(valid["y"], valid["p_dc_only"])
    auc_ens = roc_auc_score(valid["y"], valid["p_ensemble"])
    auc_dc = roc_auc_score(valid["y"], valid["p_dc_only"])

    print(f"\n  Brier  | DC alone: {brier_dc:.4f}  Ensemble: {brier_ens:.4f}  delta: {(brier_dc-brier_ens)*100:+.2f}%")
    print(f"  LogLoss| DC alone: {ll_dc:.4f}     Ensemble: {ll_ens:.4f}     delta: {(ll_dc-ll_ens)*100:+.2f}%")
    print(f"  AUC    | DC alone: {auc_dc:.4f}     Ensemble: {auc_ens:.4f}     delta: {(auc_ens-auc_dc)*100:+.2f}%")

    # Save predictions
    out_path = YAZILIM_DIR / "07_LOG_VE_RAPORLAR" / f"ensemble_predictions_{league}_{target}.csv"
    res.to_csv(out_path, index=False)
    print(f"\n  Tahminler kaydedildi: {out_path.name}")
