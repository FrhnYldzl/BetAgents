"""
TOTO · KAYNAKLAR — açık veri yükleyicileri (kulüp maçları + milli maçlar)
=========================================================================
football-data (ana ligler sezon dosyaları + ek ligler tek dosya) ve
martj42/international_results tek tabloya indirgenir:

  kulup():  tarih · lig · ev · dep · ge · gd · sonuc(0/1/2 indeks) · p_kap(3) · p_acl(3)
            · oran_kaynak · şut/isabetli şut/korner (varsa)
  milli():  tarih · ev · dep · ge · gd · sonuc · turnuva · tarafsiz

Oranlardan olasılık: güç yöntemiyle marj temizliği (Σ (1/o)^k = 1). Pinnacle'da
marj ~%2 olduğundan orantılı yöntemle farkı ihmal edilebilir; yüksek marjlı
kaynaklarda (ortalama, iddaa) favori-sürpriz yanlılığını daha iyi düzeltir.
"""
from __future__ import annotations

import math
from functools import lru_cache

import numpy as np
import pandas as pd

from toto_ortak import CACHE

ANA_KODLAR = ["E0", "E1", "E2", "D1", "D2", "I1", "I2", "SP1", "SP2", "F1", "F2", "N1", "B1", "P1", "T1",
              "SC0", "SC1"]
EK_KODLAR = ["BRA", "DNK", "FIN", "JPN", "NOR", "SWE", "USA"]
IDX = {"H": 0, "D": 1, "A": 2}


def marjsiz(oranlar) -> np.ndarray | None:
    """Oran üçlüsü → marjı temizlenmiş olasılık (güç yöntemi)."""
    try:
        o = np.array([float(x) for x in oranlar], dtype=float)
    except (TypeError, ValueError):
        return None
    if not np.all(np.isfinite(o)) or np.any(o <= 1.0):
        return None
    inv = 1.0 / o
    if inv.sum() <= 1.0:                      # marj yok/negatif → orantılı
        return inv / inv.sum()
    lo, hi = 1.0, 10.0
    for _ in range(60):                        # Σ inv^k = 1 için k
        k = 0.5 * (lo + hi)
        if (inv ** k).sum() > 1.0:
            lo = k
        else:
            hi = k
    p = inv ** (0.5 * (lo + hi))
    return p / p.sum()


def _oran_sec(r: pd.Series, onekler) -> tuple[np.ndarray | None, str | None]:
    for pre, ad in onekler:
        cols = [pre + x for x in "HDA"]
        if all(c in r.index for c in cols):
            p = marjsiz([r[c] for c in cols])
            if p is not None:
                return p, ad
    return None, None


KAPANIS = (("PSC", "pin_kap"), ("AvgC", "ort_kap"), ("B365C", "b365_kap"), ("MaxC", "max_kap"))
ACILIS = (("PS", "pin_acl"), ("Avg", "ort_acl"), ("B365", "b365_acl"), ("BbAv", "bbav_acl"))


def _tarih(s: pd.Series) -> pd.Series:
    t = pd.to_datetime(s, format="%d/%m/%Y", errors="coerce")
    t2 = pd.to_datetime(s, format="%d/%m/%y", errors="coerce")
    return t.fillna(t2)


@lru_cache(maxsize=1)
def kulup() -> pd.DataFrame:
    pkl = CACHE / "kulup.pkl"
    csvler = list((CACHE / "fd").glob("*.csv")) + list((CACHE / "fd_new").glob("*.csv"))
    if pkl.exists() and csvler and pkl.stat().st_mtime > max(f.stat().st_mtime for f in csvler):
        return pd.read_pickle(pkl)
    out = _kulup_kur()
    out.to_pickle(pkl)
    return out


def _kulup_kur() -> pd.DataFrame:
    parcalar = []
    for kod in ANA_KODLAR:
        for f in sorted((CACHE / "fd").glob(f"{kod}_*.csv")):
            try:
                df = pd.read_csv(f, encoding="utf-8-sig", encoding_errors="replace", on_bad_lines="skip",
                                 low_memory=False)
            except Exception:
                continue
            if "HomeTeam" not in df.columns:
                continue
            df = df.rename(columns={"HomeTeam": "Home", "AwayTeam": "Away", "FTHG": "HG", "FTAG": "AG",
                                    "FTR": "Res"})
            df["lig"] = kod
            df["sezon"] = f.stem.split("_")[1]
            parcalar.append(df)
    for kod in EK_KODLAR:
        f = CACHE / "fd_new" / f"{kod}.csv"
        if f.exists():
            df = pd.read_csv(f, encoding="utf-8-sig", encoding_errors="replace", on_bad_lines="skip",
                             low_memory=False)
            df["lig"] = kod
            df["sezon"] = df["Season"].astype(str)
            parcalar.append(df)
    ham = pd.concat(parcalar, ignore_index=True, sort=False)
    ham = ham[ham["Home"].notna() & ham["Away"].notna()].copy()
    ham["tarih"] = _tarih(ham["Date"].astype(str))
    ham = ham[ham["tarih"].notna()]
    # oran seçimi satır bazında (≈ 60 bin satır) — sonuç veri_cache/kulup.pkl'de saklanır
    pk, kk, pa, ka = [], [], [], []
    for _, r in ham.iterrows():
        p, k = _oran_sec(r, KAPANIS)
        pk.append(p); kk.append(k)
        p2, k2 = _oran_sec(r, ACILIS)
        pa.append(p2); ka.append(k2)
    out = pd.DataFrame({
        "tarih": ham["tarih"].values, "lig": ham["lig"].values, "sezon": ham["sezon"].values,
        "ev": ham["Home"].astype(str).str.strip().values, "dep": ham["Away"].astype(str).str.strip().values,
        "ge": pd.to_numeric(ham["HG"], errors="coerce").values, "gd": pd.to_numeric(ham["AG"], errors="coerce").values,
        "res": ham["Res"].values,
    })
    out["p_kap"] = pk
    out["oran_kaynak"] = kk
    out["p_acl"] = pa
    for c_src, c_dst in (("HS", "sut_ev"), ("AS", "sut_dep"), ("HST", "isut_ev"), ("AST", "isut_dep"),
                         ("HC", "korner_ev"), ("AC", "korner_dep")):
        out[c_dst] = pd.to_numeric(ham[c_src], errors="coerce").values if c_src in ham.columns else np.nan
    out["sonuc"] = out["res"].map(IDX)
    out = out[out["ge"].notna() | out["p_kap"].notna()]
    return out.sort_values("tarih").reset_index(drop=True)


@lru_cache(maxsize=1)
def milli() -> pd.DataFrame:
    df = pd.read_csv(CACHE / "intl" / "results.csv", encoding="utf-8")
    df["tarih"] = pd.to_datetime(df["date"], errors="coerce")
    df = df[df["tarih"].notna()].copy()
    df["ge"] = pd.to_numeric(df["home_score"], errors="coerce")
    df["gd"] = pd.to_numeric(df["away_score"], errors="coerce")
    df["sonuc"] = np.where(df["ge"] > df["gd"], 0, np.where(df["ge"] == df["gd"], 1, 2))
    df.loc[df["ge"].isna() | df["gd"].isna(), "sonuc"] = -1
    df["tarafsiz"] = df["neutral"].astype(str).str.upper().eq("TRUE")
    return df.rename(columns={"home_team": "ev", "away_team": "dep", "tournament": "turnuva"})[
        ["tarih", "ev", "dep", "ge", "gd", "sonuc", "turnuva", "tarafsiz", "country"]].reset_index(drop=True)


if __name__ == "__main__":
    import sys, time
    sys.stdout.reconfigure(encoding="utf-8")
    t = time.time()
    k = kulup()
    print(f"kulüp maçı: {len(k):,} · {k['tarih'].min().date()} → {k['tarih'].max().date()} · {time.time() - t:.1f} sn")
    print(k.groupby("lig").agg(n=("ev", "size"), oranli=("p_kap", lambda s: s.notna().sum()),
                               son=("tarih", "max")).to_string())
    print(k["oran_kaynak"].value_counts(dropna=False).to_string())
    m = milli()
    print(f"milli maç: {len(m):,} · son {m['tarih'].max().date()}")
