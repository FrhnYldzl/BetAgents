"""
KUPON ÖNERİCİ — başlamamış, yüksek-sinyalli, MBS-uyumlu (100 TL).
Canlı PG'den yaklaşan maç + model sinyali; iddaa'dan gerçek MBS (mbc).
Kupon YERLEŞTİRMEZ — sadece öneri sunar (sen oynarsın).
"""
import sys, json, urllib.request
from datetime import datetime, timezone
sys.path.insert(0, ".")
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass
import db
from paper_engine import PaperEngine

STAKE = 100.0


def live_mbc_map():
    """iddaa canlı event listesinden {event_id(str): mbc} haritası."""
    H = {"User-Agent": "Mozilla/5.0", "Accept": "application/json",
         "Referer": "https://www.iddaa.com/", "Origin": "https://www.iddaa.com"}
    out = {}
    try:
        req = urllib.request.Request(
            "https://sportsbookv2.iddaa.com/sportsbook/events?st=1&type=0", headers=H)
        d = json.loads(urllib.request.urlopen(req, timeout=20).read())
        for e in (d.get("data", {}).get("events") or []):
            out[str(e.get("i"))] = e.get("mbc")
    except Exception as ex:
        print("  (iddaa mbc çekilemedi:", str(ex)[:60], ")")
    return out


def main():
    eng = PaperEngine("PAPER_V1")
    c = db.connect()
    now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    rows = c.execute("""
        SELECT * FROM matches_v2
        WHERE is_settled=0 AND kickoff_utc > ? AND closing_1 IS NOT NULL
        ORDER BY kickoff_utc ASC LIMIT 400
    """, (now,)).fetchall()
    matches = [dict(r) for r in rows]
    c.close()
    print(f"Yaklaşan (başlamamış) maç: {len(matches)}")

    mbc = live_mbc_map()
    print(f"iddaa canlı MBS haritası: {len(mbc)} event\n")

    def mbs_of(m):
        v = m.get("mbs")
        if not v:
            v = mbc.get(str(m.get("external_id_iddaa")))
        try:
            return int(v) if v else 3
        except Exception:
            return 3

    sigs = []
    for m in matches:
        for s in eng.evaluate_match(m):
            s["_match"] = m
            s["_mbs"] = mbs_of(m)
            sigs.append(s)
    sigs.sort(key=lambda x: x["signal_score"], reverse=True)
    print(f"Toplam sinyal: {len(sigs)}\n")
    if not sigs:
        print("Uygun sinyal yok."); return

    used = set()
    def pick(pool, n, max_mbs):
        res, seen = [], set()
        for s in pool:
            mid = s["_match"].get("match_id")
            if mid in used or mid in seen or s["_mbs"] > max_mbs:
                continue
            res.append(s); seen.add(mid)
            if len(res) == n: break
        return res

    def line(s):
        m = s["_match"]; ko = (m.get("kickoff_utc") or "")[:16].replace("T", " ")
        return (f"{m.get('home_team','?')} vs {m.get('away_team','?')}  [{m.get('league_code')}]"
                f"  {ko}  MBS={s['_mbs']}\n"
                f"      → {s['market']}: {s['pick']} @ {s['odds']:.2f}  "
                f"(model %{s['model_prob']*100:.0f} · edge %{s['edge']*100:+.1f} · skor {s['signal_score']:.2f})")

    def show(title, picks):
        if not picks: return
        co = 1.0
        wp = 1.0
        for p in picks:
            co *= p["odds"]; wp *= p["model_prob"]
        co = round(co, 2)
        gross = STAKE * co
        net = STAKE + (gross - STAKE) * 0.90  # ~%10 vergi (kâr üzerinden)
        print("=" * 70)
        print(f"### {title}  ({len(picks)} ayak)")
        for p in picks:
            print("  • " + line(p))
        print(f"  KOMBİNE ORAN: {co}  |  100 TL → brüt {gross:.0f} TL (net ~{net:.0f} TL)")
        print(f"  Tahmini tutma olasılığı (model): %{wp*100:.0f}")
        print()

    # Alt A — TEK (sadece MBS=1 güçlü favori)
    tek = pick([s for s in sigs if s["market"] == "1X2" and s["model_prob"] >= 0.66], 1, 1)
    if tek:
        show("ALTERNATİF A — TEK MAÇ (MBS=1, güçlü favori)", tek); used.update(p["_match"]["match_id"] for p in tek)

    # Alt B — K3 KOMBO (en güçlü 3 sinyal, mbs<=3)
    k3 = pick([s for s in sigs if s["model_prob"] >= 0.60], 3, 3)
    if len(k3) == 3:
        show("ALTERNATİF B — 3'LÜ KOMBO (en güçlü sinyaller)", k3); used.update(p["_match"]["match_id"] for p in k3)

    # Alt C — K3 VALUE (edge'li 3'lü)
    kv = pick([s for s in sigs if s["edge"] >= 0.04 and s["model_prob"] >= 0.55], 3, 3)
    if len(kv) == 3:
        show("ALTERNATİF C — 3'LÜ VALUE (edge öncelikli)", kv)


if __name__ == "__main__":
    main()
