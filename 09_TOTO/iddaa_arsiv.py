"""
TOTO · İDDAA ARŞİVİ — güncel sezonun (2026/27) maç fiyatları, SALT OKUMA
========================================================================
football-data yansısında yeni sezon dosyaları henüz yok. Bu sezonun Süper Lig
ve büyük lig maçlarının iddaa kapanış fiyatları, BetAgents'ın arayüz önizlemesi
için alınmış yerel anlık görüntüde (02_VERI/ui_onizleme.db, SQLite) duruyor.
Toto bu dosyayı YALNIZ OKUR (mode=ro) — BetAgents'ın hiçbir tablosuna yazmaz,
canlı veritabanına bağlanmaz.

Canlıda Toto kendi iddaa çekimini yapar (canli.py) ve kendi tablosuna yazar;
bu modül yalnız geçmiş haftaların kalibrasyonu içindir.
"""
from __future__ import annotations

import sqlite3

import numpy as np
import pandas as pd

from kaynaklar import marjsiz
from toto_ortak import KOK

SNAPSHOT = KOK.parent / "02_VERI" / "ui_onizleme.db"


def yukle(bas: str = "2026-06-01") -> pd.DataFrame:
    if not SNAPSHOT.exists():
        return pd.DataFrame(columns=["tarih", "lig", "ev", "dep", "p_kap", "ge", "gd", "sonuc"])
    c = sqlite3.connect(f"file:{SNAPSHOT.as_posix()}?mode=ro", uri=True)
    try:
        df = pd.read_sql_query(
            "SELECT league_code, kickoff_utc, home_team, away_team, closing_1, closing_X, closing_2, "
            "home_score, away_score FROM matches_v2 WHERE kickoff_utc >= ? AND closing_1 IS NOT NULL",
            c, params=(bas,))
    finally:
        c.close()
    df["tarih"] = pd.to_datetime(df["kickoff_utc"], errors="coerce") + pd.Timedelta(hours=3)   # TR saati
    df["p_kap"] = [marjsiz((a, b, d)) for a, b, d in zip(df["closing_1"], df["closing_X"], df["closing_2"])]
    ge = pd.to_numeric(df["home_score"], errors="coerce"); gd = pd.to_numeric(df["away_score"], errors="coerce")
    df["sonuc"] = np.where(ge > gd, 0, np.where(ge == gd, 1, 2)).astype(float)
    df.loc[ge.isna() | gd.isna(), "sonuc"] = np.nan
    return pd.DataFrame({"tarih": df["tarih"], "lig": df["league_code"], "ev": df["home_team"].astype(str),
                         "dep": df["away_team"].astype(str), "p_kap": df["p_kap"], "ge": ge, "gd": gd,
                         "sonuc": df["sonuc"]}).dropna(subset=["tarih"]).reset_index(drop=True)
