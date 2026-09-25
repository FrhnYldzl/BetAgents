"""
BETAGENTS · SÜREKLİ PUANLAMA KOŞUCUSU
======================================
Ajanların GERÇEK üreteçlerini geçmiş maçlar üzerinde koşturur ve
surekli_puan.py ile puanlar. Ajan mantığı burada YENİDEN YAZILMAZ —
agents.py'deki fonksiyonlar çağrılır ki ölçtüğümüz şey gerçekten ajan olsun.

ÜRETİM KORUMASI
---------------
db.connect() bu betikte HATA FIRLATIR. Üreteçlerin bazıları veritabanına
gidiyor (KONSEY, ÇARPAN, POPÜLER, TERS); onlar sessizce yanlış veriyi
okumak yerine "koşturulamadı" diye raporlanır. Ölçüm anlık görüntüden
(ui_onizleme.db) okunur, üretime hiçbir bağlantı açılmaz.

REPLAY SINIRI
-------------
`min_lead_h` (maça kalan süre) filtresi geçmişe uygulanamaz: bugünden
bakıldığında her geçmiş maç "çok geç"tir ve ajan hiç konuşmaz. Bu filtre
replay'de sıfırlanır — yani ölçülen, ajanın ZAMANLAMA disiplini değil,
FİLTRESİNİN maç seçme becerisidir. Zamanlama ayrı ölçülür (ajan_karne.py).
"""
from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

ANLIK = THIS_DIR / "ui_onizleme.db"


def _maclar() -> list[dict]:
    """Puanlanabilir maçlar: kapanış 1X2 tam + sonuç var + fiyatlar geçerli."""
    if not ANLIK.exists():
        sys.exit(f"anlık görüntü yok: {ANLIK}\n  önce: python 02_VERI/ui_onizleme_al.py")
    c = sqlite3.connect(str(ANLIK))
    c.row_factory = sqlite3.Row
    try:
        rows = c.execute(
            "SELECT * FROM matches_v2 "
            "WHERE closing_1 IS NOT NULL AND closing_X IS NOT NULL AND closing_2 IS NOT NULL "
            "  AND home_score IS NOT NULL AND away_score IS NOT NULL "
            "  AND closing_1 > 1.05 AND closing_2 > 1.05 AND closing_X > 1.05 "
            "ORDER BY kickoff_utc").fetchall()
    finally:
        c.close()
    return [dict(r) for r in rows]


def _uretimi_kapat():
    """db.connect'i devre dışı bırak — kazara üretime uzanmayı imkânsız kıl."""
    import db

    def _yasak(*a, **k):
        raise RuntimeError("SÜREKLİ PUANLAMA: veritabanı bağlantısı kapalı "
                           "(ölçüm anlık görüntüden okunur)")
    db.connect = _yasak
    return db


def _sessiz(fn, *a, **k):
    """Üreteçler bol bol print ediyor; raporu boğmasınlar."""
    import contextlib, io
    tampon = io.StringIO()
    try:
        with contextlib.redirect_stdout(tampon):
            return fn(*a, **k), None
    except Exception as e:
        return None, f"{type(e).__name__}: {str(e)[:90]}"


def _iddialar(picks):
    for p in picks or []:
        m = p.get("_match")
        if m:
            yield p["market"], p["pick"], float(p["odds"]), m


def kos() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    import surekli_puan as SP

    M = _maclar()
    kal = SP.Kalibrasyon(M)
    bant_n = sum(1 for v in kal.kova.values() if v[1] >= kal.ASGARI)
    print(f"SÜREKLİ PUANLAMA · {len(M)} puanlanabilir maç "
          f"({M[0]['kickoff_utc'][:10]} → {M[-1]['kickoff_utc'][:10]})")
    print(f"taban: eşleştirilmiş kontrol · {bant_n} fiyat bandı "
          f"(en az {kal.ASGARI} gözlem)\n")

    _uretimi_kapat()
    import agents as A

    sonuc: list[dict] = []
    atlanan: list[tuple[str, str]] = []

    # ── TABAN ÇİZGİLERİ ────────────────────────────────────────────────
    for ad, gen in (("» PİYASA (favori)", SP.taban_piyasa),
                    ("» JOKER (rastgele)", SP.taban_joker),
                    ("» HEP EV", SP.taban_hep_ev)):
        sonuc.append(SP.puanla(gen(M), ad, kal))

    # ── AJANLAR ────────────────────────────────────────────────────────
    eng = None
    for pid, prof in A.PROFILES.items():
        mode = prof.get("mode")
        p = dict(prof)
        p["min_lead_h"] = 0          # replay sınırı: zamanlama filtresi kapalı

        if mode == "midband":
            picks, hata = _sessiz(A._midband_candidates, p, pid, M)
        elif mode == "joker":
            picks, hata = _sessiz(A._joker_candidates, p, pid, M)
        elif mode in ("value", "confirm"):
            # Bu iki mod bağımsız Poisson modelini (independent_model) ister.
            # Reyting NOKTA-ZAMANLI kurulmalı; anlık görüntünün tamamından
            # kurmak geleceği sızdırır. Sızıntılı sayı vermektense susuyoruz.
            atlanan.append((pid, f"'{mode}' bağımsız model istiyor — nokta-zaman "
                                 f"reyting olmadan sızıntısız replay edilemez"))
            continue
        elif mode is None:
            # build_coupons eşleşmeyen her modu motor yoluna düşürür; bu
            # ajanlar sinyal motorunun adaylarını kendi filtreleriyle eler.
            if eng is None:
                from paper_engine import PaperEngine
                eng = PaperEngine()
            picks, hata = _sessiz(A._engine_candidates, p, pid, M, eng)
        else:
            atlanan.append((pid, f"'{mode}' üreteci veritabanı istiyor — replay edilemez"))
            continue

        if hata:
            atlanan.append((pid, hata))
            continue
        sonuc.append(SP.puanla(_iddialar(picks), pid, kal))

    # ── RAPOR ──────────────────────────────────────────────────────────
    print(SP.BASLIK)
    print("-" * len(SP.BASLIK))
    konusan = [o for o in sonuc if o.get("n")]
    for o in sorted(konusan, key=lambda x: -x["z"]):
        print(SP.satir(o))
    for o in sonuc:
        if not o.get("n"):
            print(SP.satir(o))

    print("\nYORUM (eşik 3σ — ~20 ajan sınanıyor, 2σ'da yanlış alarm beklenir)")
    for o in sorted(konusan, key=lambda x: -x["z"]):
        print(f"   {o['ajan']:22} {SP.yorum(o)}")

    if atlanan:
        print(f"\nKOŞTURULAMAYAN ({len(atlanan)}) — sessizce yanlış ölçmektense raporlanır:")
        for pid, n in atlanan:
            print(f"   {pid:22} {n}")

    print("\nnot: sanal ROI günlük kotayı ve kupon kurgusunu yoksayar; "
          "gerçek defterle karşılaştırılamaz, ajanlar arası karşılaştırma içindir.")


if __name__ == "__main__":
    kos()
