"""
RAILWAY WORKER — Otomasyon Zamanlayıcısı
=========================================
Sürekli çalışan tek süreç. PC kapanma sorununu kalıcı çözer (Railway 7/24).

  • auto_play   : 06:00 & 15:00 UTC  (= 09:00 & 18:00 TR)  → canlı maç çek + kupon kur
  • auto_settle : her 90 dakika                            → sonuç çek + kupon kapat

Railway'de ayrı bir "worker" servisi olarak çalıştırılır:
    Start Command:  python worker.py

Aynı PostgreSQL'i (DATABASE_URL) web servisi ile paylaşır.
Loglar stdout'a yazılır (Railway otomatik toplar).
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR / "02_VERI"))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from apscheduler.schedulers.blocking import BlockingScheduler

import auto_play
import auto_settle


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def job_auto_play():
    print(f"[{_ts()}] >>> AUTO_PLAY tetiklendi")
    try:
        auto_play.run()
    except Exception as e:
        print(f"[{_ts()}] AUTO_PLAY HATA: {e}")


def job_auto_settle():
    print(f"[{_ts()}] >>> AUTO_SETTLE tetiklendi")
    try:
        auto_settle.run()
    except Exception as e:
        print(f"[{_ts()}] AUTO_SETTLE HATA: {e}")
    # CLV backfill — settle sonrası kapanış kesinleşir (Faz 0 truth meter).
    # Hata olsa bile settle akışını bozmaz.
    try:
        import clv
        res = clv.backfill_clv()
        print(f"[{_ts()}] CLV backfill: hesaplanan={res['computed']} atlanan={res['skipped']}")
    except Exception as e:
        print(f"[{_ts()}] CLV BACKFILL HATA: {e}")


def main():
    print(f"[{_ts()}] WORKER BAŞLADI — auto_play (06:00/15:00 UTC) + auto_settle (90 dk)")

    # Açılışta bir kez settle (devam eden kuponları hemen kontrol et)
    job_auto_settle()

    sched = BlockingScheduler(timezone="UTC")
    sched.add_job(job_auto_play, "cron", hour="6,15", minute=0,
                  id="auto_play", misfire_grace_time=3600, coalesce=True)
    sched.add_job(job_auto_settle, "interval", minutes=90,
                  id="auto_settle", misfire_grace_time=900, coalesce=True)

    try:
        sched.start()
    except (KeyboardInterrupt, SystemExit):
        print(f"[{_ts()}] WORKER DURDURULDU")


if __name__ == "__main__":
    main()
