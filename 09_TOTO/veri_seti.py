"""
TOTO · VERİ SETİ — geçmiş test için her Toto maçının ajan görüşleri
===================================================================
Her hafta, her maç için (yalnız o haftanın KAPANIŞINDAN önceki bilgiyle):
  sonuc/noter · aile · popülerlik · PİYASA (kapanış + açılış) · ELO · FORM · H2H

Sızıntı kuralları:
  - Elo: eşleşen kaynak satırının MAÇ ÖNCESİ puanı (sonraki maçlar görülmez).
  - FORM: lig modeli haftanın kapanış anından önceki 400 günle kurulur.
  - H2H: kapanıştan önceki aralarındaki maçlar.
  - PİYASA kapanış fiyatı maç başlangıcındaki fiyattır — Toto kapanışından
    birkaç gün SONRASINA kadar bilgi içerebilir (hafif iyimser; açılış fiyatı
    ayrıca tutulur ve kalabalık modeli için ayrıca sınanır).
Çıktı: veri_cache/veri_seti.pkl
"""
from __future__ import annotations

import sys
import time
from collections import defaultdict

import numpy as np
import pandas as pd

from ajanlar import (elo_kulup, elo_milli, form_p, form_poisson, h2h_p, sirali_lojit_fit, sirali_lojit_p,
                     ULKE)
from esle import Eslestirici, benzer
import iddaa_arsiv
from kaynaklar import kulup, milli
from sportoto import haftalar
from toto_ortak import CACHE, populer, turnuva, MILLI_EN


def _h2h_dizin(df: pd.DataFrame, anahtar) -> dict:
    d = defaultdict(list)
    for t, e, a, s in zip(df["tarih"].values, df["ev"].values, df["dep"].values, df["sonuc"].values):
        d[anahtar(e, a)].append((t, e, a, s))
    return d


def _h2h(dizin, anahtar, ev, dep, tarih, onsel, kappa=8.0, yil=8):
    t0 = np.datetime64(pd.Timestamp(tarih) - pd.Timedelta(days=365 * yil))
    t1 = np.datetime64(pd.Timestamp(tarih))
    say = np.zeros(3); n = 0
    for t, e, a, s in dizin.get(anahtar(ev, dep), []):
        if not (t0 <= t < t1) or s != s or s < 0:
            continue
        n += 1
        if e == ev:
            say[int(s)] += 1.0
        else:
            say[2 - int(s)] += 0.7
    return (say + kappa * onsel) / (say.sum() + kappa), n


def kur(kaydet: bool = True) -> pd.DataFrame:
    t0 = time.time()
    H = haftalar()
    K, M = kulup(), milli()
    E = Eslestirici(K, M)
    ok = elo_kulup(K)
    om, _ = elo_milli(M)
    # Elo → olasılık eşlemesi: 2022 öncesi maçlarla (test dönemine sızmaz)
    dk = (ok[:, 0] + ok[:, 2] - ok[:, 1]) / 400.0
    yk = K["sonuc"].values
    m_eg = ((K["tarih"] >= "2014-07-01") & (K["tarih"] < "2022-07-01") & pd.notna(yk)).values
    lk = sirali_lojit_fit(dk[m_eg], yk[m_eg].astype(int))
    dm = (om[:, 0] + om[:, 2] - om[:, 1]) / 400.0
    ym = M["sonuc"].values
    m_egm = ((M["tarih"] >= "1990-01-01") & (M["tarih"] < "2022-07-01") & (ym >= 0)).values
    lm = sirali_lojit_fit(dm[m_egm], ym[m_egm].astype(int))
    print(f"elo + eşleme hazır {time.time() - t0:.1f} sn", flush=True)
    # H2H dizinleri (sırasız takım çifti)
    sirasiz = lambda a, b: (a, b) if a < b else (b, a)
    hk = _h2h_dizin(K, sirasiz)
    hm = _h2h_dizin(M[M["tarih"] >= "1990-01-01"], sirasiz)
    # FORM modeli önbelleği: (lig, kapanış günü)
    lig_df = {L: g for L, g in K.groupby("lig")}
    r_son, h_son = elo_kulup.son
    ulke_takim = defaultdict(list)
    for (u, t) in r_son:
        ulke_takim[u].append(t)
    IA = iddaa_arsiv.yukle()
    ia_tarih = IA["tarih"].values.astype("datetime64[D]") if len(IA) else np.array([], "datetime64[D]")

    def iddaa_bul(m):
        if not len(IA):
            return None
        gun = np.datetime64(str(m["tarih"])[:10])
        aday = np.nonzero(np.abs((ia_tarih - gun).astype(int)) <= 1)[0]
        en, en_s = None, 0.0
        for i in aday:
            sk = benzer(m["ev"], IA.at[i, "ev"]) + benzer(m["dep"], IA.at[i, "dep"])
            if sk > en_s:
                en, en_s = i, sk
        return en if en is not None and en_s >= 1.5 else None

    def elo_son(lig, ev, dep):
        """Eşleşmeyen kulüp maçı: takımların SON Elo puanı (lig ülkesi içinde ad benzerliği)."""
        u = ULKE.get(lig, lig)
        adlar = ulke_takim.get(u, [])
        def bul(ad):
            en = max(adlar, key=lambda t: benzer(ad, t), default=None)
            return en if en is not None and benzer(ad, en) >= 0.75 else None
        a, b = bul(ev), bul(dep)
        if not a or not b:
            return None, None, None
        return r_son[(u, a)], r_son[(u, b)], h_son.get(lig, 60.0), a, b
    m_son = M[M["tarih"] >= "2014-01-01"]
    form_onb = {}

    satirlar = []
    for h in H:
        kap = pd.Timestamp(h["kapanis"][:19])
        for sira, m in enumerate(h["maclar"], 1):
            t = turnuva(m["turnuva"])
            aile = "MILLI" if m["milli"] else t.get("aile")
            ptr, peu = populer(m["ev"]); dtr, deu = populer(m["dep"])
            r = E.esle(m)
            kay = {"hafta_id": h["id"], "sezon": h["sezon"], "hafta": h["ad"], "kapanis": kap, "sira": sira,
                   "tarih": m["tarih"], "turnuva": m["turnuva"], "aile": aile, "ev": m["ev"], "dep": m["dep"],
                   "sonuc": m["sonuc"], "noter": m["noter"], "pop_tr": (ptr, dtr), "pop_eu": (peu, deu),
                   "eslesme": None, "p_piyasa": None, "p_acilis": None, "p_elo": None, "p_form": None,
                   "p_h2h": None, "h2h_n": 0, "kaynak_ev": None, "kaynak_dep": None}
            if r and r["kaynak"] == "kulup":
                row = K.iloc[r["idx"]]
                kay.update(eslesme="kulup", kaynak_ev=row["ev"], kaynak_dep=row["dep"],
                           p_piyasa=row["p_kap"], p_acilis=row["p_acl"])
                ra, rb, hl = ok[r["idx"]]
                pe = sirali_lojit_p((ra + hl - rb) / 400.0, *lk)
                kay["p_elo"] = pe
                L = row["lig"]
                fk = (L, kap.normalize())
                if fk not in form_onb:
                    form_onb[fk] = form_poisson(lig_df[L], kap)
                kay["p_form"] = form_p(form_onb[fk], row["ev"], row["dep"])
                u = ULKE.get(L, L)
                kay["p_h2h"], kay["h2h_n"] = _h2h(hk, sirasiz, row["ev"], row["dep"], kap, pe)
            elif r and r["kaynak"] == "milli":
                row = M.iloc[r["idx"]]
                ra, rb, hl = om[r["idx"]]
                pe = sirali_lojit_p((ra + hl - rb) / 400.0, *lm)
                if r["ters"]:
                    pe = pe[::-1].copy()
                kay.update(eslesme="milli", kaynak_ev=MILLI_EN.get(m["ev"]), kaynak_dep=MILLI_EN.get(m["dep"]),
                           p_elo=pe)
                fk = ("MILLI", kap.normalize())
                if fk not in form_onb:
                    form_onb[fk] = form_poisson(m_son, kap, yari_omur_gun=540.0) if len(m_son) else None
                pf = form_p(form_onb[fk], MILLI_EN.get(m["ev"]), MILLI_EN.get(m["dep"]))
                kay["p_form"] = pf
                kay["p_h2h"], kay["h2h_n"] = _h2h(hm, sirasiz, MILLI_EN.get(m["ev"]), MILLI_EN.get(m["dep"]), kap, pe)
            if kay["eslesme"] is None and not m["milli"] and str(m["tarih"]) >= "2026-06-01":
                i = iddaa_bul(m)                        # güncel sezon: iddaa arşivi (salt okuma)
                if i is not None:
                    kay.update(eslesme="iddaa", p_piyasa=IA.at[i, "p_kap"])
                L = t.get("fd") or t.get("fdn")
                if L:
                    sonuc_elo = elo_son(L, m["ev"], m["dep"])
                    if sonuc_elo[0] is not None:
                        ra, rb, hl, a_ad, b_ad = sonuc_elo
                        pe = sirali_lojit_p((ra + hl - rb) / 400.0, *lk)
                        kay["p_elo"] = pe
                        fk = (L, kap.normalize())
                        if fk not in form_onb:
                            form_onb[fk] = form_poisson(lig_df[L], kap) if L in lig_df else None
                        kay["p_form"] = form_p(form_onb[fk], a_ad, b_ad)
                        kay["p_h2h"], kay["h2h_n"] = _h2h(hk, sirasiz, a_ad, b_ad, kap, pe)
                        kay["kaynak_ev"], kay["kaynak_dep"] = a_ad, b_ad
            satirlar.append(kay)
        if h["id"] % 40 == 0:
            print(f"  … {h['sezon']} {h['ad']} ({time.time() - t0:.0f} sn)", flush=True)
    df = pd.DataFrame(satirlar)
    if kaydet:
        df.to_pickle(CACHE / "veri_seti.pkl")
    print(f"veri seti: {len(df)} maç · {df['hafta_id'].nunique()} hafta · {time.time() - t0:.0f} sn", flush=True)
    return df


def yukle() -> pd.DataFrame:
    return pd.read_pickle(CACHE / "veri_seti.pkl")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    df = kur()
    for c in ("p_piyasa", "p_acilis", "p_elo", "p_form", "p_h2h"):
        print(f"{c:9s} dolu: {df[c].notna().sum():5d} / {len(df)}")
