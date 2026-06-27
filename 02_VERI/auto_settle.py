"""
AUTO SETTLE — Otomatik kupon kapama
====================================
Windows Task Scheduler tarafindan her 30 dakikada bir calistirilir.
Biten maclari kapat, sonucu logla, uygulama cache'ini temizle.

Log: YAZILIM/07_LOG_VE_RAPORLAR/auto_settle.log
"""
from __future__ import annotations
import sys
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
YAZILIM  = THIS_DIR.parent
LOG_FILE = YAZILIM / "07_LOG_VE_RAPORLAR" / "auto_settle.log"

sys.path.insert(0, str(THIS_DIR))
sys.stdout.reconfigure(encoding="utf-8")

import db  # merkezî bağlantı katmanı (SQLite/PostgreSQL)

LOG_FILE.parent.mkdir(exist_ok=True)


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def void_stale_matches(hours: int = 12) -> int:
    """Kickoff'tan {hours} saat gecmis ama hala SONUCSUZ (is_settled=0, skor yok)
    maclari VOID isaretle — sonuc cekilemedi demek (off-season hazirlik maci,
    iddaa event'i silinmis vs). Boylece kupon ayagi 'push/iade' olur ve kupon
    sonsuza dek 'open' takili kalmaz.

    SADECE acik paper bahsi olan maclara dokunur (tarihsel 19k veriye degil).
    Dondurur: VOID isaretlenen mac sayisi.
    """
    conn = db.connect()
    try:
        cutoff = (datetime.now(timezone.utc).replace(tzinfo=None)
                  - timedelta(hours=hours)).isoformat()
        rows = conn.execute(
            """
            SELECT DISTINCT m.match_id
            FROM matches_v2 m
            JOIN paper_bets pb   ON pb.match_id = m.match_id
            JOIN paper_coupons pc ON pc.coupon_id = pb.coupon_id
            WHERE pc.status = 'open'
              AND m.is_settled = 0
              AND m.home_score IS NULL
              AND m.kickoff_utc < ?
            """,
            (cutoff,),
        ).fetchall()
        ids = [r[0] for r in rows]
        now_iso = datetime.utcnow().isoformat()
        for mid in ids:
            conn.execute(
                "UPDATE matches_v2 SET is_settled=1, status='VOID', refreshed_at=? "
                "WHERE match_id=?",
                (now_iso, mid),
            )
        conn.commit()
        return len(ids)
    finally:
        conn.close()


def run():
    log("=== AUTO SETTLE BASLADI ===")

    # Acik kupon var mi?
    conn = db.connect()
    open_count = conn.execute(
        "SELECT COUNT(*) FROM paper_coupons WHERE status='open'"
    ).fetchone()[0]
    conn.close()

    if open_count == 0:
        log("Acik kupon yok. Islem yapilmadi.")
        log("=== AUTO SETTLE BITTI ===\n")
        return

    log(f"Acik kupon: {open_count}  — once skorlar cekiliyor...")

    # ── ÖNCE: biten maçların skorunu iddaa.com'dan çek ──────────
    try:
        from fetch_results import fetch_results
        res = fetch_results(only_open=True, verbose=False)
        if res["updated"] > 0:
            log(f"Skor cekildi: {res['updated']} mac sonuclandi  "
                f"(kontrol:{res['checked']}, devam:{res['still_live']})")
        else:
            log(f"Yeni biten mac yok (kontrol:{res['checked']}, devam:{res['still_live']})")
    except Exception as e:
        log(f"FETCH RESULTS HATA: {e}")

    # ── Bayat maçları VOID'le (sonuç çekilemeyenler kuponu tıkamasın) ──
    try:
        n_void = void_stale_matches(hours=12)
        if n_void:
            log(f"BAYAT MAÇ VOID: {n_void} maç (kickoff+12sa sonuçsuz) → kuponlar çözülecek")
    except Exception as e:
        log(f"VOID STALE HATA: {e}")

    log("Settle deneniyor...")

    # Settle calistir
    try:
        from paper_engine import PaperEngine
        engine = PaperEngine("PAPER_V1")
        result = engine.settle_coupons()

        settled = result.get("settled", 0)
        won     = result.get("won", 0)
        pnl     = result.get("pnl", 0.0)

        if settled == 0:
            log("Kapatilacak bitmis mac bulunamadi (maclar henuz devam ediyor).")
        else:
            log(f"KAPATILDI: {settled} kupon  |  Kazanan: {won}  |  PnL: {pnl:+.2f} TL")
            # Guncel bankroll
            conn2 = db.connect()
            br = conn2.execute(
                "SELECT current_bankroll FROM paper_portfolio WHERE portfolio_id='PAPER_V1'"
            ).fetchone()
            if br:
                log(f"Guncel bankroll: {br[0]:,.2f} TL")
            conn2.close()

    except Exception as e:
        log(f"HATA: {e}")

    log("=== AUTO SETTLE BITTI ===\n")


if __name__ == "__main__":
    run()
