"""
TOTO · ZAMANLAYICI — BetAgents worker'ından AYRI süreç
=====================================================
start.py tarafından ayrı bir alt süreç olarak başlatılır (TOTO_WORKER=0 ile
kapatılır). Çökerse yalnız Toto durur; BetAgents'ın worker'ı ve paneli etkilenmez.
Yalnız `toto_*` tablolarına yazar.

  senkron      her 60 dk  Spor Toto'dan program + sonuç + ikramiye; yeni hafta
                           yayına girince "yayın" kaydı; sonuç gelince kâğıt
                           kuponları kapatır, cüzdanları günceller, dersi yazar
  analiz       09:00 · 15:00 · 21:00 (TR) açık hafta varsa; ayrıca kapanışa
                           3 saatten az kala son analiz (senkron tetikler)

Elle:  python toto_worker.py --bir-kez      (senkron + analiz, sonra çık)
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

KOK = Path(__file__).resolve().parent
sys.path.insert(0, str(KOK))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import numpy as np  # noqa: E402

import toto_db  # noqa: E402

TR = timezone(timedelta(hours=3))
_ILK_KOSU = True                  # her başlatmadan (yayın) sonra bir kez taze analiz


def _ts() -> str:
    return datetime.now(TR).strftime("%Y-%m-%d %H:%M TR")


def _tr_simdi() -> str:
    return datetime.now(TR).strftime("%Y-%m-%dT%H:%M:%S")


# ── senkron ───────────────────────────────────────────────────────
def senkron() -> None:
    global _ILK_KOSU
    from sportoto import ham_guncelle, haftalar
    print(f"[{_ts()}] TOTO senkron", flush=True)
    try:
        ham = ham_guncelle(sezon_sayisi=2)
        H = haftalar(ham)
        for h in H[-12:]:
            yeni = toto_db.hafta_yaz(h)
            if yeni and not h["ikramiye"] and (h["kapanis"] or "") > _tr_simdi():
                toto_db.kayit("yayin", f"{h['sezon']} {h['ad']} yayında · kapanış {h['kapanis']}")
                print(f"  yeni hafta yayında: {h['sezon']} {h['ad']}", flush=True)
        for h in H[-8:]:
            if h["ikramiye"]:
                kupon = [k for k in toto_db.kuponlar(h["id"]) if k["durum"] == "kagit"]
                if kupon:
                    kapat(h, kupon)
        acik = [h for h in H if not h["ikramiye"] and (h["kapanis"] or "") > _tr_simdi()]
        if acik:
            h = acik[-1]
            kap = datetime.fromisoformat(h["kapanis"][:19]).replace(tzinfo=TR)
            kalan = (kap - datetime.now(TR)).total_seconds() / 3600
            son = toto_db.son_analiz(h["id"])
            yas = 1e9
            if son:
                yas = (datetime.now(TR) - datetime.fromisoformat(son["olusturma"])).total_seconds() / 60
            # kapanışa 3 saat kala taze analiz; ayrıca yayın/yeniden başlatmadan sonra
            # BİR KEZ tazele (dağıtım kendini doğrulasın; saatlik koşu analiz üretmez)
            ilk = _ILK_KOSU
            _ILK_KOSU = False
            kosuldu = False
            if son is None or (0 < kalan <= 3 and yas > 90) or (ilk and yas > 30):
                analiz()
                kosuldu = True
            _istekleri_isle(kosuldu)
    except Exception as e:
        toto_db.kayit("hata", f"senkron: {type(e).__name__}: {e}")
        print(f"[{_ts()}] TOTO senkron HATA: {e}", flush=True)
        traceback.print_exc()


def _istekleri_isle(analiz_kostu: bool = False) -> None:
    """Vibe panelinden bırakılan işler. Web süreci ağır iş yapmaz; burada yürütülür."""
    try:
        import vibe_db
        bekleyen = vibe_db.bekleyen_istekler()
    except Exception:
        return
    for x in bekleyen[:3]:
        try:
            if x["tur"] != "analiz":
                vibe_db.istek_kapat(x["istek_id"], "atlandi", f"bilinmeyen tür: {x['tur']}")
            elif analiz_kostu:
                vibe_db.istek_kapat(x["istek_id"], "bitti", "analiz bu turda zaten tazelendi")
            else:
                analiz()
                analiz_kostu = True
                vibe_db.istek_kapat(x["istek_id"], "bitti", "analiz tazelendi")
        except Exception as e:
            vibe_db.istek_kapat(x["istek_id"], "hata", f"{type(e).__name__}: {e}")


# ── analiz ────────────────────────────────────────────────────────
def analiz() -> None:
    import canli
    from sportoto import haftalar
    print(f"[{_ts()}] TOTO analiz", flush=True)
    try:
        prog = canli.guncel_program()
        if not prog.get("kapanis") or prog["kapanis"] <= _tr_simdi():
            print("  açık hafta yok", flush=True)
            return
        A = canli.analiz(program=prog, hafta_listesi=haftalar(), cuzdan_db=True)
        toto_db.analiz_yaz(prog["id"], canli.jsonla(A))
        toto_db.kupon_yaz(prog["id"], A["kuponlar"])
        toto_db.kayit("analiz", f"{prog['sezon']} {prog['ad']} · iddaa {A['iddaa_kapsam']}/15 · {A['sure_sn']} sn")
        print(f"  analiz yazıldı · iddaa {A['iddaa_kapsam']}/15 · {A['sure_sn']} sn", flush=True)
    except Exception as e:
        toto_db.kayit("hata", f"analiz: {type(e).__name__}: {e}")
        print(f"[{_ts()}] TOTO analiz HATA: {e}", flush=True)
        traceback.print_exc()


# ── kapanış: kâğıt kuponlar, cüzdanlar, ders ──────────────────────
def kapat(h: dict, kupon: list[dict]) -> None:
    from deger import gerceklesen
    from kalabalik import kolon_sayisi, parametreler, pb_ust
    from pazar import KESIR, Pazar, aile_pazari
    A = toto_db.son_analiz(h["id"])
    sonuc = [m["sonuc"] for m in h["maclar"]]
    if any(s is None for s in sonuc):
        return
    n_g = {k: (h["n"][k] or 0) for k in (15, 14, 13, 12)}
    kupon_sonuc = []
    for k in kupon:
        S = [tuple(x) for x in json.loads(k["isaret"])]
        r = gerceklesen(S, sonuc, n_g, h["havuz"])
        toto_db.kupon_kapat(h["id"], k["profil"], k["butce"], r["dogru_en_cok"], r["odeme"])
        kupon_sonuc.append({"profil": k["profil"], "butce": k["butce"], "kolon": k["kolon"], "maliyet": k["maliyet"],
                            "dogru": r["dogru_en_cok"], "odeme": r["odeme"], "kacan": r["kacan_mac"]})
    ders = {"hafta": f"{h['sezon']} {h['ad']}", "kupon": kupon_sonuc, "mac": [], "kalabalik": None}
    if A:
        P, Q = np.array(A["P"]), np.array(A["Q"])
        cz = A.get("cuzdan") or {}
        if cz and "KULUP" not in cz:                       # eski biçim: tek cüzdan
            cz = {"KULUP": cz, "MILLI": dict(cz)}
        PZ = {a: Pazar(cz.get(a), kesir=KESIR[a]) for a in ("KULUP", "MILLI")}
        for i, m in enumerate(A["maclar"]):
            o = sonuc[i]
            gor = {a: (np.array(v) if v is not None else None) for a, v in m["gorus"].items()}
            dogru_ajan = [a for a, v in gor.items() if v is not None and int(np.argmax(v)) == o]
            ders["mac"].append({"sira": i + 1, "mac": f"{m['ev']} - {m['dep']}", "sonuc": ("1", "0", "2")[o],
                                "p": round(float(P[i][o]), 3), "q": round(float(Q[i][o]), 3),
                                "surpriz": bool(P[i][o] < 0.25), "noter": bool(h["maclar"][i]["noter"]),
                                "bilen_ajan": dogru_ajan})
            if not h["maclar"][i]["noter"]:
                PZ[aile_pazari(m.get("aile"))].cozumle(gor, o)
        toto_db.cuzdan_yaz(h["id"], {**PZ["KULUP"].W, **{"M:" + a: w for a, w in PZ["MILLI"].W.items()}})
        th = parametreler()
        x = np.array([Q[i][sonuc[i]] for i in range(15)])
        N = kolon_sayisi(h["D"], h["kapanis"], th, h["sezon"])
        bek = N * pb_ust(x)
        ders["kalabalik"] = {"tahmin": [round(float(v), 1) for v in bek], "gercek": [n_g[k] for k in (15, 14, 13, 12)]}
        ders["olasilik_15"] = float(np.prod([P[i][sonuc[i]] for i in range(15)]))
        ders["surpriz_sayisi"] = sum(1 for d in ders["mac"] if d["surpriz"])
        # insan diliyle ders
        p15 = ders["olasilik_15"]
        oz = [f"{ders['surpriz_sayisi']} sürpriz sonuç (olasılığı %25'in altında). 15 sonucun birlikte olasılığı "
              f"≈ 1/{1 / max(p15, 1e-300):,.0f}".replace(",", ".") + "."]
        oz.append(f"Kalabalık: 15 bilen {n_g[15]} (model {bek[0]:.1f}) · 14 bilen {n_g[14]:,} (model {bek[1]:,.0f}) · "
                  f"12 bilen {n_g[12]:,} (model {bek[3]:,.0f}).".replace(",", "."))
        say = {}
        for dm in ders["mac"]:
            for a in dm["bilen_ajan"]:
                say[a] = say.get(a, 0) + 1
        if say:
            en_a = max(say, key=say.get)
            oz.append(f"Bu haftanın en isabetli ajanı {en_a}: favorisi 15 maçın {say[en_a]}'inde tuttu.")
        for kr in sorted(kupon_sonuc, key=lambda r: -r["dogru"])[:3]:
            kac = ", ".join(f"{i}. maç (sonuç olasılığı %{P[i - 1][sonuc[i - 1]] * 100:.0f})" for i in kr["kacan"][:5])
            oz.append(f"{kr['profil']} {kr['kolon']} kolon: {kr['dogru']} doğru" + (f" — kaçan: {kac}" if kac else ""))
        ders["ozet"] = oz
    toto_db.ders_yaz(h["id"], ders)
    en = max(kupon_sonuc, key=lambda r: r["dogru"]) if kupon_sonuc else None
    toto_db.kayit("sonuc", f"{h['sezon']} {h['ad']} sonuçlandı · 15 bilen {n_g[15]} · en iyi kuponumuz "
                           f"{en['dogru'] if en else '-'} doğru")
    print(f"  {h['sezon']} {h['ad']} kapatıldı", flush=True)


def _uretim_korumasi() -> None:
    """Yerelde (Railway dışında) üretim veritabanına BAĞLANMA — .env yerelde otomatik yüklenir ve
    genel proxy bağlantısı canlı siteyi dondurabilir (railway-genel-proxy dersi)."""
    import db
    railway = any(k.startswith("RAILWAY_") for k in os.environ)
    if db.is_postgres() and not railway and os.environ.get("TOTO_URETIM_ONAY") != "1":
        sys.exit("toto_worker yerelde üretime bağlanmaz. Önizleme için: python 09_TOTO/yerel.py")


def main() -> None:
    from apscheduler.schedulers.blocking import BlockingScheduler
    _uretim_korumasi()
    toto_db.kur()
    try:
        import vibe_db
        vibe_db.kur()                 # Vibe paneli tabloları (sohbet · geri bildirim · istek)
    except Exception as e:
        print(f"[{_ts()}] vibe tabloları kurulamadı: {e}", flush=True)
    toto_db.kayit("basla", "Toto zamanlayıcı başladı")
    print(f"[{_ts()}] TOTO zamanlayıcı başladı", flush=True)
    time.sleep(20)                    # web ve BetAgents worker'ı önce ayağa kalksın
    senkron()
    s = BlockingScheduler(timezone="Europe/Istanbul")
    s.add_job(senkron, "interval", minutes=60, max_instances=1, coalesce=True, misfire_grace_time=600)
    s.add_job(analiz, "cron", hour="9,15,21", minute=5, max_instances=1, coalesce=True, misfire_grace_time=900)
    s.start()


if __name__ == "__main__":
    if "--bir-kez" in sys.argv:
        _uretim_korumasi()
        toto_db.kur()
        senkron()
        if "--analiz" in sys.argv:
            analiz()
    else:
        main()
