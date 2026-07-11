"""
🛡 AGENT: TEMKİNLİ — kanıta dayalı, düşük riskli ikinci ajan
============================================================
Kasa: 1.000 TL · Hedef: 2.500 TL / 1 ay (kullanıcı hedefi — agresif; ajan
kaybetmemeyi önceler, hedefe ancak seri isabetle yaklaşır) · Stop: -%15.

KURALLAR — 227 karar bahisin analizi (2026-07) ile belirlendi:
  ✅ OYNAR : KG_YOK  (%80 isabet, +1.3% flatROI — tek pozitif pazar)
             UST_25  (%77 isabet, +0.4%)
             GUCLU_FAV 1X2 (%79 isabet, -1.8% ≈ başabaş; sadece mp>=0.72)
  ⛔ YASAK : KG_VAR  (%60 isabet, -22.5% ROI, n=68 — ana kayıp kaynağı)
             ALT_25  (-10.6%), zayıf FAV (mp<0.70: -6.1%)
  🎯 AYAK  : 1-2 ayak 10/10 kazandı (+%28..+%44); 3 ayak %41/-27.2%.
             → MBS=1 maçta TEK öncelik; mecbursa TEK adet, sıkı-filtreli 3'lü.
  💰 STAKE : TEK %5, K3 %4 (dönem-başı kasaya göre) · günde MAX 2 kupon ·
             açık kupon MAX 4 · kombine oran tavanı 2.60.
  🧊 FREN  : son 3 settle üst üste kayıpsa → PAS (loss-streak molası, T16).

PAS bir sonuçtur: uygun sinyal yoksa TEMKİNLİ oynamaz.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import db
from paper_engine import PaperEngine

PID = "TEMKINLI_V1"
INITIAL = 1000.0
TARGET_PCT = 1.50          # 1.000 → 2.500 (kullanıcı hedefi)
STOP_PCT = -0.15
MAX_DAILY = 2
MAX_OPEN = 4
MAX_COMBO_ODDS = 2.60
ALLOWED = {"KG_YOK", "UST_25"}          # sinyal adları (1X2 ayrı kural)
STRONG_FAV_MIN = 0.72                    # 1X2 için asgari piyasa olasılığı


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()


def ensure_portfolio() -> None:
    """TEMKINLI_V1 portföyünü idempotent oluştur (SQLite + PG)."""
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
            (PID, "TEMKİNLİ (kanıta dayalı düşük risk)", INITIAL, INITIAL,
             INITIAL, "temkinli_v1",
             "Kurallar: KG_YOK+UST_25+GUCLU_FAV(>=0.72); KG_VAR yasak; "
             "TEK öncelik; gün max 2; oran tavan 2.60; stop -15%.",
             now, now),
        )
        conn.commit()
        # Dönem alanları (kolonlar varsa) — hedef %150 / stop -%15
        try:
            conn.execute(
                "UPDATE paper_portfolio SET period_start_bankroll=?, "
                "period_start_date=?, period_status='active', "
                "monthly_target_pct=?, stop_loss_pct=?, locked_profit=0, "
                "completed_periods=0 WHERE portfolio_id=? "
                "AND period_start_date IS NULL",
                (INITIAL, now, TARGET_PCT, STOP_PCT, PID),
            )
            conn.commit()
        except Exception:
            conn.rollback()
    finally:
        conn.close()


def _loss_streak(conn, n: int = 3) -> bool:
    rows = conn.execute(
        "SELECT status FROM paper_coupons WHERE portfolio_id=? "
        "AND status IN ('won','lost') ORDER BY settled_at DESC LIMIT ?",
        (PID, n)).fetchall()
    return len(rows) == n and all(r[0] == "lost" for r in rows)


def _mbs(m: dict) -> int:
    v = m.get("mbs")
    try:
        return int(v) if v else 3
    except Exception:
        return 3


def build_coupons(eng: PaperEngine) -> list[dict]:
    """Kanıt-kurallı kupon üretimi. PAS = boş liste."""
    conn = db.connect()
    try:
        if _loss_streak(conn):
            print("[TEMKINLI] 3 ardisik kayip -> PAS (loss-streak molasi)")
            return []
        today = _now()[:10]
        n_today = conn.execute(
            "SELECT COUNT(*) FROM paper_coupons WHERE portfolio_id=? "
            "AND session_date=?", (PID, today)).fetchone()[0]
        n_open = conn.execute(
            "SELECT COUNT(*) FROM paper_coupons WHERE portfolio_id=? "
            "AND status='open'", (PID,)).fetchone()[0]
        if n_today >= MAX_DAILY or n_open >= MAX_OPEN:
            print(f"[TEMKINLI] limit (bugun {n_today}/{MAX_DAILY}, "
                  f"acik {n_open}/{MAX_OPEN}) -> PAS")
            return []
        rows = conn.execute(
            """
            SELECT * FROM matches_v2
            WHERE is_settled=0 AND kickoff_utc > ? AND closing_1 IS NOT NULL
              AND match_id NOT IN (
                  SELECT pb.match_id FROM paper_bets pb
                  JOIN paper_coupons pc ON pb.coupon_id=pc.coupon_id
                  WHERE pc.status='open' AND pb.match_id IS NOT NULL)
            ORDER BY kickoff_utc ASC LIMIT 200
            """, (_now(),)).fetchall()
        matches = [dict(r) for r in rows]
    finally:
        conn.close()

    per = eng.manage_period(PID)
    if not per["can_bet"]:
        print(f"[TEMKINLI] donem kilidi ({per['status']}) -> PAS")
        return []
    bankroll = per["period_start_bankroll"]

    # Sinyalleri topla ve KANIT-KURALLARLA filtrele
    picks: list[dict] = []
    for m in matches:
        try:
            sigs = eng.evaluate_match(m)
        except Exception:
            continue
        for s in sigs:
            s["_match"] = m
            sn = s.get("signal_name") or ""
            mkt = s.get("market") or ""
            mp = s.get("model_prob") or 0
            if mkt == "KG_VAR":                      # ⛔ yasak pazar
                continue
            if mkt == "1X2":
                if mp < STRONG_FAV_MIN:              # sadece çok güçlü favori
                    continue
            elif sn.split("_H2H")[0] not in ALLOWED and mkt not in ("KG_YOK", "UST_25"):
                continue
            if mp < 0.66 or (s.get("odds") or 0) < 1.18:
                continue
            picks.append(s)

    picks.sort(key=lambda x: x["model_prob"], reverse=True)
    coupons: list[dict] = []
    used: set = set()

    # 1) TEK (MBS=1) — en yüksek güvenli tekli (kanıt: 1 ayak 10/10)
    for s in picks:
        m = s["_match"]
        if _mbs(m) == 1 and m.get("match_id") not in used:
            stake = round(bankroll * 0.05, 2)
            coupons.append({
                "coupon_type": "T_TEK", "picks": [s], "stake": stake,
                "combined_odds": round(s["odds"], 3),
                "potential_return": round(stake * s["odds"], 2)})
            used.add(m.get("match_id"))
            break

    # 2) Gerekirse TEK adet sıkı-filtreli 3'lü (MBS>=3 dünyasında tek yol)
    if len(coupons) < MAX_DAILY:
        sel = []
        for s in picks:
            mid = s["_match"].get("match_id")
            if mid in used or any(p["_match"].get("match_id") == mid for p in sel):
                continue
            if _mbs(s["_match"]) > 3:
                continue
            trial = sel + [s]
            co = 1.0
            for p in trial:
                co *= p["odds"]
            if co > MAX_COMBO_ODDS:
                continue
            sel = trial
            if len(sel) == 3:
                break
        if len(sel) == 3:
            co = 1.0
            for p in sel:
                co *= p["odds"]
            stake = round(bankroll * 0.04, 2)
            coupons.append({
                "coupon_type": "T_K3_GUVENLI", "picks": sel, "stake": stake,
                "combined_odds": round(co, 3),
                "potential_return": round(stake * co, 2)})
            for p in sel:
                used.add(p["_match"].get("match_id"))

    return coupons[:MAX_DAILY]


def run(place: bool = True) -> list[str]:
    """Worker girişi: portföyü garanti et, kupon kur (varsa) ve yerleştir."""
    ensure_portfolio()
    eng = PaperEngine(PID)
    coupons = build_coupons(eng)
    if not coupons:
        print("[TEMKINLI] bugun uygun kanit-kurali sinyal yok -> PAS")
        return []
    for c in coupons:
        legs = ", ".join(
            f"{p['_match'].get('home_team','?')[:14]} {p['market']}:{p['pick']}@{p['odds']:.2f}"
            for p in c["picks"])
        print(f"[TEMKINLI] {c['coupon_type']} oran {c['combined_odds']:.2f} "
              f"stake {c['stake']:.0f} TL -> {legs}")
    if not place:
        return []
    ids = eng.place_coupons(coupons, dry_run=False)
    print(f"[TEMKINLI] {len(ids)} kupon yerlestirildi ({PID}).")
    return ids


if __name__ == "__main__":
    run(place="--place" in sys.argv)
