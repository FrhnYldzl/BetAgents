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
    # 📝 İDDİA DEFTERİ — ajanın KOTASIZ görüşünü kaydet (bahis YERLEŞTİRMEZ).
    # auto_play'den SONRA koşar: yazar taraması ve fiyatlar zaten taze, ikinci
    # kez çekilmesin. Kupon defteri oynadığını tutar, bu defter söylediğini —
    # ajanlar görüş bildirdikleri maçların çoğunu kota yüzünden oynamıyor ve
    # o görüşler ölçülmeden kayboluyordu.
    try:
        import iddia_defteri
        iddia_defteri.kaydet()
    except Exception as e:
        print(f"[{_ts()}] IDDIA_DEFTERI HATA: {e}")


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


def job_kapanis():
    """⏱ KAPANIŞ YAKALAMA — maça ≤45 dk kalan maçların fiyatı, 15 dk'da bir.

    Neden (19.09.2026, kullanıcı onayı: "maliyeti çok artırmaz"): ana çekim
    3 saatte bir; CLV'nin 'kapanışı' çoğu zaman maçtan saatler önceki
    fiyattı. Maliyet: TEK API çağrısı (fiyatlar olayın içinde), pazar
    defterine yalnız değişen fiyat. Ana çekimle aynı anda koşmaz (kilit)."""
    try:
        from fetch_iddaa_live import kapanis_yakala
        r = kapanis_yakala()
        if r.get("olay"):
            print(f"[{_ts()}] ⏱ KAPANIŞ: {r['olay']} maç · defter "
                  f"{r.get('defter', 0)} yeni fiyat · matches_v2 {r.get('mac', 0)}")
    except Exception as e:
        print(f"[{_ts()}] KAPANIŞ HATA: {type(e).__name__}: {e}")


def job_swat():
    """🔫 SWAT veri hattı — ilk yarı skorlarını çek, eşleştir, yaz.

    Ucuz: lig-sezon başına TEK çağrı (yapılandırılmış 5 lig = 5 istek).
    Maç istatistiği (maç başına bir çağrı) BİLEREK yok — ücretsiz katman
    günde 100 istek ve 10.000 maçlık geçmiş 100 gün sürerdi.

    ⚠️ Kaynak kapalıysa (anahtar yok/askıda) hata yazar ve geçer. SWAT
    ajanları o durumda MEŞRU PAS geçer; sahte ölçüm üretmezler.
    """
    # ⚠️ VARSAYILAN KAPALI — PAYLAŞIMLI IP SORUNU (08.11.2026)
    # API-Football desteği, Free hesapların askıya alınma sebeplerinden
    # birini açıkça şöyle tanımlıyor: "Cloudflare Workers, Google Cloud
    # Run, AWS Lambda, shared hosting, proxies, VPNs… aynı çıkış IP'sini
    # paylaşan başka kullanıcılar anti-abuse korumasını tetikleyebilir."
    # Railway tam olarak bu ailede. Yani çağrı hızını düzeltmek yetmez:
    # Free planda PAYLAŞIMLI IP'den istek atmak başlı başına risk.
    # Çekim bu yüzden kullanıcının kendi makinesinden (adanmış IP)
    # yapılmalı; worker'dan yalnız açıkça izin verilirse koşar.
    import os as _os
    if _os.environ.get("SWAT_WORKER_CEKIM") != "1":
        print(f"[{_ts()}] SWAT: worker'dan çekim KAPALI (paylaşımlı IP "
              f"riski) — açmak için SWAT_WORKER_CEKIM=1", flush=True)
        return
    print(f"[{_ts()}] >>> SWAT veri hattı tetiklendi")
    try:
        import os as _os
        import sys as _sys
        _d = _os.path.join(str(THIS_DIR), "12_SWAT")
        if _d not in _sys.path:
            _sys.path.append(_d)
        import swat_cek
        r = swat_cek.calistir()
        print(f"[{_ts()}] SWAT: çekilen {r['cekilen']} · yazılan "
              f"{r['yazilan']} · kota kalan {r.get('kota_kalan')}", flush=True)
        if r.get("hata"):
            print(f"[{_ts()}] SWAT UYARI: {' | '.join(r['hata'])[:200]}",
                  flush=True)
    except Exception as e:
        print(f"[{_ts()}] SWAT HATA: {type(e).__name__}: {e}", flush=True)


def job_kupon_orkestra():
    """🎟️ KUPONLAR FERHAN — saat başı kupon üret, deftere yaz, sonuçları kapat.

    Kullanıcı isteği (01.11.2026): "saat başı ya da auto ile aynı zamanda bu
    kuponların kazanma şansı bu kadar diyeceksin".

    Yeni SEÇİM üretmez — ajanların zaten açtığı pozisyonları kupon şekline
    sokar. Bahis de yerleştirmez; yalnız kendi defterine (ferhan_kupon) yazar.

    ⚠️ YAZMAK ŞART, göstermek yetmez: kaydedilmeyen "şans %60" iddiası
    hiçbir zaman yanlış çıkmaz. Defter, söylenen şans ile gerçekleşen
    isabeti karşılaştırılabilir kılan tek şey.
    """
    print(f"[{_ts()}] >>> KUPON ORKESTRA tetiklendi")
    try:
        import db
        import ferhan_kupon
        import kupon_orkestra as KO
        c = db.connect()
        try:
            kr = KO.karne_haritasi(c)
            normal = KO.uret(KO.gunun_adaylari(c), kr, en_cok=9)
            n1 = ferhan_kupon.kaydet(normal, "normal", c)
            # Canlıda 3'lü yok: canlı fiyat saniyede değişiyor, fiyat kayması
            # ayak sayısıyla büyüyor.
            try:
                canli = KO.uret(KO.canli_adaylari(c), kr, sekiller=(1, 2),
                                en_cok=4)
            except Exception as e:
                canli, n2 = [], 0
                print(f"[{_ts()}] KUPON CANLI HATA: {e}")
            else:
                n2 = ferhan_kupon.kaydet(canli, "canli", c)
            sn = ferhan_kupon.sonuclandir(c)
            print(f"[{_ts()}] KUPON: {n1} normal + {n2} canlı yazıldı · "
                  f"kapanan {sn['kazandi']}K/{sn['kaybetti']}Y/"
                  f"{sn['iptal']}İ · açık {sn['acik']}", flush=True)
        finally:
            c.close()
    except Exception as e:
        print(f"[{_ts()}] KUPON ORKESTRA HATA: {e}", flush=True)


def job_auto_settle():
    print(f"[{_ts()}] >>> AUTO_SETTLE tetiklendi")
    try:
        auto_settle.run()
    except Exception as e:
        print(f"[{_ts()}] AUTO_SETTLE HATA: {e}")
    # 📡 CANLI sonuç bağlantısı — maç içi fiyat serisi ancak sonuç varsa
    # ölçülebilir. Toplayıcı sonucu kendi başına YAZAMIYOR: kaynağı
    # fixtures?live=all yalnız CANLI maçları döndürüyor, maç bitince akıştan
    # düşüyor ve "bitti" anı hiç görülmüyor. Sonuç buradan, matches_v2'den
    # bağlanır (BetAgents yalnız OKUNUR, yazma cl_mac'e).
    try:
        import os as _os
        import sys as _sys
        _c = _os.path.join(str(THIS_DIR), "10_CANLI")
        if _c not in _sys.path:
            _sys.path.append(_c)
        import canli_db as _cdb
        _r = _cdb.sonuc_baglan()
        if _r.get("yazilan"):
            print(f"[{_ts()}] CANLI sonuç bağlandı: {_r['yazilan']} maç "
                  f"· ölçülebilir toplam {_cdb.olculebilir()}", flush=True)
        elif _r.get("hata"):
            print(f"[{_ts()}] CANLI SONUÇ HATA: {_r['hata']}", flush=True)
    except Exception as e:
        print(f"[{_ts()}] CANLI SONUÇ HATA: {e}", flush=True)

    # 📝 İddia defterini derecelendir — sonucu gelen iddialar kapanır.
    # Settle ile aynı ritimde: skor buraya düştüğü an iddia da puanlanabilir.
    try:
        import iddia_defteri
        iddia_defteri.derecelendir()
    except Exception as e:
        print(f"[{_ts()}] IDDIA_DERECE HATA: {e}")
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
          f"auto_settle (90 dk) + fetch_program (3 sa) + kapanış (15 dk) + "
          f"ölçüm defteri (04:20 günlük · pzt 03:10 tam)")

    # Açılışta: önce settle/temizlik, sonra taze program (deploy sonrası
    # sistem dakikalar içinde güncel olsun)
    # 🛡 AÇILIŞ KALKANI: deploy sonrası ilk iş — ajanlar çöküyor mu?
    # (Bir bağımlılık/şema kırılması haftalarca 'pasiflik' sanılmasın.)
    # 📡 GENİŞ TOPLAMA PENCERESİ — kalıcı.
    # Önce 7 günlük deneme olarak açılmıştı; kullanıcı 01.11.2026'da sınırı
    # kaldırdı ("ücrete bant genişliğine bakarız"). Eski denemeden kalan
    # bitiş tarihi varsa temizlenir ki süreli mantık devreye girmesin.
    # Maliyet: API kotası HARCANMAZ (fiyat iddaa'dan ücretsiz, 45 sn);
    # kotayı yakan API-Football'un ayrı rezervi var.
    try:
        import os as _os
        import sys as _sys
        _c = _os.path.join(str(THIS_DIR), "10_CANLI")
        if _c not in _sys.path:
            _sys.path.append(_c)
        import canli_db as _cdb
        _cdb.kur()
        for _a, _v in (("pencere_hafta_ici", "12:00-24:00"),
                       ("pencere_hafta_sonu", "10:00-24:00"),
                       ("genis_pencere_bitis", "")):
            if _cdb.ayar_oku(_a, "__yok__") != _v:
                _cdb.ayar_yaz(_a, _v)
        print(f"[{_ts()}] 📡 toplama penceresi: hafta içi 12:00-24:00 · "
              f"hafta sonu 10:00-24:00 (kalıcı)", flush=True)
    except Exception as e:
        print(f"[{_ts()}] PENCERE HATA: {e}", flush=True)

    # 🗓 ERA-4 — bir kez, kendiliğinden. Üretime elle müdahale edilmediği için
    # geçiş buradan yapılır: era_no < 4 ise kurulur, sonraki açılışlarda atlanır.
    #
    # NEDEN GEREKTİ: ERA-3'ün karnesi bozuk sayılarla kirlendi. Lig P&L'i kasa
    # alanlarından hesaplanıyordu ve kadro dışı bırakma işlemi o alanları
    # değiştirdiği için yüzdeler anlamsızlaştı — kasa eksiye düştü (ÇARPAN
    # -1.500 TL), kârda olan ajan atıldı (EUVOX +232 TL iken "lig sonuncusu").
    # Kural düzeltildi ama ESKİ SAYILAR duruyor; temiz karşılaştırma ancak
    # ortak başlangıçla mümkün. start_era arşivler, sıfırlar, benched=0 yapar.
    try:
        import agents as _agents
        import db as _db          # worker modül düzeyinde db'yi almıyor
        _conn = _db.connect()
        try:
            _r = _conn.execute(
                "SELECT MAX(COALESCE(era_no,0)) FROM paper_portfolio").fetchone()
            _era = int((_r[0] if _r else 0) or 0)
        finally:
            _conn.close()
        if _era < 4:
            print(f"[{_ts()}] 🗓 ERA-4 kuruluyor (mevcut era {_era})", flush=True)
            _agents.start_era(era_no=4, bankroll=1000.0)
        else:
            print(f"[{_ts()}] era {_era} — ERA-4 geçişi zaten yapılmış", flush=True)
    except Exception as e:
        print(f"[{_ts()}] ERA-4 HATA: {e}", flush=True)

    # 🟢 TOTO TAKIM · ERA-5 — YALNIZ bu takım, bir kez.
    #
    # NEDEN: 01.11.2026'da Toto takımının kârlılık şartı değişti. Eski kural
    # kenarı MARJSIZ olasılığa göre süzüyordu ve kendi modelimize göre bile
    # kaybeden bahisleri geçiriyordu (Kuzey Makedonya-İsviçre: bizim %18,9,
    # başabaş %21,3, beklenen getiri 0,888). Yeni kural p × oran ≥ 1,03.
    # TOTOCU'nun o ana kadarki 2 bahsi ESKİ kuralla açılmıştı; karnede
    # durmaları yeni kuralın ölçümünü yanıltır.
    #
    # Diğer takımlara DOKUNULMAZ: onların kuralı değişmedi, biriktirdikleri
    # veri geçerli. Lig saati de sıfırlanmaz.
    try:
        import agents as _agents
        import db as _db
        _conn = _db.connect()
        try:
            _r = _conn.execute(
                "SELECT MIN(COALESCE(era_no,0)) FROM paper_portfolio "
                "WHERE portfolio_id IN ('TOTOCU_V1','KAZANC_V1','TOTO_KONTROL_V1')"
            ).fetchone()
            _te = int((_r[0] if _r and _r[0] is not None else 0) or 0)
        finally:
            _conn.close()
        if _te < 5:
            print(f"[{_ts()}] 🟢 TOTO ERA-5 kuruluyor (takım erası {_te})", flush=True)
            _agents.start_era(era_no=5, bankroll=1000.0, takim="toto")
        else:
            print(f"[{_ts()}] toto erası {_te} — ERA-5 zaten yapılmış", flush=True)
    except Exception as e:
        print(f"[{_ts()}] TOTO ERA-5 HATA: {e}", flush=True)

    try:
        import agents as _agents
        _agents.preflight()
    except Exception as e:
        print(f"[{_ts()}] PREFLIGHT HATA: {e}")

    job_auto_settle()
    job_kupon_orkestra()
    # 🔫 SWAT açılışta da bir kez: yeni anahtar/lig yapılandırması
    # deploy edilince sonucu 12 saat beklemeden görülsün. Ucuz (5 istek)
    # ve kaynak kapalıysa yalnız hata yazıp geçer.
    job_swat()
    job_fetch_program()

    sched = BlockingScheduler(timezone="UTC")
    sched.add_job(job_auto_play, "cron", hour="6,15", minute=0,
                  id="auto_play", misfire_grace_time=3600, coalesce=True)
    sched.add_job(job_auto_settle, "interval", minutes=90,
                  id="auto_settle", misfire_grace_time=900, coalesce=True)
    # 🎟️ Kupon orkestratörü — saat başı. Ucuz: yalnız açık pozisyonları
    # okur, API çağırmaz.
    # 🔫 SWAT veri hattı — günde iki kez yeter: ilk yarı skoru maç
    # bitince sabitlenir, acele etmeye gerek yok. 5 lig = 5 istek.
    sched.add_job(job_swat, "cron", hour="5,17", minute=30,
                  id="swat", misfire_grace_time=3600, coalesce=True,
                  max_instances=1)
    sched.add_job(job_kupon_orkestra, "interval", hours=1,
                  id="kupon_orkestra", misfire_grace_time=1800, coalesce=True,
                  max_instances=1)
    sched.add_job(job_fetch_program, "interval", hours=3,
                  id="fetch_program", misfire_grace_time=1800, coalesce=True)
    sched.add_job(job_kapanis, "interval", minutes=15,
                  id="kapanis", misfire_grace_time=300, coalesce=True,
                  max_instances=1)
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
