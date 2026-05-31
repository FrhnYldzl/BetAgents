"""
Ensemble v2: Bayesian blend mimarisi.

Sprint 1.4 dersi: DC olasılığını LightGBM'e feature olarak vermek başarısız.
Yeni mimari:
    p_final = α · p_DC  +  (1-α) · p_LGBM
    α = 0.7 (DC daha güçlü baseline)
    LGBM artık DC çıktısı KULLANMIYOR — ortogonal raw features.

Yeni feature'lar:
    - Sakatlık sayısı (home/away)
    - Mevcut: xG rolling, form, Elo, rest days

Hedef: CLV pozitif olana kadar iterate.
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

# Eski xg_lgbm'den fonksiyonları al
sys.path.insert(0, str(THIS_DIR))
from xg_lgbm import (  # noqa: E402
    build_dataset,
    add_dc_features,
    compute_elo,
    normalize_understat_team,
)


# Sadece ORTOGONAL features — DC olasılıkları YOK!
FEATURE_COLS_V2 = [
    # xG rolling 5 + 10 (8)
    "home_xg_for_5", "home_xg_against_5",
    "home_xg_for_10", "home_xg_against_10",
    "away_xg_for_5", "away_xg_against_5",
    "away_xg_for_10", "away_xg_against_10",
    # Form 5 (6)
    "home_gf_5", "home_ga_5", "home_pts_5",
    "away_gf_5", "away_ga_5", "away_pts_5",
    # Form 10 (6)
    "home_gf_10", "home_ga_10", "home_pts_10",
    "away_gf_10", "away_ga_10", "away_pts_10",
    # Context (4)
    "home_rest_days", "away_rest_days",
    "home_matches_played", "away_matches_played",
    # Elo (2)
    "home_elo_pre", "away_elo_pre",
    # YENİ: Sakatlık (4) — opsiyonel, NaN'ler 0 doldurulur
    "home_injuries", "away_injuries",
    "home_inj_attacking", "away_inj_attacking",  # forwarders/mids
]


# ============================================================
# INJURY FEATURE
# ============================================================

ATTACKING_KEYWORDS = ("forward", "winger", "striker", "attacking", "centre forward",
                     "left winger", "right winger", "second striker")


def add_injury_features(matches: pd.DataFrame,
                         db_path: str | None = None) -> pd.DataFrame:
    """
    Maç tarihinden geriye doğru, her takım için son 14 gündeki injury sayısı.
    Note: api-football injury kayıtları fixture-bazlı (her maç günü), bu yüzden
    fixture_date geçmişteki tüm kayıtları topluyoruz, son 14 günü filtreliyoruz.
    """
    if db_path is None:
        db_path = str(YAZILIM_DIR / "02_VERI" / "bahis_agent.db")

    conn = sqlite3.connect(db_path)
    try:
        inj = pd.read_sql_query(
            "SELECT team_name, fixture_date, COUNT(*) as n_inj "
            "FROM injuries GROUP BY team_name, fixture_date",
            conn
        )
        # api-football team name normalize (Football-Data ile uyumlu)
        # injuries.team_name ile fixtures.home/away_team ile uyumsuz olabilir
        # En basit: takım adının ilk kelimesini eşle (heuristic)
    finally:
        conn.close()

    inj["fixture_date"] = pd.to_datetime(inj["fixture_date"])
    inj_dict: dict[str, pd.DataFrame] = {
        team: g.sort_values("fixture_date")
        for team, g in inj.groupby("team_name")
    }

    home_injs, away_injs = [], []
    matched_count = 0
    miss_log = set()

    # api-football <-> football-data takım ad eşlemesi (kaba)
    # injuries.team_name içinde "Manchester United" var ama matches.home_team "Man United"
    AF_TO_FD = {
        "Manchester United": "Man United",
        "Manchester City": "Man City",
        "Newcastle": "Newcastle",
        "Tottenham": "Tottenham",
        "Wolves": "Wolves",
        "Nottingham Forest": "Nott'm Forest",
        "Galatasaray": "Galatasaray",
        "Fenerbahce": "Fenerbahce",
        "Besiktas": "Besiktas",
        "Trabzonspor": "Trabzonspor",
        "Antalyaspor": "Antalyaspor",
        # Çoğu takım için aynı kalır
    }
    FD_TO_AF = {v: k for k, v in AF_TO_FD.items()}

    def get_team_inj(team_fd: str, ref_date: pd.Timestamp, lookback: int = 14) -> int:
        af = FD_TO_AF.get(team_fd, team_fd)
        # Direkt match
        df_t = inj_dict.get(af)
        if df_t is None:
            # Fuzzy: af içinde geçen takım adı
            for k in inj_dict.keys():
                if af.lower() in k.lower() or k.lower() in af.lower():
                    df_t = inj_dict[k]
                    break
        if df_t is None:
            miss_log.add(team_fd)
            return 0
        recent = df_t[(df_t["fixture_date"] < ref_date)
                      & (df_t["fixture_date"] >= ref_date - timedelta(days=lookback))]
        return int(recent["n_inj"].sum()) if not recent.empty else 0

    for _, m in matches.iterrows():
        h_count = get_team_inj(m["home_team"], m["match_date"])
        a_count = get_team_inj(m["away_team"], m["match_date"])
        home_injs.append(h_count)
        away_injs.append(a_count)
        if h_count > 0 or a_count > 0:
            matched_count += 1

    matches = matches.copy()
    matches["home_injuries"] = home_injs
    matches["away_injuries"] = away_injs
    # Saldırı pozisyonlarındaki sakatlık (basit: yarısı diyelim — gerçek için player pos lazım)
    matches["home_inj_attacking"] = (np.array(home_injs) * 0.4).astype(float)
    matches["away_inj_attacking"] = (np.array(away_injs) * 0.4).astype(float)

    print(f"  Injuries eslesti: {matched_count}/{len(matches)} mac")
    if miss_log:
        sample = list(miss_log)[:5]
        print(f"  Eslesememis takimlar (ornek): {sample}")
    return matches


# ============================================================
# WALK-FORWARD V2 — Bayesian blend
# ============================================================

def walk_forward_v2(mat: pd.DataFrame, target: str = "over25",
                     n_initial: int = 600, refit_every: int = 50,
                     alpha_dc: float = 0.7) -> pd.DataFrame:
    """
    p_final = alpha_dc · p_DC + (1 - alpha_dc) · p_LGBM
    LGBM artık DC features almıyor (ortogonal).
    """
    import lightgbm as lgb

    mat = mat.copy()
    if target == "over25":
        mat["y"] = (mat["home_goals"] + mat["away_goals"] > 2.5).astype(int)
    elif target == "btts":
        mat["y"] = ((mat["home_goals"] >= 1) & (mat["away_goals"] >= 1)).astype(int)

    n = len(mat)
    out = mat[["match_date", "home_team", "away_team",
               "home_goals", "away_goals", "y"]].copy()
    out["p_dc"] = np.nan
    out["p_lgbm"] = np.nan
    out["p_ensemble"] = np.nan

    last_model = None
    last_fit_idx = -refit_every
    cached_dc = mat.assign(p_1=np.nan, p_X=np.nan, p_2=np.nan,
                           p_over25=np.nan, p_btts=np.nan)

    # FillNA: sakatlık feature'ları için
    fill_cols = ["home_injuries", "away_injuries",
                 "home_inj_attacking", "away_inj_attacking"]
    for c in fill_cols:
        if c in mat.columns:
            mat[c] = mat[c].fillna(0)

    for i in range(n_initial, n):
        if i - last_fit_idx >= refit_every:
            cached_dc = add_dc_features(mat, train_cutoff_idx=i)
            # LGBM eğitiminde FEATURE_COLS_V2 (DC olasılıkları YOK)
            valid_cols = [c for c in FEATURE_COLS_V2 if c in cached_dc.columns]
            train = cached_dc.iloc[:i].dropna(subset=valid_cols + ["y"])
            if len(train) < 200:
                continue

            X = train[valid_cols].values
            yy = train["y"].values

            ref = cached_dc.iloc[i]["match_date"]
            days_back = (ref - train["match_date"]).dt.days.values
            w = np.exp(-days_back / 365.0)

            model = lgb.LGBMClassifier(
                n_estimators=150, max_depth=4, learning_rate=0.04,
                min_child_samples=30, reg_lambda=2.0,
                random_state=42, verbose=-1
            )
            model.fit(X, yy, sample_weight=w)
            last_model = model
            last_fit_idx = i
            if i % 200 == 0:
                print(f"  i={i} ({i/n*100:.0f}%) refit, train_n={len(train)}")

        # Tahmin
        if last_model is not None:
            row = cached_dc.iloc[i]
            valid_cols = [c for c in FEATURE_COLS_V2 if c in cached_dc.columns]
            feats = row[valid_cols]
            if not feats.isna().any():
                X_test = feats.values.reshape(1, -1).astype(float)
                p_lgbm = float(last_model.predict_proba(X_test)[0, 1])
                p_dc = float(row["p_over25"]) if target == "over25" else float(row["p_btts"])
                # Bayesian blend
                p_final = alpha_dc * p_dc + (1 - alpha_dc) * p_lgbm
                out.at[mat.index[i], "p_dc"] = p_dc
                out.at[mat.index[i], "p_lgbm"] = p_lgbm
                out.at[mat.index[i], "p_ensemble"] = p_final

    return out


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    print("=" * 70)
    print("SPRINT 1.4-v2 — Ensemble (Bayesian Blend)")
    print("=" * 70)
    league = sys.argv[1] if len(sys.argv) > 1 else "T1"
    target = sys.argv[2] if len(sys.argv) > 2 else "over25"
    alpha_dc = float(sys.argv[3]) if len(sys.argv) > 3 else 0.7

    print(f"\nLig    : {league}")
    print(f"Target : {target}")
    print(f"alpha_dc (DC ağırlığı): {alpha_dc}")
    print()

    print("[1/4] Dataset hazirlaniyor...")
    mat = build_dataset(league)
    print(f"  Total mac: {len(mat)}")

    print("\n[2/4] Sakatlık feature ekleniyor...")
    mat = add_injury_features(mat)

    print(f"\n[3/4] Walk-forward (alpha_dc={alpha_dc})...")
    res = walk_forward_v2(mat, target=target, n_initial=600, refit_every=50,
                           alpha_dc=alpha_dc)

    print(f"\n[4/4] Sonuçlar:")
    valid = res.dropna(subset=["p_ensemble"])
    print(f"  Out-of-sample : {len(valid)}")
    print(f"  Mean y        : {valid['y'].mean():.4f}")

    from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
    metrics = {}
    for col in ["p_dc", "p_lgbm", "p_ensemble"]:
        v = valid.dropna(subset=[col])
        if len(v) == 0:
            continue
        metrics[col] = {
            "brier": brier_score_loss(v["y"], v[col]),
            "logloss": log_loss(v["y"], v[col]),
            "auc": roc_auc_score(v["y"], v[col]),
            "n": len(v),
        }

    print(f"\n  {'Model':<14}{'N':>6}  {'Brier':>8}  {'LogLoss':>9}  {'AUC':>7}")
    print(f"  {'-'*14}{'-'*6}  {'-'*8}  {'-'*9}  {'-'*7}")
    for k, m in metrics.items():
        print(f"  {k:<14}{m['n']:>6}  {m['brier']:>8.4f}  {m['logloss']:>9.4f}  {m['auc']:>7.4f}")

    if "p_dc" in metrics and "p_ensemble" in metrics:
        d = metrics["p_dc"]; e = metrics["p_ensemble"]
        b_delta = (d["brier"] - e["brier"]) / d["brier"] * 100
        ll_delta = (d["logloss"] - e["logloss"]) / d["logloss"] * 100
        auc_delta = (e["auc"] - d["auc"]) / d["auc"] * 100
        print(f"\n  Ensemble vs DC: Brier {b_delta:+.2f}%  LogLoss {ll_delta:+.2f}%  AUC {auc_delta:+.2f}%")
        if b_delta > 0 and ll_delta > 0:
            print(f"  >>> ENSEMBLE ICIN: DC'den DAHA IYI! Sprint 1.4-v2 BASARILI <<<")
        else:
            print(f"  >>> Ensemble DC'yi yenemedi. Iterate gerekli.")

    out_path = YAZILIM_DIR / "07_LOG_VE_RAPORLAR" / f"ensemble_v2_{league}_{target}_a{alpha_dc}.csv"
    res.to_csv(out_path, index=False)
    print(f"\n  Kaydedildi: {out_path.name}")
