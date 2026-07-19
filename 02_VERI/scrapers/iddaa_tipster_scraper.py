"""
SELECTIVE EDGE v1.0 — iddaa.com Yazar Yorumları Tipster Scraper

Endpoint keşfi:
    Base: https://contentv2.iddaa.com
    GET /editors                       → 12 yazar (Ali Erim, Mert Elam, İlker Dural...)
    GET /editorDetails/{editor_id}     → o yazarın son tüm yorumları + kupon detayları
    GET /mainPageEditors               → ana sayfadaki yazarlar
    GET /mainPage                      → ana sayfa yorumları

Editor detail dönüşü (her yorum):
    eventId              → iddaa_match_id ile mapping
    muk                  → market subtype, ör. "2_101" = Alt/Üst, "1_1" = MS, "2_7" = MS+A/Ü
    sov                  → stake value (line), ör. "2.5", "+1"
    outcomeNo            → 1=Alt/1, 2=Üst/X, ...
    outcomeName          → "Alt", "Üst", "1 ve Alt", ...
    homeTeam, awayTeam, leagueName
    odd, webOdd          → pick anındaki oran (ortalama line)
    currentOdd           → ŞU AN oran (CLV sinyali: currentOdd < odd ise sharp money kabul etti)
    resultStatus         → -1=tutmadı, 0=henüz oynanmadı, 1=tuttu (görünen pattern)
    matchStartDateTime   → unix timestamp
    commentText          → Türkçe full analiz metni
    last5BetsResults     → editor.last5 = recent form

Bu data **gerçek tipster track record** içerir:
    win_rate = sum(resultStatus==1) / sum(resultStatus in {-1,1})
    CLV_agreement = mean(odd > currentOdd)  → sharp money tipster ile aynı yönde mi
"""
from __future__ import annotations

import json
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib import request, error

THIS_DIR = Path(__file__).resolve().parent
VERI_DIR = THIS_DIR.parent
sys.path.insert(0, str(VERI_DIR))

import database as db


API_BASE = "https://contentv2.iddaa.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.7",
    "Referer": "https://www.iddaa.com/",
    "Origin": "https://www.iddaa.com",
}


def _get(url: str, timeout: int = 15) -> dict:
    req = request.Request(url, headers=HEADERS)
    with request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def fetch_editors(page_size: int = 50) -> list[dict]:
    """Tüm iddaa.com yazarlarını çek."""
    results = []
    page = 1
    while True:
        try:
            r = _get(f"{API_BASE}/editors?pageSize={page_size}&page={page}")
        except error.HTTPError:
            # bazı parametre kombinasyonları reddedilir, fallback
            r = _get(f"{API_BASE}/editors")
            results.extend(r.get("data", {}).get("results", []) or [])
            break
        data = r.get("data", {})
        batch = data.get("results", []) or []
        results.extend(batch)
        total_pages = data.get("totalPage", 1)
        if page >= total_pages or not batch:
            break
        page += 1
        time.sleep(0.3)
    return results


def fetch_editor_detail(editor_id: int) -> dict | None:
    try:
        r = _get(f"{API_BASE}/editorDetails/{editor_id}")
        return r.get("data") or None
    except Exception as e:
        print(f"  editor/{editor_id} ERR: {e}")
        return None


# muk = "{t}_{st}" → canonical market key (odds scraper ile aynı eşleme)
def muk_to_market(muk: str, sov: str | None) -> str:
    """'2_101' + sov='2.5' → 'OU2.5' formatı."""
    mapping = {
        "1_1":   "1X2",
        "2_101": "OU",
        "2_60":  "HT_OU",
        "2_89":  "BTTS",
        "2_92":  "DC",
        "2_100": "HC",
        "2_7":   "1X2_OU",
        "2_90":  "HT_FT",
        "2_88":  "HT_1X2",
        "2_91":  "OE",
        "2_4":   "TOTAL_GOALS",
        "2_86":  "CORRECT_SCORE",
        "2_698": "1X2_BTTS",
        "2_700": "OU_BTTS",
    }
    base = mapping.get(muk, muk)  # fallback raw muk
    if base in ("OU", "HT_OU") and sov:
        return f"{base}{sov}"
    if base == "HC" and sov:
        try:
            n = float(sov)
            sign = "+" if n >= 0 else "-"
            return f"HC{sign}{abs(n):g}"
        except Exception:
            return f"HC{sov}"
    return base


def write_picks(editor: dict, comments: list[dict]) -> int:
    """Bir yazarın yorumlarını tipster_picks tablosuna yaz."""
    if not comments:
        return 0
    conn = db.connect()
    try:
        now = datetime.utcnow().isoformat()
        tipster_id = f"iddaa:{editor.get('editorId')}"
        tipster_name = editor.get("editorName")
        # İdempotent: editorDetails her seferinde TAM geçmişi döner →
        # eski satırları sil, tazesini yaz (mükerrer birikimi önler)
        try:
            conn.execute("DELETE FROM tipster_picks WHERE tipster_id=?",
                         (tipster_id,))
        except Exception:
            conn.rollback()
        n = 0
        for c in comments:
            try:
                # Unix timestamp → ISO
                ts = c.get("matchStartDateTime")
                kick_iso = None
                if ts:
                    try:
                        kick_iso = datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
                    except Exception:
                        pass
                rs = c.get("resultStatus")
                mst = c.get("status")  # 4 = FT (final)
                # Gerçek pattern (data inspect):
                #   resultStatus=1  → kupon TUTTU
                #   resultStatus=0  → kupon TUTMADI (eğer mac status=4=FT ise)
                #   resultStatus=-1 → mac henüz oynanmadı (pending)
                # Settled SADECE mac biti (status==4) ve resultStatus != -1 ise
                if mst == 4 and rs in (0, 1):
                    settled = 1
                    won = 1 if rs == 1 else 0
                else:
                    settled = 0
                    won = None

                conn.execute("""
                    INSERT INTO tipster_picks(
                        tipster_id, tipster_name, source, posted_at, kickoff_iso,
                        home_team, away_team, market, selection, pick_odd,
                        stake_units, confidence, settled, won, inserted_at, raw_json
                    ) VALUES (?, ?, 'iddaa', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    tipster_id, tipster_name, now, kick_iso,
                    c.get("homeTeam"), c.get("awayTeam"),
                    muk_to_market(c.get("muk", ""), c.get("sov")),
                    c.get("outcomeName"),
                    c.get("odd"),
                    None,  # stake_units (iddaa expose etmez)
                    None,  # confidence
                    settled, won, now,
                    json.dumps(c, ensure_ascii=False)
                ))
                n += 1
            except Exception:
                pass
        conn.commit()
        return n
    finally:
        conn.close()


def wilson_interval(wins: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score confidence interval for binomial proportion."""
    import math as _m
    if n == 0:
        return (0.0, 1.0)
    p = wins / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * _m.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    lower = max(0.0, centre - half)
    upper = min(1.0, centre + half)
    return (lower, upper)


def update_editor_stats(editor_id: int, editor_name: str,
                        min_settled_for_score: int = 10) -> dict:
    """
    tipster_stats güncelle. Wilson CI + min sample filter.

    Composite score formülü (v1.1):
        score = wilson_lower × log(settled+1) × (1 + ROI_clipped)

    wilson_lower kullanmak küçük örnek riskini azaltır:
        n=8, %88 win → wilson_lower=%52 → score düşer
        n=100, %60 win → wilson_lower=%50 → score yüksek

    min_settled_for_score: bu eşiğin altındaki tipster için score=None.
    """
    conn = db.connect()
    try:
        tipster_id = f"iddaa:{editor_id}"
        row = conn.execute("""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN settled=1 THEN 1 ELSE 0 END) AS settled_n,
                SUM(CASE WHEN won=1 THEN 1 ELSE 0 END) AS wins,
                AVG(pick_odd) AS avg_odd,
                MAX(posted_at) AS last_pick
            FROM tipster_picks
            WHERE tipster_id = ?
        """, (tipster_id,)).fetchone()

        total = row["total"] or 0
        settled_n = row["settled_n"] or 0
        wins = row["wins"] or 0
        avg_odd = row["avg_odd"] or 0
        last_pick = row["last_pick"]

        win_rate = (wins / settled_n) if settled_n else None

        # ROI
        roi = None
        if settled_n:
            rsum = 0.0
            for p in conn.execute(
                "SELECT pick_odd, won FROM tipster_picks "
                "WHERE tipster_id=? AND settled=1", (tipster_id,)
            ):
                if p["won"] == 1 and p["pick_odd"]:
                    rsum += (p["pick_odd"] - 1)
                else:
                    rsum -= 1
            roi = rsum / settled_n

        # Wilson CI %95
        wilson_lower, wilson_upper = wilson_interval(wins, settled_n) if settled_n else (None, None)

        # Composite score - sample size penalize: wilson_lower kullan
        import math
        score = None
        if settled_n >= min_settled_for_score and wilson_lower is not None:
            roi_clip = max(-0.5, min(1.0, roi or 0))
            score = wilson_lower * math.log(settled_n + 1) * (1.0 + roi_clip)

        now = datetime.utcnow().isoformat()
        # PG-uyumlu upsert: OR REPLACE çevrilemiyor → sil + ekle
        try:
            conn.execute("DELETE FROM tipster_stats WHERE tipster_id=?",
                         (tipster_id,))
        except Exception:
            conn.rollback()
        conn.execute("""
            INSERT INTO tipster_stats(
                tipster_id, tipster_name, source,
                total_picks, settled_picks, wins,
                win_rate, avg_odd, roi, recent_form_50,
                variance, score, last_pick_at, updated_at,
                wilson_lower, wilson_upper
            ) VALUES (?, ?, 'iddaa', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            tipster_id, editor_name,
            total, settled_n, wins,
            win_rate, avg_odd, roi, win_rate,
            None, score, last_pick, now,
            wilson_lower, wilson_upper
        ))
        conn.commit()
        return {
            "tipster_id": tipster_id, "name": editor_name,
            "total": total, "settled": settled_n, "wins": wins,
            "win_rate": win_rate, "wilson_lower": wilson_lower,
            "wilson_upper": wilson_upper,
            "roi": roi, "score": score,
        }
    finally:
        conn.close()


def ingest_all_editors(delay: float = 0.5) -> dict:
    """
    Tüm iddaa.com yazarlarını çek + her birinin yorumlarını + stats güncelle.
    """
    print("[tipster] /editors fetch...")
    editors = fetch_editors()
    print(f"  {len(editors)} yazar bulundu")

    total_picks = 0
    summary = []
    for i, ed in enumerate(editors):
        eid = ed.get("editorId")
        ename = ed.get("editorName")
        print(f"  [{i+1}/{len(editors)}] id={eid:>3} {ename}")
        d = fetch_editor_detail(eid)
        if d:
            comments = d.get("comments", []) or []
            n = write_picks(d, comments)
            total_picks += n
            stats = update_editor_stats(eid, ename)
            summary.append(stats)
            print(f"      -> {n} pick, win_rate={stats['win_rate']}, roi={stats['roi']}")
        time.sleep(delay)
    return {"editors": len(editors), "picks": total_picks, "summary": summary}


def stats():
    conn = db.connect()
    try:
        n_picks = conn.execute("SELECT COUNT(*) FROM tipster_picks").fetchone()[0]
        n_tipsters = conn.execute("SELECT COUNT(*) FROM tipster_stats").fetchone()[0]
        print("=== TIPSTER STATS ===")
        print(f"  Toplam pick     : {n_picks:>5,}")
        print(f"  Tipster sayisi  : {n_tipsters:>5,}")
        if n_tipsters:
            print(f"\n  Tipster track records (Wilson CI 95%):")
            print(f"    {'name':25s}  {'picks':>5s} {'sttld':>5s} {'win%':>5s} {'CI_low':>6s} {'CI_up':>6s} {'ROI%':>7s} {'score':>6s}")
            for r in conn.execute(
                "SELECT * FROM tipster_stats ORDER BY score DESC NULLS LAST"
            ).fetchall():
                wr = f"{(r['win_rate'] or 0)*100:.0f}" if r['win_rate'] is not None else "-"
                wlow = f"{(r['wilson_lower'] or 0)*100:.0f}" if r['wilson_lower'] is not None else "-"
                wup = f"{(r['wilson_upper'] or 0)*100:.0f}" if r['wilson_upper'] is not None else "-"
                roi = f"{(r['roi'] or 0)*100:+.1f}" if r['roi'] is not None else "-"
                sc = f"{r['score']:.3f}" if r['score'] is not None else "-(n<10)"
                print(f"    {r['tipster_name'][:25]:25s}  {r['total_picks']:>5} {r['settled_picks']:>5} "
                      f"{wr:>5} {wlow:>6} {wup:>6} {roi:>7} {sc:>6}")
    finally:
        conn.close()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "fetch"
    if cmd == "fetch":
        result = ingest_all_editors()
        print(f"\n[OK] {result['editors']} yazar, {result['picks']} pick kaydedildi")
        stats()
    elif cmd == "stats":
        stats()
    elif cmd == "editors":
        eds = fetch_editors()
        for e in eds:
            print(f"  id={e.get('editorId'):>3}  {e.get('editorName')}")
    else:
        print("Komutlar: fetch | stats | editors")
