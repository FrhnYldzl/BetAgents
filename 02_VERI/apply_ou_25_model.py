"""
MULTI-MARKET V2 — A/Ü 2.5 model entegrasyon
==============================================

Mevcut DC modelinden (model_lam_h, model_lam_a) A/Ü 2.5 olasılığı türet,
market closing odds ile karşılaştır, edge tespit et.

Yeni kolonlar:
  fp_ou_model_over    — model olasılığı Üst
  fp_ou_model_under   — model olasılığı Alt
  s_ou_model          — |edge| sinyal gücü
  dir_ou_model        — Over / Under / None

Q5+a2 sniper için A/Ü pazarında benzer hit rate olcumu.
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
from base.markets import prob_over_under


EXTEND_SCHEMA = """
ALTER TABLE signal_snapshots ADD COLUMN fp_ou_model_over REAL;
ALTER TABLE signal_snapshots ADD COLUMN fp_ou_model_under REAL;
ALTER TABLE signal_snapshots ADD COLUMN s_ou_model REAL;
ALTER TABLE signal_snapshots ADD COLUMN dir_ou_model TEXT;
ALTER TABLE signal_snapshots ADD COLUMN ou_model_edge REAL;
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


def compute_ou_model(lam: float, mu: float, rho: float = -0.1,
                    threshold: float = 2.5, max_goals: int = 8) -> dict:
    """DC lam,μ'den A/Ü olasılığı türet."""
    if lam is None or mu is None or lam <= 0 or mu <= 0:
        return {"over": None, "under": None}
    try:
        M = score_matrix(lam=lam, mu=mu, rho=rho, max_goals=max_goals)
        p = prob_over_under(M, threshold)
        return {"over": p["over"], "under": p["under"]}
    except Exception:
        return {"over": None, "under": None}


def compute_signal(model_p_over, market_odd_over, market_odd_under,
                   edge_threshold=0.05):
    """Model vs market karşılaştır, sinyal türet."""
    if model_p_over is None or market_odd_over is None or market_odd_under is None:
        return {"s_ou": 0, "dir_ou": None, "edge": None}
    if market_odd_over <= 1.0 or market_odd_under <= 1.0:
        return {"s_ou": 0, "dir_ou": None, "edge": None}
    # De-vigged market prob
    imp_over = 1.0 / market_odd_over
    imp_under = 1.0 / market_odd_under
    s = imp_over + imp_under
    market_p_over = imp_over / s

    edge = model_p_over - market_p_over

    # Sinyal: |edge| büyükse sinyal var
    s_ou = min(1.0, abs(edge) / 0.10)  # 10pp edge → 1.0

    direction = None
    if edge > edge_threshold:
        direction = "Over"
    elif edge < -edge_threshold:
        direction = "Under"

    return {"s_ou": s_ou if direction else 0,
            "dir_ou": direction, "edge": edge,
            "market_p_over": market_p_over}


def run():
    print("=" * 80)
    print("MULTI-MARKET V2: A/Ü 2.5 Model Entegrasyon")
    print("=" * 80)

    add_columns()

    conn = db.connect()
    df = pd.read_sql_query("""
        SELECT match_uid, league_code, season, kickoff_iso,
               home_team, away_team,
               model_lam_h, model_lam_a,
               odd_over25, odd_under25,
               result_1x2, settled,
               home_score, away_score
        FROM signal_snapshots
        WHERE source='football_data'
          AND model_lam_h IS NOT NULL AND model_lam_a IS NOT NULL
    """, conn)
    print(f"\n[1] {len(df)} satir DC lam ile (settled+unsettled)")

    # Compute model OU prob
    print(f"\n[2] DC -> A/U 2.5 olasilik turetiliyor...")
    df["fp_ou_over"] = df.apply(
        lambda r: compute_ou_model(r["model_lam_h"], r["model_lam_a"])["over"],
        axis=1
    )
    df["fp_ou_under"] = 1 - df["fp_ou_over"]

    # Compute signal
    print(f"\n[3] Market karsilastirma + sinyal turetimi...")
    signals = df.apply(
        lambda r: compute_signal(r["fp_ou_over"], r["odd_over25"], r["odd_under25"]),
        axis=1
    )
    df["s_ou_model"] = signals.apply(lambda x: x["s_ou"])
    df["dir_ou_model"] = signals.apply(lambda x: x["dir_ou"])
    df["ou_model_edge"] = signals.apply(lambda x: x["edge"])

    # Batch UPDATE
    print(f"\n[4] Batch UPDATE: {len(df)} satir...")
    updates = []
    for _, r in df.iterrows():
        updates.append((
            float(r["fp_ou_over"]) if pd.notna(r["fp_ou_over"]) else None,
            float(r["fp_ou_under"]) if pd.notna(r["fp_ou_under"]) else None,
            float(r["s_ou_model"]) if pd.notna(r["s_ou_model"]) else 0,
            r["dir_ou_model"],
            float(r["ou_model_edge"]) if pd.notna(r["ou_model_edge"]) else None,
            r["match_uid"],
        ))
    conn.executemany("""
        UPDATE signal_snapshots
        SET fp_ou_model_over=?, fp_ou_model_under=?,
            s_ou_model=?, dir_ou_model=?, ou_model_edge=?
        WHERE match_uid=? AND source='football_data'
    """, updates)
    conn.commit()

    # Stats
    n_with_sig = df["s_ou_model"].apply(lambda x: x > 0).sum()
    n_over = (df["dir_ou_model"] == "Over").sum()
    n_under = (df["dir_ou_model"] == "Under").sum()
    print(f"\n[5] Sinyal dagilimi:")
    print(f"    s_ou > 0:      {n_with_sig} ({n_with_sig/len(df)*100:.0f}%)")
    print(f"    Direction Over: {n_over}")
    print(f"    Direction Under:{n_under}")

    # === Hit rate ölçümü ===
    print("\n" + "=" * 80)
    print(">>> A/Ü 2.5 MODEL HIT RATE — Q5 quintile (settled only)")
    print("=" * 80)

    # Sadece settled için
    df_set = df[df["settled"] == 1].copy()
    df_set["total_goals"] = df_set["home_score"].fillna(0) + df_set["away_score"].fillna(0)
    df_set["over_actual"] = (df_set["total_goals"] > 2).astype(int)
    df_set["won"] = df_set.apply(
        lambda r: (r["dir_ou_model"] == "Over" and r["over_actual"] == 1)
                or (r["dir_ou_model"] == "Under" and r["over_actual"] == 0),
        axis=1
    )
    df_set["odd"] = df_set.apply(
        lambda r: r["odd_over25"] if r["dir_ou_model"]=="Over"
                  else r["odd_under25"] if r["dir_ou_model"]=="Under"
                  else None,
        axis=1
    )

    df_sig = df_set[df_set["dir_ou_model"].notna() & df_set["odd"].notna()].copy()
    if df_sig.empty:
        print("  (sinyal yok)")
        return
    print(f"  Sinyal var (settled): {len(df_sig)}")

    # Lig × yön matrix
    print(f"\n{'Lig':<5s} {'Yon':<6s} {'n':>5s} {'hit%':>5s} {'avg_odd':>8s} {'edge_pp':>8s}")
    print("-" * 50)
    for lg in ["T1","E0","SP1","D1","I1","F1"]:
        for direction in ["Over", "Under"]:
            sub = df_sig[(df_sig["league_code"]==lg) & (df_sig["dir_ou_model"]==direction)]
            if len(sub) < 30: continue
            n = len(sub); won = sub["won"].sum()
            hit = won/n
            avg_odd = sub["odd"].mean()
            breakeven = 1/avg_odd
            edge_pp = (hit - breakeven)*100
            print(f"{lg:<5s} {direction:<6s} {n:>5d} {hit*100:>4.0f}% "
                  f"{avg_odd:>7.2f} {edge_pp:>+7.2f}")

    # Tüm 6 lig, yön bağımsız
    print(f"\n>>> TUM 6 LIG (yön bağımsız):")
    for direction in ["Over", "Under"]:
        sub = df_sig[df_sig["dir_ou_model"] == direction]
        if len(sub) >= 50:
            n = len(sub); won = sub["won"].sum()
            hit = won/n
            avg_odd = sub["odd"].mean()
            edge_pp = (hit - 1/avg_odd)*100
            print(f"  {direction}: n={n}, hit %{hit*100:.0f}, "
                  f"avg_odd {avg_odd:.2f}, edge {edge_pp:+.2f}pp")

    # Quintile analizi (edge gücüne göre)
    print(f"\n>>> Edge magnitude bins:")
    try:
        df_sig["abs_edge"] = df_sig["ou_model_edge"].abs()
        for lo, hi in [(0.05, 0.08), (0.08, 0.12), (0.12, 0.20), (0.20, 1.0)]:
            sub = df_sig[(df_sig["abs_edge"] >= lo) & (df_sig["abs_edge"] < hi)]
            if len(sub) < 30: continue
            n = len(sub); won = sub["won"].sum()
            hit = won/n
            avg_odd = sub["odd"].mean()
            edge_pp = (hit - 1/avg_odd)*100
            print(f"  edge [{lo:.2f}-{hi:.2f}): n={n}, hit %{hit*100:.0f}, "
                  f"avg_odd {avg_odd:.2f}, market-edge {edge_pp:+.2f}pp")
    except Exception as e:
        print(f"  err: {e}")

    conn.close()

    # Markdown rapor
    rapor = ["# Multi-Market V2 — A/Ü 2.5 Hit Rate Sonuçları\n"]
    rapor.append(f"**Tarih:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n\n")
    rapor.append(f"**Sample:** {len(df)} satir DC lam ile, {len(df_sig)} sinyal var (settled)\n\n")
    rapor.append("## Lig × Yön Hit Rate\n\n")
    rapor.append("| Lig | Yön | n | hit% | avg_odd | edge_pp |\n")
    rapor.append("|---|---|---|---|---|---|\n")
    for lg in ["T1","E0","SP1","D1","I1","F1"]:
        for direction in ["Over", "Under"]:
            sub = df_sig[(df_sig["league_code"]==lg) & (df_sig["dir_ou_model"]==direction)]
            if len(sub) < 30: continue
            n = len(sub); won = sub["won"].sum()
            hit = won/n
            avg_odd = sub["odd"].mean()
            edge_pp = (hit - 1/avg_odd)*100
            rapor.append(f"| {lg} | {direction} | {n} | {hit*100:.0f}% | "
                         f"{avg_odd:.2f} | {edge_pp:+.2f}pp |\n")
    out = YAZILIM / "RAPOR" / "V2_MULTIMARKET_OU25.md"
    out.write_text("".join(rapor), encoding="utf-8")
    print(f"\n[OK] Rapor: {out}")


if __name__ == "__main__":
    run()
