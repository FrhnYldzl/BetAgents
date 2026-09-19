"""
TOTO · AJAN DURUMU — üretimde ağır veri işlemeden ajan görüşü üretmek için
==========================================================================
Neden: Railway'de BetAgents ile AYNI kapta çalışıyoruz. 70 bin kulüp maçı +
50 bin milli maçı her gün yeniden işlemek bellek ve işlemci ister; BetAgents'ı
etkileme riski taşır. Onun yerine ajanların "hafızası" yerelde hesaplanıp
küçük bir dosyaya yazılır (model_durum.json, ~1 MB) ve üretim yalnız onu okur:

  elo      kulüp puanları (ülke → takım → puan), lig ev avantajı, milli puanlar
  form     lig başına hücum/savunma katsayıları (son 400 gün, yarı ömür 120 gün)
  h2h      son 8 yılın aralarındaki maç sayımları (ev sahibi bakışından)
  lojit    Elo farkı → 1/0/2 eşleme katsayıları

Tazeleme: haftada bir yerelde `python 09_TOTO/durum.py` → commit → push.
(Piyasa fiyatı zaten her koşuda canlı çekilir; durum dosyası yavaş değişen kısımdır.)
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from toto_ortak import KOK

DURUM_DOSYA = KOK / "model_durum.json"


def disa_aktar() -> dict:
    from ajanlar import ULKE, elo_kulup, elo_milli, form_poisson, sirali_lojit_fit
    from kaynaklar import kulup, milli
    K, M = kulup(), milli()
    ok = elo_kulup(K)
    r_k, h_k = elo_kulup.son
    om, r_m = elo_milli(M)
    dk = (ok[:, 0] + ok[:, 2] - ok[:, 1]) / 400.0; yk = K["sonuc"].values
    mk = ((K["tarih"] >= "2014-07-01") & pd.notna(yk)).values
    dm = (om[:, 0] + om[:, 2] - om[:, 1]) / 400.0; ym = M["sonuc"].values
    mm = ((M["tarih"] >= "1990-01-01") & (ym >= 0)).values
    lk = sirali_lojit_fit(dk[mk], yk[mk].astype(int))
    lm = sirali_lojit_fit(dm[mm], ym[mm].astype(int))
    simdi = pd.Timestamp.now()
    son_tarih = K["tarih"].max()
    elo = defaultdict(dict)
    son_gorulme = K.groupby("ev")["tarih"].max().to_dict()
    for (u, t), v in r_k.items():
        if son_gorulme.get(t, pd.Timestamp("2000-01-01")) >= son_tarih - pd.Timedelta(days=900):
            elo[u][t] = round(float(v), 1)
    # form: her lig için bugünkü model (lig verisi 400 günden eskiyse sezon sonu verisiyle)
    form = {}
    for lig, g in K.groupby("lig"):
        an = min(simdi, g["tarih"].max() + pd.Timedelta(days=1))
        f = form_poisson(g, an, 120.0)
        if f:
            form[lig] = {"hucum": {k: round(float(v), 4) for k, v in f["hucum"].items()},
                         "savunma": {k: round(float(v), 4) for k, v in f["savunma"].items()},
                         "ev": float(f["ev"]), "ort": float(f["ort"]), "veri_son": str(g["tarih"].max().date())}
    fm = form_poisson(M[M["tarih"] >= "2014-01-01"], simdi, 540.0)
    if fm:
        form["MILLI"] = {"hucum": {k: round(float(v), 4) for k, v in fm["hucum"].items()},
                         "savunma": {k: round(float(v), 4) for k, v in fm["savunma"].items()},
                         "ev": float(fm["ev"]), "ort": float(fm["ort"]), "veri_son": str(M["tarih"].max().date())}
    # h2h sayımları (son 8 yıl)
    def say(df):
        d = defaultdict(lambda: [0, 0, 0])
        for e, a, s in zip(df["ev"].values, df["dep"].values, df["sonuc"].values):
            if s == s and s >= 0:
                d[f"{e}|{a}"][int(s)] += 1
        return dict(d)
    esik = simdi - pd.Timedelta(days=365 * 8)
    h2h = {"kulup": say(K[K["tarih"] >= esik]), "milli": say(M[M["tarih"] >= esik])}
    out = {"olusturma": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "veri_son": {"kulup": str(K["tarih"].max().date()), "milli": str(M["tarih"].max().date())},
           "elo": {"kulup": elo, "ev_avantaji": {k: round(float(v), 1) for k, v in h_k.items()},
                   "milli": {k: round(float(v), 1) for k, v in r_m.items()}},
           "ulke": ULKE, "form": form, "h2h": h2h,
           "lojit": {"kulup": [float(x) for x in lk], "milli": [float(x) for x in lm]}}
    DURUM_DOSYA.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return out


_ONB: dict = {}


def yukle() -> dict:
    if "d" not in _ONB:
        _ONB["d"] = json.loads(DURUM_DOSYA.read_text(encoding="utf-8"))
    return _ONB["d"]


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    d = disa_aktar()
    print(f"durum: {DURUM_DOSYA.stat().st_size / 1e6:.2f} MB · kulüp ülkesi {len(d['elo']['kulup'])} · "
          f"milli {len(d['elo']['milli'])} · form ligi {len(d['form'])} · h2h çift "
          f"{len(d['h2h']['kulup'])}+{len(d['h2h']['milli'])}")
