"""
🩺 AJAN KARNESİ — bir ajan dönem dönem neyi, nasıl oynadı
==========================================================
"Önceki hâli iyiydi, şimdi kötü" iddiasını sınamanın aracı. Tek bir ROI
sayısı neyin değiştiğini söylemez; bu modül aynı ajanın dönemlerini
KIRILIMLARIYLA yan yana koyar:

    · dönem       isabet · fiyatın beklediği · fark · ROI (düz) · CLV
    · pazar       UST_25 / KG_YOK / ...
    · oran bandı  1,60–1,75 / 1,75–1,90 / 1,90+
    · kupon türü  TEK / K2 / K3
    · öne süre    kupon maçtan kaç saat önce kuruldu
    · lig         kodlu / kodsuz

ve son dönemdeki HER bahisin sonucunu skordan YENİDEN hesaplar: defterin
yazdığı ile skorun söylediği uyuşmuyorsa satır işaretlenir. --dogrula
verilirse skor iddaa'dan TEKRAR çekilir ve veritabanındakiyle karşılaştırılır
(yanlış yazılmış skor = yanlış kapanmış bahis).

SALT OKUMA — hiçbir şey yazmaz, hiçbir şey düzeltmez.

    python ajan_karne.py CESUR_V1
    python ajan_karne.py CESUR_V1 --dogrula
"""
from __future__ import annotations

import math
import sys
from datetime import datetime
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import db

# Dönem 2'nin başlangıcı (start_era, 23.08.2026). Dönem 3'ün başlangıcı
# ajanın KENDİ paper_portfolio.era_start değerinden okunur.
ERA2 = "2026-08-23T00:00"


def _dt(s):
    try:
        return datetime.fromisoformat(str(s).replace("Z", "")[:19])
    except Exception:
        return None


def _sonuc(mk, pk, hs, aws):
    """Skordan sonuç: True kazandı · False kaybetti · None bilinmiyor."""
    if hs is None or aws is None:
        return None
    try:
        hs, aws = int(hs), int(aws)
    except (TypeError, ValueError):
        return None
    mk = str(mk or "").upper()
    pk = str(pk or "").upper()
    t = hs + aws
    if mk == "UST_25":
        return t > 2.5
    if mk == "ALT_25":
        return t < 2.5
    if mk == "KG_VAR":
        return hs > 0 and aws > 0
    if mk == "KG_YOK":
        return not (hs > 0 and aws > 0)
    if mk == "1X2":
        r = "1" if hs > aws else ("2" if aws > hs else "X")
        return pk == r or (r == "X" and pk == "0")
    return None


def _alt_kuyruk(n: int, k: int, p: float) -> float:
    """P(X ≤ k), X ~ Binom(n, p) — tam hesap."""
    if n <= 0:
        return 1.0
    p = min(max(p, 1e-9), 1 - 1e-9)
    return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i)
               for i in range(0, k + 1))


def _ozet(v: list[dict]) -> str:
    n = len(v)
    if not n:
        return "—"
    won = sum(1 for x in v if x["st"] == "won")
    exp = sum(1.0 / x["o"] for x in v) / n
    roi = sum((x["o"] - 1.0) if x["st"] == "won" else -1.0 for x in v) / n
    clv = [x["clv"] for x in v if x["clv"] is not None]
    c = (f" · CLV {sum(clv)/len(clv)*100:+.2f}% (n={len(clv)})" if clv else "")
    return (f"n={n:3d} · isabet %{won/n*100:5.1f} · fiyat %{exp*100:5.1f} · "
            f"fark {(won/n-exp)*100:+6.1f}p · ROI {roi*100:+6.1f}% · "
            f"ort. oran {sum(x['o'] for x in v)/n:.2f}{c}")


def _band(o: float) -> str:
    return "1,60–1,75" if o < 1.75 else ("1,75–1,90" if o < 1.90 else "1,90+")


def _one(h) -> str:
    if h is None:
        return "?"
    return "<12sa" if h < 12 else ("12–36sa" if h < 36 else "36sa+")


def karne(pid: str, dogrula: bool = False) -> None:
    conn = db.connect()
    try:
        r = conn.execute("SELECT era_start FROM paper_portfolio "
                         "WHERE portfolio_id=?", (pid,)).fetchone()
        era3 = str(r[0])[:16] if (r and r[0]) else None
        rows = [dict(x) for x in conn.execute(
            "SELECT pb.market mk, pb.pick pk, pb.odds o, pb.status st, "
            "pb.kickoff_utc ko, pb.home_team h, pb.away_team a, pb.clv clv, "
            "pc.created_at ca, pc.coupon_type ct, "
            "m.league_code lg, m.mbs mbs, m.home_score hs, m.away_score aws, "
            "m.external_id_iddaa idd, m.status mst "
            "FROM paper_bets pb "
            "JOIN paper_coupons pc ON pc.coupon_id = pb.coupon_id "
            "LEFT JOIN matches_v2 m ON m.match_id = pb.match_id "
            "WHERE pb.portfolio_id = ? AND pb.status IN ('won','lost') "
            "AND pb.odds > 1.01 ORDER BY pc.created_at", (pid,)).fetchall()]
    finally:
        conn.close()

    for x in rows:
        x["o"] = float(x["o"])
        try:
            x["clv"] = float(x["clv"]) if x["clv"] is not None else None
        except (TypeError, ValueError):
            x["clv"] = None
        ca = str(x["ca"] or "")[:16]
        x["era"] = ("3" if (era3 and ca >= era3) else
                    ("2" if ca >= ERA2 else "1"))
        k, c = _dt(x["ko"]), _dt(x["ca"])
        x["one"] = ((k - c).total_seconds() / 3600) if (k and c) else None
        x["kodlu"] = str(x["lg"] or "") not in ("", "ALL", "None")

    print(f"🩺 AJAN KARNESİ — {pid}  (dönem 3 başlangıcı: {era3 or '—'})")
    print(f"   kapanmış bahis: {len(rows)}\n")
    donemler = [e for e in ("1", "2", "3") if any(x["era"] == e for x in rows)]
    print("DÖNEM")
    for e in donemler:
        print(f"  dönem {e}: {_ozet([x for x in rows if x['era'] == e])}")

    def kirilim(baslik, anahtar):
        print(f"\n{baslik}")
        degerler = sorted({anahtar(x) for x in rows}, key=str)
        for d in degerler:
            print(f"  {str(d):12s}")
            for e in donemler:
                v = [x for x in rows if x["era"] == e and anahtar(x) == d]
                if v:
                    print(f"      dönem {e}: {_ozet(v)}")

    kirilim("PAZAR", lambda x: x["mk"])
    kirilim("ORAN BANDI", lambda x: _band(x["o"]))
    kirilim("KUPON TÜRÜ", lambda x: x["ct"] or "?")
    kirilim("ÖNE SÜRE (kupon kurulduğunda maça kalan)", lambda x: _one(x["one"]))
    kirilim("LİG", lambda x: "kodlu" if x["kodlu"] else "kodsuz")
    kirilim("MBS", lambda x: x["mbs"] if x["mbs"] is not None else "?")

    son = [x for x in rows if x["era"] == (donemler[-1] if donemler else "3")]
    if son:
        n = len(son)
        won = sum(1 for x in son if x["st"] == "won")
        p = sum(1.0 / x["o"] for x in son) / n
        print(f"\nŞANS SINAVI — son dönem {won}/{n}, fiyat %{p*100:.1f} "
              f"bekliyordu: bu kadar AZ isabetin şansla gelme olasılığı "
              f"P(X ≤ {won}) = %{_alt_kuyruk(n, won, p)*100:.2f}")

    print("\nSON DÖNEM — HER BAHİS (defter ↔ skordan yeniden hesap)")
    card = None
    if dogrula:
        try:
            from fetch_results import fetch_match_card as card
        except Exception as e:
            print(f"  (iddaa doğrulaması yüklenemedi: {e})")
    uyusmaz = 0
    for x in son:
        hes = _sonuc(x["mk"], x["pk"], x["hs"], x["aws"])
        defter = x["st"] == "won"
        isaret = "" if hes is None or hes == defter else "  ⚠️ DEFTER≠SKOR"
        if isaret:
            uyusmaz += 1
        taze = ""
        if card and x["idd"]:
            d = card(x["idd"]) or {}
            th = ((d.get("h") or {}).get("sc"))
            ta = ((d.get("a") or {}).get("sc"))
            if th is not None and ta is not None:
                ayni = (str(th), str(ta)) == (str(x["hs"]), str(x["aws"]))
                taze = (f"  iddaa {th}-{ta} st={d.get('st')}" +
                        ("" if ayni else "  ⚠️ SKOR FARKLI"))
                if not ayni:
                    uyusmaz += 1
        print(f"  {str(x['ko'])[:16]} {str(x['h'])[:16]:16s}-{str(x['a'])[:14]:14s} "
              f"{x['mk']:7s}{str(x['pk']):4s} {x['o']:.2f} "
              f"skor {x['hs']}-{x['aws']} {x['st']:4s} "
              f"{x['ct'] or '?':5s} öne {('%.0f' % x['one']) if x['one'] is not None else '?'}sa "
              f"lig {x['lg'] or '—'} mbs {x['mbs']}{isaret}{taze}")
    print(f"\n  uyuşmazlık: {uyusmaz}"
          + ("" if dogrula else "  (skoru iddaa'dan yeniden çekmek için --dogrula)"))


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    karne(args[0] if args else "CESUR_V1", dogrula="--dogrula" in sys.argv)
