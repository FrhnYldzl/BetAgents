"""
🧠 GEREKÇE DEFTERİ — her ajan neden ve nasıl seçti, sonra ne oldu?
==================================================================
İki katman:

1) SEÇİM NOTU (bahis kurulurken): "Bu maçı neden seçtim?"
   Ajanın türüne göre gerekçe metni üretilir — sinyal adı, model olasılığı,
   piyasa olasılığı, edge, korelasyon katsayısı, adil oran...

2) POST-MORTEM (sonuç geldiğinde): "Neden oldu / neden olmadı?"
   Kaybettiyse NE KADAR YAKINDI: "1 gol eksik", "90+3'te yendi",
   "tam tersi oldu". Tuttuysa NASIL tuttu: "rahat", "son dakika",
   "kıl payı". Bu, kaybın kalitesini ölçer — 3-0 kaybetmekle
   2-1 kaybetmek aynı şey değildir.

Neden önemli: kupon sonucu ikili (kazandı/kaybetti) ama BİLGİ süreklidir.
"Kaç gol eksik kaldı" verisi, filtreyi ayarlamak için sonuçtan daha
öğreticidir.
"""
from __future__ import annotations

import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import db

SIGNAL_TR = {
    "GUCLU_FAV": "güçlü favori", "FAV": "favori", "KG_YOK": "karşılıklı gol yok",
    "KG_VAR": "karşılıklı gol", "UST_25": "üst 2.5", "ALT_25": "alt 2.5",
    "KORELASYON_DEGERI": "maç içi korelasyon değeri",
    "MIDBAND": "orta oran bandı", "FADE": "yazar-tersleme",
    "POP": "yazar konsensüsü", "COUNCIL": "kurul oylaması",
    "JOKER": "rastgele kontrol",
}


def build_reason(pick: dict, prof: dict | None = None) -> str:
    """Bahis kurulurken 'neden bu maç' notu."""
    try:
        mkt = pick.get("market") or "?"
        sel = pick.get("pick") or "?"
        o = float(pick.get("odds") or 0)
        mp = pick.get("model_prob")
        ip = pick.get("implied_prob")
        sn = pick.get("signal_name") or ""
        m = pick.get("_match") or {}
        parts = []
        # ana gerekçe
        if sn == "KORELASYON_DEGERI":
            ss = pick.get("signal_score")
            parts.append(
                f"KOMBO: '{sel}' seçimi, bileşenlerinin çarpımına göre "
                f"korelasyon-düzeltilmiş adil oranı "
                f"{(1/mp):.2f} iken iddaa {o:.2f} veriyor"
                + (f" (+%{ss*100:.1f} değer)" if ss else "")
                + (f" · bileşen gücü: {pick['_strength']}"
                   if pick.get("_strength") else ""))
        elif sn:
            parts.append(f"sinyal: {SIGNAL_TR.get(sn, sn)}")
        if mp and ip:
            parts.append(f"model %{mp*100:.0f} · piyasa %{ip*100:.0f} "
                         f"(fark {(mp-ip)*100:+.1f}p)")
        elif mp:
            parts.append(f"model olasılığı %{mp*100:.0f}")
        parts.append(f"oran {o:.2f}")
        if m.get("league_code"):
            parts.append(f"lig {m['league_code']}")
        try:
            from datetime import datetime as _dt
            lead = (_dt.fromisoformat(str(m.get("kickoff_utc"))[:19])
                    - _dt.utcnow()).total_seconds() / 3600
            parts.append(f"maça {lead:.0f} saat")
        except Exception:
            pass
        return " · ".join(parts)[:480]
    except Exception:
        return ""


# ──────────────────────────────────────────────────────────────
# POST-MORTEM: sonuç geldiğinde "ne kadar yakındı?"
# ──────────────────────────────────────────────────────────────

def postmortem(market: str, pick: str, hs: int, aws: int, won: bool) -> str:
    """Sonuçtan sonra: neden oldu / neden olmadı, ne kadar yakındı."""
    try:
        tot = hs + aws
        sc = f"{hs}-{aws}"
        m = (market or "").upper()
        p = (pick or "").strip()

        def ou_note(line: float, side: str) -> str:
            need = line
            if side == "UST":
                d = need - tot + 0.5
                return (f"{sc}: {tot} gol oldu, üst için {int(need+0.5)} gerekiyordu — "
                        f"{int(d)} gol eksik" if not won else
                        f"{sc}: {tot} gol — üst rahat geldi"
                        if tot >= need + 1.5 else f"{sc}: {tot} gol — kıl payı üst")
            d = tot - need + 0.5
            return (f"{sc}: {tot} gol oldu, alt için en fazla {int(need-0.5)} olmalıydı — "
                    f"{int(d)} gol fazla" if not won else
                    f"{sc}: {tot} gol — alt rahat tuttu"
                    if tot <= need - 1.5 else f"{sc}: {tot} gol — kıl payı alt")

        if m in ("UST_25", "OU2.5") or p.upper() in ("UST", "ÜST"):
            return ou_note(2.5, "UST")
        if m == "ALT_25" or p.upper() == "ALT":
            return ou_note(2.5, "ALT")
        if m == "KG_YOK":
            return (f"{sc}: iki taraf da golü buldu — tutmadı"
                    if not won else
                    f"{sc}: bir taraf gol atamadı — tuttu")
        if m == "KG_VAR":
            return (f"{sc}: bir taraf gol atamadı — tutmadı" if not won
                    else f"{sc}: iki taraf da attı — tuttu")
        if m == "1X2":
            res = "1" if hs > aws else ("2" if aws > hs else "0")
            fark = abs(hs - aws)
            if won:
                return (f"{sc}: {fark} farkla kazandı" if fark else f"{sc}: beraberlik geldi")
            if p == "0":
                return f"{sc}: beraberlik {fark} gol farkla kaçtı"
            if res == "0":
                return f"{sc}: berabere kaldı — 1 gol yetiyordu"
            return f"{sc}: karşı taraf {fark} farkla kazandı"
        # kombo pazarlar: "0 ve Üst" gibi
        if " ve " in p:
            a, b = [x.strip() for x in p.split(" ve ", 1)]
            res = "1" if hs > aws else ("2" if aws > hs else "0")
            ok_a = (a == res)
            bu = b.upper()
            if bu in ("ÜST", "UST"):
                ok_b = tot > 2.5
            elif bu == "ALT":
                ok_b = tot < 2.5
            elif bu == "VAR":
                ok_b = hs > 0 and aws > 0
            elif bu == "YOK":
                ok_b = not (hs > 0 and aws > 0)
            else:
                ok_b = won
            if won:
                return f"{sc}: iki şart da tuttu ({a} ✓, {b} ✓)"
            if ok_a and not ok_b:
                return f"{sc}: '{a}' tuttu ama '{b}' tutmadı — yarı yolda kaldı"
            if ok_b and not ok_a:
                return f"{sc}: '{b}' tuttu ama '{a}' tutmadı — yarı yolda kaldı"
            return f"{sc}: iki şart da tutmadı"
        return f"{sc}: {'tuttu' if won else 'tutmadı'}"
    except Exception:
        return ""


def ensure_columns(conn) -> None:
    for col in ("reason", "postmortem"):
        try:
            conn.execute(f"ALTER TABLE paper_bets ADD COLUMN {col} TEXT")
            conn.commit()
        except Exception:
            conn.rollback()


def backfill_postmortems(limit: int = 500) -> int:
    """Sonuçlanmış ama post-mortem'i olmayan bahisleri doldur."""
    conn = db.connect()
    n = 0
    try:
        ensure_columns(conn)
        rows = conn.execute(
            "SELECT bet_id, market, pick, home_score, away_score, status "
            "FROM paper_bets WHERE status IN ('won','lost') "
            "AND (postmortem IS NULL OR postmortem='') "
            "AND home_score IS NOT NULL LIMIT ?", (limit,)).fetchall()
        for r in rows:
            note = postmortem(r[1], r[2], int(r[3] or 0), int(r[4] or 0),
                              r[5] == "won")
            if not note:
                continue
            conn.execute("UPDATE paper_bets SET postmortem=? WHERE bet_id=?",
                         (note, r[0]))
            n += 1
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"[GEREKÇE] backfill hatası: {e}")
    finally:
        conn.close()
    return n


def backfill_reasons(limit: int = 3000) -> int:
    """Mevcut bahislere kayıtlı alanlardan gerekçe notu üret.
    (market, pick, odds, model_prob, implied_prob, signal_name zaten
    paper_bets'te duruyor — sonradan da yeniden inşa edilebilir.)"""
    conn = db.connect()
    n = 0
    try:
        ensure_columns(conn)
        rows = conn.execute(
            "SELECT bet_id, market, pick, odds, model_prob, implied_prob, "
            "signal_name, league, kickoff_utc FROM paper_bets "
            "WHERE reason IS NULL OR reason='' LIMIT ?", (limit,)).fetchall()
        for r in rows:
            pick = {
                "market": r[1], "pick": r[2], "odds": r[3],
                "model_prob": r[4], "implied_prob": r[5],
                "signal_name": r[6],
                "_match": {"league_code": r[7], "kickoff_utc": r[8]},
            }
            note = build_reason(pick)
            if not note:
                continue
            conn.execute("UPDATE paper_bets SET reason=? WHERE bet_id=?",
                         (note, r[0]))
            n += 1
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"[GEREKÇE] reason backfill hatası: {e}")
    finally:
        conn.close()
    return n


if __name__ == "__main__":
    print(f"gerekçe yazılan: {backfill_reasons()}")
    print(f"post-mortem yazılan: {backfill_postmortems()}")
