"""
CANLI CLV — bahsin iyi olup olmadığını SONUCU BEKLEMEDEN öğren
===============================================================
Bu projenin darboğazı kenar bulmak değil, ÖLÇÜM HIZI. Bir ajanın gerçekten
iyi olduğunu gerçekleşen getiriden anlamak yüzlerce bahis istiyor; o yüzden
kasa 30 karardan azına açılmıyor (bkz. kasa.py). CLV çok daha hızlı
yakınsıyor çünkü gürültüsü küçük: sonuç 0/1 zar atışı, fiyat ise sürekli.

Klasik CLV bahsin oranını KAPANIŞ oranıyla karşılaştırır. Canlı CLV aynı
şeyi maç içine uzatır:

    canli_clv = (aldığın oran / piyasanın sonraki oranı) − 1

Artıysa piyasadan ÖNCE davranmışsın: aldığın fiyat, piyasanın daha sonra
verdiği fiyattan iyi. Eksiyse geç kalmışsın ya da yanlış taraftasın.

NEDEN CANLI FİYATA GÜVENİYORUZ
Ölçüldü (01.11.2026, 1.688 maç): canlı piyasa fiyatı bizim canlı
modelimizden HER dakika diliminde daha iyi kalibre (Brier farkı +0,029 …
+0,080, hep piyasa lehine). Yani canlı fiyat bizim için bir rakip değil,
ELİMİZDEKİ EN İYİ GERÇEK TAHMİNİ. Ölçü aleti olarak kullanılır.

⚠️ NE DEĞİLDİR
Canlı CLV bir bahis sinyali DEĞİLDİR. Aynı veride üç şey ölçüldü ve üçü de
negatif çıktı: canlı modelimiz piyasayı geçmiyor, gol sonrası aşırı tepki
45 sn çözünürlükte görünmüyor, ve kâr kilitleme (scalping) tutmaya 16-20
puan kaybettiriyor. Bu modül PARA KAZANMAK için değil, HIZLI ÖLÇMEK için.

⚠️ HAM ORAN KULLANILIR, MARJSIZ DEĞİL
İki tarafta da ham oran karşılaştırılır; marj yaklaşık olarak sadeleşir.
Marjsız olasılıkla ham oranı karıştırmak bu projede iki kez hataya yol
açtı (bkz. kenar-sutunu-marj ve toto_iddaa kârlılık şartı).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent
for _p in (str(KOK), str(KOK.parent / "02_VERI")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import db  # noqa: E402

# 1X2 sütun sırası ve pick gösterimi. Beraberlik "0" — proje geneliyle aynı.
SIRA = {"1": 0, "0": 1, "X": 1, "2": 2}
# Erken pencere: maç başı, skor henüz değişmemiş. Fiyat burada "kapanış
# sonrası ilk bilgili fiyat" sayılır.
ERKEN_DK = 10


def _oran(satir) -> list | None:
    try:
        o = json.loads(satir)
    except Exception:
        return None
    if isinstance(o, dict):
        o = o.get("1X2")
    if not o or len(o) != 3 or min(o) <= 1.01:
        return None
    t = sum(1.0 / x for x in o)
    # Sağlık süzgeci: toplam ima 1,00'in altı İMKÂNSIZ (bozuk kayıt), 1,40
    # üstü de gerçekçi değil. Ölçüldü: canlı medyan 1,212, ama kuyrukta
    # 0,228 gibi çöp satırlar var.
    return o if 1.00 <= t <= 1.40 else None


def _askida(v) -> bool:
    """'askida' alanı NULL değil 'None' STRING'i tutabiliyor — düz doğruluk
    kontrolü bütün sağlam satırları eler (bir kez elendi)."""
    return bool(v) and str(v) != "None" and '"1X2"' in str(v)


def bahis_clv(conn, asgari_anlik: int = 5) -> list[dict]:
    """Her sonuçlanmış 1X2 bahsi için canlı CLV.

    Bahis → maç → cl_mac (iddaa kimliğinden) → cl_anlik serisi.
    Erken pencere fiyatı referans alınır; yoksa serinin ilk sağlam fiyatı.
    """
    B = conn.execute(
        "SELECT pb.bet_id, pb.portfolio_id, pb.market, pb.pick, pb.odds, pb.status, "
        "       m.mac_id "
        "FROM paper_bets pb "
        "JOIN matches_v2 mv ON mv.match_id = pb.match_id "
        "JOIN cl_mac m ON CAST(m.iddaa_id AS TEXT) = CAST(mv.external_id_iddaa AS TEXT) "
        "WHERE pb.market = '1X2' AND pb.status IN ('won','lost') AND pb.odds > 1.01"
    ).fetchall()
    if not B:
        return []
    maclar = {r[6] for r in B}
    seri: dict = {}
    for mid in maclar:
        rows = conn.execute(
            "SELECT dakika, ev_skor, dep_skor, oran, askida FROM cl_anlik "
            "WHERE mac_id = ? ORDER BY ts", (mid,)).fetchall()
        temiz = []
        for dk, h, a, o, ask in rows:
            if _askida(ask):
                continue
            oo = _oran(o)
            if oo:
                temiz.append((dk, (h or 0) + (a or 0), oo))
        if len(temiz) >= asgari_anlik:
            seri[mid] = temiz
    out = []
    for bet_id, pid, mkt, pick, odds, durum, mid in B:
        S = seri.get(mid)
        if not S:
            continue
        j = SIRA.get(str(pick))
        if j is None:
            continue
        # Erken pencere: ilk ERKEN_DK dakika VE henüz gol yok
        erken = [o for dk, gol, o in S
                 if (dk or 0) <= ERKEN_DK and gol == 0]
        ref = (erken[0] if erken else S[0][2])[j]
        out.append({
            "bet_id": bet_id, "ajan": pid, "pick": str(pick),
            "oran": float(odds), "ref_oran": float(ref),
            "canli_clv": float(odds) / float(ref) - 1.0,
            "kazandi": 1 if durum == "won" else 0,
            "erken": bool(erken), "anlik": len(S),
        })
    return out


def ozet(satirlar: list[dict]) -> dict:
    """Ajan bazında canlı CLV — ve CLV'nin sonucu ÖNGÖRÜP öngörmediği.

    İkincisi şart: CLV ancak gerçekten sonuçla ilişkiliyse hızlı ölçüm
    aracıdır. İlişkisizse yalnız gürültüdür ve ona göre karar verilemez.
    """
    import statistics as st
    from collections import defaultdict
    g = defaultdict(list)
    for x in satirlar:
        g[x["ajan"]].append(x)
    out = []
    for ajan, K in g.items():
        v = [x["canli_clv"] for x in K]
        out.append({"ajan": ajan, "n": len(K), "clv": st.mean(v),
                    "clv_se": (st.pstdev(v) / len(v) ** 0.5) if len(v) > 1 else 0.0,
                    "isabet": sum(x["kazandi"] for x in K) / len(K)})
    return {"ajanlar": sorted(out, key=lambda x: -x["clv"]),
            "toplam": len(satirlar)}


def clv_sonucu_ongoruyor_mu(satirlar: list[dict]) -> dict:
    """CLV artı olan bahisler, eksi olanlardan daha sık mı kazanıyor?

    Bu, bütün yaklaşımın SINAVI. Geçmezse canlı CLV bir ölçü aleti değildir.
    """
    import statistics as st
    arti = [x for x in satirlar if x["canli_clv"] > 0]
    eksi = [x for x in satirlar if x["canli_clv"] <= 0]
    if len(arti) < 30 or len(eksi) < 30:
        return {"yeterli": False, "arti": len(arti), "eksi": len(eksi)}

    def _b(K):
        p = sum(x["kazandi"] for x in K) / len(K)
        return p, (p * (1 - p) / len(K)) ** 0.5
    pa, sa = _b(arti)
    pe, se = _b(eksi)
    fark = pa - pe
    sef = (sa ** 2 + se ** 2) ** 0.5
    # Getiri de ayrı ölçülür: isabet tek başına yanıltır (kısa oran).
    def _g(K):
        v = [(x["oran"] - 1.0) if x["kazandi"] else -1.0 for x in K]
        return st.mean(v), st.pstdev(v) / len(v) ** 0.5
    ga, gsa = _g(arti)
    ge, gse = _g(eksi)
    return {"yeterli": True,
            "arti_n": len(arti), "arti_isabet": pa, "arti_getiri": ga,
            "eksi_n": len(eksi), "eksi_isabet": pe, "eksi_getiri": ge,
            "isabet_farki": fark, "isabet_z": fark / sef if sef else 0.0,
            "getiri_farki": ga - ge,
            "getiri_z": (ga - ge) / ((gsa ** 2 + gse ** 2) ** 0.5)
                        if (gsa or gse) else 0.0}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    c = db.connect()
    try:
        S = bahis_clv(c)
    finally:
        c.close()
    print(f"canlı CLV hesaplanan bahis: {len(S):,}")
    if not S:
        sys.exit(0)
    t = clv_sonucu_ongoruyor_mu(S)
    print("\nSINAV — canlı CLV sonucu öngörüyor mu?")
    if not t.get("yeterli"):
        print(f"  örneklem yetersiz (artı {t['arti']} · eksi {t['eksi']})")
    else:
        print(f"  CLV > 0 : n={t['arti_n']:5,} isabet %{t['arti_isabet']*100:5.1f} "
              f"birim getiri %{t['arti_getiri']*100:+6.1f}")
        print(f"  CLV ≤ 0 : n={t['eksi_n']:5,} isabet %{t['eksi_isabet']*100:5.1f} "
              f"birim getiri %{t['eksi_getiri']*100:+6.1f}")
        print(f"  fark    : isabet {t['isabet_farki']*100:+.1f}p (z={t['isabet_z']:+.2f}) · "
              f"getiri {t['getiri_farki']*100:+.1f}p (z={t['getiri_z']:+.2f})")
        print("\n  z ≥ 2 ise canlı CLV gerçek bir ölçü aletidir; altındaysa gürültüdür.")
    o = ozet(S)
    print(f"\n{'ajan':18} {'n':>6} {'canlı CLV':>11} {'±95%':>8} {'isabet':>8}")
    print("-" * 56)
    for a in o["ajanlar"][:14]:
        print(f"{a['ajan']:18} {a['n']:6,} %{a['clv']*100:+10.2f} "
              f"%{1.96*a['clv_se']*100:7.2f} %{a['isabet']*100:7.1f}")
