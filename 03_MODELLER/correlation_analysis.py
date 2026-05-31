"""
CREATIVE EDGE v1.0 — Data Correlation Analysis

Hipotez:
    Hangi sütun (xG, possession, shots, passes, vb.) Over 2.5 ile
    en güçlü korelasyona sahip? Hangi feature kombinasyonu CLV pozitif yapabilir?

Yöntem:
    1. fixtures + fixture_statistics + xg_data → unified dataset
    2. Her sütun ile target (Over 2.5, KG, vs.) Pearson + mutual information
    3. Top-K feature kombinasyonu LightGBM ile test
    4. AUC, Brier, CLV ölç → Creative Edge v1.0 features tanımla
"""
from __future__ import annotations

import sys
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
YAZILIM_DIR = THIS_DIR.parent
sys.path.insert(0, str(YAZILIM_DIR / "02_VERI"))

import database as db

DB_PATH = YAZILIM_DIR / "02_VERI" / "bahis_agent.db"


def load_unified_dataset() -> pd.DataFrame:
    """
    Tüm tabloları join et:
        fixtures + fixture_statistics (home+away separately) + xg_data
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        # Önce hangi fixture'lar için stats var
        n_stats = conn.execute("SELECT COUNT(DISTINCT fixture_id) FROM fixture_statistics").fetchone()[0]
        print(f"  fixture_statistics kayıtları: {n_stats} fixture için var")

        if n_stats == 0:
            print("  HENÜZ STATS YOK — önce stats_ingest.py çalıştır")
            return pd.DataFrame()

        # JOIN: fixtures + stats (home) + stats (away)
        q = """
        SELECT
            f.fixture_id, f.league_code, f.season, f.kickoff_utc,
            f.home_team, f.away_team, f.home_score, f.away_score,
            -- Home stats
            sh.shots_on AS h_shots_on, sh.shots_off AS h_shots_off,
            sh.shots_total AS h_shots_total, sh.shots_inside AS h_shots_inside,
            sh.fouls AS h_fouls, sh.corners AS h_corners, sh.offsides AS h_offsides,
            sh.possession_pct AS h_possession, sh.yellow AS h_yellow,
            sh.red AS h_red, sh.saves AS h_saves,
            sh.passes_total AS h_passes_total, sh.passes_acc AS h_passes_acc,
            sh.passes_pct AS h_passes_pct, sh.xg AS h_xg,
            sh.goals_prevented AS h_gp,
            -- Away stats
            sa.shots_on AS a_shots_on, sa.shots_off AS a_shots_off,
            sa.shots_total AS a_shots_total, sa.shots_inside AS a_shots_inside,
            sa.fouls AS a_fouls, sa.corners AS a_corners, sa.offsides AS a_offsides,
            sa.possession_pct AS a_possession, sa.yellow AS a_yellow,
            sa.red AS a_red, sa.saves AS a_saves,
            sa.passes_total AS a_passes_total, sa.passes_acc AS a_passes_acc,
            sa.passes_pct AS a_passes_pct, sa.xg AS a_xg,
            sa.goals_prevented AS a_gp
        FROM fixtures f
        LEFT JOIN fixture_statistics sh
            ON sh.fixture_id = f.fixture_id AND sh.is_home = 1
        LEFT JOIN fixture_statistics sa
            ON sa.fixture_id = f.fixture_id AND sa.is_home = 0
        WHERE f.status = 'FT'
          AND f.home_score IS NOT NULL
          AND sh.fixture_id IS NOT NULL
        """
        df = pd.read_sql_query(q, conn)
        print(f"  Birleşik tablo: {len(df)} maç (FT, stats var)")
        return df
    finally:
        conn.close()


def compute_targets(df: pd.DataFrame) -> pd.DataFrame:
    """Bahis hedeflerini hesapla."""
    df = df.copy()
    df["total_goals"] = df["home_score"] + df["away_score"]
    df["y_over25"] = (df["total_goals"] > 2.5).astype(int)
    df["y_over15"] = (df["total_goals"] > 1.5).astype(int)
    df["y_btts"] = ((df["home_score"] >= 1) & (df["away_score"] >= 1)).astype(int)
    df["y_home_win"] = (df["home_score"] > df["away_score"]).astype(int)
    df["y_draw"] = (df["home_score"] == df["away_score"]).astype(int)
    df["y_away_win"] = (df["home_score"] < df["away_score"]).astype(int)

    # Türetilmiş features (önemli)
    df["total_shots"] = df["h_shots_total"] + df["a_shots_total"]
    df["total_xg"] = df["h_xg"] + df["a_xg"]
    df["xg_diff"] = df["h_xg"] - df["a_xg"]
    df["total_corners"] = df["h_corners"] + df["a_corners"]
    df["total_cards"] = df["h_yellow"] + df["a_yellow"] + (df["h_red"] + df["a_red"]) * 2
    df["pass_dominance"] = df["h_passes_total"] / (df["a_passes_total"] + 1)
    return df


def correlation_table(df: pd.DataFrame, target_col: str = "y_over25") -> pd.DataFrame:
    """Tüm sayısal sütunların target ile Pearson korelasyonu."""
    df = df.dropna(subset=[target_col])
    num_cols = df.select_dtypes(include=[np.number]).columns
    num_cols = [c for c in num_cols if c != target_col and not c.startswith("y_")
                and not c.startswith("home_score") and not c.startswith("away_score")]

    rows = []
    for c in num_cols:
        s = df[[c, target_col]].dropna()
        if len(s) < 30:
            continue
        try:
            corr = s[c].corr(s[target_col])
            rows.append({"feature": c, "pearson_corr": corr, "n": len(s)})
        except Exception:
            pass
    return pd.DataFrame(rows).sort_values("pearson_corr",
                                            key=lambda s: s.abs(), ascending=False)


def main():
    print("=" * 70)
    print("CREATIVE EDGE v1.0 — Correlation Analysis")
    print("=" * 70)

    print("\n[1/3] Birleşik dataset yükleniyor...")
    df = load_unified_dataset()
    if df.empty:
        return

    print("\n[2/3] Target hedefleri + türetilmiş features...")
    df = compute_targets(df)
    print(f"  Toplam satır: {len(df)}")
    print(f"  Over 2.5 oranı: {df['y_over25'].mean()*100:.1f}%")
    print(f"  KG var oranı  : {df['y_btts'].mean()*100:.1f}%")
    print(f"  Ev galip oranı: {df['y_home_win'].mean()*100:.1f}%")

    print("\n[3/3] Korelasyon analizi (Over 2.5 vs tüm features)")
    print("-" * 70)
    corr_df = correlation_table(df, "y_over25")
    print("\nTOP 15 KORELASYON (Over 2.5):")
    print(corr_df.head(15).to_string(index=False))

    print("\n" + "=" * 70)
    print("KG Var korelasyonu:")
    print("-" * 70)
    corr_btts = correlation_table(df, "y_btts")
    print(corr_btts.head(10).to_string(index=False))

    print("\n" + "=" * 70)
    print("Ev galip korelasyonu:")
    print("-" * 70)
    corr_hw = correlation_table(df, "y_home_win")
    print(corr_hw.head(10).to_string(index=False))

    # CSV kaydet
    out = YAZILIM_DIR / "07_LOG_VE_RAPORLAR" / "correlation_report.csv"
    corr_df.to_csv(out, index=False)
    print(f"\nKaydedildi: {out.name}")

    # ÖZET — Creative Edge v1.0 için en güçlü features
    print("\n" + "=" * 70)
    print("CREATIVE EDGE v1.0 — Önerilen feature seti (|corr|>0.1):")
    strong = corr_df[corr_df["pearson_corr"].abs() > 0.1]
    print(strong.to_string(index=False))


if __name__ == "__main__":
    main()
