"""
SPRINT 3 — Ensemble v4: + YARATICI PLAYER FEATURES

KULLANICIN VİZYONU:
    "asist yapan adamın sonraki maç oynaması..., gol krallığında mücadele edenin
    galibiyete etkisi..., gol olura etkisi, yaratıcı olmak zorundayız."

YENI FEATURE'LAR (player_features.py):
    home/away top_scorer_goals      — gol kralı yarışında ne kadar gol
    home/away top_assist_count      — asist kralı yarışı
    home/away card_risk             — kart kralı (cezalı kalma riski)
    home/away squad_depth           — top-3 oyuncu kombine katkı
    star_battle_score               — iki yıldızın yakınlığı (derbi motivasyon)

TEST: Multi-league walk-forward CLV pozitif çıkar mı?
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
MODEL_DIR = THIS_DIR.parent
YAZILIM_DIR = MODEL_DIR.parent

sys.path.insert(0, str(MODEL_DIR))
sys.path.insert(0, str(YAZILIM_DIR / "02_VERI"))
sys.path.insert(0, str(THIS_DIR))

from xg_lgbm import build_dataset, add_dc_features, FEATURE_COLS  # noqa
from xg_lgbm_v2 import add_injury_features, FEATURE_COLS_V2  # noqa
from xg_lgbm_v3 import GEMINI_FEATURE_COLS, add_gemini_features  # noqa
import player_features as pf  # noqa


# YARATICI player features
PLAYER_FEATURE_COLS = [
    "home_top_scorer_goals", "away_top_scorer_goals",
    "home_top_assist_count", "away_top_assist_count",
    "home_card_risk", "away_card_risk",
    "star_battle_score",
    "home_squad_depth", "away_squad_depth",
]

# DC olasılıkları YOK (ortogonal blend), tüm rest var
FEATURE_COLS_V4 = FEATURE_COLS_V2 + GEMINI_FEATURE_COLS + PLAYER_FEATURE_COLS


# ============================================================
# Takım adı haritalama (football-data → api-football)
# ============================================================

FD_TO_AF = {
    # Premier League
    "Man City": "Manchester City", "Man United": "Manchester United",
    "Nott'm Forest": "Nottingham Forest",
    # Süper Lig — top_players DB'sindeki AF isimleri
    "Fenerbahce": "Fenerbahçe", "Besiktas": "Beşiktaş",
    "Buyuksehyr": "Başakşehir",
    "Eyupspor": "Eyüpspor", "Goztepe": "Göztepe",
    "Kasimpasa": "Kasımpaşa",
    "Ad. Demirspor": "Adana Demirspor",
    "Gaziantep": "Gaziantep FK",
    # Türkçe karakterler için "ı" ve normal eşleşmeyenler de
    # Bundesliga — AF tam isimleri
    "Leverkusen": "Bayer Leverkusen",
    "Ein Frankfurt": "Eintracht Frankfurt",
    "M'gladbach": "Borussia Mönchengladbach",
    "Bayern Munich": "Bayern München",
    "Wolfsburg": "VfL Wolfsburg",
    "Bochum": "VfL Bochum",
    "Stuttgart": "VfB Stuttgart",
    "Augsburg": "FC Augsburg",
    "Mainz": "FSV Mainz 05",
    "Freiburg": "SC Freiburg",
    "Heidenheim": "1. FC Heidenheim",
    "Hoffenheim": "1899 Hoffenheim",
    "Dortmund": "Borussia Dortmund",
    "RB Leipzig": "RB Leipzig",
    "Union Berlin": "Union Berlin",
    # FD'de aynı isim olan takımlar (exact match) için mapping gerekmez
    # ama bazıları üstte çıkıyor; explicit olarak ekleyelim:
    "Holstein Kiel": "Holstein Kiel",
    "Werder Bremen": "Werder Bremen",
    "St Pauli": "FC St. Pauli",  # AF'de "FC St. Pauli" olabilir
}

def fd_to_af(team_fd: str) -> str:
    return FD_TO_AF.get(team_fd, team_fd)


# ============================================================
# PLAYER FEATURE EKLE
# ============================================================

def date_to_af_season(d) -> int:
    """match_date → api-football season int (2024-25 sezon = 2024)."""
    # Avrupa sezon: Ağustos-Mayıs → Ağustos öncesi previous year
    if hasattr(d, "month"):
        return d.year - 1 if d.month < 7 else d.year
    # String fallback
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(str(d)[:10])
        return dt.year - 1 if dt.month < 7 else dt.year
    except Exception:
        return 2024


def add_player_features(mat: pd.DataFrame, league_code: str,
                         season_lookup: int | None = None) -> pd.DataFrame:
    """
    Her maç için yaratıcı player features ekle.
    Season-aware: match_date'a göre uygun sezonun player data'sı kullanılır.
    DB'de yoksa en yakın sezona fallback.
    """
    print(f"\n  Player features ekleniyor ({len(mat)} mac, lig {league_code})...")
    # DB'de mevcut sezonlar
    import sqlite3
    conn = sqlite3.connect(YAZILIM_DIR / "02_VERI" / "bahis_agent.db")
    available_seasons = set()
    try:
        for r in conn.execute(
            "SELECT DISTINCT season FROM top_players WHERE league_code = ?",
            (league_code,)
        ):
            available_seasons.add(r[0])
    finally:
        conn.close()
    print(f"    Mevcut sezonlar: {sorted(available_seasons)}")

    def best_season(target):
        if not available_seasons:
            return None
        if target in available_seasons:
            return target
        return min(available_seasons, key=lambda s: abs(s - target))

    feats_list = []
    miss = 0
    for _, r in mat.iterrows():
        h_af = fd_to_af(r["home_team"])
        a_af = fd_to_af(r["away_team"])
        s_target = season_lookup if season_lookup else date_to_af_season(r["match_date"])
        s_use = best_season(s_target) or 2024
        try:
            feats = pf.compute_player_features(h_af, a_af, league_code, s_use)
        except Exception:
            feats = {c: 0 for c in PLAYER_FEATURE_COLS}
        if feats["home_top_scorer_goals"] == 0 and feats["away_top_scorer_goals"] == 0:
            miss += 1
        feats_list.append(feats)

    df_feat = pd.DataFrame(feats_list, index=mat.index)
    mat = mat.copy()
    for c in PLAYER_FEATURE_COLS:
        mat[c] = df_feat[c]
    if miss:
        print(f"    {miss}/{len(mat)} mac iki takim da bulunamadi")
    return mat


# ============================================================
# WALK-FORWARD V4
# ============================================================

def walk_forward_v4(mat: pd.DataFrame, target: str = "over25",
                     n_initial: int = 600, refit_every: int = 50,
                     alpha_dc: float = 0.5) -> pd.DataFrame:
    """alpha_dc düşük (0.5) — yeni feature'ları daha çok güven."""
    import lightgbm as lgb

    mat = mat.copy()
    if target == "over25":
        mat["y"] = (mat["home_goals"] + mat["away_goals"] > 2.5).astype(int)
    else:
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

    fill_cols = (["home_injuries", "away_injuries",
                  "home_inj_attacking", "away_inj_attacking"]
                 + GEMINI_FEATURE_COLS + PLAYER_FEATURE_COLS)
    for c in fill_cols:
        if c in mat.columns:
            med = mat[c].median() if mat[c].notna().any() else 0
            mat[c] = mat[c].fillna(med)
            cached_dc[c] = mat[c]

    for i in range(n_initial, n):
        if i - last_fit_idx >= refit_every:
            cached_dc = add_dc_features(mat, train_cutoff_idx=i)
            for c in GEMINI_FEATURE_COLS + PLAYER_FEATURE_COLS:
                if c in mat.columns:
                    cached_dc[c] = mat[c]
            valid_cols = [c for c in FEATURE_COLS_V4 if c in cached_dc.columns]
            train = cached_dc.iloc[:i].dropna(subset=valid_cols + ["y"])
            if len(train) < 200:
                continue

            X = train[valid_cols].values
            yy = train["y"].values
            ref = cached_dc.iloc[i]["match_date"]
            dback = (ref - train["match_date"]).dt.days.values
            w = np.exp(-dback / 365.0)

            model = lgb.LGBMClassifier(
                n_estimators=250, max_depth=5, learning_rate=0.04,
                min_child_samples=25, reg_lambda=1.5,
                random_state=42, verbose=-1
            )
            model.fit(X, yy, sample_weight=w)
            last_model = model
            last_fit_idx = i
            if i % 200 == 0:
                print(f"    i={i} ({i/n*100:.0f}%) refit, features={len(valid_cols)}")

        if last_model is not None:
            row = cached_dc.iloc[i]
            valid_cols = [c for c in FEATURE_COLS_V4 if c in cached_dc.columns]
            feats = row[valid_cols]
            if not feats.isna().any():
                X_test = feats.values.reshape(1, -1).astype(float)
                p_lgbm = float(last_model.predict_proba(X_test)[0, 1])
                p_dc = float(row["p_over25"]) if target == "over25" else float(row["p_btts"])
                p_final = alpha_dc * p_dc + (1 - alpha_dc) * p_lgbm
                out.at[mat.index[i], "p_dc"] = p_dc
                out.at[mat.index[i], "p_lgbm"] = p_lgbm
                out.at[mat.index[i], "p_ensemble"] = p_final

    return out


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--league", default="T1")
    p.add_argument("--target", default="over25")
    p.add_argument("--alpha", type=float, default=0.5)
    p.add_argument("--mock", action="store_true")
    p.add_argument("--tail", type=int, default=900)
    args = p.parse_args()

    if args.mock:
        import llm_features
        llm_features.LLM_MODE = "mock"
        llm_features.GEMINI_KEY = ""

    print("=" * 70)
    print(f"SPRINT 3 v4 — DC + xG + Inj + Gemini + PLAYER FEATURES")
    print(f"Lig: {args.league}  Target: {args.target}  alpha_dc: {args.alpha}")
    print("=" * 70)

    print("\n[1/5] Dataset (DC+xG+Elo)...")
    mat = build_dataset(args.league)
    if args.tail > 0:
        mat = mat.tail(args.tail).reset_index(drop=True)
    print(f"  {len(mat)} mac")

    print("\n[2/5] Injuries...")
    mat = add_injury_features(mat)

    print("\n[3/5] Gemini features...")
    mat = add_gemini_features(mat, league_name="futbol")

    print("\n[4/5] YARATICI Player features...")
    mat = add_player_features(mat, args.league, season_lookup=2024)

    print("\n[5/5] Walk-forward...")
    res = walk_forward_v4(mat, target=args.target, n_initial=600,
                           refit_every=50, alpha_dc=args.alpha)

    valid = res.dropna(subset=["p_ensemble"])
    print(f"\nOut-of-sample: {len(valid)}")

    from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
    for col, name in [("p_dc","DC alone"),
                       ("p_lgbm","LGBM alone"),
                       ("p_ensemble","Ensemble v4")]:
        v = valid.dropna(subset=[col])
        if len(v) == 0: continue
        b = brier_score_loss(v["y"], v[col])
        ll = log_loss(v["y"], v[col])
        a = roc_auc_score(v["y"], v[col])
        print(f"  {name:14s}: Brier {b:.4f}  LogLoss {ll:.4f}  AUC {a:.4f}")

    # Karşılaştırma
    v = valid.dropna(subset=["p_dc","p_ensemble"])
    if len(v) > 0:
        b_dc = brier_score_loss(v["y"], v["p_dc"])
        b_e = brier_score_loss(v["y"], v["p_ensemble"])
        delta = (b_dc - b_e) / b_dc * 100
        print(f"\n  Ensemble v4 vs DC: Brier {delta:+.2f}% {'[BETTER]' if delta > 0 else '[WORSE]'}")

    out_path = YAZILIM_DIR / "07_LOG_VE_RAPORLAR" / f"v4_predictions_{args.league}_{args.target}.csv"
    res.to_csv(out_path, index=False)
    print(f"\nKaydedildi: {out_path.name}")
