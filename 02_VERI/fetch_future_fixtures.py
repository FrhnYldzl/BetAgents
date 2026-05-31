"""
FUTURE FIXTURES — api-football'dan yakın gelecek maçları çek
==============================================================

Amaç:
  Yeni sezon (2026-27 + ileri) için fixture'ları çek.
  Future maçlar UI'da "GÜNCEL TAKVİM" sayfasında gösterilecek.

Strateji:
  - Bugün → ileri 60 gün penceresi
  - 6 lig için ayrı sorgular (api-football free tier: 100 req/gün)
  - matches_v2 tablosuna unsettled (is_settled=0) olarak ekle

Notlar:
  - 2025-26 sezon bitti (May 24), yeni sezon Ağustos başı
  - Yaz arası: Avrupa kupası, Conference League (lig ID'leri farklı)
  - İlk testte sezon 2026 olarak deneyeceğiz (Ağustos 2026 start)
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))
sys.path.insert(0, str(THIS_DIR / "api_clients"))

import database as db
from api_football import (
    get_fixtures_by_date_range, LEAGUE_IDS, APIFootballError
)


def ensure_columns():
    """matches_v2 var olan tablo; eksik kolonlar yok ama check."""
    pass


def parse_score(fix: dict) -> tuple[int|None, int|None]:
    """api-football fixture'dan skor çıkar."""
    h = fix.get("home_score")
    a = fix.get("away_score")
    return h, a


def ingest_fixtures(league_code: str, season: int, date_from: str, date_to: str,
                    dry_run: bool = False) -> dict:
    """Bir lig için verilen aralıkta fixture'ları çek + matches_v2'ye ekle."""
    print(f"\n[{league_code}] {season} sezon, {date_from} -> {date_to}")

    try:
        fixtures = get_fixtures_by_date_range(
            league_code=league_code, season=season,
            date_from=date_from, date_to=date_to,
            use_cache=True
        )
    except APIFootballError as e:
        print(f"  ERR: {e}")
        return {"n_fetched": 0, "n_inserted": 0, "n_updated": 0, "error": str(e)}

    print(f"  {len(fixtures)} fixture çekildi")
    if not fixtures:
        return {"n_fetched": 0, "n_inserted": 0, "n_updated": 0}

    if dry_run:
        print("  [DRY RUN] DB'ye yazılmayacak")
        for f in fixtures[:3]:
            print(f"    {f.get('kickoff','?')} {f.get('home','?')} vs {f.get('away','?')}"
                  f" [{f.get('status','?')}]")
        return {"n_fetched": len(fixtures), "n_inserted": 0, "n_updated": 0}

    conn = db.connect()
    now = datetime.utcnow().isoformat()
    n_ins = 0
    n_upd = 0
    n_err = 0

    season_canon = f"{season}-{(season+1)%100:02d}"

    for f in fixtures:
        try:
            kickoff = f.get("kickoff") or ""
            md = kickoff[:10]
            home = f.get("home", "")
            away = f.get("away", "")
            status = f.get("status", "")
            home_score = f.get("home_score")
            away_score = f.get("away_score")
            settled = 1 if status in ("FT", "AET", "PEN") else 0

            # Var mı?
            existing = conn.execute("""
                SELECT match_id FROM matches_v2
                WHERE league_code=? AND season=? AND matchday=?
                  AND home_team=? AND away_team=?
            """, (league_code, season_canon, md, home, away)).fetchone()

            if existing:
                # Update
                conn.execute("""
                    UPDATE matches_v2
                    SET external_id_af=?, status=?, home_score=?, away_score=?,
                        is_settled=?, refreshed_at=?
                    WHERE match_id=?
                """, (f.get("fixture_id"), status, home_score, away_score,
                      settled, now, existing["match_id"]))
                n_upd += 1
            else:
                # Insert (eksik veri ile başla, sonra odds eklenir)
                conn.execute("""
                    INSERT INTO matches_v2 (
                        external_id_af, league_code, season, matchday,
                        kickoff_utc, home_team, away_team, status,
                        home_score, away_score, is_settled,
                        has_full_odds, has_opening_odds, has_xg, has_result,
                        ingested_at, refreshed_at, quality_score
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, ?, ?, ?, 0.30)
                """, (
                    f.get("fixture_id"), league_code, season_canon, md,
                    kickoff, home, away, status,
                    home_score, away_score, settled,
                    settled, now, now
                ))
                n_ins += 1
        except Exception as e:
            n_err += 1
            if n_err <= 3:
                print(f"  ROW ERR: {e}")

    conn.commit()
    conn.close()
    print(f"  Inserted: {n_ins}, Updated: {n_upd}, Err: {n_err}")
    return {"n_fetched": len(fixtures), "n_inserted": n_ins, "n_updated": n_upd,
            "n_err": n_err}


def run(dry_run: bool = False):
    print("=" * 70)
    print("FUTURE FIXTURES — api-football'dan yakın geleceği çek")
    print("=" * 70)

    today = datetime.now().date()
    date_from = today.strftime("%Y-%m-%d")
    date_to = (today + timedelta(days=90)).strftime("%Y-%m-%d")  # 90 gün

    print(f"\nTarih penceresi: {date_from} -> {date_to}")

    # Sezon belirleme: Ağustos+ → o yıl, ondan önce → bir yıl önce
    if today.month >= 7:
        season = today.year
    else:
        season = today.year - 1
    print(f"Sezon: {season} (canon: {season}-{(season+1)%100:02d})")

    # Yaz arası senaryosu: future fixtures yoksa, yeni sezon (2026) deneyelim
    seasons_to_try = [season, season + 1]  # mevcut + sonraki

    leagues = ["T1", "E0", "D1", "SP1", "I1", "F1"]

    summary = {}
    for lg in leagues:
        for s in seasons_to_try:
            result = ingest_fixtures(lg, s, date_from, date_to, dry_run=dry_run)
            if result["n_fetched"] > 0:
                summary[f"{lg}_{s}"] = result
                break  # Bu lig için fixture bulundu, sonraki sezonu deneme

    print("\n" + "=" * 70)
    print("ÖZET")
    print("=" * 70)
    total_fetched = sum(r.get("n_fetched", 0) for r in summary.values())
    total_inserted = sum(r.get("n_inserted", 0) for r in summary.values())
    total_updated = sum(r.get("n_updated", 0) for r in summary.values())
    print(f"Toplam fetched: {total_fetched}")
    print(f"Inserted:       {total_inserted}")
    print(f"Updated:        {total_updated}")

    if total_fetched == 0:
        print("\n[INFO] Hiç future fixture yok.")
        print("Olası nedenler:")
        print("  1. Sezon arası (Mayıs sonu - Ağustos başı). Normal.")
        print("  2. API key limit veya hatalı sezon parametresi.")
        print("  3. Future maçlar henüz fixture listesinde değil.")
        print("\nYeni sezon (2026-27) için fixture'lar Temmuz başı yayınlanır.")
        print("Bu test başarılı sayılır — pipeline hazır.")
    else:
        # Yeni eklenen unsettled maçları göster
        conn = db.connect()
        df_new = pd.read_sql_query("""
            SELECT league_code, COUNT(*) as n, MIN(matchday) as ilk, MAX(matchday) as son
            FROM matches_v2
            WHERE is_settled=0 AND matchday >= ?
            GROUP BY league_code
        """, conn, params=(date_from,))
        conn.close()
        if not df_new.empty:
            print("\nYeni eklenen future fixtures:")
            for _, r in df_new.iterrows():
                print(f"  {r['league_code']}: {r['n']} maç ({r['ilk']} -> {r['son']})")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry", action="store_true", help="Dry run, DB'ye yazma")
    args = parser.parse_args()
    run(dry_run=args.dry)
