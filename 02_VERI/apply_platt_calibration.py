"""
PLATT KALIBRASYON — KG + A/Ü modelleri için
=============================================

Sorun:
  KG model: model_p_yes 0.30-0.40 bandında gerçek %52 (+%14 underestimate)
  A/Ü model: >%20 edge bandında overconfident

Çözüm:
  Platt scaling: sigmoid kalibrasyon
    p_calibrated = 1 / (1 + exp(A * p_raw + B))
  Train: settled sample üzerinde A, B optimize
  Apply: signal_snapshots'a yeni kalibre kolon ekle

Yeni kolonlar:
  fp_btts_model_yes_cal  — Platt-kalibre KG prob
  fp_ou_model_over_cal   — Platt-kalibre A/Ü prob

Sonra:
  fp_*_cal kullanarak sinyal yeniden hesapla.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))

import database as db


EXTEND_SCHEMA = """
ALTER TABLE signal_snapshots ADD COLUMN fp_btts_model_yes_cal REAL;
ALTER TABLE signal_snapshots ADD COLUMN fp_btts_model_no_cal REAL;
ALTER TABLE signal_snapshots ADD COLUMN fp_ou_model_over_cal REAL;
ALTER TABLE signal_snapshots ADD COLUMN fp_ou_model_under_cal REAL;
ALTER TABLE signal_snapshots ADD COLUMN s_ou_model_cal REAL;
ALTER TABLE signal_snapshots ADD COLUMN dir_ou_model_cal TEXT;
ALTER TABLE signal_snapshots ADD COLUMN s_btts_model_cal REAL;
ALTER TABLE signal_snapshots ADD COLUMN dir_btts_model_cal TEXT;
"""


def add_columns():
    conn = db.connect()
    for stmt in EXTEND_SCHEMA.strip().split(";"):
        stmt = stmt.strip()
        if not stmt: continue
        try:
            conn.execute(stmt)
        except Exception as e:
            if "duplicate column" not in str(e).lower():
                print(f"  err: {e}")
    conn.commit()
    conn.close()


def platt_fit(p_raw: np.ndarray, y_actual: np.ndarray) -> tuple[float, float]:
    """
    Platt scaling: A, B parametrelerini optimize et.
    p_calibrated = 1 / (1 + exp(A * p_raw + B))

    Args:
        p_raw: Modelin verdigi ham olasilik (0-1)
        y_actual: Gercek sonuc 0 veya 1
    Returns:
        (A, B) optimized
    """
    # Clip p_raw to avoid log(0)
    p_raw = np.clip(p_raw, 1e-6, 1 - 1e-6)

    def neg_log_likelihood(params):
        A, B = params
        p_cal = 1.0 / (1.0 + np.exp(A * p_raw + B))
        p_cal = np.clip(p_cal, 1e-15, 1 - 1e-15)
        ll = y_actual * np.log(p_cal) + (1 - y_actual) * np.log(1 - p_cal)
        return -np.sum(ll)

    # Initial: A=-1 (negatif eğim mantıklı), B=0
    result = minimize(neg_log_likelihood, x0=[-1.0, 0.0],
                     method="Nelder-Mead", options={"maxiter": 1000})
    return float(result.x[0]), float(result.x[1])


def platt_apply(p_raw: np.ndarray, A: float, B: float) -> np.ndarray:
    """Platt kalibrasyonu uygula."""
    p_raw = np.clip(p_raw, 1e-6, 1 - 1e-6)
    return 1.0 / (1.0 + np.exp(A * p_raw + B))


# ============================================================
# KG (BTTS) Kalibrasyon
# ============================================================

def calibrate_btts():
    print("\n" + "=" * 60)
    print("KG (BTTS) PLATT KALIBRASYON")
    print("=" * 60)

    conn = db.connect()
    df = pd.read_sql_query("""
        SELECT match_uid, league_code, fp_btts_model_yes,
               home_score, away_score, settled
        FROM signal_snapshots
        WHERE source='football_data' AND settled=1
          AND fp_btts_model_yes IS NOT NULL
          AND home_score IS NOT NULL AND away_score IS NOT NULL
    """, conn)
    conn.close()

    df["btts_actual"] = ((df["home_score"] > 0) & (df["away_score"] > 0)).astype(int)
    df = df[df["fp_btts_model_yes"].between(0.01, 0.99)]

    print(f"Train sample: {len(df)} settled mac")

    # Train ALL leagues (global Platt)
    A, B = platt_fit(df["fp_btts_model_yes"].values, df["btts_actual"].values)
    print(f"Platt params (global KG): A={A:.4f}, B={B:.4f}")

    # Save per league - kalibrasyon bant bant farkli olabilir
    league_params = {"_global": (A, B)}
    for lg in ["T1","E0","SP1","D1","I1","F1"]:
        sub = df[df["league_code"] == lg]
        if len(sub) >= 100:
            A_lg, B_lg = platt_fit(sub["fp_btts_model_yes"].values,
                                  sub["btts_actual"].values)
            league_params[lg] = (A_lg, B_lg)
            print(f"  {lg}: A={A_lg:.4f}, B={B_lg:.4f} (n={len(sub)})")

    # Calibrate all (per league + fallback global)
    print(f"\nUygulama: signal_snapshots UPDATE...")
    conn = db.connect()
    df_all = pd.read_sql_query("""
        SELECT match_uid, league_code, fp_btts_model_yes
        FROM signal_snapshots
        WHERE source='football_data' AND fp_btts_model_yes IS NOT NULL
    """, conn)

    updates = []
    for _, r in df_all.iterrows():
        A_lg, B_lg = league_params.get(r["league_code"], league_params["_global"])
        p_cal = platt_apply(np.array([r["fp_btts_model_yes"]]), A_lg, B_lg)[0]
        updates.append((float(p_cal), float(1-p_cal), r["match_uid"]))

    conn.executemany("""
        UPDATE signal_snapshots
        SET fp_btts_model_yes_cal=?, fp_btts_model_no_cal=?
        WHERE match_uid=? AND source='football_data'
    """, updates)
    conn.commit()
    print(f"  {len(updates)} satir kalibre edildi")

    # Yeni sinyal hesapla (yön + güç)
    df_cal = pd.read_sql_query("""
        SELECT match_uid, fp_btts_model_yes_cal
        FROM signal_snapshots
        WHERE source='football_data' AND fp_btts_model_yes_cal IS NOT NULL
    """, conn)

    updates2 = []
    for _, r in df_cal.iterrows():
        p_yes = r["fp_btts_model_yes_cal"]
        dev = p_yes - 0.5
        s = min(1.0, abs(dev) / 0.20)
        direction = None
        if dev > 0.10: direction = "Var"
        elif dev < -0.10: direction = "Yok"
        updates2.append((float(s if direction else 0), direction, r["match_uid"]))
    conn.executemany("""
        UPDATE signal_snapshots
        SET s_btts_model_cal=?, dir_btts_model_cal=?
        WHERE match_uid=? AND source='football_data'
    """, updates2)
    conn.commit()

    # === Reliability check (after calibration) ===
    print(f"\nKalibrasyon SONRASI reliability:")
    df_test = pd.read_sql_query("""
        SELECT fp_btts_model_yes_cal, home_score, away_score
        FROM signal_snapshots
        WHERE source='football_data' AND settled=1
          AND fp_btts_model_yes_cal IS NOT NULL
          AND home_score IS NOT NULL
    """, conn)
    df_test["btts_actual"] = ((df_test["home_score"]>0) & (df_test["away_score"]>0)).astype(int)
    print(f"  {'Bant':<14s} {'n':>5s} {'avg_p':>7s} {'actual':>7s} {'gap':>8s}")
    for lo, hi in [(0.30,0.40),(0.40,0.45),(0.45,0.50),(0.50,0.55),
                   (0.55,0.60),(0.60,0.70),(0.70,0.85)]:
        mask = (df_test["fp_btts_model_yes_cal"] >= lo) & (df_test["fp_btts_model_yes_cal"] < hi)
        n = mask.sum()
        if n < 100: continue
        avg_p = df_test.loc[mask, "fp_btts_model_yes_cal"].mean()
        actual = df_test.loc[mask, "btts_actual"].mean()
        gap = actual - avg_p
        marker = " <- ok" if abs(gap) < 0.03 else " <- gap"
        print(f"  [{lo:.2f}-{hi:.2f})  {n:>5d}  {avg_p*100:>5.1f}%  "
              f"{actual*100:>5.1f}%  {gap*100:>+5.1f}pp{marker}")

    conn.close()
    return league_params


# ============================================================
# A/U 2.5 Kalibrasyon
# ============================================================

def calibrate_ou_25():
    print("\n" + "=" * 60)
    print("A/U 2.5 PLATT KALIBRASYON")
    print("=" * 60)

    conn = db.connect()
    df = pd.read_sql_query("""
        SELECT match_uid, league_code, fp_ou_model_over,
               odd_over25, odd_under25,
               home_score, away_score, settled
        FROM signal_snapshots
        WHERE source='football_data' AND settled=1
          AND fp_ou_model_over IS NOT NULL
          AND home_score IS NOT NULL
    """, conn)
    conn.close()

    df["over_actual"] = ((df["home_score"] + df["away_score"]) > 2).astype(int)
    df = df[df["fp_ou_model_over"].between(0.01, 0.99)]

    print(f"Train sample: {len(df)} settled mac")

    A, B = platt_fit(df["fp_ou_model_over"].values, df["over_actual"].values)
    print(f"Platt params (global OU): A={A:.4f}, B={B:.4f}")

    league_params = {"_global": (A, B)}
    for lg in ["T1","E0","SP1","D1","I1","F1"]:
        sub = df[df["league_code"] == lg]
        if len(sub) >= 100:
            A_lg, B_lg = platt_fit(sub["fp_ou_model_over"].values,
                                  sub["over_actual"].values)
            league_params[lg] = (A_lg, B_lg)
            print(f"  {lg}: A={A_lg:.4f}, B={B_lg:.4f} (n={len(sub)})")

    # Apply
    print(f"\nUygulama: signal_snapshots UPDATE...")
    conn = db.connect()
    df_all = pd.read_sql_query("""
        SELECT match_uid, league_code, fp_ou_model_over,
               odd_over25, odd_under25
        FROM signal_snapshots
        WHERE source='football_data' AND fp_ou_model_over IS NOT NULL
    """, conn)

    updates = []
    for _, r in df_all.iterrows():
        A_lg, B_lg = league_params.get(r["league_code"], league_params["_global"])
        p_cal = platt_apply(np.array([r["fp_ou_model_over"]]), A_lg, B_lg)[0]

        # New direction + signal strength
        odd_o = r["odd_over25"]; odd_u = r["odd_under25"]
        s = 0; direction = None
        if pd.notna(odd_o) and pd.notna(odd_u):
            imp_o = 1.0/odd_o; imp_u = 1.0/odd_u
            s_total = imp_o + imp_u
            market_p_over = imp_o / s_total
            edge = p_cal - market_p_over
            s = min(1.0, abs(edge) / 0.10)
            if edge > 0.05: direction = "Over"
            elif edge < -0.05: direction = "Under"

        updates.append((
            float(p_cal), float(1-p_cal),
            float(s if direction else 0), direction,
            r["match_uid"]
        ))

    conn.executemany("""
        UPDATE signal_snapshots
        SET fp_ou_model_over_cal=?, fp_ou_model_under_cal=?,
            s_ou_model_cal=?, dir_ou_model_cal=?
        WHERE match_uid=? AND source='football_data'
    """, updates)
    conn.commit()
    print(f"  {len(updates)} satir kalibre edildi")

    # Reliability check
    print(f"\nKalibrasyon SONRASI reliability (A/U Over):")
    df_test = pd.read_sql_query("""
        SELECT fp_ou_model_over_cal, home_score, away_score
        FROM signal_snapshots
        WHERE source='football_data' AND settled=1
          AND fp_ou_model_over_cal IS NOT NULL
          AND home_score IS NOT NULL
    """, conn)
    df_test["over_actual"] = ((df_test["home_score"]+df_test["away_score"]) > 2).astype(int)
    print(f"  {'Bant':<14s} {'n':>5s} {'avg_p':>7s} {'actual':>7s} {'gap':>8s}")
    for lo, hi in [(0.30,0.40),(0.40,0.45),(0.45,0.50),(0.50,0.55),
                   (0.55,0.60),(0.60,0.70),(0.70,0.85)]:
        mask = (df_test["fp_ou_model_over_cal"] >= lo) & (df_test["fp_ou_model_over_cal"] < hi)
        n = mask.sum()
        if n < 100: continue
        avg_p = df_test.loc[mask, "fp_ou_model_over_cal"].mean()
        actual = df_test.loc[mask, "over_actual"].mean()
        gap = actual - avg_p
        marker = " <- ok" if abs(gap) < 0.03 else " <- gap"
        print(f"  [{lo:.2f}-{hi:.2f})  {n:>5d}  {avg_p*100:>5.1f}%  "
              f"{actual*100:>5.1f}%  {gap*100:>+5.1f}pp{marker}")

    conn.close()
    return league_params


# ============================================================
# Yeni Q5+a2 testleri (kalibre edilmiş ile)
# ============================================================

def test_calibrated_picks():
    print("\n" + "=" * 60)
    print("KALIBRE EDILMIS Q5+a2 TESTLERI (yeni vs eski)")
    print("=" * 60)

    conn = db.connect()
    df = pd.read_sql_query("""
        SELECT league_code, dir_btts_model_cal, dir_ou_model_cal,
               s_btts_model_cal, s_ou_model_cal,
               home_score, away_score, settled,
               odd_over25, odd_under25
        FROM signal_snapshots
        WHERE source='football_data' AND settled=1
    """, conn)
    conn.close()

    df["btts_actual"] = ((df["home_score"]>0) & (df["away_score"]>0)).astype(int)
    df["over_actual"] = ((df["home_score"]+df["away_score"])>2).astype(int)

    # KG calibrated per lig
    print("\n[KG] Kalibre edilmiş sonuçlar:")
    print(f"  {'Lig':<5s} {'Yon':<5s} {'n':>5s} {'hit%':>6s}")
    for lg in ["T1","E0","SP1","D1","I1","F1"]:
        for d in ["Var", "Yok"]:
            sub = df[(df["league_code"]==lg) & (df["dir_btts_model_cal"]==d)]
            if len(sub) < 30: continue
            n = len(sub)
            if d == "Var":
                won = sub["btts_actual"].sum()
            else:
                won = (1-sub["btts_actual"]).sum()
            hit = won/n
            print(f"  {lg:<5s} {d:<5s} {n:>5d} {hit*100:>5.0f}%")

    # OU calibrated
    print("\n[A/U 2.5] Kalibre edilmiş sonuçlar:")
    print(f"  {'Lig':<5s} {'Yon':<7s} {'n':>5s} {'hit%':>6s} {'avg_odd':>8s} {'edge_pp':>8s}")
    for lg in ["T1","E0","SP1","D1","I1","F1"]:
        for d in ["Over", "Under"]:
            sub = df[(df["league_code"]==lg) & (df["dir_ou_model_cal"]==d)]
            if len(sub) < 30: continue
            n = len(sub)
            if d == "Over":
                won = sub["over_actual"].sum()
                avg_odd = sub["odd_over25"].mean()
            else:
                won = (1-sub["over_actual"]).sum()
                avg_odd = sub["odd_under25"].mean()
            hit = won/n
            edge_pp = (hit - 1/avg_odd)*100 if avg_odd else 0
            print(f"  {lg:<5s} {d:<7s} {n:>5d} {hit*100:>5.0f}% "
                  f"{avg_odd:>7.2f} {edge_pp:>+7.2f}")


def run():
    print("=" * 60)
    print("PLATT KALIBRASYON — KG + A/U 2.5")
    print("=" * 60)

    add_columns()
    calibrate_btts()
    calibrate_ou_25()
    test_calibrated_picks()


if __name__ == "__main__":
    run()
