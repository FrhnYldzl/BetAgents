"""
TOTO · GERİ TEST — "bu sistemle geçmiş haftalarda oynasaydık ne olurdu?"
=======================================================================
İleriye yürüyen (walk-forward) protokol — her hafta YALNIZ o haftanın
kapanışından önce bilinebilecek bilgiyle kurulur:

  P (bizim olasılık)   ajan pazarı fiyatı; PİYASA ajanı AÇILIŞ fiyatını görür
                       (Toto kapanırken maçların kapanış fiyatı henüz yok)
  q (kalabalık)        kalabalık modeli, o haftadan ÖNCEKİ haftalarla kalibre
                       (her 4 haftada yeniden; ilk 26 hafta yalnız ısınma)
  N, havuzlar          geçen haftanın dağıtılan tutarı (D) + ilan edilmiş devir
  kupon                profil × bütçe (kolon) — FAVORİ / 15_AVCISI / DENGELİ

Sonuç açıklanınca: gerçek sonuç ve gerçek ikramiyelerle kuponun ödemesi
(kendi kolonlarımız kazanan sayısına eklenir), en çok kaç doğru, kaçan maçlar.

Bilgisi eksik hafta (15 maçın 2'sinden fazlasında hiçbir ajanın görüşü yok)
atlanır ve raporda sayılır — kör oynanan hafta, sistemin sınavı değildir.

Çıktı: veri_cache/geri_test.pkl (+ özet yazdırır)
"""
from __future__ import annotations

import sys
import time

import numpy as np
import pandas as pd

from deger import Degerlendirici, boyut, gerceklesen, kur
from kalabalik import VARSAYILAN, hafta_ozeti, kalibre_et, kolon_sayisi, q_sabit, q_uret
from pazar import ileri_yurut
from sportoto import haftalar
from toto_ortak import CACHE, KADEME_PAY, kolon_bedeli

PROFILLER = ("FAVORİ", "15_AVCISI", "DENGELİ")
BUTCELER = (32, 256, 2048)
ISINMA = 26
YENIDEN_KALIBRE = 4


def _p_ref(r):
    """Kalabalığın referans fiyatı: açılış → kapanış → pazar fiyatı."""
    for c in ("p_acilis", "p_piyasa", "pi"):
        v = r.get(c)
        if v is not None and not (isinstance(v, float) and np.isnan(v)):
            return np.asarray(v, float)
    return None


def hazirla_veri():
    df = pd.read_pickle(CACHE / "veri_seti.pkl")
    # PİYASA ajanı açılış fiyatını görür (kapanış Toto kapanışından sonra oluşur)
    df["p_piyasa_kapanis"] = df["p_piyasa"]
    df["p_piyasa"] = [a if a is not None else b for a, b in zip(df["p_acilis"], df["p_piyasa_kapanis"])]
    pi, pazar = ileri_yurut(df)
    df["pi"] = pi
    df["p_ref"] = [_p_ref(r) for r in df.to_dict("records")]
    return df, pazar


def _kupon(prof: str, P, Q, N, havuz, B: int, deg, tohum: int):
    """Kuponu kuran kimse ona yönlendir.

    Klasik profiller (FAVORİ/15_AVCISI/DENGELİ) deger.kur()'a gider.
    TOTO TAKIM ajanları kendi ağırlıklı kurucularını kullanır — böylece
    ajanlar bu modülün SIZINTISIZ yürüyen protokolünde sınanır: kalabalık
    modeli yalnız önceki haftalarla kalibre, PİYASA açılış fiyatını görür,
    havuz geçen haftanın D'si. Ajan için ayrı bir geri test yazmak, bu
    korumaların ikinci kez ve yanlış kurulması riskini doğururdu.
    """
    try:
        import toto_takim as TT
        if prof in TT.TAKIM:
            return TT.kupon(prof, P, Q, N, havuz, B, deg, tohum + B)
    except ImportError:
        pass
    S, _ = kur(P, Q, N, havuz, B, prof, deg)
    return S


def calis(profiller=PROFILLER, butceler=BUTCELER, bas: str | None = None, son: str | None = None,
          M: int = 12000, cikti: str = "geri_test"):
    """`cikti` çıktı dosyasının adı. Varsayılan geri_test.pkl — Geçmiş Test
    sayfasının okuduğu dosya. TOTO TAKIM gibi ayrı bir profil kümesini
    koştururken BAŞKA bir ad verilmeli, yoksa klasik profillerin sonucu
    sessizce ezilir ve sayfa yanlış veriyi gösterir."""
    t0 = time.time()
    df, pazar = hazirla_veri()
    H = [h for h in haftalar() if h["ikramiye"] and h["D"]]
    gruplar = {hid: g.sort_values("sira") for hid, g in df.groupby("hafta_id")}
    th = dict(VARSAYILAN)
    gecmis_veri = []          # kalibrasyon için (ozet, y, D, kapanis)
    kayit, atlanan = [], []
    son_kal = -99
    D_once = None
    for n, h in enumerate(H):
        g = gruplar.get(h["id"])
        satir = g.to_dict("records") if g is not None else []
        if len(satir) != 15 or not h["sonuclandi"]:
            D_once = h["D"]
            continue
        # ── ex-ante: kalabalık modeli bu haftadan önceki veriyle ──
        if n >= ISINMA and (n - son_kal) >= YENIDEN_KALIBRE and len(gecmis_veri) >= ISINMA:
            th, _ = kalibre_et(gecmis_veri, baslangic=th)
            son_kal = n
        bilgisiz = sum(1 for r in satir if r["pi"] is None)
        uygun = n >= ISINMA and bilgisiz <= 2 and D_once and (bas is None or h["kapanis"] >= bas) \
            and (son is None or h["kapanis"] < son)
        if uygun:
            P = np.array([np.asarray(r["pi"], float) if r["pi"] is not None else np.array([0.45, 0.28, 0.27])
                          for r in satir])
            pr = [r["p_ref"] for r in satir]
            Pref = np.array([x if x is not None else P[i] for i, x in enumerate(pr)])
            tr = np.array([r["pop_tr"] for r in satir], float)
            eu = np.array([r["pop_eu"] for r in satir], float)
            Q = q_uret(Pref, tr, eu, th, [r["aile"] for r in satir])
            for i, r in enumerate(satir):
                if r["pi"] is None:
                    Q[i] = q_sabit(th)
            sezon = h["sezon"]
            N = kolon_sayisi(D_once, h["kapanis"], th, sezon)
            havuz = {k: KADEME_PAY[k] * D_once + h["devir_gelen"][k] for k in KADEME_PAY}
            fiyat = kolon_bedeli(h["kapanis"])
            sonuc = [int(r["sonuc"]) for r in satir]
            n_g = {k: (h["n"][k] or 0) for k in KADEME_PAY}
            havuz_g = h["havuz"]
            deg = Degerlendirici(P, Q, N, havuz, M=M, tohum=h["id"])
            for prof in profiller:
                for B in butceler:
                    S = _kupon(prof, P, Q, N, havuz, B, deg, h["id"])
                    r_ex = deg.degerle(S)
                    r_ger = gerceklesen(S, sonuc, n_g, havuz_g)
                    kolon = boyut(S)
                    kayit.append({
                        "hafta_id": h["id"], "sezon": sezon, "hafta": h["ad"], "kapanis": h["kapanis"],
                        "profil": prof, "butce": B, "kolon": kolon, "maliyet": kolon * fiyat, "fiyat": fiyat,
                        "S": [list(x) for x in S],
                        "ev": r_ex["ev"], "ev_k": r_ex["ev_k"], "p15": r_ex["p15"], "p14p": r_ex["p14p"],
                        "p13p": r_ex["p13p"], "p12p": r_ex["p12p"], "odul15_beklenen": r_ex["odul15"],
                        "dogru": r_ger["dogru_en_cok"], "n_bizim": r_ger["n"], "odeme": r_ger["odeme"],
                        "kacan": r_ger["kacan_mac"], "N_tahmin": N, "D_tahmin": D_once, "D_gercek": h["D"],
                        "devir15": h["devir_gelen"][15],
                    })
            print(f"  {h['sezon']} {h['ad']:>9} · kalan bilgisiz {bilgisiz} · {time.time() - t0:.0f} sn", flush=True)
        elif n >= ISINMA:
            atlanan.append((h["sezon"], h["ad"], bilgisiz))
        # ── hafta kapandı: kalibrasyon verisine ekle ──
        oz = hafta_ozeti(satir, "p_ref")
        if oz is not None and len(oz["unc"]) <= 2:
            gecmis_veri.append((oz, np.array([h["n"][k] or 0 for k in (15, 14, 13, 12)], float), h["D"], h["kapanis"]))
        D_once = h["D"]
    K = pd.DataFrame(kayit)
    K.to_pickle(CACHE / f"{cikti}.pkl")
    pd.to_pickle({"atlanan": atlanan, "th_son": th, "cuzdan": {a: P.gecmis for a, P in pazar.items()}},
                 CACHE / f"{cikti}_meta.pkl")
    print(f"bitti: {K['hafta_id'].nunique() if len(K) else 0} hafta · atlanan {len(atlanan)} · {time.time() - t0:.0f} sn")
    return K


def ozet(K: pd.DataFrame | None = None) -> pd.DataFrame:
    if K is None:
        K = pd.read_pickle(CACHE / "geri_test.pkl")
    rows = []
    for (prof, B), g in K.groupby(["profil", "butce"]):
        maliyet, odeme = g["maliyet"].sum(), g["odeme"].sum()
        rows.append({
            "profil": prof, "bütçe(kolon)": B, "hafta": len(g), "ort. kolon": round(g["kolon"].mean()),
            "maliyet TL": round(maliyet), "ödeme TL": round(odeme), "getiri/TL": round(odeme / maliyet, 3),
            "beklenen/TL": round(g["ev"].sum() / maliyet, 3),
            "15": int((g["dogru"] == 15).sum()), "14+": int((g["dogru"] >= 14).sum()),
            "13+": int((g["dogru"] >= 13).sum()), "12+": int((g["dogru"] >= 12).sum()),
            "beklenen 15": round(g["p15"].sum(), 2), "beklenen 12+": round(g["p12p"].sum(), 1),
            "en büyük ödeme": round(g["odeme"].max()),
        })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    K = calis()
    pd.set_option("display.width", 250)
    print(ozet(K).to_string(index=False))
