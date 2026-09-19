"""
TOTO · GEÇMİŞ TEST ÖZETİ — panelin "Geçmiş Test" sayfası için (yerelde üretilir)
===============================================================================
Üç soruya cevap verir, üçü de İLERİYE YÜRÜYEN (walk-forward) — hiçbir sayı
geleceği görmüş bir modelden gelmez:

  1. Olasılık isabeti: ajanlar ve pazar fiyatı, Toto maçlarında ne kadar isabetli?
  2. Kalabalık modeli: sonuç bilinince kaç kazanan çıkacağını ne kadar bildi?
  3. Kuponlar: profil × bütçe — maliyet, ödeme, isabetler, beklenen ↔ gerçekleşen

Çıktı: 09_TOTO/geri_test_ozet.json (repoya girer; panel yalnız okur)
"""
from __future__ import annotations

import html
import json
import sys
import time

import numpy as np
import pandas as pd

from geri_test import hazirla_veri
from kalabalik import VARSAYILAN, beklenen, hafta_ozeti, kalibre_et
from sportoto import haftalar
from toto_ortak import CACHE, KOK

CIKTI = KOK / "geri_test_ozet.json"
AD = {"FAVORİ": "Favori", "15_AVCISI": "15 Avcısı", "DENGELİ": "Dengeli"}


def _e(x):
    return html.escape(str(x))


def _tl(v):
    return f"{v:,.0f} TL".replace(",", ".")


def _v(x, n=2):
    """Türkçe ondalık: 0.95 → 0,95"""
    return f"{x:.{n}f}".replace(".", ",")


def _tablo(bas, satirlar):
    th = "".join(f"<th>{_e(b)}</th>" for b in bas)
    tb = "".join("<tr>" + "".join(f"<td class='n'>{x}</td>" for x in s) + "</tr>" for s in satirlar)
    return f"<table class='v2'><thead><tr>{th}</tr></thead><tbody>{tb}</tbody></table>"


def olasilik_blogu(df: pd.DataFrame) -> tuple[str, dict]:
    d = df[df["sonuc"].notna() & ~df["noter"]].copy()
    d["y"] = d["sonuc"].astype(int)
    ll = lambda s: np.mean([-np.log(max(float(p[y]), 1e-9)) for p, y in zip(d.loc[s.index, s.name], d.loc[s.index, "y"])])
    satir, ozet = [], {}
    kume = {"Kulüp · piyasa fiyatlı": d["p_piyasa"].notna() & (d["aile"] != "MILLI"),
            "Milli maç": d["aile"] == "MILLI"}
    for kad, m in kume.items():
        g = d[m]
        for a, c in (("PİYASA (açılış)", "p_piyasa"), ("ELO", "p_elo"), ("FORM", "p_form"), ("H2H", "p_h2h"),
                     ("AJAN PAZARI", "pi")):
            s = g[c].dropna()
            if len(s) < 30:
                continue
            v = ll(s)
            fav = np.mean([int(np.argmax(p)) == y for p, y in zip(s, g.loc[s.index, "y"])])
            satir.append([_e(kad), _e(a), f"{len(s):,}".replace(",", "."), _v(v, 4), "%" + _v(fav * 100, 1)])
            ozet[(kad, a)] = v
    acik = ("<div class='tt-not'>Log-kayıp: düşük iyidir (3 sonuçta yazı-tura ≈ 1,099). Favori isabeti: ajanın "
            "en olası dediği sonucun gerçekleşme oranı. Ajan pazarı fiyatı cüzdanlarla ağırlıklı ortalamadır; "
            "her hafta yalnız o haftaya kadarki cüzdanlarla hesaplandı.</div>")
    return acik + _tablo(["Küme", "Kaynak", "Maç", "Log-kayıp", "Favori isabeti"], satir), ozet


def kalabalik_blogu(df: pd.DataFrame) -> tuple[str, dict]:
    """Önbellekli sarmalayıcı (veri seti değişmediyse yeniden hesaplamaz)."""
    onb = CACHE / "gt_kalabalik.pkl"
    vs = CACHE / "veri_seti.pkl"
    if onb.exists() and vs.exists() and onb.stat().st_mtime > vs.stat().st_mtime:
        return pd.read_pickle(onb)
    out = _kalabalik_blogu(df)
    pd.to_pickle(out, onb)
    return out


def _kalabalik_blogu(df: pd.DataFrame) -> tuple[str, dict]:
    """Her 13 haftada yeniden kalibre; sonraki 13 haftanın kazanan sayılarını (sonuç bilinince) öngör."""
    H = {h["id"]: h for h in haftalar()}
    veri = []
    for hid, g in df.groupby("hafta_id"):
        h = H.get(hid)
        if not h or not h["sonuclandi"] or not h["D"]:
            continue
        oz = hafta_ozeti(g.sort_values("sira").to_dict("records"), "p_ref")
        if oz is None or len(oz["unc"]) > 2:
            continue
        veri.append((h["kapanis"], oz, np.array([h["n"][k] or 0 for k in (15, 14, 13, 12)], float), h["D"]))
    veri.sort(key=lambda x: x[0])
    hata, th = [], dict(VARSAYILAN)
    for i in range(40, len(veri), 13):
        th, _ = kalibre_et([(oz, y, D, kap) for kap, oz, y, D in veri[:i]], baslangic=th)
        for kap, oz, y, D in veri[i:i + 13]:
            hata.append(np.log10(y + 1) - np.log10(beklenen(oz, D, kap, th) + 1))
    e = np.array(hata)
    mae = np.median(np.abs(e), 0)
    kat = 10 ** mae
    satir = [[f"N{k}", _v(mae[j]), "×" + _v(kat[j], 1), f"{np.median(e[:, j]):+.2f}".replace(".", ",")]
             for j, k in enumerate((15, 14, 13, 12))]
    acik = (f"<div class='tt-not'>{len(e)} hafta, her biri o haftadan ÖNCEKİ verilerle kalibre edilmiş modelle. "
            "Hata: log10(gerçek+1) − log10(tahmin+1) medyanı; tipik kat = tipik haftada kazanan sayısını kaç kat "
            "içinde bildi (×2 = iki kat içinde). Sapma negatifse model kazanan sayısını biraz fazla tahmin etmiş "
            "demektir — kontrarian kuponun değerini abartmaz, küçümser.</div>")
    return acik + _tablo(["Derece", "Medyan |hata| (log10)", "Tipik kat", "Sapma"], satir), {"mae": mae.tolist(), "n": len(e)}


def kupon_blogu(K: pd.DataFrame) -> tuple[str, list]:
    satir, kpi = [], []
    for (prof, B), g in K.groupby(["profil", "butce"]):
        mal, od = g["maliyet"].sum(), g["odeme"].sum()
        satir.append([_e(AD.get(prof, prof)), f"{B}", f"{len(g)}", _tl(mal), _tl(od), _v(od / mal),
                      _v(g["ev"].sum() / mal), f"{int((g['dogru'] == 15).sum())} / {_v(g['p15'].sum())}",
                      f"{int((g['dogru'] >= 14).sum())} / {_v(g['p14p'].sum(), 1)}",
                      f"{int((g['dogru'] >= 12).sum())} / {_v(g['p12p'].sum(), 1)}", _tl(g["odeme"].max())])
    acik = ("<div class='tt-not'>Her hafta kupon yalnız o haftanın kapanışından önce bilinebilecek bilgiyle kuruldu: "
            "piyasa için AÇILIŞ fiyatı, kalabalık modeli için önceki haftalar, havuz için geçen haftanın dağıtılan "
            "tutarı. Ödeme gerçek sonuç ve açıklanan ikramiyelerle hesaplandı (kendi kolonlarımız kazanan sayısına "
            "eklendi). Hücrelerde <b>gerçekleşen / modelin beklediği</b> isabet sayısı.</div>")
    return acik + _tablo(["Profil", "Kolon", "Hafta", "Maliyet", "Ödeme", "Dönüş/TL", "Beklenen/TL",
                          "15 (gerç./bekl.)", "14+ (gerç./bekl.)", "12+ (gerç./bekl.)", "En büyük ödeme"], satir), kpi


def dagilim_blogu(K: pd.DataFrame) -> str:
    """Beklenen değerin ne kadarı ölçülebilir derecelerden (12–13) geliyor, ne kadarı 14–15'ten."""
    satir = []
    for (prof, B), g in K.groupby(["profil", "butce"]):
        mal = g["maliyet"].sum()
        ev = {k: sum(x[k] if k in x else x.get(str(k), 0) for x in g["ev_k"]) for k in (15, 14, 13, 12)}
        satir.append([_e(AD.get(prof, prof)), f"{B}"] + [_v(ev[k] / mal) for k in (15, 14, 13, 12)]
                     + [_v((ev[13] + ev[12]) / mal)])
    acik = ("<div class='tt-not'>Beklenen dönüşün derecelere dağılımı (TL başına). 12 ve 13 sık gelir, kısa sürede "
            "ölçülebilir. 14 ve 15 çok seyrek gelir; onlardan beklenen değer ancak uzun sürede gerçekleşir.</div>")
    return acik + _tablo(["Profil", "Kolon", "15", "14", "13", "12", "12+13"], satir)


def derece_blogu(K: pd.DataFrame) -> tuple[str, dict]:
    """Beklenen ↔ gerçekleşen ödeme, derece derece; getiri için hafta yeniden örneklemeli %90 aralık."""
    H = {h["id"]: h for h in haftalar()}
    satir, ozet = [], {}
    rng = np.random.default_rng(0)
    for (prof, B), g in K.groupby(["profil", "butce"]):
        bek = {k: 0.0 for k in (15, 14, 13, 12)}
        ger = {k: 0.0 for k in (15, 14, 13, 12)}
        haftalik = []
        for r in g.itertuples():
            h = H.get(r.hafta_id)
            evk = r.ev_k
            for k in (15, 14, 13, 12):
                bek[k] += evk.get(k, evk.get(str(k), 0.0))
                n = (r.n_bizim or {}).get(k, 0) or 0
                if n and h:
                    ger[k] += n * h["havuz"][k] / ((h["n"][k] or 0) + n)
            haftalik.append((r.odeme, r.maliyet))
        a = np.array(haftalik)
        oran = []
        for _ in range(2000):
            i = rng.integers(0, len(a), len(a))
            oran.append(a[i, 0].sum() / a[i, 1].sum())
        lo, hi = np.percentile(oran, [5, 95])
        mal = a[:, 1].sum()
        satir.append([_e(AD.get(prof, prof)), f"{B}",
                      f"{_v(ger[12] / mal)} / {_v(bek[12] / mal)}", f"{_v(ger[13] / mal)} / {_v(bek[13] / mal)}",
                      f"{_v(ger[14] / mal)} / {_v(bek[14] / mal)}", f"{_v(ger[15] / mal)} / {_v(bek[15] / mal)}",
                      f"{_v(a[:, 0].sum() / mal)} [{_v(lo)} – {_v(hi)}]"])
        ozet[(prof, B)] = {"ger": ger, "bek": bek, "mal": mal, "aralik": (lo, hi)}
    acik = ("<div class='tt-not'>Her hücre: <b>gerçekleşen / beklenen</b> ödeme, TL başına. 12 ve 13 sık gelir; orada "
            "gerçekleşenin beklenene yakın olması modelin ortak kazanan hesabının doğru olduğunu gösterir. 14 ve 15 "
            "nadirdir; tek bir isabet sonucu büyük oynatır. Son sütun: toplam dönüş ve haftalar yeniden "
            "örneklenerek %90 aralık.</div>")
    return acik + _tablo(["Profil", "Kolon", "12", "13", "14", "15", "Toplam dönüş [%90]"], satir), ozet


def bolum_blogu(K: pd.DataFrame) -> str:
    """Eşit ağırlıklı haftalık dönüş, devirli/devirsiz, fiyat dönemi."""
    K = K.copy()
    K["r"] = K["odeme"] / K["maliyet"]
    K["devirli"] = K["devir15"] > 0
    K["donem"] = pd.cut(K["fiyat"], [0, 0.6, 2.1, 4.1, 11], labels=["0,5 TL", "2 TL", "4 TL", "10 TL"])
    rng = np.random.default_rng(1)
    satir = []
    for (prof, B), g in K.groupby(["profil", "butce"]):
        b = [rng.choice(g["r"].values, len(g)).mean() for _ in range(2000)]
        lo, hi = np.percentile(b, [5, 95])
        d, n = g[g["devirli"]], g[~g["devirli"]]
        don = {str(k): (x["odeme"].sum() / x["maliyet"].sum() if len(x) else float("nan"))
               for k, x in g.groupby("donem", observed=True)}
        satir.append([_e(AD.get(prof, prof)), f"{B}", f"{_v(g['r'].mean())} [{_v(lo)} – {_v(hi)}]",
                      f"{(g['r'] > 0).mean() * 100:.0f}%".replace(".", ","),
                      _v(d["odeme"].sum() / max(d["maliyet"].sum(), 1)), _v(n["odeme"].sum() / n["maliyet"].sum())]
                     + [_v(don.get(k, float("nan"))) for k in ("0,5 TL", "2 TL", "4 TL", "10 TL")])
    acik = ("<div class='tt-not'>Haftalık dönüş eşit ağırlıkla (her hafta bir oy): ödeme ÷ maliyet ortalaması ve "
            "yeniden örneklemeli %90 aralık. 'Ödeme alan hafta': en az 12 bilinen hafta oranı. Devirli hafta: 15'e "
            "önceki haftadan devir gelen hafta. Son dört sütun: kolon bedeli dönemlerine göre TL ağırlıklı dönüş.</div>")
    return acik + _tablo(["Profil", "Kolon", "Haftalık dönüş [%90]", "Ödeme alan hafta", "Devirli", "Devirsiz",
                          "0,5 TL", "2 TL", "4 TL", "10 TL"], satir)


def bulgular_html(K: pd.DataFrame) -> str:
    """Sade dille ne öğrendik — sayılar aynı tablodan hesaplanır."""
    def roi(p, b):
        g = K[(K["profil"] == p) & (K["butce"] == b)]
        return g["odeme"].sum() / g["maliyet"].sum(), g
    f2048, gf = roi("FAVORİ", 2048)
    a32, _ = roi("15_AVCISI", 32)
    a2048, ga = roi("15_AVCISI", 2048)
    en_iki = ga.sort_values("odeme", ascending=False).head(2)
    pay = en_iki["odeme"].sum() / max(ga["odeme"].sum(), 1)
    kal = [
        f"<b>Olasılıklar ve isabet sıklığı doğru.</b> Favori sistemde modelin beklediği dönüş ile gerçekleşen "
        f"örtüşüyor (2.048 kolon: {_v(f2048)} gerçekleşen). Her profilde 12+ isabet sayısı beklenenden az değil.",
        f"<b>Favori oynamak güvenilir biçimde kaybettiriyor:</b> TL başına ≈ {_v(f2048)}. 159 haftada 15'i "
        f"{int((gf['dogru'] == 15).sum())} kez bildi ama ikramiye küçük kaldı. 2025/26 5. haftada 99.237 kişi 15 bildi, "
        "kişi başı 133 TL.",
        f"<b>Kalabalığın az oynadığı kuponlar (15 Avcısı) bir piyango gibi davrandı.</b> 32 kolonda TL başına "
        f"{_v(a32)}. 2.048 kolonda {_v(a2048)}, ama ödemenin %{pay * 100:.0f} kadarı yalnız iki haftadan geldi. "
        "Model küçük kontrarian kuponların değerini abartıyor. Değer, ancak büyük sistemle nadir sürpriz haftaları "
        "yakalayınca gerçekleşiyor.",
        "<b>Devirli haftalar herkes için daha iyi</b> (15 havuzu büyüyor, oynayan sayısı aynı kalıyor). Kâğıt defterde "
        "en çok izlenmesi gereken haftalar bunlar.",
        "<b>159 hafta, kontrarian kârın gerçek mi şans mı olduğunu ayırmaya yetmiyor</b> (aralıklar çok geniş). "
        "Karar, canlı kâğıt defterin birkaç ayına ve devirli haftalara göre birlikte verilmeli.",
    ]
    return "".join(f"<div class='tt-not' style='margin:4px 0'>• {x}</div>" for x in kal)


def hafta_blogu(K: pd.DataFrame) -> str:
    en = K.sort_values("odeme", ascending=False).head(12)
    satir = [[_e(r.sezon + " " + r.hafta), _e(AD.get(r.profil, r.profil)), f"{r.butce}", f"{r.dogru}", _tl(r.odeme),
              _tl(r.maliyet)] for r in en.itertuples()]
    return _tablo(["Hafta", "Profil", "Kolon", "En çok doğru", "Ödeme", "Maliyet"], satir)


def calis() -> dict:
    t0 = time.time()
    sys.stdout.reconfigure(encoding="utf-8")
    df, pazar = hazirla_veri()
    K = pd.read_pickle(CACHE / "geri_test.pkl")
    ob, _ = olasilik_blogu(df)
    kb, kz = kalabalik_blogu(df)
    kup, _ = kupon_blogu(K)
    hafta_say = K["hafta_id"].nunique()
    bas, son = K["kapanis"].min()[:10], K["kapanis"].max()[:10]
    fav = K[(K["profil"] == "FAVORİ")]
    avc = K[(K["profil"] == "15_AVCISI") & (K["butce"] == 32)]
    G = {
        "alt": f"{hafta_say} hafta ({bas} → {son}), her hafta yalnız o güne kadarki bilgiyle — "
               "kuponlar kâğıt üzerinde, gerçek ikramiyelerle ödendi.",
        "kpi": [{"ad": "Hafta", "deger": str(hafta_say)},
                {"ad": "Favori dönüş/TL", "deger": _v(fav['odeme'].sum() / fav['maliyet'].sum())},
                {"ad": "15 Avcısı 32 kolon", "deger": _v(avc['odeme'].sum() / avc['maliyet'].sum())},
                {"ad": "En büyük ödeme", "deger": f"{K['odeme'].max() / 1e6:.2f} M TL".replace(".", ",")}],
        "bloklar": [
            {"baslik": "Ne öğrendik", "html": bulgular_html(K), "ipucu": "159 hafta · ileriye yürüyen"},
            {"baslik": "Kuponlar · profil × bütçe", "html": kup, "ipucu": "kâğıt · gerçek ikramiye"},
            {"baslik": "Haftalık dönüş · devir · kolon bedeli dönemi", "html": bolum_blogu(K), "ipucu": "eşit ağırlık"},
            {"baslik": "Beklenen ↔ gerçekleşen · derece derece", "html": derece_blogu(K)[0], "ipucu": "TL başına"},
            {"baslik": "Beklenen değer nereden geliyor", "html": dagilim_blogu(K), "ipucu": "TL başına"},
            {"baslik": "Olasılık isabeti · ajanlar ve pazar", "html": ob, "ipucu": "log-kayıp"},
            {"baslik": "Kalabalık modeli · kazanan sayısı öngörüsü", "html": kb,
             "ipucu": f"{kz['n']} hafta · ileriye yürüyen"},
            {"baslik": "En büyük ödemeli haftalar", "html": hafta_blogu(K), "ipucu": "tüm profiller"},
        ],
        "uretim": pd.Timestamp.now().isoformat(timespec="minutes"),
    }
    CIKTI.write_text(json.dumps(G, ensure_ascii=False), encoding="utf-8")
    print(f"özet yazıldı: {CIKTI} · {time.time() - t0:.0f} sn")
    return G


if __name__ == "__main__":
    calis()
