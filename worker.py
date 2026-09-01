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
        auto_play.run(max_events=120)   # sezonda 40 yetmez — kapsami genis tut
    except Exception as e:
        print(f"[{_ts()}] AUTO_PLAY HATA: {e}")
    # 🤖 AGENT LİGİ — TEMKİNLİ + MEMUR + AVCI (her biri ayrı 1K kasa,
    # kendi kanıt-kurallı profili). Fetch zaten yapıldı; kupon kurarlar.
    try:
        import agents
        agents.run_all(place=True)
    except Exception as e:
        print(f"[{_ts()}] AGENTS HATA: {e}")


def job_olcum_defteri(tam: bool = False):
    """📓 ÖLÇÜM DEFTERİ — her bulguyu ön kayıtlı kuralına karşı yeniden ölç.

    Neden worker'da: bir bulgu, ölçüldüğü gün doğru olduğu için sonsuza
    kadar doğru kalmaz. Bu projede ROI +%9,7'den -%0,1'e düştü ve "edge
    sıralaması çalışıyor" hükmünün tek ajanın 15 bahsine dayandığı ancak
    TEKRAR ÖLÇÜLDÜĞÜ için anlaşıldı. Elle koşulan ölçüm unutulur.

    Günlük koşu hafif ölçümleri alır (K_BECERI her kapanan bahisle
    değişir). Haftalık koşu ağırları da ekler (skor modeli kalibrasyonu
    18.000 maç üzerinde lambda çözer — pahalı, ama yavaş değişir)."""
    kip = "TAM" if tam else "hızlı"
    print(f"[{_ts()}] >>> ÖLÇÜM DEFTERİ tetiklendi ({kip})")
    try:
        import olcum_defteri
        olcum_defteri.run(hizli=not tam)
    except Exception as e:
        print(f"[{_ts()}] ÖLÇÜM DEFTERİ HATA: {type(e).__name__}: {e}")


def job_defter_denetim():
    """🔎 DEFTER DENETİMİ — kâr eğrisi ancak defter tutarlıysa bir şey söyler.

    Neden worker'da: 1 Eylül 2026'da verify_settlements.py'nin AÇIK
    ayakları süzüp atıp kuponu erken "kazandı" yazdığı bulundu. Bir
    kupon 1 Eylül'de ödendi, iki maçı 2 ve 4 Eylül'de oynanacaktı —
    kasaya var olmayan para girdi. Kök neden düzeltildi, ama böyle bir
    bozulmanın SESSİZ kalması asıl tehlike: her ölçüm, her ROI, her
    hüküm bozuk defterin üstüne kurulur.

    Denetim yalnız RAPORLAR, kendiliğinden onarmaz. Onarım sonuç-kör
    bir karardır (fix_early_settled.py) ve elle tetiklenir."""
    print(f"[{_ts()}] >>> DEFTER DENETİMİ tetiklendi")
    try:
        import db
        conn = db.connect()
        try:
            erken = conn.execute(
                "SELECT COUNT(*) FROM (SELECT pc.coupon_id FROM paper_coupons pc "
                "JOIN paper_bets pb ON pb.coupon_id=pc.coupon_id "
                "WHERE pc.status IN ('won','lost','void') GROUP BY pc.coupon_id "
                "HAVING SUM(CASE WHEN pb.status='open' THEN 1 ELSE 0 END)>0 "
                "AND SUM(CASE WHEN pb.status='lost' THEN 1 ELSE 0 END)=0) t"
            ).fetchone()[0]
            oksuz = conn.execute(
                "SELECT COUNT(*) FROM paper_bets pb LEFT JOIN paper_coupons pc "
                "ON pc.coupon_id=pb.coupon_id WHERE pc.coupon_id IS NULL"
            ).fetchone()[0]
            kasa = conn.execute(
                "SELECT COUNT(*) FROM (SELECT pp.portfolio_id FROM paper_portfolio pp "
                "LEFT JOIN paper_coupons pc ON pc.portfolio_id=pp.portfolio_id "
                "AND pc.status IN ('won','lost') "
                "AND (pp.era_start IS NULL OR pc.created_at >= pp.era_start) "
                "GROUP BY pp.portfolio_id, pp.current_bankroll, pp.initial_bankroll "
                "HAVING ABS(pp.current_bankroll - (pp.initial_bankroll + "
                "COALESCE(SUM(pc.pnl),0))) > 0.5) t"
            ).fetchone()[0]
        finally:
            conn.close()
        if erken or oksuz or kasa:
            print(f"[{_ts()}] ⛔ DEFTER BOZUK — erken kapanmış kupon={erken} · "
                  f"öksüz bahis={oksuz} · kasa mutabakatsız ajan={kasa}")
            print(f"[{_ts()}]    onarım: python 02_VERI/fix_early_settled.py --dry")
        else:
            print(f"[{_ts()}] ✅ DEFTER TEMİZ")
    except Exception as e:
        print(f"[{_ts()}] DEFTER DENETİMİ HATA: {type(e).__name__}: {e}")


def job_fetch_program():
    """Sadece iddaa programini tazele (kupon KURMAZ). Amac:
    - kapanis oranlari kickoff'a yakin yakalansin (CLV kalitesi)
    - Hazir Kuponlar / sinyaller taze kalsin
    - skorlar icin refreshed_at güncel olsun."""
    print(f"[{_ts()}] >>> FETCH_PROGRAM tetiklendi")
    try:
        from fetch_iddaa_live import fetch_and_ingest
        fetch_and_ingest(dry_run=False, max_events=120, only_target_leagues=False)
        print(f"[{_ts()}] FETCH_PROGRAM tamam")
    except Exception as e:
        print(f"[{_ts()}] FETCH_PROGRAM HATA: {e}")
    # 🤖 Ajanlar taze programla TEKRAR degerlendirsin (gunde 2 pencere azdi —
    # kickoff'lar gun icine dagiliyor; limitler zaten spam'i engeller)
    try:
        import agents
        agents.run_all(place=True)
    except Exception as e:
        print(f"[{_ts()}] AGENTS(FETCH) HATA: {e}")


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

    # 📋 Yönetici özeti — 2 günde bir numaralı arşiv raporu
    try:
        import exec_report
        exec_report.generate()
    except Exception as e:
        print(f"[{_ts()}] RAPOR HATA: {e}")


def main():
    print(f"[{_ts()}] WORKER BAŞLADI — auto_play (06:00/15:00 UTC) + "
          f"auto_settle (90 dk) + fetch_program (3 sa) + "
          f"ölçüm defteri (04:20 günlük · pzt 03:10 tam)")

    # Açılışta: önce settle/temizlik, sonra taze program (deploy sonrası
    # sistem dakikalar içinde güncel olsun)
    # 🛡 AÇILIŞ KALKANI: deploy sonrası ilk iş — ajanlar çöküyor mu?
    # (Bir bağımlılık/şema kırılması haftalarca 'pasiflik' sanılmasın.)
    try:
        import agents as _agents
        _agents.preflight()
    except Exception as e:
        print(f"[{_ts()}] PREFLIGHT HATA: {e}")

    job_auto_settle()
    job_fetch_program()

    sched = BlockingScheduler(timezone="UTC")
    sched.add_job(job_auto_play, "cron", hour="6,15", minute=0,
                  id="auto_play", misfire_grace_time=3600, coalesce=True)
    sched.add_job(job_auto_settle, "interval", minutes=90,
                  id="auto_settle", misfire_grace_time=900, coalesce=True)
    sched.add_job(job_fetch_program, "interval", hours=3,
                  id="fetch_program", misfire_grace_time=1800, coalesce=True)
    # 📓 ölçüm defteri — sessiz saatte, auto_play'den (06:00) önce.
    # Günlük hafif: hızlı değişen ölçümler (K_BECERI her bahisle kayar).
    # Pazartesi tam: ağır olanlar da (skor modeli kalibrasyonu).
    sched.add_job(job_olcum_defteri, "cron", hour=4, minute=20,
                  id="olcum_defteri", misfire_grace_time=3600, coalesce=True)
    sched.add_job(job_olcum_defteri, "cron", day_of_week="mon", hour=3, minute=10,
                  kwargs={"tam": True},
                  id="olcum_defteri_tam", misfire_grace_time=7200, coalesce=True)
    # 🔎 defter denetimi — ölçüm defterinden ÖNCE koşar. Sırası önemli:
    # bozuk defterin üstünde ölçülen her bulgu değersizdir; önce defterin
    # kendisi tutarlı mı, sonra bulgular. Yalnız raporlar, onarmaz.
    sched.add_job(job_defter_denetim, "cron", hour=4, minute=10,
                  id="defter_denetim", misfire_grace_time=3600, coalesce=True)

    try:
        sched.start()
    except (KeyboardInterrupt, SystemExit):
        print(f"[{_ts()}] WORKER DURDURULDU")


if __name__ == "__main__":
    main()
