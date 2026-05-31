"""
MULTI-MARKET V2 — KG (Karşılıklı Gol) modeli
==============================================

Mevcut DC modelinden (model_lam_h, model_lam_a) KG olasılığı türet.
KG closing odds yok (FD CSV vermiyor) — sadece model hit rate ölç.

Yeni kolonlar:
  fp_btts_model_yes  — model olasılığı KG Var
  fp_btts_model_no   — model olasılığı KG Yok
  s_btts_model       — sinyal gücü (|model_p - 0.5| / 0.5)
  dir_btts_model     — Var / Yok / None

Test: gerçek sonuç (home_goals >= 1 AND away_goals >= 1) ile karşılaştır.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
YAZILIM = THIS_DIR.parent
sys.path.insert(0, str(THIS_DIR))
sys.path.insert(0, str(YAZILIM / "03_MODELLER"))

import database as db
from base.dixon_coles import score_matrix
from base.markets import prob_btts


EXTEND_SCHEMA = """
ALTER TABLE signal_snapshots ADD COLUMN fp_btts_model_yes REAL;
ALTER TABLE signal_snapshots ADD COLUMN fp_btts_model_no REAL;
ALTER TABLE signal_snapshots ADD COLUMN s_btts_model REAL;
ALTER TABLE signal_snapshots ADD COLUMN dir_btts_model TEXT;
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
                print(f"  ALTER err: {e}")
    conn.commit()
    conn.close()


def compute_btts_model(lam: float, mu: float, rho: float = -0.1,
                       max_goals: int = 8) -> dict:
    """DC lam,mu'den KG olasilik."""
    if lam is None or mu is None or lam <= 0 or mu <= 0:
        return {"yes": None, "no": None}
    try:
        M = score_matrix(lam=lam, mu=mu, rho=rho, max_goals=max_goals)
        p = prob_btts(M)
        return {"yes": p["yes"], "no": p["no"]}
    except Exception:
        return {"yes": None, "no": None}


def compute_signal(p_yes, threshold=0.10):
    """Model olasiligi 0.5'ten ne kadar uzak?"""
    if p_yes is None:
        return {"s": 0, "dir": None}
    deviation = p_yes - 0.5
    s = min(1.0, abs(deviation) / 0.20)  # 20pp deviation -> 1.0

    direction = None
    if deviation > threshold:
        direction = "Var"
    elif deviation < -threshold:
        direction = "Yok"

    return {"s": s if direction else 0, "dir": direction}


def run():
    print("=" * 80)
    print("MULTI-MARKET V2: KG (Karsilikli Gol) Modeli")
    print("=" * 80)

    add_columns()

    conn = db.connect()
    df = pd.read_sql_query("""
        SELECT match_uid, league_code, season, kickoff_iso,
               home_team, away_team,
               model_lam_h, model_lam_a,
               result_1x2, settled,
               home_score, away_score, ft_btts
        FROM signal_snapshots
        WHERE source='football_data'
          AND model_lam_h IS NOT NULL AND model_lam_a IS NOT NULL
    """, conn)
    print(f"\n[1] {len(df)} satir DC lam ile")

    # Compute model BTTS prob
    print(f"\n[2] DC -> KG olasilik turetiliyor...")
    df["fp_btts_yes"] = df.apply(
        lambda r: compute_btts_model(r["model_lam_h"], r["model_lam_a"])["yes"],
        axis=1
    )
    df["fp_btts_no"] = 1 - df["fp_btts_yes"]

    # Compute signal
    print(f"\n[3] Sinyal turetimi (10pp threshold)...")
    signals = df.apply(
        lambda r: compute_signal(r["fp_btts_yes"], 0.10), axis=1
    )
    df["s_btts_model"] = signals.apply(lambda x: x["s"])
    df["dir_btts_model"] = signals.apply(lambda x: x["dir"])

    # Batch UPDATE
    print(f"\n[4] Batch UPDATE: {len(df)} satir...")
    updates = []
    for _, r in df.iterrows():
        updates.append((
            float(r["fp_btts_yes"]) if pd.notna(r["fp_btts_yes"]) else None,
            float(r["fp_btts_no"]) if pd.notna(r["fp_btts_no"]) else None,
            float(r["s_btts_model"]) if pd.notna(r["s_btts_model"]) else 0,
            r["dir_btts_model"],
            r["match_uid"],
        ))
    conn.executemany("""
        UPDATE signal_snapshots
        SET fp_btts_model_yes=?, fp_btts_model_no=?,
            s_btts_model=?, dir_btts_model=?
        WHERE match_uid=? AND source='football_data'
    """, updates)
    conn.commit()

    # Stats
    n_with_sig = (df["s_btts_model"] > 0).sum()
    n_var = (df["dir_btts_model"] == "Var").sum()
    n_yok = (df["dir_btts_model"] == "Yok").sum()
    print(f"\n[5] Sinyal dagilimi:")
    print(f"    s_btts > 0:      {n_with_sig} ({n_with_sig/len(df)*100:.0f}%)")
    print(f"    Direction Var:   {n_var}")
    print(f"    Direction Yok:   {n_yok}")

    # === Hit rate ölçümü ===
    print("\n" + "=" * 80)
    print(">>> KG MODEL HIT RATE (settled only)")
    print("=" * 80)

    df_set = df[df["settled"] == 1].copy()
    # Actual BTTS
    df_set["btts_actual"] = (
        (df_set["home_score"] > 0) & (df_set["away_score"] > 0)
    ).astype(int)

    # Sinyal var olan picks
    df_sig = df_set[df_set["dir_btts_model"].notna()].copy()
    df_sig["won"] = df_sig.apply(
        lambda r: (r["dir_btts_model"] == "Var" and r["btts_actual"] == 1)
                or (r["dir_btts_model"] == "Yok" and r["btts_actual"] == 0),
        axis=1
    )
    print(f"  Sinyal var (settled): {len(df_sig)}")

    # Lig x yön hit rate
    print(f"\n{'Lig':<5s} {'Yon':<6s} {'n':>5s} {'hit%':>6s} {'baseline':>9s} {'edge':>8s}")
    print("-" * 50)
    for lg in ["T1","E0","SP1","D1","I1","F1"]:
        for direction in ["Var", "Yok"]:
            sub = df_sig[(df_sig["league_code"]==lg) & (df_sig["dir_btts_model"]==direction)]
            if len(sub) < 30: continue
            n = len(sub); won = sub["won"].sum()
            hit = won/n
            # Baseline: ortalama BTTS rate per league
            base_all = df_set[df_set["league_code"]==lg]["btts_actual"].mean()
            base = base_all if direction == "Var" else (1 - base_all)
            edge_pp = (hit - base) * 100
            print(f"{lg:<5s} {direction:<6s} {n:>5d} {hit*100:>5.0f}% "
                  f"{base*100:>8.1f}% {edge_pp:>+7.2f}")

    # Tüm 6 lig özet
    print(f"\n>>> TUM 6 LIG (yön bağımsız):")
    for direction in ["Var", "Yok"]:
        sub = df_sig[df_sig["dir_btts_model"] == direction]
        n = len(sub)
        if n >= 50:
            won = sub["won"].sum()
            hit = won/n
            print(f"  {direction}: n={n}, hit %{hit*100:.0f}")

    # Q5 + agree (klasik sinyallerle birleştir)
    # KG modeli kendisi bir sinyal - ne kadar kalibre?
    print(f"\n>>> MODEL CONFIDENCE BANDS:")
    print(f"  {'p_yes range':<14s} {'n':>5s} {'actual%':>9s} {'gap':>8s}")
    for lo, hi in [(0.30, 0.40), (0.40, 0.45), (0.45, 0.50),
                   (0.50, 0.55), (0.55, 0.60), (0.60, 0.70), (0.70, 0.85)]:
        mask = (df_set["fp_btts_yes"] >= lo) & (df_set["fp_btts_yes"] < hi)
        n = mask.sum()
        if n < 100: continue
        avg_p = df_set.loc[mask, "fp_btts_yes"].mean()
        actual = df_set.loc[mask, "btts_actual"].mean()
        gap = actual - avg_p
        print(f"  [{lo:.2f}-{hi:.2f})   {n:>5d}   {avg_p*100:>5.1f}%   "
              f"{actual*100:>5.1f}%   {gap*100:>+5.1f}pp")

    conn.close()

    # Rapor
    rapor = ["# Multi-Market V2 — KG (Karsilikli Gol) Modeli\n"]
    rapor.append(f"**Tarih:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n\n")
    rapor.append(f"**Sample:** {len(df)} satir DC lam ile, {len(df_sig)} sinyal\n\n")
    rapor.append("## NOT: KG icin Closing Odds Yok\n\n")
    rapor.append("Football-Data CSV'de BTS yok. Sadece model hit rate olcumu yapildi.\n")
    rapor.append("Production icin iddaa.com KG odds scraper gerekli.\n\n")
    rapor.append("## Lig x Yon Hit Rate\n\n")
    rapor.append("| Lig | Yon | n | hit% | baseline | edge_pp |\n")
    rapor.append("|---|---|---|---|---|---|\n")
    for lg in ["T1","E0","SP1","D1","I1","F1"]:
        for direction in ["Var", "Yok"]:
            sub = df_sig[(df_sig["league_code"]==lg) & (df_sig["dir_btts_model"]==direction)]
            if len(sub) < 30: continue
            n = len(sub); won = sub["won"].sum()
            hit = won/n
            base_all = df_set[df_set["league_code"]==lg]["btts_actual"].mean()
            base = base_all if direction == "Var" else (1 - base_all)
            edge_pp = (hit - base) * 100
            rapor.append(f"| {lg} | {direction} | {n} | {hit*100:.0f}% | "
                         f"{base*100:.0f}% | {edge_pp:+.2f}pp |\n")
    out = YAZILIM / "RAPOR" / "V2_MULTIMARKET_BTTS.md"
    out.write_text("".join(rapor), encoding="utf-8")
    print(f"\n[OK] Rapor: {out}")


if __name__ == "__main__":
    run()
