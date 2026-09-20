"""
CANLI · TOPLAYICI — ayrı süreç, kendi tabloları
================================================
İki ritim:
  FİYAT  iddaa akışı her `FIYAT_SN` saniyede (ücretsiz, sınırsıza yakın)
  DURUM  API-Football `fixtures?live=all` her `DURUM_SN` saniyede
         (günde 100 istek kotası: yalnız canlı maç varken ve seyrek)

Maç öncesi fiyat, maç başlamadan ÖNCE kaydedilir — canlıya geçince akışta
kalmıyor ve modelin tek sağlam girdisi o.

Üretim koruması: Railway dışında PostgreSQL'e yazmaz (canlı veritabanını
yerelden kirletmemek için). Yerelde SQLite önizlemesine yazar.
"""
from __future__ import annotations

import os
import sys
import time
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

KOK = Path(__file__).resolve().parent
for _p in (str(KOK), str(KOK.parent / "02_VERI")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import canli_db  # noqa: E402
import canli_kaynak as KAYNAK  # noqa: E402
import canli_model as MODEL  # noqa: E402

TR = timezone(timedelta(hours=3))
# 45 sn: gole aşırı tepki birkaç dakikada sönüyor; 120 sn ile sıçrama ıskalanır.
# iddaa çekimi ücretsiz, tek maliyet bant genişliği.
FIYAT_SN = int(os.environ.get("CANLI_FIYAT_SN", "45"))
DURUM_SN = int(os.environ.get("CANLI_DURUM_SN", "300"))
ONMAC_SN = int(os.environ.get("CANLI_ONMAC_SN", "900"))
BITTI = {"FT", "AET", "PEN", "PST", "CANC", "ABD", "AWD", "WO"}


def _ts() -> str:
    return datetime.now(TR).strftime("%Y-%m-%d %H:%M TR")


def _uretim_korumasi() -> None:
    import db
    if db.is_postgres() and not os.environ.get("RAILWAY_ENVIRONMENT") \
            and os.environ.get("CANLI_URETIM_ONAY") != "1":
        sys.exit("CANLI: üretim veritabanına yerelden yazma engellendi "
                 "(RAILWAY_ENVIRONMENT yok). Yerel için BETAGENTS_DB=sqlite kullan.")


class Toplayici:
    def __init__(self) -> None:
        self.son_durum = 0.0
        self.son_onmac = 0.0
        self.durum: list[dict] | None = None
        self.af_hata = 0

    def _onmac(self) -> int:
        """Başlamamış maçların fiyatını sakla (bir kez yazılır)."""
        n = 0
        for m in KAYNAK.iddaa_onmac():
            try:
                canli_db.mac_yaz({**m, "durum": "bekliyor"})
                n += 1
            except Exception:
                pass
        return n

    def tur(self) -> dict:
        simdi = time.time()
        if simdi - self.son_onmac >= ONMAC_SN:
            try:
                self._onmac()
                self.son_onmac = simdi
            except Exception as e:
                canli_db.kayit("hata", f"önmaç: {type(e).__name__}: {e}")
        idd = KAYNAK.iddaa_canli()
        if not idd:
            return {"canli": 0, "yazilan": 0}
        # durum yalnız seyrek tazelenir (kota)
        if self.durum is None or simdi - self.son_durum >= DURUM_SN:
            try:
                d = KAYNAK.af_canli()
                if d is not None:
                    self.durum, self.son_durum, self.af_hata = d, simdi, 0
                else:
                    self.af_hata += 1
            except Exception:
                self.af_hata += 1
        M = KAYNAK.esle(idd, self.durum)
        once = canli_db.oran_once_harita()
        yazilan = 0
        for m in M:
            p_piyasa = MODEL.marjsiz(m.get("oran")) if m.get("oran") else None
            oz = once.get(m["mac_id"]) or {}
            oz12 = oz.get("1X2") if isinstance(oz, dict) else oz      # eski biçim: düz 1X2 üçlüsü
            p_once = MODEL.marjsiz(oz12) if oz12 else None
            p_model = None
            if m.get("dakika") is not None:
                p_model = MODEL.inplay(p_once, m.get("dakika"), m.get("safha"), m.get("ev_skor"),
                                       m.get("dep_skor"), m.get("kirmizi_ev") or 0,
                                       m.get("kirmizi_dep") or 0)["p"]
            bitti = (m.get("safha") or "") in BITTI
            canli_db.mac_yaz({**m, "durum": "bitti" if bitti else "canli",
                              "sonuc_ev": m.get("ev_skor") if bitti else None,
                              "sonuc_dep": m.get("dep_skor") if bitti else None})
            canli_db.anlik_yaz(m["mac_id"], {
                "dakika": m.get("dakika"), "safha": m.get("safha"), "ev_skor": m.get("ev_skor"),
                "dep_skor": m.get("dep_skor"), "kirmizi_ev": m.get("kirmizi_ev"),
                "kirmizi_dep": m.get("kirmizi_dep"), "oran": m.get("oran"), "pazar": m.get("pazar"),
                "p_piyasa": [round(x, 4) for x in p_piyasa] if p_piyasa else None,
                "p_model": [round(x, 4) for x in p_model] if p_model else None})
            yazilan += 1
        return {"canli": len(M), "yazilan": yazilan,
                "durumlu": sum(1 for m in M if m.get("dakika") is not None)}


def basla() -> None:
    _uretim_korumasi()
    canli_db.kur()
    canli_db.kayit("basla", "CANLI toplayıcı başladı")
    print(f"[{_ts()}] CANLI toplayıcı başladı · fiyat {FIYAT_SN} sn · durum {DURUM_SN} sn", flush=True)
    t = Toplayici()
    bos = 0
    kapali_bildirildi = False
    while True:
        # Panelden açılıp kapanan anahtar: KAPALIYKEN HİÇBİR İSTEK YAPILMAZ.
        # Varsayılan kapalı — boşuna kaynak ve API kotası harcamasın.
        try:
            acik = canli_db.ayar_oku("toplayici", "kapali") == "acik"
        except Exception:
            acik = False
        if not acik:
            if not kapali_bildirildi:
                print(f"[{_ts()}] toplayıcı KAPALI (panelden açılır) — bekliyor", flush=True)
                kapali_bildirildi = True
            time.sleep(60)
            continue
        if kapali_bildirildi:
            print(f"[{_ts()}] toplayıcı AÇILDI", flush=True)
            kapali_bildirildi = False
        try:
            r = t.tur()
            if r["canli"]:
                bos = 0
                print(f"[{_ts()}] canlı {r['canli']} · durumlu {r.get('durumlu', 0)} · "
                      f"yazılan {r['yazilan']}", flush=True)
            else:
                bos += 1
                if bos % 10 == 1:
                    print(f"[{_ts()}] sahada maç yok", flush=True)
        except Exception as e:
            canli_db.kayit("hata", f"tur: {type(e).__name__}: {e}")
            print(f"[{_ts()}] CANLI HATA: {e}", flush=True)
            traceback.print_exc()
        time.sleep(FIYAT_SN if bos < 5 else FIYAT_SN * 4)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if "--bir-kez" in sys.argv:
        _uretim_korumasi()
        canli_db.kur()
        print(Toplayici().tur())
        print("sayım:", canli_db.sayim())
    else:
        basla()
