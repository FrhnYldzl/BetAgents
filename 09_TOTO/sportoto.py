"""
TOTO · SPOR TOTO İSTEMCİSİ — resmi program, sonuç ve ikramiye verisi
=====================================================================
Kaynak: webapi.sportoto.gov.tr (sportoto.gov.tr/spor-toto-listeler sayfasının
arka ucu). Hasılat ve devreden ALANI YOK; ikisi de kesin olarak türetilir:

  havuz_k = kazanan_k × ikramiye_k           (kazanan varsa)
  D       = havuz_12 / 0,25                   (devir almayan kademe)
  kazanan yoksa ikramiye alanı DEVREDEN tutarı gösterir (m.11)

216 haftada devir zinciri 4 kademede birebir doğrulandı (RAPOR §3.1).
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request

from toto_ortak import CACHE, KADEME_PAY, SECENEK

BASE = "https://webapi.sportoto.gov.tr/"
HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json",
           "Origin": "https://www.sportoto.gov.tr", "Referer": "https://www.sportoto.gov.tr/"}
_K = {15: "fifteen", 14: "fourteen", 13: "thirteen", 12: "twelve"}


def api(yol: str, deneme: int = 3):
    for i in range(deneme):
        try:
            with urllib.request.urlopen(urllib.request.Request(BASE + yol, headers=HEADERS), timeout=30) as r:
                d = json.loads(r.read())
            return d.get("object")
        except Exception:
            if i == deneme - 1:
                raise
            time.sleep(2 + 3 * i)


def sezonlar() -> list[str]:
    return [y["year"] for y in api("api/GameRound/GetGameRoundYears") or []]


def turlar(sezon: str) -> list[dict]:
    return api("api/GameRound/GetGameRoundNamesByYear?year=" + urllib.parse.quote(sezon, safe="")) or []


def tur_ham(gid: int) -> dict:
    return {"maclar": api(f"api/GameMatch/GetGameMatches/?gameRoundId={gid}"),
            "sonuc": api(f"api/GameResult/GetGameResultByGameRoundId?Id={gid}")}


def guncel_tur() -> dict | None:
    """Yayındaki (en son) tur — kapanış zamanı ve liste görseli dahil."""
    o = api("api/GameRound")
    if isinstance(o, list):
        o = o[0] if o else None
    return o


def ham_guncelle(yol=None, sadece_eksik: bool = True, son_n_tur: int = 6, sezon_sayisi: int | None = None) -> dict:
    """Yerel ham arşivi (veri_cache/toto_ham.json) tamamla/tazele.
    Son `son_n_tur` tur her zaman yeniden çekilir (sonuç/ikramiye sonradan gelir).
    sezon_sayisi: üretimde yalnız son N sezon (kap yeniden başlayınca arşiv boş olur)."""
    yol = yol or (CACHE / "toto_ham.json")
    try:
        ham = json.load(open(yol, encoding="utf-8"))
    except Exception:
        ham = {}
    tum = []
    for s in sezonlar()[: (sezon_sayisi or 99)]:
        for t in turlar(s):
            tum.append((s, t))
    tum_id = sorted(int(t["id"]) for _, t in tum)
    tazele = set(tum_id[-son_n_tur:])
    for s, t in tum:
        gid = int(t["id"])
        if sadece_eksik and str(gid) in ham and gid not in tazele:
            continue
        h = tur_ham(gid)
        ham[str(gid)] = {"sezon": s, "ad": t["name"], "yayin": t.get("isPublished"),
                         "maclar": h["maclar"], "sonuc": h["sonuc"]}
        time.sleep(0.25)
    CACHE.mkdir(exist_ok=True)
    json.dump(ham, open(yol, "w", encoding="utf-8"), ensure_ascii=False)
    return ham


def _mac(x: dict) -> dict:
    m = x.get("match") or {}
    sc = m.get("score") or {}
    ht, at = m.get("homeTeam") or {}, m.get("awayTeam") or {}
    fw = m.get("fullTimeWin")
    return {
        "mac_uuid": m.get("id"), "dis_id": m.get("externalMatchId"),
        "tarih": m.get("date"), "turnuva": m.get("tournamentId"),
        "ev": (ht.get("name") or "").strip(), "dep": (at.get("name") or "").strip(),
        "ev_ulke": ht.get("countryId"), "dep_ulke": at.get("countryId"),
        "milli": bool(ht.get("isNational")),
        "sonuc": {1: 0, 0: 1, 2: 2}.get(fw),          # indeks: 0=1 · 1=0(beraberlik) · 2=2
        "noter": m.get("noterWin") == 1,
        "skor": (sc.get("homeRegular"), sc.get("awayRegular")),
    }


def haftalar(ham: dict | None = None) -> list[dict]:
    """Ham arşiv → kronolojik hafta listesi (havuzlar, D, devir zinciri, 15 maç)."""
    if ham is None:
        ham = json.load(open(CACHE / "toto_ham.json", encoding="utf-8"))
    H = []
    for gid, v in ham.items():
        s = v.get("sonuc") or {}
        kap = s.get("gameRoundCloseDate")
        maclar = [_mac(x) for x in (v.get("maclar") or [])]
        if not kap and maclar:                      # sonuç henüz yok → kapanış = ilk maç
            kap = min(m["tarih"] for m in maclar if m["tarih"])
        n = {k: s.get(a + "WinCount") for k, a in _K.items()}
        o = {k: s.get(a + "WinPrize") for k, a in _K.items()}
        H.append({"id": int(gid), "sezon": v.get("sezon"), "ad": v.get("ad"),
                  "hafta_no": int(re.match(r"(\d+)", v["ad"]).group(1)) if re.match(r"(\d+)", v.get("ad") or "") else None,
                  "kapanis": kap, "n": n, "odul": o, "maclar": maclar})
    H = [h for h in H if h["kapanis"]]
    H.sort(key=lambda h: h["kapanis"])
    devir = {k: 0.0 for k in KADEME_PAY}
    for h in H:
        n, o = h["n"], h["odul"]
        h["havuz"] = {k: (n[k] or 0) * (o[k] or 0) for k in KADEME_PAY}
        h["ikramiye"] = any((n[k] or 0) > 0 for k in KADEME_PAY)
        h["sonuclandi"] = h["ikramiye"] and all(m["sonuc"] is not None for m in h["maclar"])
        h["devir_gelen"] = dict(devir)
        h["D"] = None
        if not h["ikramiye"]:
            continue
        for k in (12, 13, 14):
            if (n[k] or 0) > 0 and devir[k] == 0:
                h["D"] = h["havuz"][k] / KADEME_PAY[k]
                break
        for k in KADEME_PAY:
            devir[k] = devir[k] + KADEME_PAY[k] * h["D"] if (n[k] or 0) == 0 else 0.0
        # kazananı olmayan kademede gerçek havuz = devreden tutar (ikramiye alanı)
        for k in KADEME_PAY:
            if (n[k] or 0) == 0:
                h["havuz"][k] = o[k] or (KADEME_PAY[k] * h["D"] + h["devir_gelen"][k])
        h["devir_giden"] = dict(devir)
    return H


def isaret(idx: int | None) -> str:
    return SECENEK[idx] if idx is not None else "?"
