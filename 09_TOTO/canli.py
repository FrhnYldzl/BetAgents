"""
TOTO · CANLI HAFTA — "bu hafta ne oynayalım, neden?"
====================================================
Yayındaki Spor Toto programı için uçtan uca (üretimde ağır veri İŞLEMEZ):

  1. Program: sportoto.gov.tr (15 maç, kapanış = ilk maçın başlangıcı)
  2. PİYASA: iddaa'nın o anki 1/0/2 fiyatı (Toto'nun KENDİ çekimi; BetAgents'a dokunmaz)
  3. Ajanlar: ELO · FORM · H2H — hafızaları model_durum.json'dan (durum.py)
  4. Ajan pazarı: cüzdan ağırlıklı fiyat (cüzdanlar geçmiş isabetten; haftalık güncellenir)
  5. Kalabalık (q): Türkiye'deki oyuncuların işaretleme tahmini (β·log p + popülerlik)
  6. Havuz: son sonuçlanan haftanın dağıtılan tutarı + devir. Önceki hafta henüz
     sonuçlanmadıysa devir BELİRSİZ → iki senaryo (devir yok / devir var) hesaplanır
  7. Kuponlar: profil × bütçe — her işaretin gerekçesiyle

Kullanım:  python canli.py [--butce=32,256,2048]
"""
from __future__ import annotations

import json
import math
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone

import numpy as np

import durum as DURUM
import kadro as KADRO
from ajanlar import form_p, sirali_lojit_p
from deger import Degerlendirici, boyut, kur
from esle import benzer
from kaynaklar import marjsiz
from kalabalik import PARAM_DOSYA, kolon_sayisi, parametreler, q_uret
from pazar import KESIR, Pazar, aile_pazari
from sportoto import _mac, api, haftalar, ham_guncelle
from toto_ortak import CACHE, KADEME_PAY, MILLI_EN, SECENEK, kolon_bedeli, populer, turnuva

TR = timezone(timedelta(hours=3))
IDDAA = "https://sportsbookv2.iddaa.com/sportsbook/events?st=1&type=0"
IDDAA_H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                         "Chrome/120.0.0.0 Safari/537.36",
           "Accept": "application/json, text/plain, */*", "Accept-Language": "tr-TR,tr;q=0.9",
           "Referer": "https://www.iddaa.com/", "Origin": "https://www.iddaa.com"}
PROFIL_AD = {"FAVORİ": "Favori", "15_AVCISI": "15 Avcısı", "DENGELİ": "Dengeli"}
PROFIL_ACIKLAMA = {
    "FAVORİ": "15'i EN SIK tutturan sistem: her maçta en olası sonuç(lar). Kalabalık da bunu oynar — "
              "15 gelse bile ikramiye çok kişiyle bölünür. Karşılaştırma için.",
    "15_AVCISI": "DEĞERLİ 15 peşinde: hem olası hem kalabalığın az oynadığı sonuçlar. 15 gelirse "
                 "ikramiyeyi az kişiyle paylaşır. İsabet seyrek, isabet olursa büyük.",
    "DENGELİ": "Dört derecenin (15-14-13-12) toplam beklenen getirisini en çok yapan sistem.",
}


# ── 1. program ────────────────────────────────────────────────────
def guncel_program() -> dict:
    turlar = api("api/GameRound") or []
    t = max(turlar, key=lambda x: x["id"])
    ham = api(f"api/GameMatch/GetGameMatches/?gameRoundId={t['id']}") or []
    return {"id": t["id"], "sezon": t.get("year"), "ad": t.get("name"), "kapanis": t.get("roundCloseDate"),
            "liste_gorseli": (t.get("attachment") or {}).get("attachmentName"),
            "maclar": [_mac(x) for x in ham]}


# ── 2. iddaa fiyatı ───────────────────────────────────────────────
def iddaa_olaylar() -> list[dict]:
    for i in range(2):
        try:
            with urllib.request.urlopen(urllib.request.Request(IDDAA, headers=IDDAA_H), timeout=30) as r:
                return json.loads(r.read()).get("data", {}).get("events", []) or []
        except Exception:
            if i:
                raise
            time.sleep(5)
    return []


def _ms_oran(ev: dict):
    for m in ev.get("m", []) or []:
        if m.get("t") == 1 and m.get("st") == 1:
            d = {}
            for o in m.get("o", []) or []:
                n = str(o.get("n") or "").strip().upper()
                d["0" if n == "X" else n] = o.get("odd")
            if all(d.get(k) for k in ("1", "0", "2")):
                return (float(d["1"]), float(d["0"]), float(d["2"]))
    return None


def iddaa_esle(maclar: list[dict], olaylar: list[dict]) -> list[dict | None]:
    out = []
    for m in maclar:
        t = datetime.fromisoformat(m["tarih"][:19]).replace(tzinfo=TR)
        en, en_s = None, 0.0
        for e in olaylar:
            try:
                te = datetime.fromtimestamp(int(e.get("d")), tz=timezone.utc)
            except Exception:
                continue
            if abs((te - t).total_seconds()) > 36 * 3600:
                continue
            s = benzer(m["ev"], e.get("hn") or "") + benzer(m["dep"], e.get("an") or "")
            if s > en_s:
                en, en_s = e, s
        if en is not None and en_s >= 1.5:
            o = _ms_oran(en)
            out.append({"event_id": en.get("i"), "ev": en.get("hn"), "dep": en.get("an"), "oran": o,
                        "p": (marjsiz(o).tolist() if o else None), "skor": round(en_s, 2)})
        else:
            out.append(None)
    return out


# ── 3. ajanlar (durum dosyasından) ────────────────────────────────
class Ajanlar:
    def __init__(self, d: dict | None = None):
        self.d = d or DURUM.yukle()
        self.lk = self.d["lojit"]["kulup"]
        self.lm = self.d["lojit"]["milli"]

    def _kulup_ad(self, u, ad):
        adlar = list(self.d["elo"]["kulup"].get(u, {}).keys())
        en = max(adlar, key=lambda t: benzer(ad, t), default=None)
        return en if en is not None and benzer(ad, en) >= 0.75 else None

    def _h2h(self, tur, a, b, onsel, kappa=8.0):
        h = self.d["h2h"][tur]
        s1 = np.array(h.get(f"{a}|{b}", [0, 0, 0]), float)
        s2 = np.array(h.get(f"{b}|{a}", [0, 0, 0]), float)[::-1] * 0.7
        say = s1 + s2
        n = int(round(np.array(h.get(f"{a}|{b}", [0, 0, 0])).sum() + np.array(h.get(f"{b}|{a}", [0, 0, 0])).sum()))
        return ((say + kappa * onsel) / (say.sum() + kappa)).tolist(), n

    def _form(self, lig, a, b):
        f = self.d["form"].get(lig)
        if not f:
            return None
        p = form_p(f, a, b)
        return p.tolist() if p is not None else None

    def karne(self, m: dict, H: list | None = None) -> dict:
        """İki takımın karnesi: Elo (sıra), hücum/savunma (lig içi sıra), Toto geçmişi."""
        t = turnuva(m["turnuva"])
        out = {"ev": {}, "dep": {}}
        milli = m["milli"] or t.get("aile") == "MILLI"
        if milli:
            em = self.d["elo"]["milli"]
            sirali = sorted(em, key=lambda k: -em[k])
            adlar = {"ev": MILLI_EN.get(m["ev"]), "dep": MILLI_EN.get(m["dep"])}
            f = self.d["form"].get("MILLI")
            for y, a in adlar.items():
                if a and a in em:
                    out[y]["elo"] = round(em[a]); out[y]["elo_sira"] = f"{sirali.index(a) + 1}/{len(sirali)} (dünya)"
                if f and a in f["hucum"]:
                    out[y].update(self._form_sira(f, a, "dünya"))
        else:
            lig = t.get("fd") or t.get("fdn")
            if lig:
                u = self.d["ulke"].get(lig, lig)
                ek = self.d["elo"]["kulup"].get(u, {})
                f = self.d["form"].get(lig)
                lig_takim = set(f["hucum"]) if f else set(ek)
                sirali = sorted([k for k in ek if k in lig_takim] or ek, key=lambda k: -ek[k])
                for y, ad in (("ev", m["ev"]), ("dep", m["dep"])):
                    a = self._kulup_ad(u, ad)
                    if a and a in ek:
                        out[y]["elo"] = round(ek[a])
                        if a in sirali:
                            out[y]["elo_sira"] = f"{sirali.index(a) + 1}/{len(sirali)} (lig)"
                    if f and a in f["hucum"]:
                        out[y].update(self._form_sira(f, a, "lig"))
        if H:
            for y, ad in (("ev", m["ev"]), ("dep", m["dep"])):
                son = []
                for h in H:
                    for mm in h["maclar"]:
                        if mm["sonuc"] is None or (mm["ev"] != ad and mm["dep"] != ad):
                            continue
                        s = mm["sonuc"]
                        if s == 1:
                            son.append("B")
                        elif (s == 0) == (mm["ev"] == ad):
                            son.append("G")
                        else:
                            son.append("M")
                out[y]["toto_n"] = len(son)
                out[y]["toto_son"] = "".join(son[-5:])
        return out

    @staticmethod
    def _form_sira(f, a, kapsam):
        hs = sorted(f["hucum"], key=lambda k: -f["hucum"][k])
        ss = sorted(f["savunma"], key=lambda k: f["savunma"][k])          # düşük = iyi savunma
        return {"hucum": round(f["hucum"][a], 2), "hucum_sira": f"{hs.index(a) + 1}/{len(hs)}",
                "savunma": round(f["savunma"][a], 2), "savunma_sira": f"{ss.index(a) + 1}/{len(ss)}",
                "form_kapsam": kapsam}

    def gorus(self, m: dict) -> dict:
        t = turnuva(m["turnuva"])
        out = {"ELO": None, "FORM": None, "H2H": None, "not": {}}
        if m["milli"] or t.get("aile") == "MILLI":
            a, b = MILLI_EN.get(m["ev"]), MILLI_EN.get(m["dep"])
            em = self.d["elo"]["milli"]
            if not a or not b or a not in em or b not in em:
                return out
            pe = sirali_lojit_p((em[a] + 100.0 - em[b]) / 400.0, *self.lm)
            out["ELO"] = pe.tolist()
            out["not"]["elo"] = (round(em[a]), round(em[b]))
            out["FORM"] = self._form("MILLI", a, b)
            out["H2H"], out["not"]["h2h_n"] = self._h2h("milli", a, b, pe)
            return out
        lig = t.get("fd") or t.get("fdn")
        if not lig:
            return out
        u = self.d["ulke"].get(lig, lig)
        a, b = self._kulup_ad(u, m["ev"]), self._kulup_ad(u, m["dep"])
        if not a or not b:
            return out
        ek = self.d["elo"]["kulup"][u]
        pe = sirali_lojit_p((ek[a] + self.d["elo"]["ev_avantaji"].get(lig, 60.0) - ek[b]) / 400.0, *self.lk)
        out["ELO"] = pe.tolist()
        out["not"]["elo"] = (round(ek[a]), round(ek[b]))
        out["FORM"] = self._form(lig, a, b)
        out["H2H"], out["not"]["h2h_n"] = self._h2h("kulup", a, b, pe)
        return out


# ── gerekçe metinleri ─────────────────────────────────────────────
def _yuzde(x: float) -> str:
    return f"%{x * 100:.0f}"


def mac_gerekcesi(s: dict, P: np.ndarray, Q: np.ndarray) -> dict:
    """Bir maçın kalabalık-değer özeti: kim fazla, kim az oynanıyor; en değerli seçim."""
    oran = P / np.maximum(Q, 1e-9)
    fav = int(np.argmax(P))
    deger = int(np.argmax(oran))
    fazla = int(np.argmax(Q / np.maximum(P, 1e-9)))
    ent = float(-(P * np.log(np.maximum(P, 1e-12))).sum() / math.log(3))
    satir = []
    satir.append(f"Olasılık (pazar): 1 {_yuzde(P[0])} · 0 {_yuzde(P[1])} · 2 {_yuzde(P[2])}")
    satir.append(f"Kalabalık oynuyor: 1 {_yuzde(Q[0])} · 0 {_yuzde(Q[1])} · 2 {_yuzde(Q[2])}")
    if oran[fazla] < 0.92:
        satir.append(f"Aşırı oynanan: {SECENEK[fazla]} (kalabalık {_yuzde(Q[fazla])}, gerçek {_yuzde(P[fazla])})")
    if oran[deger] > 1.08:
        satir.append(f"Değerli seçim: {SECENEK[deger]} — gerçek {_yuzde(P[deger])}, oynanan {_yuzde(Q[deger])} "
                     f"(değer oranı {oran[deger]:.2f})")
    return {"favori": SECENEK[fav], "deger": SECENEK[deger], "deger_orani": [round(float(x), 3) for x in oran],
            "belirsizlik": round(ent, 3), "satirlar": satir}


def kupon_gerekcesi(S, P, Q, gerekce_mac) -> list[str]:
    out = []
    for i, x in enumerate(S):
        isr = " ".join(SECENEK[j] for j in x)
        fav = int(np.argmax(P[i]))
        if len(x) == 3:
            neden = "üçlü: belirsiz maç, sigorta"
        elif len(x) == 2:
            neden = "ikili: " + " + ".join(f"{SECENEK[j]} ({_yuzde(P[i][j])})" for j in x)
        elif x[0] == fav:
            neden = f"favori ({_yuzde(P[i][fav])}; kalabalık {_yuzde(Q[i][fav])})"
        else:
            j = x[0]
            neden = (f"kontra: {SECENEK[j]} gerçek {_yuzde(P[i][j])}, kalabalık {_yuzde(Q[i][j])} oynuyor "
                     f"— tutarsa ikramiyeyi az kişiyle bölüşürüz")
        out.append(f"{i + 1}. {isr} — {neden}")
    return out


def sans_metni(p: float) -> str:
    if p <= 0:
        return "—"
    n = 1.0 / p
    if n < 1.5:
        return "neredeyse her hafta"
    if n < 60:
        return f"≈ {n:.0f} haftada bir"
    yil = n / 52.0
    return f"≈ {yil:.0f} yılda bir" if yil < 1000 else "çok uzak ihtimal"


# ── 4–7. hafta analizi ────────────────────────────────────────────
def _cuzdanlar(param: dict, db_oku: bool = False) -> dict:
    """{"KULUP": {...}, "MILLI": {...}} — üretimde (db_oku=True) önce Toto'nun kendi tablosu (haftalık
    güncellenir), yoksa kalibrasyon dosyası. Milli cüzdan tabloda "M:" önekiyle durur.

    ⚠️ Yerel komut satırı ve zamanlanmış hatırlatıcı db_oku=False çalışır: .env yerelde otomatik
    yüklendiği için veritabanına dokunmak ÜRETİME bağlanmak demektir (railway-genel-proxy dersi —
    genel proxy bağlantısı canlı siteyi dondurabilir). Veritabanını yalnız Railway'deki Toto
    zamanlayıcısı okur/yazar."""
    out = {"KULUP": dict(param.get("pazar_servet") or {}),
           "MILLI": dict(param.get("pazar_servet_milli") or param.get("pazar_servet") or {})}
    if not db_oku:
        return out
    try:
        import toto_db
        w = toto_db.son_cuzdan()
        if w:
            k = {a: v for a, v in w.items() if not a.startswith("M:")}
            m = {a[2:]: v for a, v in w.items() if a.startswith("M:")}
            if k:
                out["KULUP"] = k
            if m:
                out["MILLI"] = m
    except Exception:
        pass
    return out


def analiz(butceler=(32, 256, 2048), profiller=("FAVORİ", "15_AVCISI", "DENGELİ"), program: dict | None = None,
           olaylar: list | None = None, hafta_listesi: list | None = None, cuzdan_db: bool = False) -> dict:
    t0 = time.time()
    param = json.loads(PARAM_DOSYA.read_text(encoding="utf-8"))
    th = parametreler()
    prog = program or guncel_program()
    maclar = prog["maclar"]
    try:
        olaylar = iddaa_olaylar() if olaylar is None else olaylar
    except Exception:
        olaylar = []
    idd = iddaa_esle(maclar, olaylar)
    AJ = Ajanlar()
    CZ = _cuzdanlar(param, db_oku=cuzdan_db)
    PZ = {a: Pazar(CZ[a], kesir=KESIR[a]) for a in ("KULUP", "MILLI")}
    H = hafta_listesi if hafta_listesi is not None else haftalar()
    satir = []
    for i, m in enumerate(maclar):
        g = AJ.gorus(m)
        gor = {"PİYASA": idd[i]["p"] if idd[i] else None, "ELO": g["ELO"], "FORM": g["FORM"], "H2H": g["H2H"]}
        t = turnuva(m["turnuva"])
        aile = "MILLI" if m["milli"] else t.get("aile")
        try:                                   # KADRO: eksik oyuncular (veri penceresi dışında susar)
            kp, kn = KADRO.kadro_gorusu(m, gor["PİYASA"] or g["ELO"], m["milli"] or aile == "MILLI")
            gor["KADRO"] = kp
            if kn:
                g["not"]["kadro"] = kn
        except Exception as _e:
            gor["KADRO"] = None
            g["not"]["kadro_hata"] = f"{type(_e).__name__}"
        pazar = PZ[aile_pazari(aile)]
        pi, pay = pazar.fiyat(gor)
        ptr, peu = populer(m["ev"]); dtr, deu = populer(m["dep"])
        satir.append({"sira": i + 1, "tarih": m["tarih"], "ev": m["ev"], "dep": m["dep"], "turnuva": t["ad"],
                      "aile": aile, "iddaa": idd[i], "gorus": gor, "pay": pay,
                      "pi": (pi.tolist() if pi is not None else None), "not": g["not"],
                      "pop_tr": (ptr, dtr), "pop_eu": (peu, deu), "islemler": pazar.islemler(gor),
                      "karne": AJ.karne(m, [h for h in H if h["kapanis"] < (prog["kapanis"] or "9999")])})
    P = np.array([s["pi"] if s["pi"] is not None else [0.45, 0.28, 0.27] for s in satir], float)
    Pref = np.array([s["iddaa"]["p"] if s["iddaa"] and s["iddaa"]["p"] is not None else P[i]
                     for i, s in enumerate(satir)], float)
    Q = q_uret(Pref, np.array([s["pop_tr"] for s in satir], float), np.array([s["pop_eu"] for s in satir], float),
               th, [s["aile"] for s in satir])
    for i, s in enumerate(satir):
        s["q"] = Q[i].tolist()
        s["gerekce"] = mac_gerekcesi(s, P[i], Q[i])
        s["bilgi"] = "piyasa" if s["iddaa"] and s["iddaa"]["p"] else ("ajan" if s["pi"] is not None else "yok")
    # havuz: son SONUÇLANAN haftanın D'si; devir önceki haftanın durumuna göre
    kap = prog["kapanis"] or datetime.now(TR).isoformat()
    onceki = [h for h in H if h["kapanis"] < kap]
    son_tamam = next((h for h in reversed(onceki) if h["ikramiye"] and h["D"]), None)
    D = son_tamam["D"] if son_tamam else 1e8
    hemen_once = onceki[-1] if onceki else None
    if hemen_once and hemen_once["ikramiye"]:
        devir = dict(hemen_once.get("devir_giden") or {k: 0.0 for k in KADEME_PAY})
        devir_kesin, devir_senaryo = True, None
    else:
        devir = {k: 0.0 for k in KADEME_PAY}
        devir_kesin = False
        gelen = (hemen_once or {}).get("devir_gelen") or {k: 0.0 for k in KADEME_PAY}
        devir_senaryo = {k: float(gelen.get(k, 0.0)) + KADEME_PAY[k] * D for k in KADEME_PAY}
    havuz = {k: KADEME_PAY[k] * D + devir.get(k, 0.0) for k in KADEME_PAY}
    fiyat = kolon_bedeli(kap)
    N = kolon_sayisi(D, kap, th, prog["sezon"])
    deg = Degerlendirici(P, Q, N, havuz, M=16000, tohum=prog["id"])
    kuponlar = []
    for prof in profiller:
        for B in butceler:
            S, _ = kur(P, Q, N, havuz, B, prof, deg)
            r = Degerlendirici(P, Q, N, havuz, M=60000, tohum=prog["id"] + 1).degerle(S)
            kol = boyut(S)
            k = {"profil": prof, "profil_ad": PROFIL_AD[prof], "profil_aciklama": PROFIL_ACIKLAMA[prof],
                 "butce": B, "kolon": kol, "maliyet": kol * fiyat, "S": [list(map(int, x)) for x in S],
                 "isaret": [" ".join(SECENEK[j] for j in x) for x in S],
                 "ev_tl": r["ev"] / (kol * fiyat), "ev": r["ev"], "ev_k": r["ev_k"],
                 "p15": r["p15"], "p14p": r["p14p"], "p13p": r["p13p"], "p12p": r["p12p"],
                 "odul15": r["odul15"], "sans15": sans_metni(r["p15"]), "sans12": sans_metni(r["p12p"]),
                 "gerekce": kupon_gerekcesi(S, P, Q, None)}
            if devir_senaryo:
                hv2 = {kk: KADEME_PAY[kk] * D + devir_senaryo[kk] for kk in KADEME_PAY}
                r2 = Degerlendirici(P, Q, N, hv2, M=60000, tohum=prog["id"] + 1).degerle(S)
                k["ev_tl_devirli"] = r2["ev"] / (kol * fiyat)
                k["odul15_devirli"] = r2["odul15"]
            kuponlar.append(k)
    kap_dt = datetime.fromisoformat(kap[:19]).replace(tzinfo=TR)
    return {"hafta": {k: prog[k] for k in ("id", "sezon", "ad", "kapanis", "liste_gorseli")},
            "olusturma": datetime.now(TR).isoformat(timespec="minutes"),
            "kalan_saat": round((kap_dt - datetime.now(TR)).total_seconds() / 3600, 1),
            "fiyat": fiyat, "D_tahmin": D, "devir": devir, "devir_kesin": devir_kesin,
            "devir_senaryo": devir_senaryo, "havuz": havuz, "N_tahmin": N,
            "onceki_hafta": ({"id": hemen_once["id"], "ad": hemen_once["ad"], "sezon": hemen_once["sezon"],
                              "sonuclandi": bool(hemen_once["ikramiye"]), "kapanis": hemen_once["kapanis"],
                              "n": hemen_once["n"], "odul": hemen_once["odul"]} if hemen_once else None),
            # oyun planı m.9/1: yeni program, önceki programın kapanışından sonra satışa açılır
            "satis_acilis": hemen_once["kapanis"] if hemen_once else None,
            "maclar": satir, "P": P.tolist(), "Q": Q.tolist(), "kuponlar": kuponlar,
            "cuzdan": {a: dict(P.W) for a, P in PZ.items()},
            "iddaa_kapsam": sum(1 for s in satir if s["bilgi"] == "piyasa"),
            "model": {"kalabalik_beta": th["beta"], "gTR": th["gTR"], "gEU": th["gEU"], "gTRM": th.get("gTRM"),
                      "sezon_olcek": th.get("log_s"), "param_tarihi": param.get("guncelleme"),
                      "durum_tarihi": AJ.d.get("olusturma")},
            "sure_sn": round(time.time() - t0, 1)}


def _json(o):
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.bool_):
        return bool(o)
    raise TypeError(type(o))


def jsonla(A: dict) -> str:
    return json.dumps(A, ensure_ascii=False, default=_json)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    butce = (32, 256, 2048)
    for a in sys.argv[1:]:
        if a.startswith("--butce"):
            butce = tuple(int(x) for x in a.split("=", 1)[1].split(","))
    ham_guncelle()
    A = analiz(butce)
    yol = CACHE / f"canli_{A['hafta']['id']}.json"
    yol.write_text(jsonla(A), encoding="utf-8")
    print(f"{A['hafta']['sezon']} {A['hafta']['ad']} · kapanış {A['hafta']['kapanis']} · kalan {A['kalan_saat']} sa "
          f"· {A['sure_sn']} sn · iddaa kapsamı {A['iddaa_kapsam']}/15")
    print(f"D {A['D_tahmin'] / 1e6:.1f} M TL · N ≈ {A['N_tahmin'] / 1e6:.1f} M kolon · devir kesin mi: "
          f"{A['devir_kesin']} · senaryo 15: {((A['devir_senaryo'] or {}).get(15, 0)) / 1e6:.1f} M TL")
    for s in A["maclar"]:
        print(f"{s['sira']:2d} {s['ev'][:16]:>16}-{s['dep'][:16]:<16} [{s['bilgi']}] " + " · ".join(s["gerekce"]["satirlar"][2:]))
    for k in A["kuponlar"]:
        print(f"{k['profil_ad']:10s} {k['kolon']:5d} kolon {k['maliyet']:>8,.0f} TL · beklenen/TL {k['ev_tl']:.2f}"
              f" (devirli {k.get('ev_tl_devirli', float('nan')):.2f}) · 15: {k['sans15']} · 12+: {k['sans12']}")
