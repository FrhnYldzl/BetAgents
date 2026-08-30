"""
🧑‍💻 OPUS 5 — MANUEL AJAN (gerçek oyun defteri)
================================================
iddaa gerçek kupon arşivini siliyor; buraya kaydedersek gerçek performans
ajanlarla AYNI metriklerle (flat ROI, isabet, kanıt eşiği, CLV) ölçülebilir.

İlke: hiçbir şey uydurulmaz. Kupon, ajanların AÇIK kuponlarından ya da
onların ayaklarından kopyalanır — maç, pazar, oran birebir aynı kalır.
Kullanıcı yalnızca "bunu gerçekte oynadım" der; stake varsayılan 50 TL.

Sonuçlandırma: auto_settle tüm portföyleri döndüğü için OPUS 5 kuponları
diğer ajanlarla aynı anda, aynı kaynaktan settle olur. Ayrıcalık yok.

CLI:
    python manual_book.py --list          # ajanların açık kuponları
    python manual_book.py --stats         # OPUS 5 karnesi
"""
from __future__ import annotations

import sys
import uuid
from datetime import datetime
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import db

PID = "OPUS5_V1"
NAME = "OPUS 5 (manuel — gerçek oyun defteri)"
INITIAL = 1000.0
DEFAULT_STAKE = 50.0


def _now() -> str:
    return datetime.utcnow().isoformat()


# ──────────────────────────────────────────────────────────────
# Portföy
# ──────────────────────────────────────────────────────────────

def ensure_portfolio() -> None:
    conn = db.connect()
    try:
        now = _now()
        conn.execute(
            """
            INSERT OR IGNORE INTO paper_portfolio
              (portfolio_id, name, initial_bankroll, current_bankroll,
               peak_bankroll, total_bets, total_wins, total_coupons,
               won_coupons, total_staked, total_return, status,
               strategy_version, notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 0, 0, 0, 0, 0, 0, 'active', ?, ?, ?, ?)
            """,
            (PID, NAME, INITIAL, INITIAL, INITIAL, "opus5_manuel",
             "Gerçek hayatta oynanan kuponların defteri — sabit birim", now, now))
        conn.commit()
        # era + dönem alanları (lig cezalarına tabi DEĞİL: PROFILES'da yok)
        conn.execute(
            "UPDATE paper_portfolio SET era_start=COALESCE(era_start,?), "
            "era_no=COALESCE(era_no,2), period_status=COALESCE(period_status,'active'), "
            "period_start_bankroll=COALESCE(period_start_bankroll,?), "
            "period_start_date=COALESCE(period_start_date,?) WHERE portfolio_id=?",
            (now, INITIAL, now, PID))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"[OPUS5] portföy hatası: {e}")
    finally:
        conn.close()


# ──────────────────────────────────────────────────────────────
# Ajanların açık kuponları (sepet kaynağı)
# ──────────────────────────────────────────────────────────────

def open_coupons(exclude_started: bool = True) -> list[dict]:
    """Tüm ajanların AÇIK kuponları + ayakları. OPUS5'in kendi kuponları hariç."""
    conn = db.connect()
    try:
        cps = conn.execute(
            "SELECT coupon_id, portfolio_id, coupon_type, combined_odds, "
            "num_legs, created_at FROM paper_coupons WHERE status='open' "
            "AND portfolio_id<>? ORDER BY portfolio_id, created_at DESC", (PID,)).fetchall()
        if not cps:
            return []
        legs_all = conn.execute(
            "SELECT pb.coupon_id, pb.bet_id, pb.match_id, pb.home_team, pb.away_team, "
            "pb.league, pb.kickoff_utc, pb.market, pb.pick, pb.odds "
            "FROM paper_bets pb JOIN paper_coupons pc ON pb.coupon_id=pc.coupon_id "
            "WHERE pc.status='open' AND pc.portfolio_id<>?", (PID,)).fetchall()
        # zaten kopyaladıklarım
        mine = set()
        for r in conn.execute(
                "SELECT reasoning FROM paper_coupons WHERE portfolio_id=?", (PID,)).fetchall():
            txt = str(r[0] or "")
            if "src=" in txt:
                mine.add(txt.split("src=")[1].split()[0])
    finally:
        conn.close()

    by_c: dict = {}
    for l in legs_all:
        by_c.setdefault(l[0], []).append({
            "bet_id": l[1], "match_id": l[2], "home": l[3], "away": l[4],
            "league": l[5], "kickoff": l[6], "market": l[7],
            "pick": l[8], "odds": float(l[9] or 1)})
    now = _now()
    out = []
    for c in cps:
        legs = by_c.get(c[0], [])
        if not legs:
            continue
        # ⚠️ UX DERSİ: eskiden başlamış maçlı kuponlar listeden TAMAMEN
        # siliniyordu — kullanıcı "ajanlarım eksik" diye görüyordu.
        # Artık gösterilir ama OYNANAMAZ olarak işaretlenir (şeffaflık).
        started = any(str(x["kickoff"] or "") <= now for x in legs)
        if exclude_started and started:
            pass                          # yine de listeye alınır, işaretli
        out.append({
            "coupon_id": c[0], "agent": c[1], "type": c[2],
            "odds": float(c[3] or 1), "n_legs": len(legs),
            "created_at": c[5], "legs": legs,
            "already": c[0] in mine,
            "playable": not started,
            "why_not": "maç başladı — gerçekte oynanamaz" if started else "",
            "kickoff": min(str(x["kickoff"] or "") for x in legs),
        })
    out.sort(key=lambda x: (x["agent"], x["kickoff"]))
    return out


# ──────────────────────────────────────────────────────────────
# Kayıt (kopyalama)
# ──────────────────────────────────────────────────────────────

def _insert(conn, legs: list[dict], stake: float, ctype: str, reasoning: str) -> str:
    odds = 1.0
    for l in legs:
        odds *= float(l["odds"] or 1)
    cid = str(uuid.uuid4())
    now = _now()
    conn.execute(
        "INSERT INTO paper_coupons (coupon_id, portfolio_id, session_date, "
        "created_at, coupon_type, num_legs, combined_odds, stake, "
        "potential_return, status, model_version, reasoning) "
        "VALUES (?,?,?,?,?,?,?,?,?,'open',?,?)",
        (cid, PID, now[:10], now, ctype, len(legs), round(odds, 3), stake,
         round(stake * odds, 2), "OPUS5_MANUEL", reasoning))
    for l in legs:
        conn.execute(
            "INSERT INTO paper_bets (bet_id, coupon_id, portfolio_id, match_id, "
            "league, home_team, away_team, kickoff_utc, market, pick, odds, "
            "implied_prob, status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,'open')",
            (str(uuid.uuid4()), cid, PID, l["match_id"], l.get("league"),
             l.get("home"), l.get("away"), l.get("kickoff"), l["market"],
             l["pick"], float(l["odds"] or 1),
             1.0 / float(l["odds"] or 1)))
    return cid


def play_coupon(source_coupon_id: str, stake: float = DEFAULT_STAKE) -> dict:
    """Bir ajanın kuponunu AYNEN oynadım olarak kaydet."""
    ensure_portfolio()
    conn = db.connect()
    try:
        c = conn.execute(
            "SELECT portfolio_id, coupon_type, combined_odds FROM paper_coupons "
            "WHERE coupon_id=?", (source_coupon_id,)).fetchone()
        if not c:
            return {"ok": False, "msg": "Kupon bulunamadı."}
        dup = conn.execute(
            "SELECT COUNT(*) FROM paper_coupons WHERE portfolio_id=? "
            "AND reasoning LIKE ?", (PID, f"%src={source_coupon_id}%")).fetchone()[0]
        if dup:
            return {"ok": False, "msg": "Bu kupon zaten defterinde."}
        legs = [dict(zip(("match_id", "home", "away", "league", "kickoff",
                          "market", "pick", "odds"), r)) for r in conn.execute(
            "SELECT match_id, home_team, away_team, league, kickoff_utc, "
            "market, pick, odds FROM paper_bets WHERE coupon_id=?",
            (source_coupon_id,)).fetchall()]
        if not legs:
            return {"ok": False, "msg": "Kuponun ayakları okunamadı."}
        if any(str(l["kickoff"] or "") <= _now() for l in legs):
            return {"ok": False, "msg": "Maç başlamış — gerçekte oynanamazdı."}
        src_agent = c[0]
        cid = _insert(conn, legs, stake, f"M_{c[1]}",
                      f"Gerçekte oynandı · kaynak={src_agent} src={source_coupon_id}")
        conn.commit()
        return {"ok": True, "coupon_id": cid, "agent": src_agent,
                "odds": float(c[2] or 1), "legs": len(legs),
                "msg": f"Kaydedildi: {src_agent.split('_')[0]} kuponu, "
                       f"{stake:.0f} TL @ {float(c[2] or 1):.2f}"}
    except Exception as e:
        conn.rollback()
        return {"ok": False, "msg": f"Hata: {e}"}
    finally:
        conn.close()


def play_custom(bet_ids: list[str], stake: float = DEFAULT_STAKE) -> dict:
    """Farklı ajanların ayaklarından KENDİ kuponunu kur (sepet)."""
    ensure_portfolio()
    if not bet_ids:
        return {"ok": False, "msg": "Sepet boş."}
    conn = db.connect()
    try:
        qs = ",".join("?" for _ in bet_ids)
        rows = conn.execute(
            "SELECT match_id, home_team, away_team, league, kickoff_utc, market, "
            f"pick, odds FROM paper_bets WHERE bet_id IN ({qs})", tuple(bet_ids)).fetchall()
        legs, seen = [], set()
        for r in rows:
            key = (r[0], r[5], r[6])
            if key in seen:
                continue
            seen.add(key)
            legs.append(dict(zip(("match_id", "home", "away", "league",
                                  "kickoff", "market", "pick", "odds"), r)))
        if not legs:
            return {"ok": False, "msg": "Ayak bulunamadı."}
        if any(str(l["kickoff"] or "") <= _now() for l in legs):
            return {"ok": False, "msg": "Sepette başlamış maç var."}
        if len({l["match_id"] for l in legs}) != len(legs):
            return {"ok": False, "msg": "Aynı maçtan iki ayak olamaz."}
        ctype = {1: "M_TEK", 2: "M_K2", 3: "M_K3"}.get(len(legs), f"M_K{len(legs)}")
        cid = _insert(conn, legs, stake, ctype, "Gerçekte oynandı · kaynak=SEPET")
        conn.commit()
        odds = 1.0
        for l in legs:
            odds *= float(l["odds"] or 1)
        return {"ok": True, "coupon_id": cid, "legs": len(legs), "odds": odds,
                "msg": f"Sepet kuponu kaydedildi: {len(legs)} ayak @ {odds:.2f}"}
    except Exception as e:
        conn.rollback()
        return {"ok": False, "msg": f"Hata: {e}"}
    finally:
        conn.close()


def undo(coupon_id: str) -> dict:
    """Yanlış kaydı geri al — YALNIZ henüz sonuçlanmamış kuponlar."""
    conn = db.connect()
    try:
        r = conn.execute("SELECT status FROM paper_coupons WHERE coupon_id=? "
                         "AND portfolio_id=?", (coupon_id, PID)).fetchone()
        if not r:
            return {"ok": False, "msg": "Kupon defterinde yok."}
        if r[0] != "open":
            return {"ok": False, "msg": "Sonuçlanmış kupon silinemez (arşiv bütünlüğü)."}
        conn.execute("DELETE FROM paper_bets WHERE coupon_id=?", (coupon_id,))
        conn.execute("DELETE FROM paper_coupons WHERE coupon_id=?", (coupon_id,))
        conn.commit()
        return {"ok": True, "msg": "Kayıt geri alındı."}
    except Exception as e:
        conn.rollback()
        return {"ok": False, "msg": f"Hata: {e}"}
    finally:
        conn.close()


# ──────────────────────────────────────────────────────────────
# Karne
# ──────────────────────────────────────────────────────────────

def stats() -> dict:
    conn = db.connect()
    try:
        rows = conn.execute(
            "SELECT status, combined_odds, stake, COALESCE(pnl,0), reasoning "
            "FROM paper_coupons WHERE portfolio_id=?", (PID,)).fetchall()
        dec = [r for r in rows if r[0] in ("won", "lost")]
        n = len(dec)
        out = {"total": len(rows), "open": sum(1 for r in rows if r[0] == "open"),
               "n": n, "won": sum(1 for r in dec if r[0] == "won")}
        if n:
            out["hit"] = out["won"] / n * 100
            out["pnl"] = sum(float(r[3]) for r in dec)
            out["staked"] = sum(float(r[2] or 0) for r in dec)
            out["roi"] = out["pnl"] / out["staked"] * 100 if out["staked"] else 0
            out["flat_roi"] = sum(((float(r[1] or 1) - 1) if r[0] == "won" else -1)
                                  for r in dec) / n * 100
            out["avg_odds"] = sum(float(r[1] or 1) for r in dec) / n
        # kaynak ajan dağılımı
        src: dict = {}
        for r in rows:
            t = str(r[4] or "")
            a = t.split("kaynak=")[1].split()[0] if "kaynak=" in t else "?"
            d = src.setdefault(a, {"n": 0, "won": 0, "pnl": 0.0})
            d["n"] += 1
            if r[0] == "won":
                d["won"] += 1
            d["pnl"] += float(r[3] or 0)
        out["sources"] = src
        return out
    finally:
        conn.close()


if __name__ == "__main__":
    ensure_portfolio()
    if "--stats" in sys.argv:
        s = stats()
        print(f"OPUS 5: {s['total']} kupon ({s['open']} açık, {s['n']} karar)")
        if s.get("n"):
            print(f"  isabet %{s['hit']:.1f} · PnL {s['pnl']:+.0f} TL · "
                  f"ROI {s['roi']:+.1f}% · flat {s['flat_roi']:+.1f}%")
        for a, d in sorted(s["sources"].items(), key=lambda x: -x[1]["n"]):
            print(f"  kaynak {a:14s} n={d['n']:3d} kazanan={d['won']:3d} "
                  f"pnl={d['pnl']:+.0f}")
    else:
        for c in open_coupons()[:25]:
            legs = " + ".join(f"{l['home'][:12]} {l['market']}:{l['pick']}@{l['odds']:.2f}"
                              for l in c["legs"])
            print(f"[{c['agent'].split('_')[0]:9s}] {c['type']:6s} "
                  f"@{c['odds']:.2f} → {legs}")
