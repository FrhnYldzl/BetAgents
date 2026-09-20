"""
CANLI · DATA — iki kaynak, tek tablo
=====================================
FİYAT   iddaa canlı akışı (sportsbookv2) — oranları verir, skoru/dakikayı VERMEZ.
DURUM   API-Football `fixtures?live=all` — TEK istekte bütün canlı maçların
        skoru, dakikası ve kırmızı kartı. (Kota: günde 100 istek; bu yüzden
        durum seyrek, fiyat sık çekilir.)

İkisi takım adı + başlangıç saatine göre eşleşir. Eşleşmeyen maç kaydedilir
ama durumu boş kalır — yanlış eşleştirmektense eksik bırakmak yeğdir.

Bu modül SALT OKUMA kaynaklardan besleniyor ve yalnız `cl_*` tablolarına yazar.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import unicodedata
from difflib import SequenceMatcher
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

KOK = Path(__file__).resolve().parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

import canli_db  # noqa: E402

TR = timezone(timedelta(hours=3))
IDDAA_CANLI = "https://sportsbookv2.iddaa.com/sportsbook/events?st=1&type=1"
IDDAA_H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                         "Chrome/120.0.0.0 Safari/537.36",
           "Accept": "application/json, text/plain, */*", "Accept-Language": "tr-TR,tr;q=0.9",
           "Referer": "https://www.iddaa.com/", "Origin": "https://www.iddaa.com"}
AF_HOST = "v3.football.api-sports.io"
ESIK = 1.25          # iki takım adının toplam benzerlik eşiği (2 üzerinden)
SAAT_TOLERANS = 3.5  # başlangıç saati farkı (saat) — canlı maçta dakika kayması olur


# ── ad normalizasyonu ve benzerlik (yerel; başka pakete bağlanmaz) ─
# DİKKAT: "united" ve "city" SİLİNMEZ — İngiliz kulüplerinde ayırt edici olan
# tam da onlardır (Manchester United ↔ Manchester City aksi hâlde birebir eşleşir).
_SIL = re.compile(r"\b(fc|fk|sc|sk|cf|ac|as|if|bk|sv|ss|cd|club|kulubu|kulübü|spor|sport|sportif|"
                  r"futbol|calcio)\b")


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.replace("ı", "i").replace("ğ", "g").replace("ş", "s").replace("ç", "c").replace("ö", "o").replace("ü", "u")
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = _SIL.sub(" ", s)
    return " ".join(s.split())


def benzer(a: str, b: str) -> float:
    """0–1. İki ölçünün en iyisi: simge kapsama (Halmstad ↔ Halmstads BK) ve
    karakter benzerliği (AIK Solna ↔ AIK Stockholm, E. Cottbus ↔ Energie Cottbus)."""
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return 0.0
    A, B = set(na.split()), set(nb.split())
    ortak = len(A & B)
    simge = ortak / min(len(A), len(B)) * (0.75 + 0.25 * ortak / max(len(A), len(B))) if ortak else 0.0
    # Gövde benzerliği YALNIZ hiç ortak simge yokken: "Halmstads" ↔ "Halmstad".
    # Ortak simge varsa (Real Madrid ↔ Real Sociedad) bonus verilmez — yanlış eşleşme kaynağı.
    on = ortak == 0 and any(x.startswith(y) or y.startswith(x)
                            for x in A for y in B if min(len(x), len(y)) >= 4)
    karakter = SequenceMatcher(None, na, nb).ratio()
    return max(simge, karakter, 0.80 if on and karakter >= 0.45 else 0.0)


# ── iddaa canlı fiyat ─────────────────────────────────────────────
def _ms_oran(ev: dict):
    """Maç sonucu 1/0/2 — canlı akışta pazar tipi t=4 (ön maçta t=1)."""
    for m in ev.get("m") or []:
        if m.get("t") not in (1, 4):
            continue
        d = {}
        for o in m.get("o") or []:
            n = str(o.get("n") or "").strip().upper()
            if n in ("1", "0", "2", "X"):
                d["0" if n == "X" else n] = o.get("odd")
        if all(d.get(k) for k in ("1", "0", "2")):
            try:
                v = (float(d["1"]), float(d["0"]), float(d["2"]))
            except (TypeError, ValueError):
                continue
            if min(v) > 1.0:
                return v
    return None


def iddaa_onmac() -> list[dict]:
    """Henüz başlamamış olaylar ve MAÇ ÖNCESİ 1/0/2 fiyatı — modelin girdisi.
    Maç canlıya geçtiğinde bu fiyat artık akışta yok; şimdi kaydedilmezse kaybolur."""
    r = urllib.request.Request(IDDAA_CANLI.replace("type=1", "type=0"), headers=IDDAA_H)
    with urllib.request.urlopen(r, timeout=30) as x:
        d = json.loads(x.read())
    ol = (d.get("data") or {}).get("events") or d.get("events") or []
    out = []
    for e in ol:
        if e.get("s"):
            continue
        oran = _ms_oran(e)
        if not oran:
            continue
        try:
            bas = datetime.fromtimestamp(int(e.get("d") or 0), TR).isoformat(timespec="seconds")
        except Exception:
            bas = None
        out.append({"mac_id": f"i{e.get('i')}", "iddaa_id": e.get("i"), "ev": (e.get("hn") or "").strip(),
                    "dep": (e.get("an") or "").strip(), "baslangic": bas, "oran_once": oran})
    return out


def iddaa_canli() -> list[dict]:
    """Oynanmakta olan iddaa olayları (s=1) ve 1/0/2 fiyatları."""
    r = urllib.request.Request(IDDAA_CANLI, headers=IDDAA_H)
    with urllib.request.urlopen(r, timeout=30) as x:
        d = json.loads(x.read())
    ol = (d.get("data") or {}).get("events") or d.get("events") or []
    out = []
    for e in ol:
        if not e.get("s"):                      # s=1 → sahada
            continue
        oran = _ms_oran(e)
        try:
            bas = datetime.fromtimestamp(int(e.get("d") or 0), TR).isoformat(timespec="seconds")
        except Exception:
            bas = None
        out.append({"iddaa_id": e.get("i"), "ev": (e.get("hn") or "").strip(),
                    "dep": (e.get("an") or "").strip(), "baslangic": bas, "oran": oran})
    return out


# ── API-Football canlı durum ──────────────────────────────────────
def _anahtar() -> tuple[str, str]:
    k = os.environ.get("API_FOOTBALL_KEY", "").strip()
    h = os.environ.get("API_FOOTBALL_HOST", "").strip() or AF_HOST
    if not k:
        try:
            for satir in open(KOK.parent / ".env", encoding="utf-8"):
                if satir.strip().startswith("API_FOOTBALL_KEY="):
                    k = satir.split("=", 1)[1].strip().strip('"').strip("'")
        except Exception:
            pass
    return k, h


def af_canli() -> list[dict] | None:
    """Tek istekte bütün canlı maçlar: skor, dakika, kırmızı kart."""
    k, h = _anahtar()
    if not k:
        return None
    r = urllib.request.Request(f"https://{h}/fixtures?live=all",
                               headers={"x-rapidapi-key": k, "x-rapidapi-host": h})
    with urllib.request.urlopen(r, timeout=30) as x:
        d = json.loads(x.read())
    if d.get("errors"):
        return None
    out = []
    for f in d.get("response") or []:
        fx, t, g = f.get("fixture") or {}, f.get("teams") or {}, f.get("goals") or {}
        st = fx.get("status") or {}
        kir = {"ev": 0, "dep": 0}
        for ev in f.get("events") or []:
            if str(ev.get("detail") or "").lower().startswith("red"):
                taraf = "ev" if (ev.get("team") or {}).get("name") == (t.get("home") or {}).get("name") else "dep"
                kir[taraf] += 1
        try:
            bas = datetime.fromisoformat(str(fx.get("date")).replace("Z", "+00:00")).astimezone(TR)
            bas = bas.isoformat(timespec="seconds")
        except Exception:
            bas = None
        out.append({"af_id": fx.get("id"), "ev": ((t.get("home") or {}).get("name") or "").strip(),
                    "dep": ((t.get("away") or {}).get("name") or "").strip(), "baslangic": bas,
                    "dakika": st.get("elapsed"), "safha": st.get("short"),
                    "ev_skor": g.get("home"), "dep_skor": g.get("away"),
                    "kirmizi_ev": kir["ev"], "kirmizi_dep": kir["dep"],
                    "lig": ((f.get("league") or {}).get("name") or "")})
    return out


# ── eşleştirme ────────────────────────────────────────────────────
def _saat_farki(a: str | None, b: str | None) -> float:
    try:
        return abs((datetime.fromisoformat(a) - datetime.fromisoformat(b)).total_seconds()) / 3600.0
    except Exception:
        return 99.0


def esle(iddaa: list[dict], af: list[dict] | None) -> list[dict]:
    """iddaa olaylarını API-Football fikstürlerine bağla. Bulunamayanın durumu boş kalır."""
    out = []
    kullanilan = set()
    for e in iddaa:
        en, skor = None, 0.0
        for i, f in enumerate(af or []):
            if i in kullanilan:
                continue
            if _saat_farki(e.get("baslangic"), f.get("baslangic")) > SAAT_TOLERANS:
                continue
            s = benzer(e["ev"], f["ev"]) + benzer(e["dep"], f["dep"])
            if s > skor:
                en, skor = (i, f), s
        m = dict(e)
        if en is not None and skor >= ESIK:
            kullanilan.add(en[0])
            m.update({k: en[1].get(k) for k in ("af_id", "dakika", "safha", "ev_skor", "dep_skor",
                                                "kirmizi_ev", "kirmizi_dep", "lig")})
            m["eslesme"] = round(skor, 2)
        else:
            m["eslesme"] = None
        m["mac_id"] = f"i{e['iddaa_id']}"
        out.append(m)
    return out


def topla() -> list[dict]:
    """Bir turluk toplama: fiyat + durum + eşleştirme. Yazma yapmaz."""
    idd = iddaa_canli()
    try:
        af = af_canli()
    except Exception:
        af = None
    return esle(idd, af)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    t0 = time.time()
    M = topla()
    es = sum(1 for m in M if m.get("eslesme"))
    fiyatli = sum(1 for m in M if m.get("oran"))
    print(f"canlı maç: {len(M)} · durumu eşleşen: {es} · fiyatı olan: {fiyatli} · {time.time() - t0:.1f} sn\n")
    for m in M[:14]:
        o = m.get("oran")
        of = f"{o[0]:.2f}/{o[1]:.2f}/{o[2]:.2f}" if o else "fiyat yok"
        dk = f"{m.get('dakika')}'" if m.get("dakika") is not None else "—"
        sk = (f"{m.get('ev_skor')}-{m.get('dep_skor')}" if m.get("ev_skor") is not None else "—")
        print(f"  {m['ev'][:22]:22s} {sk:>5} {m['dep'][:22]:22s} {dk:>5}  {of:>18}  "
              f"{(m.get('lig') or '')[:22]}")
