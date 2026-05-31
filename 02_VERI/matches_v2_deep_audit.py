"""
matches_v2 DEEP AUDIT — Yeni 19K'da hangi alanlar ne kadar zengin?
====================================================================

Soru: Yeni 19K matches_v2 üzerinde model+data iyileştirme için
       hangi alanda ne kadar boşluk var?

Audit kategorileri:
  1) Lig × Sezon coverage matrisi (sample yoğunluğu)
  2) Sinyal alanları:
     - has_full_odds (1X2 closing)
     - has_opening_odds (B365 opening)
     - has_xg (Understat xG)
     - has_match_stats (shots, corners, cards, referee)
     - has_clv (computed CLV)
     - opening/closing A/Ü 2.5
  3) Yeni eklenen sezonlar (2017-2021) ne sağlıyor?
  4) Hangi modüller hazır, hangi data eksik?

Bu audit, "büyük adım nereye?" sorusunun cevabıdır.
"""
from __future__ import annotations

import sys
import sqlite3
from pathlib import Path

import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))
import database as db


def run():
    print("=" * 90)
    print("matches_v2 DEEP AUDIT — Data + Model iyileştirme seçenekleri")
    print("=" * 90)

    conn = db.connect()

    # === 1) LIG × SEZON COVERAGE ===
    print("\n" + "-" * 90)
    print(">>> 1) LIG × SEZON COVERAGE MATRİSİ")
    print("-" * 90)
    df = pd.read_sql_query("""
        SELECT league_code, season,
               COUNT(*) as n_total,
               SUM(is_settled) as n_settled,
               SUM(has_full_odds) as n_closing,
               SUM(has_opening_odds) as n_opening,
               SUM(has_xg) as n_xg,
               SUM(has_match_stats) as n_stats,
               SUM(has_clv) as n_clv
        FROM matches_v2
        GROUP BY league_code, season
        ORDER BY league_code, season
    """, conn)

    print(f"\n{'Lig':<5s} {'Sezon':<10s} {'n':>5s} {'set%':>5s} {'odd%':>5s} {'open%':>6s} "
          f"{'xG%':>5s} {'stat%':>6s} {'CLV%':>5s}")
    print("-" * 75)
    for _, r in df.iterrows():
        n = r['n_total']
        sett = r['n_settled'] / n * 100 if n else 0
        clos = r['n_closing'] / n * 100 if n else 0
        open_ = r['n_opening'] / n * 100 if n else 0
        xg = r['n_xg'] / n * 100 if n else 0
        stat = r['n_stats'] / n * 100 if n else 0
        clv = r['n_clv'] / n * 100 if n else 0
        print(f"{r['league_code']:<5s} {r['season']:<10s} {n:>5d} "
              f"{sett:>4.0f}% {clos:>4.0f}% {open_:>5.0f}% "
              f"{xg:>4.0f}% {stat:>5.0f}% {clv:>4.0f}%")

    # === 2) PER-LIG ÖZET ===
    print("\n" + "-" * 90)
    print(">>> 2) PER-LIG ÖZET (hangi lig hangi alanda zengin?)")
    print("-" * 90)
    df_lig = pd.read_sql_query("""
        SELECT league_code,
               COUNT(*) as n_total,
               SUM(is_settled) as n_settled,
               SUM(has_full_odds) as n_closing,
               SUM(has_opening_odds) as n_opening,
               SUM(has_xg) as n_xg,
               SUM(has_match_stats) as n_stats,
               SUM(has_clv) as n_clv,
               AVG(quality_score) as avg_q
        FROM matches_v2
        GROUP BY league_code
        ORDER BY league_code
    """, conn)
    print(f"\n{'Lig':<5s} {'n':>6s} {'odd%':>5s} {'xG%':>5s} {'stat%':>6s} {'CLV%':>5s} {'avg_q':>6s}")
    print("-" * 50)
    for _, r in df_lig.iterrows():
        print(f"{r['league_code']:<5s} {r['n_total']:>6d} "
              f"{r['n_closing']/r['n_total']*100:>4.0f}% "
              f"{r['n_xg']/r['n_total']*100:>4.0f}% "
              f"{r['n_stats']/r['n_total']*100:>5.0f}% "
              f"{r['n_clv']/r['n_total']*100:>4.0f}% "
              f"{r['avg_q']:>5.2f}")

    # === 3) YENİ 4 SEZON ÖZEL ANALİZ ===
    print("\n" + "-" * 90)
    print(">>> 3) YENİ 4 SEZON (2017-2021) — Detaylı Analiz")
    print("-" * 90)
    new_seasons = ['2017-18', '2018-19', '2019-20', '2020-21']
    df_new = pd.read_sql_query(f"""
        SELECT league_code, season,
               COUNT(*) as n,
               SUM(has_full_odds) as n_closing,
               SUM(has_opening_odds) as n_opening,
               SUM(has_xg) as n_xg,
               SUM(has_match_stats) as n_stats,
               SUM(has_clv) as n_clv
        FROM matches_v2
        WHERE season IN ('2017-18','2018-19','2019-20','2020-21')
        GROUP BY league_code, season
        ORDER BY league_code, season
    """, conn)
    print(f"\n{'Lig':<5s} {'Sezon':<10s} {'n':>5s} {'odd':>4s} {'open':>5s} "
          f"{'xG':>4s} {'stat':>5s} {'CLV':>4s}")
    print("-" * 60)
    for _, r in df_new.iterrows():
        print(f"{r['league_code']:<5s} {r['season']:<10s} {r['n']:>5d} "
              f"{r['n_closing']:>4d} {r['n_opening']:>5d} "
              f"{r['n_xg']:>4d} {r['n_stats']:>5d} {r['n_clv']:>4d}")

    # === 4) KRITIK EKSİKLİKLER ===
    print("\n" + "-" * 90)
    print(">>> 4) KRİTİK EKSİKLİKLER (model iyileştirme alanları)")
    print("-" * 90)

    # T1 xG
    n_t1 = conn.execute("SELECT COUNT(*) FROM matches_v2 WHERE league_code='T1'").fetchone()[0]
    n_t1_xg = conn.execute("SELECT COUNT(*) FROM matches_v2 WHERE league_code='T1' AND has_xg=1").fetchone()[0]
    print(f"\nT1 (Türk Süper Lig):")
    print(f"  Toplam: {n_t1}, xG var: {n_t1_xg} ({n_t1_xg/n_t1*100:.0f}%)")
    print(f"  KRİTİK EKSİKLİK: T1 xG yok -> FotMob/Sofascore scraper gerekli")

    # 2017-2021 xG (D1 hariç)
    print(f"\n2017-2021 dönemi xG kapsamı:")
    df_xg_new = pd.read_sql_query("""
        SELECT league_code, COUNT(*) as n, SUM(has_xg) as n_xg
        FROM matches_v2
        WHERE season IN ('2017-18','2018-19','2019-20','2020-21')
        GROUP BY league_code
    """, conn)
    for _, r in df_xg_new.iterrows():
        pct = r['n_xg']/r['n']*100 if r['n'] else 0
        print(f"  {r['league_code']:<5s}: {r['n_xg']}/{r['n']} ({pct:.0f}%)")
    print(f"  ÖNERİ: Understat 2017-2021 scrape genişlet")

    # 2025-26 odds eksikleri
    print(f"\n2025-26 (devam eden sezon) odds durumu:")
    df_2526 = pd.read_sql_query("""
        SELECT league_code, COUNT(*) as n,
               SUM(has_full_odds) as n_closing,
               SUM(is_settled) as n_settled
        FROM matches_v2
        WHERE season='2025-26'
        GROUP BY league_code
    """, conn)
    for _, r in df_2526.iterrows():
        pct_clo = r['n_closing']/r['n']*100 if r['n'] else 0
        pct_set = r['n_settled']/r['n']*100 if r['n'] else 0
        print(f"  {r['league_code']:<5s}: n={r['n']}, settled {pct_set:.0f}%, closing {pct_clo:.0f}%")
    print(f"  NOT: Sezon yarısı, kalan maçlar henüz oynanmadı (normal)")

    # === 5) MODEL ÇIKTILARI mevcut mu? ===
    print("\n" + "-" * 90)
    print(">>> 5) MODEL ÇIKTILARI (signal_snapshots) — 19K içinde ne kadar?")
    print("-" * 90)
    df_ss = pd.read_sql_query("""
        SELECT season, COUNT(*) as n
        FROM signal_snapshots
        WHERE source='football_data' AND settled=1
        GROUP BY season
        ORDER BY season
    """, conn)
    SEASON_CONV = {
        "1718":"2017-18","1819":"2018-19","1920":"2019-20","2021":"2020-21",
        "2122":"2021-22","2223":"2022-23","2324":"2023-24","2425":"2024-25","2526":"2025-26",
    }
    df_ss["canon"] = df_ss["season"].astype(str).map(lambda s: SEASON_CONV.get(s, s))
    df_ss_by_season = df_ss.groupby("canon")["n"].sum().to_dict()

    print(f"\n{'Sezon':<10s} {'matches_v2':>11s} {'signal_snap':>12s} {'Coverage':>10s}")
    print("-" * 50)
    for ss in ['2017-18','2018-19','2019-20','2020-21','2021-22','2022-23','2023-24','2024-25','2025-26']:
        n_m2 = conn.execute(
            f"SELECT COUNT(*) FROM matches_v2 WHERE season=? AND is_settled=1",
            (ss,)
        ).fetchone()[0]
        n_ss = df_ss_by_season.get(ss, 0)
        cov = n_ss / n_m2 * 100 if n_m2 else 0
        marker = "✗" if cov == 0 else ("⚠" if cov < 80 else "✓")
        marker_ascii = "X" if cov == 0 else ("!" if cov < 80 else "OK")
        print(f"{ss:<10s} {n_m2:>11d} {n_ss:>12d} {cov:>8.0f}%  {marker_ascii}")

    n_total_m2 = conn.execute("SELECT COUNT(*) FROM matches_v2 WHERE is_settled=1").fetchone()[0]
    n_total_ss = conn.execute("SELECT COUNT(*) FROM signal_snapshots WHERE source='football_data' AND settled=1").fetchone()[0]
    print(f"\nTOPLAM: matches_v2 {n_total_m2}, signal_snapshots {n_total_ss}")
    print(f"  -> Yeni 4 sezon (2017-2021) için sinyal yok!")
    print(f"  -> V2 retrain için DC modeli + sinyaller yeniden hesaplanmalı")

    # === 6) İYİLEŞTİRME SEÇENEKLERİ ÖZET ===
    print("\n" + "=" * 90)
    print(">>> 6) DATA + MODEL İYİLEŞTİRME SEÇENEKLERİ (KARAR İÇİN)")
    print("=" * 90)

    secenek_text = """
    +-----------------------------------------------------------------------+
    | SECENEK A: DC retrain + sinyal regen (2017-2021 icin)                 |
    |   - Yeni 8,536 mac icin DC parametre fit                               |
    |   - Form + anomaly + xG luck cache yenile                              |
    |   - score_v13 hesapla -> signal_snapshots'a ekle                       |
    |   - Sonuc: 19K mac hepsi model-ready                                   |
    |   - Sure: 1-2 gun                                                      |
    |   - Etki: V2 retrain icin tam sample, TRIVOX/DUOVOX sample ~2x        |
    |                                                                       |
    | SECENEK B: Multi-market V2 baslat (A/U 2.5 ilk pazar)                 |
    |   - DC Poisson'dan A/U 2.5 olasiligi turet                             |
    |   - Mevcut DC modelini A/U icin validate et                            |
    |   - 19K matches_v2'de Q5+a2 hit olc A/U icin                           |
    |   - Sure: 1 gun                                                        |
    |   - Etki: Edge alani 2x (yeni pazar), trader icin yeni opsiyon         |
    |                                                                       |
    | SECENEK C: T1 xG scraper (FotMob)                                     |
    |   - FotMob'dan T1 maclari icin xG cek                                  |
    |   - 5+ sezon retrofit                                                  |
    |   - TRIVOX'ta xG sinyali aktif et                                      |
    |   - Sure: 2-3 gun                                                      |
    |   - Etki: T1 picks dogrulugu artar (modelin %50 zayif alani)          |
    |                                                                       |
    | SECENEK D: Match stats entegrasyon (shots/corners/cards/referee)      |
    |   - matches_v2'de zaten %99 kapli                                      |
    |   - Yeni sinyaller turet:                                              |
    |     * shots_diff_signal (shots advantage)                              |
    |     * referee_bias (hakem yon etkisi)                                  |
    |     * cards_pressure_signal                                            |
    |   - Sure: 1 gun                                                        |
    |   - Etki: 3 yeni ortogonal sinyal, edge birikir                        |
    |                                                                       |
    | SECENEK E: Transfermarkt sakatlik scraper                             |
    |   - Sakatlik + kadro degeri 5 sezon retrofit                           |
    |   - lineup_quality sinyali turet                                       |
    |   - Sure: 2-3 gun                                                      |
    |   - Etki: Star-player impact, kucuk ama anlamli edge                   |
    |                                                                       |
    | SECENEK F: CLV pipeline derinlestir                                   |
    |   - Live CLV tracker (her pick icin)                                   |
    |   - Picks_log_v2 doldur                                                |
    |   - CLV-historical sinyali turet                                       |
    |   - Sure: 1 gun                                                        |
    |   - Etki: Edge olcumunun altin standardi, V2 validation                |
    |                                                                       |
    | SECENEK G: 19K uzerinde DC sezonsal retrain                           |
    |   - Sezon-ici DC fit (sezon baslangici onceki sezon verisi)            |
    |   - Walk-forward proper (komite A2 maddesi)                            |
    |   - Sure: 2 gun                                                        |
    |   - Etki: In-sample bias duzeltmesi, durust sonuc                      |
    +-----------------------------------------------------------------------+

    BENIM TAVSIYEM (oncelikli sira):
      Oncelik 1: SECENEK A (yeni 4 sezonu sinyallere dahil et)
      Oncelik 2: SECENEK D (mevcut data'dan 3 yeni sinyal turet)
      Oncelik 3: SECENEK B (A/U 2.5 multi-market baslangic)
      Sonra:    SECENEK G (walk-forward DC dogru implement)
      Sonra:    SECENEK C/E/F (yeni veri kaynaklari)

    SORU TRADER'A: Hangi secenekten baslayalim?
    """
    print(secenek_text)

    conn.close()


if __name__ == "__main__":
    run()
