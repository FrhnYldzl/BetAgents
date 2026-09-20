"""
VIBE BETTING · ARAÇLAR — ajanın verilere ve koda bakma yolları
===============================================================
Hepsi SALT OKUMA; yalnız iki araç yazar ve ikisi de kendi `vibe_*` tablosuna:
`geri_bildirim` (geliştirme kanalı) ve `analiz_iste` (worker'a iş bırakır).

Güvenlik kuralları:
  • Kod araçları yalnız 09_TOTO ve 08_AI_TRADER altındaki .py/.md dosyalarını görür.
  • `.env`, veritabanı ve önbellek dosyaları erişime kapalı; çıktıda anahtar
    görünümlü diziler maskelenir (üretimde panel ortam değişkenlerini taşıyor).
  • Çıktılar kırpılır — bağlam ve maliyet kontrolü.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent
YAZILIM = KOK.parent
for _p in (str(KOK), str(YAZILIM / "02_VERI")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import toto_db  # noqa: E402
import vibe_db  # noqa: E402

KOD_DIZIN = {"09_TOTO": KOK, "08_AI_TRADER": YAZILIM / "08_AI_TRADER"}
KOD_UZANTI = {".py", ".md"}
YASAK = re.compile(r"(^|/)\.env|\.db($|-)|veri_cache|_cache_llm|yedek_|\.pkl$|\.pickle$", re.I)
SIR = re.compile(r"((?:api[_-]?key|token|secret|password|passwd|pwd|dsn|database_url)\W{0,3})([A-Za-z0-9_\-:/@.+]{8,})",
                 re.I)
DSN = re.compile(r"\b(postgres(?:ql)?|mysql|redis)://[^\s\"']+", re.I)


def _maskele(s: str) -> str:
    s = DSN.sub(r"\1://***gizli***", s)
    return SIR.sub(lambda m: m.group(1) + "***gizli***", s)


def _kirp(s: str, n: int) -> str:
    s = str(s)
    return s if len(s) <= n else s[:n] + f"\n… (kırpıldı, toplam {len(s)} karakter)"


def _yuzde3(x):
    return [round(float(v), 3) for v in x]


# ── TOTO ──────────────────────────────────────────────────────────
def _analiz() -> dict | None:
    """En son analiz (toto_db çözümlenmiş sözlük döndürür)."""
    try:
        return toto_db.son_analiz()
    except Exception:
        return None


def toto_bu_hafta() -> dict:
    """Güncel Toto haftası: kapı kararı, havuz, kupon özetleri ve 15 maç."""
    A = _analiz()
    if not A:
        return {"hata": "Güncel analiz bulunamadı. Toto worker henüz analiz üretmemiş olabilir."}
    maclar = []
    for i, m in enumerate(A.get("maclar") or []):
        P = A["P"][i] if i < len(A.get("P") or []) else None
        Q = A["Q"][i] if i < len(A.get("Q") or []) else None
        idd = m.get("iddaa") or {}
        g = m.get("gerekce") or {}
        maclar.append({
            "sira": m.get("sira"), "mac": f"{m.get('ev')} - {m.get('dep')}", "tarih": m.get("tarih"),
            "turnuva": m.get("turnuva"), "aile": m.get("aile"), "bilgi": m.get("bilgi"),
            "P_1_0_2": _yuzde3(P) if P else None, "kalabalik_q": _yuzde3(Q) if Q else None,
            "iddaa_oran": idd.get("oran"), "favori": g.get("favori"), "degerli": g.get("deger"),
            "deger_orani": g.get("deger_orani"),
        })
    kuponlar = [{"profil": k.get("profil_ad") or k.get("profil"), "butce": k.get("butce"),
                 "kolon": k.get("kolon"), "maliyet": k.get("maliyet"), "p15": k.get("p15"),
                 "p12p": k.get("p12p"), "sans15": k.get("sans15"), "sans12": k.get("sans12"),
                 "ev_tl": k.get("ev_tl"), "ev_tl_devirli": k.get("ev_tl_devirli"),
                 "isaretler": [" ".join(("1", "0", "2")[j] for j in s) for s in (k.get("S") or [])]}
                for k in (A.get("kuponlar") or [])]
    h = A.get("hafta") or {}
    return {
        "hafta": f"{h.get('sezon')} {h.get('ad')}", "hafta_id": h.get("id"), "kapanis": h.get("kapanis"),
        "kalan_saat": A.get("kalan_saat"), "satis_acilis": A.get("satis_acilis"),
        "analiz_zamani": A.get("olusturma"), "kolon_bedeli": A.get("fiyat"),
        "havuz": A.get("havuz"), "devir": A.get("devir"), "devir_kesin": A.get("devir_kesin"),
        "devir_senaryo": A.get("devir_senaryo"), "onceki_hafta": A.get("onceki_hafta"),
        "N_tahmin": A.get("N_tahmin"), "iddaa_kapsam": A.get("iddaa_kapsam"), "kadro": A.get("kadro"),
        "kapi": A.get("kapi"), "kuponlar": kuponlar, "maclar": maclar,
        "not": "P = ajan pazarının olasılığı, q = kalabalığın işaretleme payı. Kazandıran fark P/q'dur. "
               "havuz kademelere göre TL; devir önceki haftadan gelen ek paradır.",
    }


def toto_mac(sira: int) -> dict:
    """Tek maçın derinliği: ajan görüşleri, takım karnesi, eksik oyuncular, gerekçe."""
    A = _analiz()
    if not A:
        return {"hata": "Güncel analiz bulunamadı."}
    try:
        m = next(x for x in A["maclar"] if int(x.get("sira") or 0) == int(sira))
    except StopIteration:
        return {"hata": f"{sira}. maç yok (1–15 arası olmalı)."}
    i = int(sira) - 1
    notlar = dict(m.get("not") or {})
    return {
        "sira": m.get("sira"), "mac": f"{m.get('ev')} - {m.get('dep')}", "tarih": m.get("tarih"),
        "turnuva": m.get("turnuva"), "aile": m.get("aile"), "bilgi": m.get("bilgi"),
        "P_1_0_2": _yuzde3(A["P"][i]), "kalabalik_q": _yuzde3(A["Q"][i]),
        "iddaa": m.get("iddaa"), "ajan_gorusleri": m.get("gorus"), "ajan_paylari": m.get("pay"),
        "pazar_islemleri": m.get("islemler"), "takim_karnesi": m.get("karne"),
        "notlar": notlar, "gerekce": m.get("gerekce"),
    }


def toto_ajan_pazari() -> dict:
    """Ajan cüzdanları: hangi ajanın sesi ne kadar, nasıl değişti."""
    A = _analiz()
    out: dict = {"cuzdan": (A or {}).get("cuzdan"), "model": (A or {}).get("model")}
    try:
        out["cuzdan_gecmis"] = [list(x) for x in toto_db.cuzdan_gecmisi()[-24:]]
    except Exception:
        pass
    out["aciklama"] = ("Kelly bahisçileri pazarı: her ajan servetinin bir kesrini görüşüne göre dağıtır; "
                       "fiyat servet ağırlıklı ortalamadır. KULUP ve MILLI ayrı pazarlardır.")
    return out


def _html_metin(s: str) -> str:
    s = re.sub(r"<br\s*/?>", "\n", s or "")
    s = re.sub(r"</(tr|div|p|table)>", "\n", s)
    s = re.sub(r"</t[hd]>", " | ", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return re.sub(r"[ \t]{2,}", " ", s).strip()


def toto_gecmis_test(bolum: str | None = None) -> dict:
    """204 haftalık ileriye yürüyen geçmiş test: bulgular, kuponlar, kalibrasyon, kombine karşılaştırması."""
    p = KOK / "geri_test_ozet.json"
    if not p.exists():
        return {"hata": "Geçmiş test özeti yok."}
    G = json.loads(p.read_text(encoding="utf-8"))
    bloklar = G.get("bloklar") or []
    if bolum:
        bloklar = [b for b in bloklar if bolum.lower() in (b.get("baslik") or "").lower()] or bloklar
        return {"kpi": G.get("kpi"), "bloklar": [{"baslik": b["baslik"], "metin": _kirp(_html_metin(b["html"]), 4000)}
                                                 for b in bloklar[:2]]}
    return {"alt": G.get("alt"), "kpi": G.get("kpi"), "uretim": G.get("uretim"),
            "bolumler": [b.get("baslik") for b in bloklar],
            "ozet": _kirp(_html_metin((bloklar[0] or {}).get("html", "")), 2500),
            "not": "Bir bölümün tamamı için bolum= parametresiyle tekrar çağır."}


def toto_arsiv(n: int = 5) -> dict:
    """Sonuçlanmış haftalar: ne önerdik, ne oldu, ne öğrendik."""
    try:
        d = toto_db.dersler(int(n))
    except Exception as e:
        return {"hata": f"Arşiv okunamadı: {type(e).__name__}"}
    out = []
    for x in d[: int(n)]:
        out.append({"hafta": x.get("hafta"), "ozet": x.get("ozet"), "surpriz_sayisi": x.get("surpriz_sayisi"),
                    "kalabalik": x.get("kalabalik"),
                    "kuponlar": [{"profil": k.get("profil"), "kolon": k.get("kolon"), "dogru": k.get("dogru"),
                                  "odeme": k.get("odeme"), "maliyet": k.get("maliyet")}
                                 for k in (x.get("kupon") or [])]})
    return {"haftalar": out}


# ── İDDAA (BetAgents) — salt okuma ────────────────────────────────
def _sorgu(sql: str, par: tuple = ()) -> list[tuple]:
    import db
    c = db.connect()
    try:
        return c.execute(sql, par).fetchall()
    finally:
        c.close()


# paper_bets.status: won | lost | void | open  (result sütunu SKORdur, kazanma değil)
KAPANMIS = "status IN ('won','lost')"
# birim getiri: kazanırsa oran−1, kaybederse −1 → 1 birimlik bahisin uzun vade dönüşü
BIRIM = "AVG(CASE WHEN status='won' THEN odds - 1.0 ELSE -1.0 END)"


def iddaa_ozet() -> dict:
    """BetAgents kasası ve kâğıt bahis performansının özeti."""
    try:
        p = _sorgu("SELECT name, current_bankroll, initial_bankroll, total_bets, total_wins, total_staked, "
                   "total_return, status, era_no FROM paper_portfolio ORDER BY portfolio_id DESC")
        b = _sorgu("SELECT status, COUNT(*), AVG(edge), AVG(clv) FROM paper_bets GROUP BY status")
        s = _sorgu(f"SELECT COUNT(*), SUM(CASE WHEN status='won' THEN 1 ELSE 0 END), AVG(odds), {BIRIM}, "
                   f"AVG(clv) FROM paper_bets WHERE {KAPANMIS}")
    except Exception as e:
        return {"hata": f"BetAgents verisi okunamadı: {type(e).__name__}: {e}"}
    kap, kaz, ort, birim, clv = (s[0] if s else (0, 0, None, None, None))
    return {
        "portfoyler": [{"ad": x[0], "kasa": x[1], "baslangic": x[2], "bahis": x[3], "kazanan": x[4],
                        "yatirilan": x[5], "donen": x[6], "durum": x[7], "donem": x[8]} for x in p[:6]],
        "bahis_durumu": [{"durum": x[0], "adet": x[1], "ort_kenar": x[2], "ort_clv": x[3]} for x in b],
        "kapanmis": {"adet": kap, "kazanan": kaz, "isabet": (kaz / kap) if kap else None, "ort_oran": ort,
                     "birim_getiri": birim, "ort_clv": clv},
        "not": "Kâğıt bahis; Toto'dan bağımsız ürün. 'birim_getiri' 1 birimlik bahisin ortalama dönüşüdür: "
               "0'ın üstü kâr, altı zarar. İptal (void) bahisler hesaba katılmaz.",
    }


def iddaa_bahisler(durum: str = "kapanmis", n: int = 20) -> dict:
    """Son kâğıt bahisler: seçim, oran, kenar, CLV, sonuç."""
    n = max(1, min(int(n), 50))
    alan = ("SELECT kickoff_utc, league, home_team, away_team, market, pick, odds, model_prob, edge, "
            "signal_name, status, result, clv FROM paper_bets WHERE ")
    try:
        if durum in ("won", "lost", "open", "void"):
            r = _sorgu(alan + "status = ? ORDER BY kickoff_utc DESC", (durum,))
        else:
            durum = "kapanmis"
            r = _sorgu(alan + KAPANMIS + " ORDER BY kickoff_utc DESC")
    except Exception as e:
        return {"hata": f"Okunamadı: {type(e).__name__}"}
    return {"durum": durum, "bahisler": [
        {"tarih": x[0], "lig": x[1], "mac": f"{x[2]} - {x[3]}", "pazar": x[4], "secim": x[5], "oran": x[6],
         "model_olasilik": x[7], "kenar": x[8], "ajan": x[9], "durum": x[10], "skor": x[11], "clv": x[12]}
        for x in r[:n]]}


def iddaa_ajan_performansi(n: int = 15) -> dict:
    """Hangi BetAgents ajanı ne kadar bahis yaptı, isabeti ve birim getirisi ne."""
    try:
        r = _sorgu(f"SELECT signal_name, COUNT(*), SUM(CASE WHEN status='won' THEN 1 ELSE 0 END), AVG(odds), "
                   f"AVG(edge), AVG(clv), {BIRIM} FROM paper_bets WHERE {KAPANMIS} GROUP BY signal_name "
                   f"ORDER BY COUNT(*) DESC")
    except Exception as e:
        return {"hata": f"Okunamadı: {type(e).__name__}"}
    out = []
    for x in r[: max(1, min(int(n), 40))]:
        adet = x[1] or 0
        out.append({"ajan": x[0], "bahis": adet, "kazanan": x[2], "isabet": (x[2] / adet) if adet else None,
                    "ort_oran": x[3], "ort_kenar": x[4], "ort_clv": x[5], "birim_getiri": x[6]})
    return {"ajanlar": out,
            "not": "İsabet tek başına yanıltır: yüksek oranda düşük isabet iyi olabilir. Doğru ölçü birim_getiri "
                   "(0 üstü kâr) ve CLV'dir. Az bahisli ajanda fark gürültüdür."}


def iddaa_maclar(n: int = 20, lig: str | None = None) -> dict:
    """Yaklaşan maçlar ve iddaa fiyatları (BetAgents'ın maç tablosu)."""
    n = max(1, min(int(n), 50))
    try:
        if lig:
            r = _sorgu("SELECT kickoff_utc, league_code, home_team, away_team, closing_1, closing_X, closing_2, "
                       "status, home_score, away_score FROM matches_v2 WHERE league_code = ? "
                       "ORDER BY kickoff_utc DESC", (lig,))
        else:
            r = _sorgu("SELECT kickoff_utc, league_code, home_team, away_team, closing_1, closing_X, closing_2, "
                       "status, home_score, away_score FROM matches_v2 ORDER BY kickoff_utc DESC")
    except Exception as e:
        return {"hata": f"Okunamadı: {type(e).__name__}"}
    return {"maclar": [{"tarih": x[0], "lig": x[1], "mac": f"{x[2]} - {x[3]}", "oran_1x2": [x[4], x[5], x[6]],
                        "durum": x[7], "skor": (f"{x[8]}-{x[9]}" if x[8] is not None else None)} for x in r[:n]]}


# ── KOD ───────────────────────────────────────────────────────────
def _dosyalar() -> list[Path]:
    out = []
    for kok in KOD_DIZIN.values():
        if not kok.exists():
            continue
        for p in kok.rglob("*"):
            if p.is_file() and p.suffix.lower() in KOD_UZANTI and not YASAK.search(p.as_posix()):
                out.append(p)
    return out


def _gorece(p: Path) -> str:
    try:
        return p.relative_to(YAZILIM).as_posix()
    except ValueError:
        return p.name


def kod_ara(desen: str, n: int = 25) -> dict:
    """Kaynak kodda ve belgelerde ara (09_TOTO ve 08_AI_TRADER · .py/.md)."""
    try:
        rx = re.compile(desen, re.I)
    except re.error as e:
        return {"hata": f"Geçersiz desen: {e}"}
    bulgu = []
    for p in _dosyalar():
        try:
            for no, satir in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if rx.search(satir):
                    bulgu.append({"dosya": _gorece(p), "satir": no, "metin": _maskele(satir.strip()[:200])})
                    if len(bulgu) >= max(1, min(int(n), 60)):
                        return {"desen": desen, "bulgu": bulgu, "not": "Sonuç sınırına ulaşıldı."}
        except Exception:
            continue
    return {"desen": desen, "bulgu": bulgu, "adet": len(bulgu)}


def kod_oku(dosya: str, bas: int = 1, satir_sayisi: int = 120) -> dict:
    """Bir kaynak dosyanın bölümünü oku (yalnız izinli dizinler)."""
    hedef = None
    for p in _dosyalar():
        if _gorece(p) == dosya or p.name == dosya:
            hedef = p
            break
    if hedef is None:
        return {"hata": f"Dosya bulunamadı ya da erişime kapalı: {dosya}",
                "ipucu": "kod_ara ile tam yolu bulabilirsin (ör. 09_TOTO/deger.py)."}
    try:
        satirlar = hedef.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception as e:
        return {"hata": f"Okunamadı: {type(e).__name__}"}
    b = max(1, int(bas))
    k = max(1, min(int(satir_sayisi), 300))
    parca = satirlar[b - 1: b - 1 + k]
    return {"dosya": _gorece(hedef), "toplam_satir": len(satirlar), "bas": b,
            "icerik": _maskele(_kirp("\n".join(f"{b + i:5d}  {s}" for i, s in enumerate(parca)), 12000))}


# ── YAZAN ARAÇLAR (yalnız vibe_* tablolarına) ─────────────────────
def geri_bildirim(tur: str, baslik: str, metin: str, oturum_id: str | None = None) -> dict:
    """Kullanıcının geri bildirimini geliştirme kuyruğuna yaz."""
    gid = vibe_db.geri_bildirim_yaz(oturum_id, tur, baslik, metin)
    return {"yazildi": True, "gb_id": gid, "tur": tur, "baslik": baslik,
            "not": "Geliştirme kuyruğuna düştü; sonraki geliştirme oturumunda okunacak."}


def analiz_iste(oturum_id: str | None = None) -> dict:
    """Toto analizinin tazelenmesini iste — Toto worker bir sonraki turunda çalıştırır."""
    iid = vibe_db.istek_yaz(oturum_id, "analiz")
    return {"yazildi": True, "istek_id": iid,
            "not": "İstek kuyrukta. Worker saatlik turunda çalıştırır (birkaç dakika). "
                   "Web sürecinde ağır iş yapılmaz; sonucu 'bu hafta' aracıyla kontrol edebilirsin."}


def istek_durumu() -> dict:
    """Bırakılan isteklerin durumu."""
    return {"istekler": vibe_db.istek_durum(8)}


# ── geliştirme paketi (kullanıcıdan geliştiriciye elden teslim) ───
def _durum_satiri() -> list[str]:
    """Paketin başına konan bağlam — geliştirici oturumunda tekrar sormaya gerek kalmasın."""
    A = _analiz()
    if not A:
        return ["- Güncel Toto analizi bulunamadı."]
    h, kapi, kadro = A.get("hafta") or {}, A.get("kapi") or {}, A.get("kadro") or {}
    out = [
        f"- Hafta: {h.get('sezon')} {h.get('ad')} · kapanış {h.get('kapanis')}",
        f"- Analiz zamanı: {A.get('olusturma')} · iddaa kapsamı {A.get('iddaa_kapsam')}/15",
        f"- Kadro verisi: {kadro.get('durum')} (kapsam {kadro.get('kapsam')}, pencere {kadro.get('pencere')})",
        f"- Kapı: {kapi.get('karar')} — {kapi.get('ozet')}",
    ]
    for v in (kapi.get("kosul") or {}).values():
        if isinstance(v, dict) and v.get("aciklama"):
            out.append(f"  - {'✓' if v.get('saglandi') else '—'} {v['aciklama']}")
    return out


def gelistirme_paketi(durum: str = "acik") -> dict:
    """Açık geri bildirimleri tek bir markdown paketine topla (geliştiriciye verilmek üzere)."""
    gb = vibe_db.geri_bildirimler(None if durum == "hepsi" else durum, 80)
    sira = {"hata": 0, "istek": 1, "fikir": 2, "soru": 3}
    gb.sort(key=lambda x: (sira.get(x.get("tur"), 9), x.get("ts") or ""))
    bas = vibe_db.simdi()[:16].replace("T", " ")
    satir = [f"# Vibe Betting · geliştirme paketi ({bas} UTC)", "",
             "Bu paket panelden üretildi. Maddeler kullanıcının kendi geri bildirimleridir.", "",
             "## Sistem durumu", *_durum_satiri(), ""]
    if not gb:
        satir += ["## Maddeler", "", "_Açık geri bildirim yok._"]
    else:
        satir += [f"## Maddeler ({len(gb)})", ""]
        for i, x in enumerate(gb, 1):
            satir += [f"### {i}. [{(x.get('tur') or '').upper()}] {x.get('baslik')}",
                      f"_{(x.get('ts') or '')[:16].replace('T', ' ')} UTC · {x.get('gb_id')}_", "",
                      (x.get("metin") or "").strip(), ""]
    ist = vibe_db.istek_durum(5)
    if ist:
        satir += ["## Son iş istekleri", ""] + [
            f"- {y.get('tur')} · {y.get('durum')} · {(y.get('ts') or '')[:16].replace('T', ' ')}"
            + (f" → {y.get('sonuc')}" if y.get("sonuc") else "") for y in ist] + [""]
    return {"adet": len(gb), "paket": "\n".join(satir),
            "not": "Paneldeki 'Geliştirme paketi' bölümünden indirilebilir ve geliştiriciye verilebilir."}
