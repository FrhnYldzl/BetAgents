"""
SPRINT 2.3-FINAL — Ensemble v3: DC + xG + Elo + Sakatlık + **GEMINI LLM FEATURES**

KRITIK TEST:
    Gemini'nin 7 ortogonal feature'u LightGBM'e girince
    CLV negatiften pozitife döner mi?

VERI:
    - Mevcut: DC olasılığı + xG rolling + Elo + sakatlık
    - YENİ: Gemini ile motivasyon, sakatlık, taktik, sentiment, narrative

CIKIS:
    - Walk-forward backtest, CLV ölçümü, bilimsel hüküm
"""
from __future__ import annotations

import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
MODEL_DIR = THIS_DIR.parent
YAZILIM_DIR = MODEL_DIR.parent

sys.path.insert(0, str(MODEL_DIR))
sys.path.insert(0, str(YAZILIM_DIR / "02_VERI"))
sys.path.insert(0, str(THIS_DIR))

from xg_lgbm import build_dataset, add_dc_features, compute_elo, FEATURE_COLS  # noqa
from xg_lgbm_v2 import add_injury_features, FEATURE_COLS_V2  # noqa
from llm_features import extract_features_via_llm, LLM_MODE  # noqa


# Yeni feature listesi — DC features YOK (ortogonal blend mantığı)
GEMINI_FEATURE_COLS = [
    "g_motivation", "g_player_doubt", "g_tactical",
    "g_sentiment_home", "g_sentiment_away",
    "g_injury_severity", "g_narrative",
]

FEATURE_COLS_V3 = FEATURE_COLS_V2 + GEMINI_FEATURE_COLS


# ============================================================
# GEMINI FEATURE BATCH
# ============================================================

def add_gemini_features(mat: pd.DataFrame, league_name: str = "futbol",
                        progress_every: int = 50) -> pd.DataFrame:
    """
    Tüm maçlar için Gemini feature'larını üret/cache'den oku.

    Mode "live" ise Gemini API çağrılır (yavaş, 15 RPM).
    Mode "mock" ise deterministik fake.
    """
    print(f"\n  Gemini feature extraction ({LLM_MODE} mode, {len(mat)} maç)...")
    rows = []
    t0 = time.time()
    for i, m in enumerate(mat.itertuples(index=False)):
        # Tarih str
        mdate = m.match_date.strftime("%Y-%m-%d") if hasattr(m.match_date, "strftime") else str(m.match_date)[:10]
        try:
            feats = extract_features_via_llm(
                home=m.home_team, away=m.away_team,
                match_date=mdate, texts=[],  # şu an metin yok, sadece takım adları
                league=league_name,
            )
            rows.append({
                "g_motivation": feats.get("motivation_score", 0.5),
                "g_player_doubt": feats.get("key_player_doubt", 0),
                "g_tactical": feats.get("tactical_change", 0),
                "g_sentiment_home": feats.get("sentiment_home", 0),
                "g_sentiment_away": feats.get("sentiment_away", 0),
                "g_injury_severity": feats.get("injury_severity", 0),
                "g_narrative": feats.get("narrative_strength", 0.5),
            })
        except Exception as e:
            rows.append({c: np.nan for c in GEMINI_FEATURE_COLS})

        if (i + 1) % progress_every == 0:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            eta = (len(mat) - i - 1) / rate if rate > 0 else 0
            print(f"    {i+1}/{len(mat)} ({rate:.1f}/sn, ETA {eta:.0f}sn)")

    gem_df = pd.DataFrame(rows, index=mat.index)
    mat = mat.copy()
    for c in GEMINI_FEATURE_COLS:
        mat[c] = gem_df[c]
    return mat


# ============================================================
# WALK-FORWARD V3 — Bayesian blend + Gemini
# ============================================================

def walk_forward_v3(mat: pd.DataFrame, target: str = "over25",
                     n_initial: int = 600, refit_every: int = 50,
                     alpha_dc: float = 0.6) -> pd.DataFrame:
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

    # FillNA
    for c in ["home_injuries", "away_injuries",
              "home_inj_attacking", "away_inj_attacking"] + GEMINI_FEATURE_COLS:
        if c in mat.columns:
            mat[c] = mat[c].fillna(mat[c].median() if mat[c].notna().any() else 0)
            cached_dc[c] = mat[c]

    for i in range(n_initial, n):
        if i - last_fit_idx >= refit_every:
            cached_dc = add_dc_features(mat, train_cutoff_idx=i)
            # GEMINI features'ları geri yükle (add_dc_features kaybediyor)
            for c in GEMINI_FEATURE_COLS:
                if c in mat.columns:
                    cached_dc[c] = mat[c]
            valid_cols = [c for c in FEATURE_COLS_V3 if c in cached_dc.columns]
            train = cached_dc.iloc[:i].dropna(subset=valid_cols + ["y"])
            if len(train) < 200:
                continue

            X = train[valid_cols].values
            yy = train["y"].values
            ref = cached_dc.iloc[i]["match_date"]
            days_back = (ref - train["match_date"]).dt.days.values
            w = np.exp(-days_back / 365.0)

            model = lgb.LGBMClassifier(
                n_estimators=200, max_depth=4, learning_rate=0.04,
                min_child_samples=30, reg_lambda=2.0,
                random_state=42, verbose=-1
            )
            model.fit(X, yy, sample_weight=w)
            last_model = model
            last_fit_idx = i
            if i % 200 == 0:
                print(f"    i={i} ({i/n*100:.0f}%) refit, n_features={len(valid_cols)}")

        if last_model is not None:
            row = cached_dc.iloc[i]
            valid_cols = [c for c in FEATURE_COLS_V3 if c in cached_dc.columns]
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
    p.add_argument("--alpha", type=float, default=0.6)
    p.add_argument("--mock", action="store_true", help="Force mock LLM (no API calls)")
    p.add_argument("--tail", type=int, default=0,
                   help="Son N maçı al (0=hepsi, hız için 600-1000 öneri)")
    args = p.parse_args()

    # Force mock mode (testing)
    if args.mock:
        import llm_features
        llm_features.LLM_MODE = "mock"
        llm_features.GEMINI_KEY = ""

    print("=" * 70)
    print(f"SPRINT 2.3-FINAL — Ensemble v3 (DC + xG + Inj + GEMINI)")
    print(f"Lig: {args.league}  Target: {args.target}  alpha_dc: {args.alpha}")
    print(f"LLM mode: {LLM_MODE} ({'FORCE MOCK' if args.mock else 'auto'})")
    if args.tail > 0:
        print(f"Tail   : son {args.tail} mac kullanilacak")
    print("=" * 70)

    print("\n[1/4] Dataset hazırlanıyor (DC + xG + Elo)...")
    mat = build_dataset(args.league)
    print(f"  {len(mat)} mac")
    if args.tail > 0:
        mat = mat.tail(args.tail).reset_index(drop=True)
        print(f"  TAIL: son {len(mat)} mac kullaniliyor")

    print("\n[2/4] Sakatlık features...")
    mat = add_injury_features(mat)

    print("\n[3/4] Gemini features...")
    mat = add_gemini_features(mat, league_name={"T1":"Türkiye Süper Lig","E0":"Premier League","D1":"Bundesliga"}.get(args.league, args.league))

    print(f"\n[4/4] Walk-forward backtest...")
    res = walk_forward_v3(mat, target=args.target, n_initial=600,
                           refit_every=50, alpha_dc=args.alpha)

    valid = res.dropna(subset=["p_ensemble"])
    print(f"\n  Out-of-sample tahmin: {len(valid)}")
    print(f"  Mean y           : {valid['y'].mean():.4f}")

    from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
    for col, name in [("p_dc", "DC alone"), ("p_lgbm", "LGBM alone"),
                       ("p_ensemble", "Ensemble v3")]:
        v = valid.dropna(subset=[col])
        if len(v) == 0: continue
        b = brier_score_loss(v["y"], v[col])
        ll = log_loss(v["y"], v[col])
        a = roc_auc_score(v["y"], v[col])
        print(f"  {name:14s}: Brier {b:.4f}  LogLoss {ll:.4f}  AUC {a:.4f}")

    # Kaydet
    out_path = YAZILIM_DIR / "07_LOG_VE_RAPORLAR" / f"v3_predictions_{args.league}_{args.target}.csv"
    res.to_csv(out_path, index=False)
    print(f"\n  Kaydedildi: {out_path.name}")
