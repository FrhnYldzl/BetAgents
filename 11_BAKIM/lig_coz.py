"""
LİG ÇÖZÜMÜ — iddaa maçlarının ligini güvenilir kaynaktan bul (ÖLÇÜM, yazma yok)
================================================================================
`matches_v2`'nin %96'sında lig kodu 'ALL'. Bu bir özensizlik DEĞİL: eski kod
lig kodunu takım adından tahmin ediyordu ve yanlış yazıyordu (kadın/genç
takımlar erkek A-lig koduyla etiketleniyordu). Kök neden düzeltilip yanlış
kodlar 'ALL' yapıldı — yani "bilmiyoruz ve tahmin etmiyoruz" demek.

Doğru çözüm daha iyi tahmin değil, GÜVENİLİR KAYNAK: API-Football
`fixtures?date=` bir istekte o günün bütün maçlarını ligiyle veriyor. Eşleştirme
CANLI'da ölçülmüş yöntemle (takım adı + başlangıç saati) yapılır.

Bu dosya YALNIZ ÖLÇER: kaç maçın ligi çözülebiliyor, hangi güvenle. Hiçbir
tabloya yazmaz. Yazma ayrı bir karardır.

    python 11_BAKIM/lig_coz.py                 # son 3 günü ölç
    python 11_BAKIM/lig_coz.py 2026-09-20 3    # belirli tarihten 3 gün
"""
from __future__ import annotations

import json
import os
import re
import sys
import unicodedata
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path

KOK = Path(__file__).resolve().parent
_V = KOK.parent / "02_VERI"
if str(_V) not in sys.path:
    sys.path.insert(0, str(_V))

TR = timezone(timedelta(hours=3))
AF_HOST = "v3.football.api-sports.io"
ESIK = 1.25
SAAT_TOLERANS = 2.5

# API-Football lig adı → bizim kanonik kodumuz (yalnız ana ligler; gerisi ad olarak kalır)
KANONIK = {"Premier League|England": "E0", "La Liga|Spain": "SP1", "Serie A|Italy": "I1",
           "Bundesliga|Germany": "D1", "Ligue 1|France": "F1", "Süper Lig|Turkey": "T1",
           "Major League Soccer|USA": "USA1", "Serie A|Brazil": "BRA1"}

_SIL = re.compile(r"\b(fc|fk|sc|sk|cf|ac|as|if|bk|sv|ss|cd|club|kulubu|kulübü|spor|sport|sportif|"
                  r"futbol|calcio)\b")


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    for a, b in (("ı", "i"), ("ğ", "g"), ("ş", "s"), ("ç", "c"), ("ö", "o"), ("ü", "u")):
        s = s.replace(a, b)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return " ".join(_SIL.sub(" ", s).split())


def benzer(a: str, b: str) -> float:
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return 0.0
    A, B = set(na.split()), set(nb.split())
    ortak = len(A & B)
    simge = ortak / min(len(A), len(B)) * (0.75 + 0.25 * ortak / max(len(A), len(B))) if ortak else 0.0
    on = ortak == 0 and any(x.startswith(y) or y.startswith(x)
                            for x in A for y in B if min(len(x), len(y)) >= 4)
    kar = SequenceMatcher(None, na, nb).ratio()
    return max(simge, kar, 0.80 if on and kar >= 0.45 else 0.0)


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


def af_gun(gun: str) -> list[dict]:
    """Bir günün bütün fikstürleri — TEK istek."""
    k, h = _anahtar()
    if not k:
        return []
    onb = KOK / f".af_{gun}.json"
    if onb.exists():
        try:
            d = json.loads(onb.read_text(encoding="utf-8"))
        except Exception:
            d = None
    else:
        d = None
    if d is None:
        r = urllib.request.Request(f"https://{h}/fixtures?date={gun}",
                                   headers={"x-rapidapi-key": k, "x-rapidapi-host": h})
        with urllib.request.urlopen(r, timeout=40) as x:
            d = json.loads(x.read())
        try:
            onb.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass
    out = []
    for f in d.get("response") or []:
        fx, t, lg = f.get("fixture") or {}, f.get("teams") or {}, f.get("league") or {}
        try:
            bas = datetime.fromisoformat(str(fx.get("date")).replace("Z", "+00:00")).astimezone(TR)
        except Exception:
            continue
        out.append({"af_id": fx.get("id"), "ev": ((t.get("home") or {}).get("name") or "").strip(),
                    "dep": ((t.get("away") or {}).get("name") or "").strip(), "baslangic": bas,
                    "lig": (lg.get("name") or "").strip(), "ulke": (lg.get("country") or "").strip()})
    return out


def kanonik(lig: str, ulke: str) -> str:
    return KANONIK.get(f"{lig}|{ulke}", f"{ulke}: {lig}"[:40] if lig else "ALL")


def coz(gunler: list[str]) -> dict:
    """Verilen günlerdeki 'ALL' kodlu iddaa maçlarını API-Football'a bağla. YAZMAZ."""
    import db
    c = db.connect()
    try:
        r = c.execute(
            "SELECT match_id, kickoff_utc, home_team, away_team, league_code FROM matches_v2 "
            "WHERE league_code = 'ALL'").fetchall()
    finally:
        c.close()
    hedef = []
    for mid, ko, ev, dep, lc in r:
        try:
            t = datetime.fromisoformat(str(ko).replace("Z", "+00:00"))
            t = (t if t.tzinfo else t.replace(tzinfo=timezone.utc)).astimezone(TR)
        except Exception:
            continue
        if t.strftime("%Y-%m-%d") in gunler:
            hedef.append({"match_id": mid, "ts": t, "ev": ev or "", "dep": dep or ""})
    fik = []
    for g in gunler:
        fik += af_gun(g)
    cozulen, cozulmeyen = [], []
    kullanilan = set()
    for m in hedef:
        en, skor = None, 0.0
        for i, f in enumerate(fik):
            if i in kullanilan:
                continue
            if abs((m["ts"] - f["baslangic"]).total_seconds()) / 3600 > SAAT_TOLERANS:
                continue
            s = benzer(m["ev"], f["ev"]) + benzer(m["dep"], f["dep"])
            if s > skor:
                en, skor = (i, f), s
        if en and skor >= ESIK:
            kullanilan.add(en[0])
            cozulen.append({**m, "af_id": en[1]["af_id"], "lig": en[1]["lig"],
                            "ulke": en[1]["ulke"], "kod": kanonik(en[1]["lig"], en[1]["ulke"]),
                            "skor": round(skor, 2)})
        else:
            cozulmeyen.append({**m, "skor": round(skor, 2)})
    return {"hedef": len(hedef), "fikstur": len(fik), "cozulen": cozulen, "cozulmeyen": cozulmeyen}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    bas = sys.argv[1] if len(sys.argv) > 1 else (datetime.now(TR) - timedelta(days=3)).strftime("%Y-%m-%d")
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    g0 = datetime.strptime(bas, "%Y-%m-%d")
    gunler = [(g0 + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(n)]
    print(f"günler: {', '.join(gunler)}  ({n} API isteği)\n")
    R = coz(gunler)
    t = R["hedef"] or 1
    print(f"'ALL' kodlu hedef maç: {R['hedef']} · API fikstürü: {R['fikstur']}")
    print(f"ÇÖZÜLEN: {len(R['cozulen'])} (%{100 * len(R['cozulen']) / t:.0f}) · "
          f"çözülemeyen: {len(R['cozulmeyen'])}\n")
    say = Counter(x["kod"] for x in R["cozulen"])
    print("çözülen ligler (ilk 14):")
    for k, v in say.most_common(14):
        print(f"   {k:34s} {v}")
    print("\nörnek eşleşmeler:")
    for x in R["cozulen"][:6]:
        print(f"   {x['ev'][:22]:22s}-{x['dep'][:22]:22s} → {x['kod'][:30]:30s} (benzerlik {x['skor']})")
    if R["cozulmeyen"]:
        print("\nçözülemeyenlerden örnek:")
        for x in R["cozulmeyen"][:5]:
            print(f"   {x['ev'][:22]:22s}-{x['dep'][:22]:22s} (en iyi benzerlik {x['skor']})")
