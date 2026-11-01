"""
🟢 TOTO TAKIM — Süper Toto modelini İDDAA'da oynat
===================================================
Fikir: o haftanın 15 Toto maçı iddaa'da da var. Toto'nun olasılık modeli
iddaa fiyatından BAĞIMSIZ bir görüş üretiyor (Elo · Form · H2H · Kadro).
Bu görüş fiyatla ayrıştığında, orada kenar olabilir.

NEDEN BU, PROJEDEKİ DİĞER AJANLARDAN FARKLI
--------------------------------------------
Ölçtük (24.10.2026): BetAgents ajanlarının `model_prob` alanı aslında
`_vig_strip(fiyat)` — yani kendi fiyatlarının marjsızı. Kendi fiyatını
tekrar eden bir "model"in kenarı yapısal olarak EKSİDİR:
    edge = raw/S − raw = −raw·(S−1)/S          (1.252 bahsin 1.252'sinde)
Toto'nun P'si ise fiyattan türetilmiyor; Elo reytingleri, gol modeli ve
aralarındaki maçlardan geliyor. Bu, projede ilk kez gerçek kenarın
olabileceği yer — "olabileceği", olduğu değil. Ölçeceğiz.

İKİ GÖRÜŞ, İKİ AJAN — ve aralarındaki dürüst gerilim
-----------------------------------------------------
Toto'nun pazar fiyatı P_toto, ajanların SERVET AĞIRLIKLI ortalamasıdır ve
PİYASA ajanı o servetin çoğuna sahiptir (kulüpte %68, millide %53) —
çünkü geçmişte en isabetli o olmuş. Dolayısıyla:

  P_toto        piyasaya DEMİRLİ. İddaa fiyatıyla farkı küçüktür ama o fark
                "piyasa çıpasından sonra kalan bilgi"dir. Muhafazakâr.
  P_bagimsiz    PİYASA ajanı ÇIKARILIP kalanlar yeniden normalize edilir.
                Tamamen fiyattan bağımsız. Agresif — ama cüzdan bu ajanların
                daha az isabetli olduğunu söylüyor.

Hangisinin doğru olduğunu bilmiyoruz. İkisi de ajan olarak sahaya çıkar,
aynı kontrol çizgisiyle ölçülür. Bilmediğimizi bilerek kurmak, birini
seçip haklı çıkmayı ummaktan iyidir.

⚠️ KAPSAM: iddaa eşleşmesi her hafta 15/15 olmuyor (ölçüldü: 8/15 —
milli maçların bir kısmı iddaa programında yok). Eşleşmeyen maç aday
OLMAZ; uydurma fiyatla bahis kurulmaz.
"""
from __future__ import annotations

PIYASA = "PİYASA"
SEC = ("1", "0", "2")
# iddaa 1X2 sütun adları — paper_bets'e bu adlarla yazılır
PAZAR = "1X2"


def _normalize(v: list[float]) -> list[float] | None:
    t = sum(x for x in v if x and x > 0)
    return [x / t for x in v] if t > 0 else None


def bagimsiz_p(mac: dict, paylar: dict | None) -> list[float] | None:
    """PİYASA ajanı ÇIKARILMIŞ, servet ağırlıklı olasılık.

    `paylar` o maçın pazar payları (analizdeki 'pay' alanı). Yoksa kalan
    ajanlar eşit ağırlıkla toplanır — pay bilgisi olmayan eski analizler
    sessizce yanlış ağırlık kullanmasın diye bu dal AÇIKÇA yazıldı.
    """
    gor = mac.get("gorus") or {}
    kalan = {a: v for a, v in gor.items() if a != PIYASA and v}
    if not kalan:
        return None
    if paylar:
        w = {a: float(paylar.get(a, 0.0)) for a in kalan}
        if sum(w.values()) <= 0:
            w = {a: 1.0 for a in kalan}
    else:
        w = {a: 1.0 for a in kalan}
    tw = sum(w.values())
    out = [0.0, 0.0, 0.0]
    for a, v in kalan.items():
        k = w[a] / tw
        for j in range(3):
            out[j] += k * float(v[j])
    return _normalize(out)


def adaylar(A: dict, hedef: str = "isabet", min_kenar: float = 0.03,
            min_oran: float = 1.20, max_oran: float = 6.00,
            gorus: str = "toto") -> list[dict]:
    """Haftanın Toto maçlarında iddaa adayları — MAÇ BAŞINA EN ÇOK BİR seçim.

    hedef = "isabet"  → KÂRLI seçenekler arasından EN OLASI olanı
            "getiri"  → KÂRLI seçenekler arasından beklentisi EN YÜKSEK olanı
            "rastgele"→ kontrol: maç kimliğinden deterministik taraf

    `min_kenar` artık "beklenen getiri 1'i ne kadar aşmalı" demektir
    (0,03 → p×oran ≥ 1,03). Eskiden marjsız olasılığa göre ölçülüyordu ve
    kaybeden bahisleri geçiriyordu; aşağıdaki nota bak.

    ⚠️ NEDEN "EN ÇOK AYRIŞANI SEÇ" KALDIRILDI
    İlk sürümde AYKIRI, piyasadan en çok ayrışan tarafı seçiyordu. Bu TOTO
    mantığıdır: parimutuel oyunda ikramiye paylaşıldığı için kalabalıktan
    ayrılmak başlı başına değerlidir. iddaa SABİT ORANLIDIR — havuz
    paylaşılmaz, kimse senin kuponunu seyreltmez. Orada ayrışmanın değeri
    SIFIRDIR; tek değerli şey İSABETTİR. Kategori hatasıydı, kaldırıldı.
    (Kullanıcı tespiti, 01.11.2026.)

    İki hedef kasıtlı olarak AYRI ajanlara verildi: "en çok isabet" ile "en
    çok kazanç" aynı şey değildir ve hangisinin daha iyi olduğunu ancak yan
    yana ölçerek öğreniriz. İsabet kısa oranı, getiri uzun oranı sever.
    """
    out = []
    P = A.get("P") or []
    for i, m in enumerate(A.get("maclar") or []):
        idd = m.get("iddaa") or {}
        q = idd.get("p")
        oranlar = idd.get("oran")
        if not q or not oranlar:
            continue                       # iddaa'da yok → aday değil
        p = (bagimsiz_p(m, m.get("pay")) if gorus == "bagimsiz"
             else (P[i] if i < len(P) else None))
        if not p:
            continue

        secenek = []
        for j in range(3):
            o = float(oranlar[j] or 0)
            if not (min_oran <= o <= max_oran):
                continue
            secenek.append((j, o, float(p[j]), float(q[j])))
        if not secenek:
            continue

        if hedef == "rastgele":
            ev = idd.get("event_id")
            h = (int(ev) * 2654435761) % len(secenek) if str(ev).isdigit() else 0
            sec = secenek[h]
        else:
            # ⚠️ KÂRLILIK ŞARTI: p × oran > 1, yani p > 1/oran.
            #
            # Önce kenarı MARJSIZ olasılığa göre süzüyordum (p − q ≥ eşik). O
            # yanlıştı: marjsız q, piyasanın "adil" görüşüdür ama parayı
            # MARJLI orandan alırsın. Piyasayla aynı fikirde olmamak başka
            # şey, FİYATI YENMEK başka şey.
            # Yakalandı (01.11.2026): Kuzey Makedonya-İsviçre beraberlik,
            # bizim %18,9 · başabaş %21,3 → kendi modelimize göre KAYBEDEN
            # bir bahis, ama q'ya göre kenarı +0,029 olduğu için süzgeci
            # geçiyordu. Bek. getirisi 0,888'di; yani oynadıkça eriyecekti.
            uygun = [x for x in secenek
                     if x[2] * x[1] >= 1.0 + min_kenar          # p·o > 1
                     and x[2] > x[3]]                            # piyasadan da yukarı
            if not uygun:
                continue
            if hedef == "getiri":
                sec = max(uygun, key=lambda x: x[2] * x[1])
            else:                           # "isabet"
                sec = max(uygun, key=lambda x: x[2])

        j, o, pj, qj = sec
        out.append({
            "sira": i + 1, "ev": m.get("ev"), "dep": m.get("dep"),
            "tarih": m.get("tarih"), "event_id": idd.get("event_id"),
            "market": PAZAR, "pick": SEC[j], "odds": o,
            "implied_prob": 1.0 / o if o else 0.0,
            "model_prob": pj, "piyasa_prob": qj,
            "edge": pj - qj,
            # başabaş için gereken isabet — tek anlamlı eşik
            "basabas": 1.0 / o if o else 0.0,
            "bek_getiri": pj * o,
            "signal_name": f"TOTO_{hedef[:3].upper()}",
            "signal_score": min(1.0, max(0.0, (pj - qj) / 0.20)),
            "hedef": hedef,
        })
    # İsabet hedefi en olasıyı, getiri hedefi en yüksek beklentiyi öne alır.
    out.sort(key=lambda x: -(x["model_prob"] if hedef == "isabet"
                             else x["bek_getiri"]))
    return out


def ozet(A: dict) -> dict:
    """Haftanın kapsamı ve iki görüşün piyasadan ne kadar ayrıştığı."""
    n = len(A.get("maclar") or [])
    eslesen = sum(1 for m in (A.get("maclar") or [])
                  if (m.get("iddaa") or {}).get("p"))
    sap_t, sap_b, k = 0.0, 0.0, 0
    P = A.get("P") or []
    for i, m in enumerate(A.get("maclar") or []):
        q = (m.get("iddaa") or {}).get("p")
        if not q:
            continue
        k += 1
        if i < len(P) and P[i]:
            sap_t += max(abs(P[i][j] - q[j]) for j in range(3))
        b = bagimsiz_p(m, m.get("pay"))
        if b:
            sap_b += max(abs(b[j] - q[j]) for j in range(3))
    return {"mac": n, "iddaa_eslesen": eslesen,
            "ort_sapma_toto": (sap_t / k) if k else 0.0,
            "ort_sapma_bagimsiz": (sap_b / k) if k else 0.0}


if __name__ == "__main__":
    import json
    import sqlite3
    import sys
    from pathlib import Path
    sys.stdout.reconfigure(encoding="utf-8")
    db = Path(__file__).resolve().parent.parent / "02_VERI" / "ui_onizleme.db"
    c = sqlite3.connect(str(db))
    r = c.execute("SELECT icerik FROM toto_analiz ORDER BY hafta_id DESC LIMIT 1").fetchone()
    if not r:
        sys.exit("toto_analiz yok")
    A = json.loads(r[0])
    o = ozet(A)
    print(f"{A['hafta']['sezon']} {A['hafta']['ad']}")
    print(f"  maç {o['mac']} · iddaa'da eşleşen {o['iddaa_eslesen']}")
    print(f"  piyasadan ortalama sapma: P_toto {o['ort_sapma_toto']:.3f} · "
          f"bağımsız {o['ort_sapma_bagimsiz']:.3f}")
    for g in ("toto", "bagimsiz"):
        A_ = adaylar(A, gorus=g)
        print(f"\n{g.upper()} görüşü · kenar ≥ %5 · {len(A_)} aday")
        for x in A_[:6]:
            print(f"  {x['ev'][:18]:18}-{x['dep'][:16]:16} {x['pick']} "
                  f"oran {x['odds']:5.2f}  biz %{x['model_prob']*100:4.1f} "
                  f"piyasa %{x['piyasa_prob']*100:4.1f}  kenar {x['edge']:+.3f}")
