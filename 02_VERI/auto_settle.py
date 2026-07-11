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


def void_stray_matches(hours: int = 48) -> int:
    """BAHİS KONMAMIŞ ama kickoff'u {hours}+ saat gecmis, hala sonucsuz
    iddaa-kaynakli maclari dogrudan VOID'le (API cagrisi YOK — event coktan
    silinmis). Bunlar birikince build_session_coupons'un LIMIT 200 penceresini
    tikiyordu (877 stray -> motor bugunun macini goremiyordu). Tablo hijyeni."""
    conn = db.connect()
    try:
        cutoff = (datetime.now(timezone.utc).replace(tzinfo=None)
                  - timedelta(hours=hours)).isoformat()
        now_iso = datetime.utcnow().isoformat()
        rows = conn.execute(
            """
            SELECT match_id FROM matches_v2
            WHERE is_settled = 0
              AND home_score IS NULL
              AND kickoff_utc < ?
              AND (external_id_iddaa IS NOT NULL OR closing_source = 'iddaa')
            """,
            (cutoff,),
        ).fetchall()
        ids = [r[0] for r in rows]
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

    conn = db.connect()
    open_count = conn.execute(
        "SELECT COUNT(*) FROM paper_coupons WHERE status='open'"
    ).fetchone()[0]
    conn.close()
    log(f"Acik kupon: {open_count}")

    # ── ÖNCE: eski stray temizliği (API'siz, hızlı) — 48sa+ sonuçsuz →
    # direkt VOID. Böylece aşağıdaki skor taraması SADECE son 48 saatin
    # küçük penceresiyle uğraşır (877 stray'e tek tek API çağrısı yapılmaz).
    try:
        n_stray = void_stray_matches(hours=48)
        if n_stray:
            log(f"STRAY TEMIZLIK: {n_stray} eski sonuçsuz maç VOID (motor penceresi açıldı)")
    except Exception as e:
        log(f"VOID STRAY HATA: {e}")

    # ── SKOR ÇEK — açık kupon olmasa da (UI skorları + CLV tazelensin).
    # only_open=False: başlamış tüm sonuçsuz iddaa maçları (yukarıdaki
    # temizlik sonrası sadece son 48 saat penceresi).
    try:
        from fetch_results import fetch_results
        res = fetch_results(only_open=False, verbose=False)
        log(f"Skor taramasi: kontrol={res['checked']} skor={res['updated']} "
            f"devam={res['still_live']} void={res.get('voided', 0)}")
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

    # Settle calistir — TÜM aktif portföyler (PAPER_V1 + TEMKINLI_V1 + ...)
    try:
        from paper_engine import PaperEngine
        from recompute_portfolio import recompute

        conn = db.connect()
        pids = [r[0] for r in conn.execute(
            "SELECT portfolio_id FROM paper_portfolio ORDER BY portfolio_id"
        ).fetchall()]
        conn.close()

        for pid in pids:
            try:
                result = PaperEngine(pid).settle_coupons()
                settled = result.get("settled", 0)
                if settled:
                    log(f"[{pid}] KAPATILDI: {settled} kupon | "
                        f"Kazanan: {result.get('won',0)} | "
                        f"PnL: {result.get('pnl',0.0):+.2f} TL")
                # SAYAÇ SENKRONU (kaynak-gerçek) — her portföy için
                rp = recompute(pid, verbose=False)
                if rp:
                    log(f"[{pid}] sayac: {rp['played']} karar "
                        f"(W{rp['won']}/V{rp['voids']}) | "
                        f"bankroll {rp['bankroll']:,.2f} TL")
            except Exception as e:
                log(f"[{pid}] SETTLE/RECOMPUTE HATA: {e}")

    except Exception as e:
        log(f"HATA: {e}")

    log("=== AUTO SETTLE BITTI ===\n")


if __name__ == "__main__":
    run()
