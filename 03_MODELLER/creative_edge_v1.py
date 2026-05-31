"""
CREATIVE EDGE v1.0

Korelasyon analizine dayalı yaratıcı feature mühendisliği:
    - Her takım için son N maçta:
        rolling_xg_for, rolling_xg_against
        rolling_shots_on, rolling_shots_total
        rolling_corners, rolling_fouls
        rolling_possession, rolling_pass_acc_pct
        rolling_goals_prevented
    - xg_diff (current match)
    - Possession farkı, faul farkı, vb.

Model: LightGBM
Test: walk-forward + gerçek Pinnacle close odds → CLV
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
YAZILIM_DIR = THIS_DIR.parent
sys.path.insert(0, str(YAZILIM_DIR / "02_VERI"))

DB_PATH = YAZILIM_DIR / "02_VERI" / "bahis_agent.db"


def load_match_stats() -> pd.DataFrame:
    """
    Birleşik maç + istatistik tablosu.
    Sadece stats'ı olan FT maçlar.
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        q = """
        SELECT
            f.fixture_id, f.league_code, f.season, f.kickoff_utc,
            f.home_team, f.away_team, f.home_score, f.away_score,
            sh.shots_on AS h_shots_on, sh.shots_off AS h_shots_off,
            sh.shots_total AS h_shots_total, sh.shots_inside AS h_shots_inside,
            sh.fouls AS h_fouls, sh.corners AS h_corners, sh.offsides AS h_offsides,
            sh.possession_pct AS h_possession, sh.yellow AS h_yellow,
            sh.red AS h_red, sh.saves AS h_saves,
            sh.passes_total AS h_passes_total, sh.passes_acc AS h_passes_acc,
            sh.passes_pct AS h_passes_pct, sh.xg AS h_xg,
            sh.goals_prevented AS h_gp,
            sa.shots_on AS a_shots_on, sa.shots_off AS a_shots_off,
            sa.shots_total AS a_shots_total, sa.shots_inside AS a_shots_inside,
            sa.fouls AS a_fouls, sa.corners AS a_corners, sa.offsides AS a_offsides,
            sa.possession_pct AS a_possession, sa.yellow AS a_yellow,
            sa.red AS a_red, sa.saves AS a_saves,
            sa.passes_total AS a_passes_total, sa.passes_acc AS a_passes_acc,
            sa.passes_pct AS a_passes_pct, sa.xg AS a_xg,
            sa.goals_prevented AS a_gp
        FROM fixtures f
        JOIN fixture_statistics sh
            ON sh.fixture_id = f.fixture_id AND sh.is_home = 1
        JOIN fixture_statistics sa
            ON sa.fixture_id = f.fixture_id AND sa.is_home = 0
        WHERE f.status = 'FT'
        ORDER BY f.kickoff_utc
        """
        df = pd.read_sql_query(q, conn, parse_dates=["kickoff_utc"])
        return df
    finally:
        conn.close()


STAT_COLS = [
    "shots_on", "shots_off", "shots_total", "shots_inside",
    "fouls", "corners", "offsides", "possession", "yellow", "red",
    "saves", "passes_total", "passes_acc", "passes_pct", "xg", "gp",
]


def build_rolling_features(df: pd.DataFrame, window: int = 5) -> pd.DataFrame:
    """
    Her maç için, her takımın o maçtan önceki son N maç rolling istatistikleri.
    """
    df = df.sort_values("kickoff_utc").reset_index(drop=True)

    # Her takım için "for" ve "against" perspectives
    team_history: dict[str, list[dict]] = {}

    rolling_rows = []
    for _, m in df.iterrows():
        h = m["home_team"]; a = m["away_team"]
        h_hist = team_history.get(h, [])[-window:]
        a_hist = team_history.get(a, [])[-window:]

        row = {"fixture_id": m["fixture_id"]}

        # Ev sahibi rolling (for=hücum, against=savunma)
        if h_hist:
            for stat in STAT_COLS:
                row[f"h_roll_{stat}_for"] = np.mean([x[f"for_{stat}"] for x in h_hist])
                row[f"h_roll_{stat}_against"] = np.mean([x[f"against_{stat}"] for x in h_hist])
        else:
            for stat in STAT_COLS:
                row[f"h_roll_{stat}_for"] = np.nan
                row[f"h_roll_{stat}_against"] = np.nan

        if a_hist:
            for stat in STAT_COLS:
                row[f"a_roll_{stat}_for"] = np.mean([x[f"for_{stat}"] for x in a_hist])
                row[f"a_roll_{stat}_against"] = np.mean([x[f"against_{stat}"] for x in a_hist])
        else:
            for stat in STAT_COLS:
                row[f"a_roll_{stat}_for"] = np.nan
                row[f"a_roll_{stat}_against"] = np.nan

        row["h_matches_played"] = len(h_hist)
        row["a_matches_played"] = len(a_hist)
        rolling_rows.append(row)

        # Sonra history'i güncelle
        h_entry = {f"for_{s}": m[f"h_{s}"] if f"h_{s}" in m else np.nan for s in STAT_COLS}
        h_entry.update({f"against_{s}": m[f"a_{s}"] if f"a_{s}" in m else np.nan for s in STAT_COLS})
        a_entry = {f"for_{s}": m[f"a_{s}"] if f"a_{s}" in m else np.nan for s in STAT_COLS}
        a_entry.update({f"against_{s}": m[f"h_{s}"] if f"h_{s}" in m else np.nan for s in STAT_COLS})
        team_history.setdefault(h, []).append(h_entry)
        team_history.setdefault(a, []).append(a_entry)

    rolling_df = pd.DataFrame(rolling_rows)
    return df.merge(rolling_df, on="fixture_id", how="left")


def add_targets_and_diffs(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["total_goals"] = df["home_score"] + df["away_score"]
    df["y_over25"] = (df["total_goals"] > 2.5).astype(int)
    df["y_btts"] = ((df["home_score"] >= 1) & (df["away_score"] >= 1)).astype(int)
    df["y_home_win"] = (df["home_score"] > df["away_score"]).astype(int)

    # Diff features (ev - dep), rolling üzerinde
    for stat in STAT_COLS:
        for_h = f"h_roll_{stat}_for"
        for_a = f"a_roll_{stat}_for"
        ag_h = f"h_roll_{stat}_against"
        ag_a = f"a_roll_{stat}_against"
        if for_h in df.columns and for_a in df.columns:
            df[f"diff_{stat}_for"] = df[for_h] - df[for_a]
        if ag_h in df.columns and ag_a in df.columns:
            df[f"diff_{stat}_against"] = df[ag_h] - df[ag_a]
    return df


# Feature columns for LGBM (current match istatistikleri YOK, sadece rolling = leakage yok)
ROLLING_COLS = [
    f"{side}_roll_{stat}_{perspective}"
    for side in ["h", "a"]
    for stat in STAT_COLS
    for perspective in ["for", "against"]
]
DIFF_COLS = [f"diff_{stat}_{p}" for stat in STAT_COLS for p in ["for","against"]]
MATCH_COLS = ["h_matches_played", "a_matches_played"]
FEATURE_COLS_CE = ROLLING_COLS + DIFF_COLS + MATCH_COLS


def walk_forward_lgbm(df: pd.DataFrame, target: str = "y_over25",
                       n_initial: int = 100, refit_every: int = 30) -> pd.DataFrame:
    import lightgbm as lgb

    df = df.sort_values("kickoff_utc").reset_index(drop=True)
    out = df[["fixture_id","kickoff_utc","home_team","away_team",
              "home_score","away_score",target]].copy()
    out["p_ce"] = np.nan

    last_model = None
    last_fit_idx = -refit_every
    valid_cols = [c for c in FEATURE_COLS_CE if c in df.columns]
    print(f"  Feature columns: {len(valid_cols)}")

    n = len(df)
    for i in range(n_initial, n):
        if i - last_fit_idx >= refit_every:
            train = df.iloc[:i].dropna(subset=valid_cols + [target])
            if len(train) < 50:
                continue
            X = train[valid_cols].values
            y = train[target].values
            model = lgb.LGBMClassifier(
                n_estimators=200, max_depth=4, learning_rate=0.04,
                min_child_samples=15, reg_lambda=1.5,
                random_state=42, verbose=-1
            )
            model.fit(X, y)
            last_model = model
            last_fit_idx = i

        if last_model is not None:
            row = df.iloc[i]
            feats = row[valid_cols]
            if not feats.isna().any():
                p = float(last_model.predict_proba(feats.values.reshape(1,-1))[0,1])
                out.at[df.index[i], "p_ce"] = p
    return out


def compute_clv_and_roi(out: pd.DataFrame, target: str = "y_over25",
                        matches_csv: str | None = None):
    """Gerçek Pinnacle close odds ile CLV ve ROI."""
    from scipy import stats
    if matches_csv is None:
        matches_csv = str(YAZILIM_DIR / "02_VERI" / "processed" / "matches.csv")

    mat = pd.read_csv(matches_csv, parse_dates=["match_date"])

    # api-football date → match_date (yyyy-mm-dd)
    out = out.copy()
    out["match_date"] = pd.to_datetime(out["kickoff_utc"]).dt.tz_localize(None).dt.normalize()
    mat["match_date"] = pd.to_datetime(mat["match_date"]).dt.normalize()

    merged = out.merge(
        mat[["match_date","home_team","away_team",
             "odds_over25_b365","odds_over25_pin_close","odds_under25_pin_close"]],
        on=["match_date","home_team","away_team"], how="left"
    )

    valid = merged.dropna(subset=["p_ce","odds_over25_pin_close"]).copy()
    print(f"\n  Pinnacle eşleşen: {len(valid)} mac")
    if len(valid) == 0:
        print("  (Pinnacle odds eşleşmedi — football-data takım adı mapping gerek)")
        return

    valid["edge"] = valid["p_ce"] * valid["odds_over25_pin_close"] - 1
    for edge_thr in [0.02, 0.03, 0.05]:
        bets = valid[valid.edge > edge_thr].copy()
        if len(bets) == 0:
            print(f"  edge>%{edge_thr*100:.0f}: 0 bet")
            continue
        bets["pnl"] = np.where(bets[target] == 1, bets.odds_over25_pin_close - 1, -1)
        roi = bets.pnl.mean() * 100
        win = bets[target].mean() * 100
        se = bets.pnl.std() / np.sqrt(len(bets))
        t = bets.pnl.mean() / se if se > 0 else 0
        p_val = 2 * (1 - stats.t.cdf(abs(t), len(bets)-1)) if se > 0 else 1.0
        print(f"  edge>%{edge_thr*100:.0f}: {len(bets):3d} bet, win {win:5.1f}%, "
              f"ROI {roi:+6.2f}%, t={t:+.2f}, p={p_val:.3f}")


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--target", default="y_over25",
                   choices=["y_over25", "y_btts", "y_home_win"])
    p.add_argument("--window", type=int, default=5)
    p.add_argument("--n_initial", type=int, default=50)
    args = p.parse_args()

    print("=" * 70)
    print(f"CREATIVE EDGE v1.0 — Target: {args.target}")
    print("=" * 70)

    print("\n[1/4] Match + stats yükleniyor...")
    df = load_match_stats()
    print(f"  {len(df)} mac (stats var)")
    if len(df) < 30:
        print("  YETERSIZ veri — daha çok ingest gerek")
        return

    print(f"\n[2/4] Rolling features (window={args.window})...")
    df = build_rolling_features(df, window=args.window)

    print("\n[3/4] Target + diff features...")
    df = add_targets_and_diffs(df)

    print(f"\n[4/4] Walk-forward LightGBM...")
    out = walk_forward_lgbm(df, target=args.target, n_initial=args.n_initial)

    valid = out.dropna(subset=["p_ce"])
    print(f"\n  Out-of-sample tahmin: {len(valid)}")
    if len(valid) == 0:
        return

    from sklearn.metrics import brier_score_loss, roc_auc_score, log_loss
    b = brier_score_loss(valid[args.target], valid["p_ce"])
    a = roc_auc_score(valid[args.target], valid["p_ce"])
    ll = log_loss(valid[args.target], valid["p_ce"])
    print(f"\n  Creative Edge v1.0:")
    print(f"    Brier   : {b:.4f}")
    print(f"    LogLoss : {ll:.4f}")
    print(f"    AUC     : {a:.4f}")

    print("\n  Pinnacle CLV/ROI testi:")
    compute_clv_and_roi(out, target=args.target)

    out_path = YAZILIM_DIR / "07_LOG_VE_RAPORLAR" / f"creative_edge_{args.target}.csv"
    out.to_csv(out_path, index=False)
    print(f"\n  Kaydedildi: {out_path.name}")


if __name__ == "__main__":
    main()
