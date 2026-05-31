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
from datetime import datetime, timezone
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
YAZILIM  = THIS_DIR.parent
LOG_FILE = YAZILIM / "07_LOG_VE_RAPORLAR" / "auto_settle.log"

sys.path.insert(0, str(THIS_DIR))
sys.stdout.reconfigure(encoding="utf-8")

LOG_FILE.parent.mkdir(exist_ok=True)


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def run():
    log("=== AUTO SETTLE BASLADI ===")

    # Acik kupon var mi?
    db_path = THIS_DIR / "bahis_agent.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
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
            conn2 = sqlite3.connect(str(db_path))
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
