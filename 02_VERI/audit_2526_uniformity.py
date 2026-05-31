"""
2025-26 SEZON UYGUNLUK AUDIT
==============================

Trader sorusu: "2025-26 için diğer sezonlardaki bütün veri setiyle uyumlu
                bir dataset lazım. Mesela T1 bitmişti."

Audit:
  1) Her ligin son matchday tarihi (bitti mi?)
  2) Beklenen vs gerçek maç sayısı (eksik var mı?)
  3) signal_snapshots vs matches_v2 uyum (settled% farkı?)
  4) Tüm sinyaller eşit kapsamlı mı (DC lam, xG, form, A/U, KG)?
  5) Aksak yerler nerede?
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))

import database as db


# Lig başına beklenen sezon maç sayısı
LEAGUE_EXPECTED = {
    "T1": 306,   # 18 takim x 17 ev = 306
    "E0": 380,   # 20 takim x 19 ev = 380
    "D1": 306,   # 18 takim x 17 ev = 306
    "SP1": 380,
    "I1": 380,
    "F1": 306,   # F1 son 4 sezon 18 takim
}


def run():
    print("=" * 90)
    print("2025-26 SEZON UYGUNLUK AUDIT — Diger sezonlarla uyum testi")
    print("=" * 90)

    conn = db.connect()

    # === 1) Lig × Sezon coverage matrix (matches_v2) ===
    print("\n[1] matches_v2: Lig × Sezon coverage (beklenen vs gercek)")
    print("-" * 90)
    df_m2 = pd.read_sql_query("""
        SELECT league_code, season,
               COUNT(*) as n,
               SUM(is_settled) as n_settled,
               MIN(matchday) as first_md,
               MAX(matchday) as last_md
        FROM matches_v2
        GROUP BY league_code, season
        ORDER BY league_code, season
    """, conn)

    # 2025-26 odak
    df_2526 = df_m2[df_m2["season"] == "2025-26"].copy()
    print(f"\n{'Lig':<5s} {'Bekl':>5s} {'Gercek':>7s} {'Set':>5s} {'Set%':>5s} "
          f"{'Ilk':>11s} {'Son':>11s} {'Durum':>10s}")
    print("-" * 70)
    for _, r in df_2526.iterrows():
        expected = LEAGUE_EXPECTED.get(r["league_code"], 0)
        n = r["n"]
        n_set = r["n_settled"]
        set_pct = n_set / n * 100 if n else 0
        # Durum analizi
        last_md = r["last_md"]
        if set_pct >= 99:
            status = "BITTI"
        elif set_pct >= 80:
            status = "PLAYOFF"
        elif set_pct >= 50:
            status = "ORTA"
        else:
            status = "ERKEN"
        print(f"{r['league_code']:<5s} {expected:>5d} {n:>7d} {n_set:>5d} "
              f"{set_pct:>4.0f}% {r['first_md']:>11s} {last_md:>11s} {status:>10s}")

    # === 2) Eksik maçlar (eğer beklenen vs gerçek farkı varsa) ===
    print("\n[2] Eksik mac kontrolu (beklenen 38. hafta vs gercek son hafta)")
    print("-" * 90)
    for _, r in df_2526.iterrows():
        expected = LEAGUE_EXPECTED.get(r["league_code"], 0)
        if r["n"] < expected:
            print(f"  {r['league_code']}: bekl {expected}, gercek {r['n']}, "
                  f"EKSIK {expected-r['n']} mac")
        elif r["n_settled"] < expected:
            print(f"  {r['league_code']}: settled {r['n_settled']}/{expected}, "
                  f"unsetlled {r['n']-r['n_settled']} mac")
        else:
            print(f"  {r['league_code']}: TAM ({r['n']} mac, hepsi settled)")

    # === 3) signal_snapshots coverage (2526) ===
    print("\n[3] signal_snapshots vs matches_v2 — 2025-26 uyum")
    print("-" * 90)
    df_ss = pd.read_sql_query("""
        SELECT league_code,
               COUNT(*) as n_ss,
               SUM(settled) as ss_settled,
               SUM(CASE WHEN model_lam_h IS NOT NULL THEN 1 ELSE 0 END) as has_lam,
               SUM(CASE WHEN s_xg IS NOT NULL AND s_xg > 0 THEN 1 ELSE 0 END) as has_xg,
               SUM(CASE WHEN s_form IS NOT NULL AND s_form > 0 THEN 1 ELSE 0 END) as has_form,
               SUM(CASE WHEN s_anomaly IS NOT NULL AND s_anomaly > 0 THEN 1 ELSE 0 END) as has_anom,
               SUM(CASE WHEN s_shots IS NOT NULL AND s_shots > 0 THEN 1 ELSE 0 END) as has_shots,
               SUM(CASE WHEN dir_ou_model IS NOT NULL THEN 1 ELSE 0 END) as has_ou,
               SUM(CASE WHEN dir_btts_model IS NOT NULL THEN 1 ELSE 0 END) as has_btts
        FROM signal_snapshots
        WHERE source='football_data' AND season='2526'
        GROUP BY league_code
        ORDER BY league_code
    """, conn)

    print(f"\n{'Lig':<5s} {'n_ss':>5s} {'set':>5s} {'lam':>5s} {'xG':>5s} "
          f"{'form':>5s} {'anom':>5s} {'shots':>6s} {'ou':>5s} {'btts':>5s}")
    print("-" * 70)
    for _, r in df_ss.iterrows():
        print(f"{r['league_code']:<5s} {r['n_ss']:>5d} {r['ss_settled']:>5d} "
              f"{r['has_lam']:>5d} {r['has_xg']:>5d} {r['has_form']:>5d} "
              f"{r['has_anom']:>5d} {r['has_shots']:>6d} {r['has_ou']:>5d} "
              f"{r['has_btts']:>5d}")

    # === 4) Diğer sezonlarla uyum karşılaştırması ===
    print("\n[4] DIGER SEZONLARLA UYUM (lig basina ortalama coverage %)")
    print("-" * 90)
    df_uyum = pd.read_sql_query("""
        SELECT season,
               COUNT(*) as n,
               SUM(CASE WHEN model_lam_h IS NOT NULL THEN 1 ELSE 0 END)*100.0/COUNT(*) as lam_pct,
               SUM(CASE WHEN s_xg IS NOT NULL AND s_xg > 0 THEN 1 ELSE 0 END)*100.0/COUNT(*) as xg_pct,
               SUM(CASE WHEN s_form IS NOT NULL AND s_form > 0 THEN 1 ELSE 0 END)*100.0/COUNT(*) as form_pct,
               SUM(CASE WHEN s_anomaly IS NOT NULL AND s_anomaly > 0 THEN 1 ELSE 0 END)*100.0/COUNT(*) as anom_pct,
               SUM(CASE WHEN dir_ou_model IS NOT NULL THEN 1 ELSE 0 END)*100.0/COUNT(*) as ou_pct,
               SUM(CASE WHEN dir_btts_model IS NOT NULL THEN 1 ELSE 0 END)*100.0/COUNT(*) as btts_pct
        FROM signal_snapshots
        WHERE source='football_data'
        GROUP BY season
        ORDER BY season
    """, conn)

    SEASON_CONV = {
        "1718":"2017-18","1819":"2018-19","1920":"2019-20","2021":"2020-21",
        "2122":"2021-22","2223":"2022-23","2324":"2023-24","2425":"2024-25","2526":"2025-26",
    }
    df_uyum["canon"] = df_uyum["season"].astype(str).map(lambda s: SEASON_CONV.get(s, s))
    print(f"\n{'Sezon':<10s} {'n':>5s} {'lam%':>6s} {'xG%':>6s} {'form%':>7s} "
          f"{'anom%':>7s} {'OU%':>6s} {'BTTS%':>7s}")
    print("-" * 60)
    for _, r in df_uyum.iterrows():
        warning = ""
        # 2526'yi diğerleriyle karşılaştır
        if r["canon"] == "2025-26":
            warning = "  <- CANLI"
        print(f"{r['canon']:<10s} {r['n']:>5d} {r['lam_pct']:>5.0f}% "
              f"{r['xg_pct']:>5.0f}% {r['form_pct']:>6.0f}% "
              f"{r['anom_pct']:>6.0f}% {r['ou_pct']:>5.0f}% "
              f"{r['btts_pct']:>6.0f}%{warning}")

    # === 5) Aksak yerler nerede? ===
    print("\n[5] AKSAK YERLER (2526 vs ortalama)")
    print("-" * 90)
    # 2526 değerleri
    row_2526 = df_uyum[df_uyum["canon"] == "2025-26"].iloc[0] if not df_uyum[df_uyum["canon"]=="2025-26"].empty else None
    other = df_uyum[df_uyum["canon"] != "2025-26"]
    if row_2526 is not None and not other.empty:
        for col in ["lam_pct","xg_pct","form_pct","anom_pct","ou_pct","btts_pct"]:
            avg = other[col].mean()
            v_2526 = row_2526[col]
            diff = v_2526 - avg
            mark = " "
            if abs(diff) > 5:
                mark = " !! UYUMSUZ"
            elif abs(diff) > 2:
                mark = " ! Hafif fark"
            print(f"  {col:<10s}: 2526 %{v_2526:.0f}, diger ort %{avg:.0f}, "
                  f"fark {diff:+.1f}pp{mark}")

    # === 6) Per lig × pazar son durumu (2526) ===
    print("\n[6] 2526 PER-LIG × PAZAR — Sample yeterli mi?")
    print("-" * 90)
    print(f"{'Lig':<5s} {'1X2_Q5+a2':>10s} {'AU25':>6s} {'KG':>5s} {'TOPLAM':>8s}")
    print("-" * 50)
    conn.close()
    conn = db.connect()
    for lg in ["T1","E0","SP1","D1","I1","F1"]:
        # 1X2 picks (FAV_CONFIRMED + Q5 + agree2)
        n_1x2 = conn.execute("""
            SELECT COUNT(*) FROM signal_snapshots
            WHERE source='football_data' AND season='2526' AND league_code=?
              AND settled=1 AND agree_count >= 2
              AND score_v14 IS NOT NULL
        """, (lg,)).fetchone()[0]
        # AU25 sinyali
        n_ou = conn.execute("""
            SELECT COUNT(*) FROM signal_snapshots
            WHERE source='football_data' AND season='2526' AND league_code=?
              AND settled=1 AND dir_ou_model IS NOT NULL
        """, (lg,)).fetchone()[0]
        # KG
        n_kg = conn.execute("""
            SELECT COUNT(*) FROM signal_snapshots
            WHERE source='football_data' AND season='2526' AND league_code=?
              AND settled=1 AND dir_btts_model IS NOT NULL
        """, (lg,)).fetchone()[0]
        total = n_1x2 + n_ou + n_kg
        print(f"{lg:<5s} {n_1x2:>10d} {n_ou:>6d} {n_kg:>5d} {total:>8d}")

    conn.close()

    print("\n" + "=" * 90)
    print("ÖZET — 2025-26 sezon trader notu:")
    print("=" * 90)


if __name__ == "__main__":
    run()
