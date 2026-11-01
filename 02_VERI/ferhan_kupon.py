"""
KUPONLAR FERHAN — üretilen kuponu SAKLA, sonucu izle, iddiayı DENETLE
======================================================================
kupon_orkestra.py "bu kuponun kazanma şansı %60" diyor. Bu modül o cümleyi
denetlenebilir yapar: kuponu üretildiği an yazar, sonucu gelince kapatır ve
SÖYLENEN şans ile GERÇEKLEŞEN isabeti karşılaştırır.

⚠️ NEDEN ŞART: saklanmayan iddia hiçbir zaman yanlış çıkmaz. Bu projede
ölçülmeyen her şey sessizce bozuldu (bkz. Mavi Takım, lig kodu, canlı
pencere). Kuponun şansını ekrana yazıp kaydetmemek, kendi kendini
denetlemeyen bir vaat olurdu.

SONUÇ NEREDEN GELİYOR — YENİDEN HESAPLANMAZ
--------------------------------------------
Kuponun ayakları uydurma değil; ajanların `paper_bets`'teki GERÇEK açık
pozisyonları. O yüzden ayağın sonucu `paper_bets.status`'tan okunur.
Pazar mantığı (1X2 · KG · ALT/ÜST · kombo · gol bandı) burada İKİNCİ KEZ
yazılmaz — yazılsa iki kopya kaçınılmaz olarak birbirinden ayrışır ve
hangisinin doğru olduğu bilinemez. Tek kaynak paper_engine.

Kupon durumu: ayakların hepsi won → kazandı · biri lost → kaybetti ·
hepsi void → iptal · kalanı → hâlâ açık (karneye GİRMEZ).

KARNE = KALİBRASYON SINAVI
---------------------------
Asıl çıktı kâr değil, şu: "%60 dediklerimin %60'ı tuttu mu?" Tutmuyorsa
olasılık yanlıştır ve kuponun ödemesi ne olursa olsun sayı anlamsızdır.
Bu yüzden karne hem SÖYLENEN ortalama şansı hem GERÇEKLEŞEN isabeti,
hem de aralarındaki farkın z'sini verir (Poisson-binom standart hatası —
her kuponun kendi olasılığı farklı olduğu için düz binom yanlış olurdu).
"""
from __future__ import annotations

import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

import db  # noqa: E402

# Karne için asgari kupon sayısı: altında kalibrasyon farkı gürültüdür.
ASGARI_KUPON = 20

# STANDART BAHİS — her kupon 100 TL oynanmış gibi kaydedilir (kullanıcı
# kararı, 01.11.2026). Sabit olması şart: değişken bahisle kuponların
# getirisi karşılaştırılamaz, iyi kupon mu büyük bahis mi anlaşılmaz.
# Ajanların defteriyle aynı form: bahis · potansiyel · dönen · kâr.
BAHIS = 100.0


def _surum() -> int:
    """Tahmini üreten formülün sürümü (kupon_orkestra.FORMUL_SURUM)."""
    try:
        import kupon_orkestra
        return int(kupon_orkestra.FORMUL_SURUM)
    except Exception:
        return 0


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def kupon_kimligi(tip: str, ayaklar: list[dict], surum: int | None = None) -> str:
    """Kuponun KİMLİĞİ = seçimlerinin kümesi + FORMÜL SÜRÜMÜ (oranı değil).

    Saat başı yeniden üretilince aynı kupon yeni satır açmaz; yoksa aynı
    kupon günde 12 kez sayılır ve kalibrasyon karnesi şişer.

    Sürüm kimliğe DAHİL: formül değişince aynı seçimler yeni bir tahmindir
    ve yeni satır açmalıdır. Dahil olmasaydı, düzeltilmiş olasılık
    "zaten var" diye sessizce atlanır, defterde yalnız eski yanlış değer
    kalırdı.
    """
    s = _surum() if surum is None else surum
    parca = sorted("{}|{}|{}".format(a.get("mac_id"), a.get("market"),
                                     a.get("pick")) for a in ayaklar)
    ham = f"{tip}::v{s}::" + "++".join(parca)
    return hashlib.sha1(ham.encode("utf-8")).hexdigest()[:16]


# ----------------------------------------------------------------------
# TABLO
# ----------------------------------------------------------------------
def kur(conn=None) -> None:
    kapat = conn is None
    conn = conn or db.connect()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ferhan_kupon (
                kupon_id     TEXT PRIMARY KEY,
                uretim_ts    TEXT,
                tip          TEXT,
                ayak         INTEGER,
                oran         REAL,
                sans         REAL,
                fiyat_sansi  REAL,
                bek_getiri   REAL,
                durum        TEXT,
                sonuc_ts     TEXT,
                surum        INTEGER,
                -- Ajanların paper_coupons formuyla birebir aynı alanlar:
                -- stake · potential_return · actual_return · pnl · reasoning
                bahis        REAL,
                potansiyel   REAL,
                donen        REAL,
                kar          REAL,
                gerekce      TEXT
            )""")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ferhan_kupon_ayak (
                kupon_id  TEXT,
                sira      INTEGER,
                bet_id    TEXT,
                mac_id    TEXT,
                ajan      TEXT,
                ev        TEXT,
                dep       TEXT,
                market    TEXT,
                pick      TEXT,
                oran      REAL,
                p         REAL,
                kickoff   TEXT,
                -- paper_bets.reason / implied_prob / edge karşılıkları
                p_piyasa  REAL,
                kenar     REAL,
                kanit     INTEGER,
                gerekce   TEXT
            )""")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_fk_ayak_tekil "
                     "ON ferhan_kupon_ayak (kupon_id, sira)")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_fk_durum "
                     "ON ferhan_kupon (durum, uretim_ts)")
        conn.commit()
        # ⚠️ ALTER'ler CREATE'ler COMMIT EDİLDİKTEN SONRA, tek tek.
        # İlk yazımda ALTER, CREATE ile commit ARASINDAYDI: PostgreSQL'de
        # DDL işlemseldir, ALTER "sütun zaten var" diye patlayıp rollback
        # çağrılınca tabloyu yaratan CREATE de geri alınıyordu. SQLite'ta
        # şansa çalıştı, üretimde ilk koşuda kırılırdı.
        for tablo, sutun, tip in (
                ("ferhan_kupon", "surum", "INTEGER"),
                ("ferhan_kupon", "bahis", "REAL"),
                ("ferhan_kupon", "potansiyel", "REAL"),
                ("ferhan_kupon", "donen", "REAL"),
                ("ferhan_kupon", "kar", "REAL"),
                ("ferhan_kupon", "gerekce", "TEXT"),
                ("ferhan_kupon_ayak", "p_piyasa", "REAL"),
                ("ferhan_kupon_ayak", "kenar", "REAL"),
                ("ferhan_kupon_ayak", "kanit", "INTEGER"),
                ("ferhan_kupon_ayak", "gerekce", "TEXT")):
            try:
                conn.execute(f"ALTER TABLE {tablo} ADD COLUMN {sutun} {tip}")
                conn.commit()
            except Exception:
                conn.rollback()     # sütun zaten var
    finally:
        if kapat:
            conn.close()



def _yz(v: float, b: int = 1) -> str:
    return f"{v*100:.{b}f}".replace(".", ",")


def _sy(v: float, b: int = 2) -> str:
    """Ondalık ayırıcı VİRGÜL — proje geneliyle aynı. Gerekçe metninde
    "2.33" ile "%28,9" yan yana durunca okuyan iki ayrı birim sanıyor."""
    return f"{v:.{b}f}".replace(".", ",")


def ayak_gerekcesi(a: dict) -> str:
    """Bu ayak neden burada ve olasılığı NEREDEN geliyor.

    Ajanların paper_bets.reason alanının karşılığı. Olasılığın kaynağını
    açıkça yazar: kanıt varsa ajanın ölçülmüş alt sınırı, yoksa piyasanın
    marjsız olasılığı. Kaynağı yazmayan bir sayı denetlenemez.
    """
    oran = float(a.get("oran") or 0)
    p = float(a.get("p") or 0)
    ajan = str(a.get("ajan") or "?")
    if a.get("kanit"):
        kenar = float(a.get("kenar") or 0)
        return (f"{ajan} · KANIT VAR → şans = 1/{_sy(oran)} + kenar alt sınırı "
                f"({_yz(kenar)}p) = %{_yz(p)}")
    ima = float(a.get("ima") or 0)
    return (f"{ajan} · kanıt yok (ölçülmüş kenar kullanılmadı) → şans = "
            f"piyasanın MARJSIZ olasılığı: 1/{_sy(oran)} ÷ {_sy(ima, 3)} "
            f"= %{_yz(p)}")


def kupon_gerekcesi(k: dict, bahis: float = None) -> str:
    """Kuponun tamamının gerekçesi — paper_coupons.reasoning karşılığı."""
    b = BAHIS if bahis is None else bahis
    oran = float(k.get("oran") or 0)
    sans = float(k.get("sans") or 0)
    piy = float(k.get("fiyat_sansi") or 0)
    bg = float(k.get("bek_getiri") or 0)
    fark = sans - piy
    isaret = "+" if fark >= 0 else "−"
    sat = [f"{k.get('ayak')} ayak · ödeme {_sy(oran)} · şans %{_yz(sans)} "
           f"(marjsız piyasa %{_yz(piy)}, fark {isaret}{_yz(abs(fark))}p)",
           f"{b:.0f} TL oynanırsa: kazanırsa {b*oran:.0f} TL · "
           f"1 TL karşılığı {_sy(bg, 3)} TL"]
    if fark <= 0.0005:
        sat.append("Kenar YOK: şans tam olarak fiyatın marjsız dediği kadar. "
                   "Beklenen getiri 1 TL'nin altında, fark marjdır.")
    for a in (k.get("ayaklar") or []):
        sat.append("  · " + ayak_gerekcesi(a))
    return chr(10).join(sat)

# ----------------------------------------------------------------------
# KAYIT
# ----------------------------------------------------------------------
def kaydet(kuponlar: list[dict], tip: str = "normal", conn=None) -> int:
    """Üretilen kuponları defterine yaz. Aynı kupon ikinci kez yazılmaz."""
    if not kuponlar:
        return 0
    kapat = conn is None
    conn = conn or db.connect()
    yeni = 0
    surum = _surum()
    try:
        kur(conn)
        for k in kuponlar:
            ayaklar = k.get("ayaklar") or []
            if not ayaklar:
                continue
            kid = kupon_kimligi(tip, ayaklar)
            if conn.execute("SELECT 1 FROM ferhan_kupon WHERE kupon_id = ?",
                            (kid,)).fetchone():
                continue
            conn.execute(
                "INSERT INTO ferhan_kupon (kupon_id, uretim_ts, tip, ayak, "
                "oran, sans, fiyat_sansi, bek_getiri, durum, surum, "
                "bahis, potansiyel, gerekce) "
                "VALUES (?,?,?,?,?,?,?,?,'acik',?,?,?,?)",
                (kid, _ts(), tip, int(k["ayak"]), float(k["oran"]),
                 float(k["sans"]), float(k.get("fiyat_sansi") or 0),
                 float(k.get("bek_getiri") or 0), surum,
                 BAHIS, BAHIS * float(k["oran"]), kupon_gerekcesi(k)))
            for i, a in enumerate(ayaklar):
                conn.execute(
                    "INSERT INTO ferhan_kupon_ayak (kupon_id, sira, bet_id, "
                    "mac_id, ajan, ev, dep, market, pick, oran, p, kickoff, "
                    "p_piyasa, kenar, kanit, gerekce) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (kid, i, str(a.get("bet_id") or ""),
                     str(a.get("mac_id") or ""), str(a.get("ajan") or ""),
                     str(a.get("ev") or ""), str(a.get("dep") or ""),
                     str(a.get("market") or ""), str(a.get("pick") or ""),
                     float(a.get("oran") or 0), float(a.get("p") or 0),
                     str(a.get("kickoff") or ""),
                     float(a.get("p_piyasa") or 0), float(a.get("kenar") or 0),
                     1 if a.get("kanit") else 0, ayak_gerekcesi(a)))
            yeni += 1
        conn.commit()
    finally:
        if kapat:
            conn.close()
    return yeni


# ----------------------------------------------------------------------
# SONUÇLANDIRMA
# ----------------------------------------------------------------------
def sonuclandir(conn=None) -> dict:
    """Açık kuponları ayaklarının paper_bets durumundan kapat.

    ⚠️ Pazar mantığı burada YOK — bilerek. Ayak zaten bir paper_bets
    satırıdır ve onu paper_engine sonuçlandırır. İkinci bir hesap, iki
    doğru cevap üretir ve hangisinin geçerli olduğu bilinemez.
    """
    kapat = conn is None
    conn = conn or db.connect()
    try:
        kur(conn)
        acik = conn.execute(
            "SELECT kupon_id, oran, COALESCE(bahis,?) FROM ferhan_kupon "
            "WHERE durum = 'acik'", (BAHIS,)).fetchall()
        sayac = {"kazandi": 0, "kaybetti": 0, "iptal": 0, "acik": 0}
        for kid, oran, bahis in acik:
            ayak = conn.execute(
                "SELECT a.bet_id, b.status FROM ferhan_kupon_ayak a "
                "LEFT JOIN paper_bets b ON CAST(b.bet_id AS TEXT) = a.bet_id "
                "WHERE a.kupon_id = ?", (kid,)).fetchall()
            if not ayak:
                continue
            durumlar = [(d or "open") for _, d in ayak]
            if any(d == "lost" for d in durumlar):
                yeni = "kaybetti"
            elif all(d == "won" for d in durumlar):
                yeni = "kazandi"
            elif all(d == "void" for d in durumlar):
                yeni = "iptal"
            else:
                # Hâlâ bekleyen ayak var. Bitmemiş kupon karneye GİRMEZ;
                # yarısı tutmuş kuponu "kazandı" saymak en bariz şişirme yolu.
                sayac["acik"] += 1
                continue
            # Ajanların formu: dönen (actual_return) ve kâr (pnl).
            # İPTAL'de bahis geri döner, kâr sıfırdır — kaybetmiş saymak
            # getiriyi olduğundan kötü gösterirdi.
            b = float(bahis or BAHIS)
            if yeni == "kazandi":
                donen = b * float(oran or 0)
            elif yeni == "iptal":
                donen = b
            else:
                donen = 0.0
            conn.execute("UPDATE ferhan_kupon SET durum = ?, sonuc_ts = ?, "
                         "donen = ?, kar = ? WHERE kupon_id = ?",
                         (yeni, _ts(), donen, donen - b, kid))
            sayac[yeni] += 1
        conn.commit()
        return sayac
    finally:
        if kapat:
            conn.close()


# ----------------------------------------------------------------------
# KARNE — SÖYLENEN ŞANS vs GERÇEKLEŞEN İSABET
# ----------------------------------------------------------------------
def karne(conn=None) -> dict:
    """Şekil başına kalibrasyon sınavı + gerçekleşen birim getiri."""
    kapat = conn is None
    conn = conn or db.connect()
    try:
        kur(conn)
        # ⚠️ YALNIZ GÜNCEL FORMÜL. Başka bir formülle üretilmiş tahmini
        # bugünün gerçekleşmeleriyle karşılaştırmak, formül değişikliğini
        # kalibrasyon bozukluğu diye raporlar.
        sr = _surum()
        r = conn.execute(
            "SELECT tip, ayak, oran, sans, durum, COALESCE(bahis,?), "
            "       COALESCE(kar,0) FROM ferhan_kupon "
            "WHERE durum IN ('kazandi','kaybetti') "
            "AND COALESCE(surum,0) = ?", (BAHIS, sr)).fetchall()
        acik = conn.execute("SELECT COUNT(*) FROM ferhan_kupon "
                            "WHERE durum = 'acik' AND COALESCE(surum,0) = ?",
                            (sr,)).fetchone()[0]
        eski = conn.execute("SELECT COUNT(*) FROM ferhan_kupon "
                            "WHERE COALESCE(surum,0) <> ?", (sr,)).fetchone()[0]
    finally:
        if kapat:
            conn.close()
    from collections import defaultdict
    g = defaultdict(list)
    for tip, ayak, oran, sans, durum, bahis, kar in r:
        g[(tip, int(ayak))].append((float(oran), float(sans),
                                    1 if durum == "kazandi" else 0,
                                    float(bahis or 0), float(kar or 0)))
    out = []
    for (tip, ayak), K in sorted(g.items()):
        n = len(K)
        soylenen = sum(x[1] for x in K) / n
        gercek = sum(x[2] for x in K) / n
        # Poisson-binom: her kuponun kendi p'si var, düz binom SE'si yanlış.
        var = sum(x[1] * (1 - x[1]) for x in K)
        se = (var ** 0.5) / n if var > 0 else 0.0
        getiri = sum((x[0] - 1.0) if x[2] else -1.0 for x in K) / n
        yatan = sum(x[3] for x in K)
        kar = sum(x[4] for x in K)
        out.append({"tip": tip, "ayak": ayak, "n": n,
                    "soylenen": soylenen, "gercek": gercek,
                    "fark": gercek - soylenen,
                    "z": (gercek - soylenen) / se if se else 0.0,
                    "getiri": getiri, "yeterli": n >= ASGARI_KUPON,
                    "yatan": yatan, "kar": kar,
                    "roi": (kar / yatan) if yatan else 0.0})
    return {"satirlar": out, "acik": int(acik), "surum": sr,
            "toplam_yatan": sum(x["yatan"] for x in out),
            "toplam_kar": sum(x["kar"] for x in out),
            "eski_surum": int(eski),
            "sonuclanan": sum(x["n"] for x in out)}


def son_kuponlar(conn=None, en_cok: int = 40) -> list[dict]:
    """Defterdeki kuponlar — ayaklarıyla, arayüzde göstermek için."""
    kapat = conn is None
    conn = conn or db.connect()
    try:
        kur(conn)
        K = conn.execute(
            "SELECT kupon_id, uretim_ts, tip, ayak, oran, sans, bek_getiri, "
            "       durum, COALESCE(bahis,?), COALESCE(potansiyel,0), "
            "       donen, kar, gerekce, fiyat_sansi FROM ferhan_kupon "
            "ORDER BY uretim_ts DESC LIMIT ?", (BAHIS, en_cok)).fetchall()
        out = []
        for (kid, ts, tip, ayak, oran, sans, bg, durum, bahis, pot,
             donen, kar, gerekce, piy) in K:
            ay = conn.execute(
                "SELECT a.ev, a.dep, a.market, a.pick, a.oran, a.ajan, "
                "       COALESCE(b.status,'open'), a.gerekce, a.kanit "
                "FROM ferhan_kupon_ayak a "
                "LEFT JOIN paper_bets b ON CAST(b.bet_id AS TEXT) = a.bet_id "
                "WHERE a.kupon_id = ? ORDER BY a.sira", (kid,)).fetchall()
            out.append({
                "kupon_id": kid, "uretim_ts": ts, "tip": tip,
                "ayak": int(ayak), "oran": float(oran), "sans": float(sans),
                "bek_getiri": float(bg or 0), "durum": durum,
                "fiyat_sansi": float(piy or 0),
                "bahis": float(bahis or BAHIS), "potansiyel": float(pot or 0),
                "donen": None if donen is None else float(donen),
                "kar": None if kar is None else float(kar),
                "gerekce": gerekce or "",
                "ayaklar": [{"ev": e, "dep": d, "market": m, "pick": p,
                             "oran": float(o or 0), "ajan": aj, "durum": st,
                             "gerekce": gk or "", "kanit": bool(kn)}
                            for e, d, m, p, o, aj, st, gk, kn in ay]})
        return out
    finally:
        if kapat:
            conn.close()


def kendi_testi() -> list[str]:
    """Uçtan uca geçici SQLite üzerinde: kaydet → sonuçlandır → karne."""
    import os
    import sqlite3
    import tempfile
    hata = []
    yol = Path(tempfile.gettempdir()) / f"fk_test_{os.getpid()}.db"
    try:
        yol.unlink()
    except Exception:
        pass
    try:
        c = sqlite3.connect(str(yol))
        c.execute("CREATE TABLE paper_bets (bet_id TEXT, status TEXT)")
        for bid, st in (("1", "won"), ("2", "won"), ("3", "lost"),
                        ("4", "open"), ("5", "void"), ("6", "void")):
            c.execute("INSERT INTO paper_bets VALUES (?,?)", (bid, st))
        c.commit()
        kur(c)

        def _k(ayak_ids, sans):
            return {"ayak": len(ayak_ids), "oran": 1 / sans, "sans": sans,
                    "fiyat_sansi": sans, "bek_getiri": 1.0,
                    "ayaklar": [{"bet_id": b, "mac_id": b, "market": "1X2",
                                 "pick": "1", "oran": 2.0, "p": 0.5,
                                 "ajan": "A"} for b in ayak_ids]}
        K = [_k(["1", "2"], 0.5), _k(["1", "3"], 0.5),
             _k(["1", "4"], 0.5), _k(["5", "6"], 0.5)]
        n = kaydet(K, "normal", c)
        if n != 4:
            hata.append(f"4 kupon yazılmalı, {n}")
        if kaydet(K, "normal", c) != 0:
            hata.append("aynı kupon ikinci kez yazıldı")
        s = sonuclandir(c)
        for ad, bek in (("kazandi", 1), ("kaybetti", 1), ("iptal", 1),
                        ("acik", 1)):
            if s[ad] != bek:
                hata.append(f"{ad} {bek} olmalı, {s[ad]}")
        # PARA: 100 TL standart · oran 2,00 → kazanan 200 döner (+100),
        # kaybeden 0 (−100), iptal bahsi geri verir (0).
        para = {d: (dn, kr_) for d, dn, kr_ in c.execute(
            "SELECT durum, donen, kar FROM ferhan_kupon "
            "WHERE durum <> 'acik'").fetchall()}
        for d, bek_donen, bek_kar in (("kazandi", 200.0, 100.0),
                                      ("kaybetti", 0.0, -100.0),
                                      ("iptal", 100.0, 0.0)):
            got = para.get(d)
            if not got or abs(got[0] - bek_donen) > 1e-6                     or abs(got[1] - bek_kar) > 1e-6:
                hata.append(f"{d}: dönen/kâr {got} olmalı "
                            f"({bek_donen}, {bek_kar})")
        kr = karne(c)
        if abs(kr.get("toplam_kar", 0) - 0.0) > 1e-6:
            hata.append(f"toplam kâr 0 olmalı (bir kazanan bir kaybeden), "
                        f"{kr.get('toplam_kar')}")
        if abs(kr.get("toplam_yatan", 0) - 200.0) > 1e-6:
            hata.append(f"toplam yatan 200 olmalı, {kr.get('toplam_yatan')}")
        if kr["sonuclanan"] != 2:
            hata.append(f"karnede 2 kupon olmalı (iptal/açık sayılmaz), "
                        f"{kr['sonuclanan']}")
        sat = kr["satirlar"][0] if kr["satirlar"] else {}
        if sat and abs(sat["gercek"] - 0.5) > 1e-9:
            hata.append(f"gerçek isabet 0,50 olmalı, {sat['gercek']}")
        if kr["acik"] != 1:
            hata.append(f"açık kupon 1 olmalı, {kr['acik']}")
        if len(son_kuponlar(c)) != 4:
            hata.append("son_kuponlar 4 satır döndürmeli")
        # ESKİ FORMÜL SÜRÜMÜ karneye GİRMEMELİ. Üretimde sürüm 1 ile
        # yazılmış satırlar var; süzgeç çalışmazsa formül değişikliği
        # "kalibrasyon bozuk" diye raporlanır.
        c.execute("INSERT INTO ferhan_kupon (kupon_id, uretim_ts, tip, ayak, "
                  "oran, sans, fiyat_sansi, bek_getiri, durum, surum) "
                  "VALUES ('eski1','2026-01-01','normal',1,2.0,0.95,0.95,"
                  "1.9,'kazandi',1)")
        c.execute("INSERT INTO ferhan_kupon_ayak (kupon_id, sira, bet_id) "
                  "VALUES ('eski1',0,'1')")
        c.commit()
        kr2 = karne(c)
        if kr2["sonuclanan"] != 2:
            hata.append(f"eski sürüm karneye girdi: {kr2['sonuclanan']} "
                        f"(2 olmalı)")
        if kr2.get("eski_surum") != 1:
            hata.append(f"eski sürüm sayısı 1 olmalı, {kr2.get('eski_surum')}")
        c.close()
    except Exception as e:
        hata.append(f"{type(e).__name__}: {e}")
    finally:
        try:
            yol.unlink()
        except Exception:
            pass
    return hata


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    h = kendi_testi()
    print("kendi testi:", "TEMİZ" if not h else f"{len(h)} sorun")
    for x in h:
        print("  ", x)
