"""
FETCH RESULTS — Biten maçların skorunu iddaa.com'dan çek
=========================================================
8504 trader'ın eksik halkasıydı: maç biter ama skor DB'ye gelmezse
auto_settle kuponu kapatamaz. Bu script:

  1. Açık kuponlardaki, başlama saati 2+ saat geçmiş, hâlâ is_settled=0 maçları bul
  2. iddaa statisticsv2 match-card API'sinden final skoru çek (sc alanı)
  3. matches_v2'ye home_score/away_score + is_settled=1 yaz

Skor alanı: data.h.sc (ev), data.a.sc (deplasman), data.st (durum), data.m (dakika)
st=6/9/12 → maç bitti

Kullanım:
  python fetch_results.py          # açık kupon maçlarının sonuçlarını çek
  python fetch_results.py --all    # tüm geçmiş is_settled=0 maçlar
"""
from __future__ import annotations
import argparse
import json
import sqlite3
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
DB = THIS_DIR / "bahis_agent.db"
sys.stdout.reconfigure(encoding="utf-8")

HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept":          "application/json",
    "Accept-Language": "tr-TR,tr;q=0.9",
    "Referer":         "https://www.iddaa.com/",
}

# iddaa match status: maç bitti sayılan kodlar
FINISHED_STATUS = {6, 9, 12, 13}  # 6=FT, 9=ended, 12=AET, 13=pen


def fetch_match_card(event_id: int) -> dict | None:
    url = f"https://statisticsv2.iddaa.com/statistics/soccer/match-card/{event_id}?isLive=true"
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.loads(r.read().decode("utf-8", errors="replace"))
            return d.get("data")
    except Exception:
        return None


def fetch_results(only_open: bool = True, verbose: bool = True,
                  void_stuck_hours: float = 14.0) -> dict:
    """
    void_stuck_hours: Maç bu kadar saat geçmiş VE iddaa API'sinde veri yoksa
    (event silinmiş) → maçı VOID işaretle ki kupon takılı kalmasın (stake iade).
    """
    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # Sonuçlanması gereken maçlar: kickoff 2+ saat geçmiş, is_settled=0
    if only_open:
        rows = conn.execute("""
            SELECT DISTINCT m.match_id, m.home_team, m.away_team,
                   m.external_id_iddaa, m.kickoff_utc
            FROM matches_v2 m
            JOIN paper_bets pb ON pb.match_id = m.match_id
            JOIN paper_coupons pc ON pb.coupon_id = pc.coupon_id
            WHERE pc.status = 'open'
              AND m.is_settled = 0
              AND m.external_id_iddaa IS NOT NULL
        """).fetchall()
    else:
        rows = conn.execute("""
            SELECT match_id, home_team, away_team, external_id_iddaa, kickoff_utc
            FROM matches_v2
            WHERE is_settled = 0
              AND external_id_iddaa IS NOT NULL
              AND kickoff_utc < ?
        """, (now.isoformat(),)).fetchall()

    updated = 0
    still_live = 0
    checked = 0
    voided = 0

    for r in rows:
        ko_raw = str(r["kickoff_utc"]).replace("Z", "")
        try:
            ko = datetime.fromisoformat(ko_raw)
        except Exception:
            continue
        elapsed_h = (now - ko).total_seconds() / 3600
        if elapsed_h < 1.8:   # daha bitmemiş olabilir
            continue

        checked += 1
        eid = r["external_id_iddaa"]
        data = fetch_match_card(eid)

        st     = (data or {}).get("st")
        minute = (data or {}).get("m") or 0
        hs     = ((data or {}).get("h") or {}).get("sc")
        as_    = ((data or {}).get("a") or {}).get("sc")

        finished  = (st in FINISHED_STATUS) or (minute >= 90)
        has_score = hs is not None and as_ is not None

        if finished and has_score:
            conn.execute("""
                UPDATE matches_v2
                SET home_score=?, away_score=?, is_settled=1, status='FT',
                    refreshed_at=?
                WHERE match_id=?
            """, (int(hs), int(as_), now.isoformat(), r["match_id"]))
            updated += 1
            if verbose:
                print(f"  [SKOR ✓] {r['home_team']} {hs}-{as_} {r['away_team']}  (st={st}, dk={minute})")
        elif elapsed_h >= void_stuck_hours and not has_score:
            # Maç çoktan bitmiş olmalı ama iddaa veri vermiyor (event silinmiş)
            # → VOID işaretle. Kupon takılı kalmaz, stake iade edilir.
            conn.execute("""
                UPDATE matches_v2
                SET is_settled=1, status='VOID', refreshed_at=?
                WHERE match_id=?
            """, (now.isoformat(), r["match_id"]))
            voided += 1
            if verbose:
                print(f"  [VOID ⛔] {r['home_team']} vs {r['away_team']}  "
                      f"({elapsed_h:.0f}sa geçti, iddaa verisi yok → iade)")
        else:
            still_live += 1
            if verbose:
                print(f"  [Devam]  {r['home_team']} vs {r['away_team']}  (st={st}, dk={minute}, skor={hs}-{as_})")

    conn.commit()
    conn.close()
    return {"checked": checked, "updated": updated,
            "still_live": still_live, "voided": voided}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true",
                        help="Sadece açık kupon değil, tüm geçmiş is_settled=0")
    args = parser.parse_args()

    print("=== FETCH RESULTS ===")
    res = fetch_results(only_open=not args.all)
    print(f"\nKontrol: {res['checked']}  |  Skor yazıldı: {res['updated']}  |  Hâlâ devam: {res['still_live']}")
