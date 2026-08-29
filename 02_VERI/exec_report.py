"""
📋 YÖNETİCİ ÖZETİ — 2 günde bir otomatik üretilen, numaralı arşiv raporu
=======================================================================
Her rapor bir "an"ı dondurur: ajan karnesi, kanıt eşikleri, kural
doğrulaması, gerçek-para kapıları ve ÖNCEKİ RAPORDAN BU YANA ne değişti.

Numaralandırma 29.08.2026'dan itibaren #1'den başlar; 48 saatte bir
yeni rapor üretilir (worker çağırır). Raporlar `exec_reports` tablosunda
JSON olarak saklanır — UI sayfası bunları okur.

Tasarım ilkesi: rapor YORUM üretmez, ÖLÇÜM dondurur. Yorum insana ait.

CLI:
    python exec_report.py            # gerekiyorsa üret
    python exec_report.py --force    # zorla üret
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timedelta
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import db
import agents

PERIOD_HOURS = 48                      # 2 günde bir
FIRST_REPORT_DATE = "2026-08-29"       # #1 bu tarihten itibaren
BIG_LEAGUES = {"T1", "E0", "SP1", "I1", "D1", "F1", "BRA1", "USA1", "P1", "N1"}


# ──────────────────────────────────────────────────────────────
# İstatistik yardımcıları
# ──────────────────────────────────────────────────────────────

def wilson_lb(k: int, n: int, z: float = 1.96) -> float:
    """Wilson alt güven sınırı — küçük örneklemde dürüst isabet tahmini."""
    if n <= 0:
        return 0.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - m


def coupons_needed(p_true: float, p_break: float, z: float = 1.96) -> int | None:
    """Bu isabet oranı sürerse, başabaşı KANITLAMAK için kaç kupon gerekir?"""
    if p_true <= p_break:
        return None
    for n in range(5, 3001):
        if wilson_lb(round(p_true * n), n, z) > p_break:
            return n
    return None


def _slice_stats(rows) -> dict:
    """(odds, won) listesinden isabet/ROI/sapma."""
    n = len(rows)
    if not n:
        return {"n": 0}
    w = sum(1 for o, won in rows if won)
    exp = sum(1.0 / (o or 1) for o, _ in rows)
    sd = math.sqrt(sum((1 / (o or 1)) * (1 - 1 / (o or 1)) for o, _ in rows)) or 1
    roi = sum(((o or 1) - 1) if won else -1 for o, won in rows) / n * 100
    return {"n": n, "hit": w / n * 100, "roi": roi, "sigma": (w - exp) / sd}


# ──────────────────────────────────────────────────────────────
# Ölçüm blokları
# ──────────────────────────────────────────────────────────────

def _totals(conn, era: str) -> dict:
    r = conn.execute(
        "SELECT COUNT(*) n, SUM(CASE WHEN status='won' THEN 1 ELSE 0 END) w, "
        "SUM(COALESCE(pnl,0)) p, AVG(combined_odds) o FROM paper_coupons "
        "WHERE created_at>=? AND status IN ('won','lost')", (era,)).fetchone()
    n = r[0] or 0
    if not n:
        return {"n": 0}
    rows = conn.execute(
        "SELECT status, combined_odds FROM paper_coupons "
        "WHERE created_at>=? AND status IN ('won','lost')", (era,)).fetchall()
    vals = [((x[1] or 1) - 1) * 100 if x[0] == "won" else -100.0 for x in rows]
    mean = sum(vals) / len(vals)
    sd = math.sqrt(sum((v - mean) ** 2 for v in vals) / len(vals)) * math.sqrt(len(vals))
    o = conn.execute(
        "SELECT COUNT(*) c, COALESCE(SUM(stake),0) s FROM paper_coupons "
        "WHERE created_at>=? AND status='open'", (era,)).fetchone()
    pnl = float(r[2] or 0)
    return {
        "n": n, "won": r[1] or 0, "hit": (r[1] or 0) / n * 100,
        "pnl": pnl, "roi": pnl / (n * 100) * 100, "avg_odds": float(r[3] or 0),
        "open_n": o[0] or 0, "open_stake": float(o[1] or 0),
        "swing": sd, "sigma": (pnl / sd) if sd else 0,
    }


def _agents(conn, era: str) -> list[dict]:
    out = []
    field = list(agents.PROFILES) + ["KURUCU_V2"]
    for pid in field:
        rows = conn.execute(
            "SELECT status, combined_odds FROM paper_coupons WHERE portfolio_id=? "
            "AND created_at>=? AND status IN ('won','lost')", (pid, era)).fetchall()
        if not rows:
            continue
        op = conn.execute(
            "SELECT COUNT(*) c FROM paper_coupons WHERE portfolio_id=? "
            "AND created_at>=? AND status='open'", (pid, era)).fetchone()[0]
        n = len(rows)
        w = sum(1 for x in rows if x[0] == "won")
        avg = sum((x[1] or 1) for x in rows) / n
        p0 = 1 / avg if avg else 1
        hit = w / n
        roi = sum(((x[1] or 1) - 1) if x[0] == "won" else -1 for x in rows) / n * 100
        lb = wilson_lb(w, n)
        need = coupons_needed(hit, p0) if hit > p0 else None
        bank = conn.execute(
            "SELECT current_bankroll FROM paper_portfolio WHERE portfolio_id=?",
            (pid,)).fetchone()
        out.append({
            "pid": pid, "n": n, "open": op or 0, "hit": hit * 100,
            "avg_odds": avg, "breakeven": p0 * 100, "edge": (hit - p0) * 100,
            "roi": roi, "lb": lb * 100, "proven": bool(lb > p0),
            "need": need, "bankroll": float(bank[0]) if bank else None,
        })
    out.sort(key=lambda x: -x["roi"])
    return out


def _rules(conn, era: str) -> dict:
    """Manuel oyun kurallarının HÂLÂ geçerli olup olmadığını her raporda sınar."""
    import collections
    rows = conn.execute(
        "SELECT pb.match_id, pb.market, pb.pick, pb.odds, pb.status, m.league_code "
        "FROM paper_bets pb JOIN paper_coupons pc ON pb.coupon_id=pc.coupon_id "
        "LEFT JOIN matches_v2 m ON pb.match_id=m.match_id "
        "WHERE pc.created_at>=? AND pc.status IN ('won','lost') "
        "AND pb.status IN ('won','lost')", (era,)).fetchall()
    crowd = collections.Counter((r[0], r[1], r[2]) for r in rows)
    uniq = {}
    for r in rows:
        uniq.setdefault((r[0], r[1], r[2]), r)
    u = list(uniq.values())

    def sl(f):
        return _slice_stats([( (x[3] or 1), x[4] == "won") for x in u if f(x)])

    return {
        "unique_bets": len(u), "raw_legs": len(rows),
        "lonely": sl(lambda x: crowd[(x[0], x[1], x[2])] == 1),
        "crowded": sl(lambda x: crowd[(x[0], x[1], x[2])] >= 2),
        "odds_low": sl(lambda x: (x[3] or 0) < 1.45),
        "odds_high": sl(lambda x: (x[3] or 0) >= 1.45),
        "big_league": sl(lambda x: (x[5] or "ALL") in BIG_LEAGUES),
        "small_league": sl(lambda x: (x[5] or "ALL") not in BIG_LEAGUES),
        "mkt_good": sl(lambda x: x[1] in ("UST_25", "KG_YOK")),
        "mkt_bad": sl(lambda x: x[1] in ("ALT_25", "1X2")),
        "single": sl(lambda x: True),   # yer tutucu (kupon tipi ayrı ölçülür)
    }


def _coupon_types(conn, era: str) -> dict:
    out = {}
    for ct in ("A_TEK", "A_K2", "A_K3"):
        r = conn.execute(
            "SELECT COUNT(*) n, SUM(CASE WHEN status='won' THEN 1 ELSE 0 END) w "
            "FROM paper_coupons WHERE created_at>=? AND coupon_type=? "
            "AND status IN ('won','lost')", (era, ct)).fetchone()
        if r[0]:
            out[ct] = {"n": r[0], "hit": (r[1] or 0) / r[0] * 100}
    return out


def _health(conn) -> dict:
    h = {}
    try:
        rows = conn.execute(
            "SELECT ts, pid, status FROM agent_diag ORDER BY ts DESC LIMIT 40").fetchall()
        seen, latest = set(), []
        for r in rows:
            if r[1] not in seen:
                seen.add(r[1])
                latest.append(r)
        h["diag_ts"] = latest[0][0] if latest else None
        h["blocked"] = sum(1 for r in latest if "TIKANIKLIK" in (r[2] or ""))
        h["played"] = sum(1 for r in latest if "OYNADI" in (r[2] or ""))
        h["data_line"] = next((r[2] for r in latest if r[1] == "SISTEM"), None)
    except Exception:
        conn.rollback()
    try:
        r = conn.execute("SELECT MAX(ts) FROM agent_runs").fetchone()
        h["last_run"] = r[0] if r else None
    except Exception:
        conn.rollback()
    return h


def _gates(totals: dict, ags: list[dict]) -> list[dict]:
    """Gerçek paraya dönüş için beş kapı — her raporda otomatik denetlenir."""
    n = totals.get("n", 0)
    joker = next((a for a in ags if a["pid"] == "JOKER_V1"), None)
    beat_joker = sum(1 for a in ags
                     if joker and a["pid"] != "JOKER_V1" and a["roi"] > joker["roi"])
    proven = [a["pid"] for a in ags if a["proven"]]
    return [
        {"key": "kanit", "name": "Kanıt kapısı",
         "target": "≥350 karar kuponu ve pozitif güven alt sınırı",
         "value": f"{n} kupon · kanıtlı ajan: {len(proven)}",
         "ok": bool(n >= 350 and proven)},
        {"key": "kontrol", "name": "Kontrol kapısı (JOKER)",
         "target": "Ajanların çoğu rastgele ajanı geçmeli",
         "value": (f"JOKER ROI {joker['roi']:+.1f}% · onu geçen: {beat_joker}"
                   if joker else "JOKER verisi yok"),
         "ok": bool(joker and beat_joker >= max(3, len(ags) // 2))},
        {"key": "slipaj", "name": "Slipaj kapısı",
         "target": "Gerçekte alınan oran ile kâğıttaki fark ölçülmeli",
         "value": "henüz ölçülmüyor (gerçek oyun kaydı yok)", "ok": False},
        {"key": "olcek", "name": "Ölçek kapısı",
         "target": "Birim = kasanın %1'i · çeyrek Kelly",
         "value": "kâğıt modda sabit 100 TL (kural hazır)", "ok": True},
        {"key": "dayanma", "name": "Dayanma kapısı",
         "target": "Zararlı ayı sindirebilmek",
         "value": (f"mevcut salınım ±{totals.get('swing', 0):,.0f} TL"
                   if totals.get("swing") else "—"),
         "ok": None},
    ]


def _deltas(conn, cur: dict) -> dict:
    """Önceki rapordan bu yana ne değişti — numaralı arşivin asıl değeri."""
    prev = conn.execute(
        "SELECT payload FROM exec_reports ORDER BY report_no DESC LIMIT 1").fetchone()
    if not prev:
        return {"first": True}
    try:
        p = json.loads(prev[0])
    except Exception:
        return {"first": True}
    d = {"first": False, "prev_no": p.get("meta", {}).get("no"),
         "prev_ts": p.get("meta", {}).get("ts")}
    pt, ct = p.get("totals", {}), cur.get("totals", {})
    d["d_n"] = ct.get("n", 0) - pt.get("n", 0)
    d["d_roi"] = ct.get("roi", 0) - pt.get("roi", 0)
    d["d_pnl"] = ct.get("pnl", 0) - pt.get("pnl", 0)
    pa = {a["pid"]: a for a in p.get("agents", [])}
    news, ups, downs = [], [], []
    for a in cur.get("agents", []):
        b = pa.get(a["pid"])
        if not b:
            news.append(a["pid"])
            continue
        if a["proven"] and not b.get("proven"):
            ups.append(a["pid"])
        if b.get("proven") and not a["proven"]:
            downs.append(a["pid"])
    d["new_agents"] = news
    d["newly_proven"] = ups
    d["lost_proof"] = downs
    # kural işaret değişimleri
    flips = []
    for k in ("lonely", "crowded", "odds_low", "odds_high",
              "big_league", "small_league", "mkt_good", "mkt_bad"):
        a0 = (p.get("rules", {}).get(k) or {}).get("roi")
        a1 = (cur.get("rules", {}).get(k) or {}).get("roi")
        if a0 is not None and a1 is not None and (a0 > 0) != (a1 > 0):
            flips.append({"rule": k, "before": a0, "after": a1})
    d["rule_flips"] = flips
    return d


def _findings(cur: dict) -> list[str]:
    """Rapordan otomatik çıkan dikkat çekici satırlar (yorum değil, tespit)."""
    out = []
    ags = cur.get("agents", [])
    r = cur.get("rules", {})
    for a in ags:
        if a["proven"]:
            out.append(f"✅ {a['pid'].split('_')[0]} kanıt eşiğini geçti "
                       f"(isabet %{a['hit']:.0f}, gereken %{a['breakeven']:.0f}, "
                       f"n={a['n']})")
    jk = next((a for a in ags if a["pid"] == "JOKER_V1"), None)
    if jk:
        better = sum(1 for a in ags if a["pid"] != "JOKER_V1" and a["roi"] > jk["roi"])
        out.append(f"🃏 Rastgele kontrol (JOKER) ROI {jk['roi']:+.1f}% — "
                   f"onu geçebilen ajan: {better}/{len(ags)-1}")
    lo, hi = r.get("odds_low", {}), r.get("odds_high", {})
    if lo.get("n") and hi.get("n"):
        out.append(f"📉 Kısa oran (<1.45) {lo['roi']:+.1f}% · "
                   f"uzun oran (≥1.45) {hi['roi']:+.1f}% "
                   f"[n={lo['n']} / {hi['n']}]")
    ln, cr = r.get("lonely", {}), r.get("crowded", {})
    if ln.get("n") and cr.get("n"):
        out.append(f"👤 Yalnız seçim {ln['roi']:+.1f}% · kalabalık {cr['roi']:+.1f}% "
                   f"(fark {ln['roi']-cr['roi']:+.1f} puan)")
    bg, sm = r.get("big_league", {}), r.get("small_league", {})
    if bg.get("n") and sm.get("n"):
        out.append(f"🌍 Büyük lig {bg['roi']:+.1f}% · küçük/egzotik {sm['roi']:+.1f}%")
    ct = cur.get("coupon_types", {})
    if ct:
        out.append("🎫 Kupon isabeti — " + " · ".join(
            f"{k.replace('A_','')} %{v['hit']:.0f} (n={v['n']})" for k, v in ct.items()))
    return out


# ──────────────────────────────────────────────────────────────
# Üretim
# ──────────────────────────────────────────────────────────────

def ensure_table(conn) -> None:
    conn.execute("CREATE TABLE IF NOT EXISTS exec_reports ("
                 "report_no INTEGER PRIMARY KEY, ts TEXT, era_start TEXT, "
                 "payload TEXT)")
    conn.commit()


def due(conn) -> bool:
    r = conn.execute("SELECT MAX(ts) FROM exec_reports").fetchone()
    if not r or not r[0]:
        return datetime.utcnow().date().isoformat() >= FIRST_REPORT_DATE
    try:
        last = datetime.fromisoformat(str(r[0])[:19])
    except Exception:
        return True
    return (datetime.utcnow() - last) >= timedelta(hours=PERIOD_HOURS)


def generate(force: bool = False) -> dict | None:
    conn = db.connect()
    try:
        ensure_table(conn)
        if not force and not due(conn):
            print("[RAPOR] henüz zamanı değil (2 günde bir).")
            return None
        era = agents.era_start(conn, "CESUR_V1") or "2026-08-23"
        cur: dict = {}
        cur["totals"] = _totals(conn, era)
        if not cur["totals"].get("n"):
            print("[RAPOR] veri yok — üretilmedi.")
            return None
        cur["agents"] = _agents(conn, era)
        cur["rules"] = _rules(conn, era)
        cur["coupon_types"] = _coupon_types(conn, era)
        cur["health"] = _health(conn)
        cur["gates"] = _gates(cur["totals"], cur["agents"])
        cur["deltas"] = _deltas(conn, cur)
        cur["findings"] = _findings(cur)
        no = (conn.execute("SELECT MAX(report_no) FROM exec_reports").fetchone()[0] or 0) + 1
        now = datetime.utcnow().isoformat()
        cur["meta"] = {"no": no, "ts": now, "era_start": era,
                       "period_hours": PERIOD_HOURS}
        conn.execute("INSERT INTO exec_reports (report_no, ts, era_start, payload) "
                     "VALUES (?,?,?,?)", (no, now, era, json.dumps(cur, ensure_ascii=False)))
        conn.commit()
        t = cur["totals"]
        print(f"[RAPOR] #{no} üretildi — {t['n']} kupon, ROI {t['roi']:+.1f}%, "
              f"{len(cur['findings'])} tespit")
        return cur
    finally:
        conn.close()


if __name__ == "__main__":
    generate(force="--force" in sys.argv)
