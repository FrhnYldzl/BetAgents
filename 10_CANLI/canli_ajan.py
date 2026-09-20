"""
CANLI · AJAN MAÇLARI — BetAgents'ın açık bahisleri canlı fiyatla yan yana
=========================================================================
BetAgents'ın `paper_bets` tablosu SALT OKUNUR. Eşleşme `iddaa_event_id` ile
birebir yapılır (ad benzerliğine gerek yok).

Üç sayı gösterilir ve üçü FARKLI şey söyler:

  alınan     ajanın bahsi aldığı fiyat
  kapanış    ilk düdükteki fiyat (cl_mac.oran_kapanis) — CLV CETVELİ BUDUR.
             alınan > kapanış ise ajan piyasadan iyi fiyat yakalamış demektir.
  canlı      şu anki fiyat — maçın DURUMUNU yansıtır, yargı değildir.
             2-0 geride olan takımın fiyatı açılır; bu ajanın hatası değildir.

Bu ayrımı karıştırmak en kolay hata: canlı fiyatla alınan fiyatı kıyaslayıp
"ajan yanıldı" demek yanlıştır. Ölçüm kapanışa göre yapılır.
"""
from __future__ import annotations

import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent
for _p in (str(KOK), str(KOK.parent / "02_VERI")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import canli_db  # noqa: E402

# BetAgents pazar/seçim → bizim topladığımız pazar ve sonuç sırası
ESLEME = {
    ("1X2", "1"): ("1X2", 0), ("1X2", "0"): ("1X2", 1), ("1X2", "X"): ("1X2", 1),
    ("1X2", "2"): ("1X2", 2),
    ("KG_VAR", "VAR"): ("KG", 0), ("KG_YOK", "YOK"): ("KG", 1),
    ("UST_25", "UST"): ("AU25", 1), ("UST_25", "ÜST"): ("AU25", 1),
    ("ALT_25", "ALT"): ("AU25", 0),
    ("UST_15", "UST"): ("AU15", 1), ("ALT_15", "ALT"): ("AU15", 0),
    ("UST_35", "UST"): ("AU35", 1), ("ALT_35", "ALT"): ("AU35", 0),
}


def _cevir(market: str, pick: str):
    a = (str(market or "").strip().upper(), str(pick or "").strip().upper())
    return ESLEME.get(a)


def acik_bahisler(n: int = 60) -> list[dict]:
    """BetAgents'ın açık kâğıt bahisleri (salt okuma)."""
    import db
    c = db.connect()
    try:
        r = c.execute(
            "SELECT bet_id, kickoff_utc, league, home_team, away_team, market, pick, odds, model_prob, "
            "edge, signal_name, iddaa_event_id FROM paper_bets WHERE status = 'open' "
            "ORDER BY kickoff_utc").fetchall()
    except Exception:
        return []
    finally:
        c.close()
    ad = ["bet_id", "kickoff", "lig", "ev", "dep", "market", "pick", "oran", "model_p", "kenar",
          "ajan", "iddaa_id"]
    return [dict(zip(ad, x)) for x in r[:n]]


def _oran(pazar, anahtar: str, sira: int):
    """Pazar sözlüğünden oran. Eski kayıtlar düz 1X2 listesi olabilir."""
    if not pazar:
        return None
    if isinstance(pazar, (list, tuple)):
        pazar = {"1X2": pazar}
    v = pazar.get(anahtar) if isinstance(pazar, dict) else None
    try:
        return float(v[sira])
    except (TypeError, ValueError, IndexError, KeyError):
        return None


def ajan_maclari(n: int = 60) -> list[dict]:
    """Açık bahisler + (varsa) kapanış fiyatı ve o anki canlı fiyat."""
    bahis = acik_bahisler(n)
    if not bahis:
        return []
    canli = {str(m.get("iddaa_id")): m for m in canli_db.canli_maclar(200) if m.get("iddaa_id")}
    kapanis = canli_db.kapanis_haritasi()
    out = []
    for b in bahis:
        eid = str(b.get("iddaa_id") or "")
        hedef = _cevir(b["market"], b["pick"])
        m = canli.get(eid)
        satir = {**b, "sahada": bool(m), "dakika": (m or {}).get("dakika"),
                 "ev_skor": (m or {}).get("ev_skor"), "dep_skor": (m or {}).get("dep_skor"),
                 "pazar_var": bool(hedef), "canli_oran": None, "kapanis_oran": None,
                 "clv": None, "canli_fark": None}
        if hedef:
            anahtar, sira = hedef
            satir["canli_oran"] = _oran((m or {}).get("pazar"), anahtar, sira)
            satir["kapanis_oran"] = _oran(kapanis.get(eid), anahtar, sira)
            try:
                if satir["kapanis_oran"] and b.get("oran"):
                    # CLV: alınan fiyatın kapanışa göre üstünlüğü (1'in üstü iyi)
                    satir["clv"] = round(float(b["oran"]) / float(satir["kapanis_oran"]) - 1.0, 4)
                if satir["canli_oran"] and b.get("oran"):
                    satir["canli_fark"] = round(float(satir["canli_oran"]) / float(b["oran"]) - 1.0, 4)
            except (TypeError, ValueError, ZeroDivisionError):
                pass
        out.append(satir)
    # sahadakiler önce, sonra kapanış fiyatı olanlar
    out.sort(key=lambda x: (not x["sahada"], x["kapanis_oran"] is None, x.get("kickoff") or ""))
    return out


def ozet(satirlar: list[dict]) -> dict:
    clv = [x["clv"] for x in satirlar if x.get("clv") is not None]
    return {"bahis": len(satirlar), "sahada": sum(1 for x in satirlar if x["sahada"]),
            "clv_olculen": len(clv),
            "clv_ort": (sum(clv) / len(clv)) if clv else None,
            "clv_pozitif": (sum(1 for x in clv if x > 0) / len(clv)) if clv else None,
            "pazar_disi": sum(1 for x in satirlar if not x["pazar_var"])}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    S = ajan_maclari()
    o = ozet(S)
    print(f"açık bahis {o['bahis']} · sahada {o['sahada']} · CLV ölçülen {o['clv_olculen']} "
          f"· topladığımız pazar dışı {o['pazar_disi']}")
    if o["clv_ort"] is not None:
        print(f"ortalama CLV {o['clv_ort']:+.2%} · pozitif oran %{100 * o['clv_pozitif']:.0f}")
    print()
    print(f"{'maç':34s}{'pazar':10s}{'seç':6s}{'alınan':>8}{'kapanış':>9}{'canlı':>8}{'CLV':>9}  durum")
    for x in S[:20]:
        dk = f"{x['dakika']}'" if x.get("dakika") is not None else ("sahada" if x["sahada"] else "—")
        sk = (f"{x['ev_skor']}-{x['dep_skor']}" if x.get("ev_skor") is not None else "")
        print(f"{(x['ev'][:15] + ' - ' + x['dep'][:15]):34s}{str(x['market'])[:9]:10s}{str(x['pick'])[:5]:6s}"
              f"{(x['oran'] or 0):>8.2f}{(x['kapanis_oran'] or 0):>9.2f}{(x['canli_oran'] or 0):>8.2f}"
              f"{(x['clv'] * 100 if x['clv'] is not None else 0):>8.1f}%  {dk} {sk}")
