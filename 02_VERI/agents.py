"""
🤖 AGENT LİGİ — profil-tabanlı çoklu ajan motoru
================================================
Üç ajan, AYNI para (1.000 TL), AYNI dönem (1 ay), FARKLI karakter:

  🛡 TEMKİNLİ — düşük risk. Sadece kanıtla pozitif/başabaş pazarlar,
                TEK öncelik, dar oran tavanı, erken PAS.
  📋 MEMUR    — orta risk. Aynı kanıt seti + biraz gevşek eşikler,
                ALT 2.5'e izin, orta oran tavanı.
  🎯 AVCI     — risk sever ama KAZANMA odaklı. SHARP (oran hareketi)
                önceliği, yüksek oran bandı (1.30+), geniş kombine tavanı.
                KG_VAR yine yasak (kanıt: -%22.5 — risk almak ayrı,
                bilerek kaybetmek ayrı).

Ortak kanıt tabanı (227 karar bahis, 2026-07):
  KG_YOK %80/+1.3 · UST_25 %77/+0.4 · GUCLU_FAV %79/-1.8 · KG_VAR %60/-22.5
  1-2 ayak 10/10 kazanç vs 3 ayak %41/-27.2

Worker: agents.run_all() — her profil kendi kasasında kupon kurar.
Settle/recompute: auto_settle zaten TÜM portföyleri dolaşıyor.
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

INITIAL = 1000.0
TARGET_PCT = 1.50            # hepsi için 1.000 → 2.500 (adil kıyas)

PROFILES: dict[str, dict] = {
    "TEMKINLI_V1": {
        "name": "TEMKİNLİ (düşük risk)",
        "stop_pct": -0.15,
        "markets": {"KG_YOK", "UST_25"},   # + 1X2 (fav_min ile)
        "fav_min": 0.72,                    # 1X2 asgari piyasa olasılığı
        "min_mp": 0.66, "min_odds": 1.18,
        "combo_cap": 2.60, "max_daily": 2, "max_open": 4,
        "max_tek": 1, "loss_streak": 3,
        "tek_stake": 0.05, "k3_stake": 0.04,
        "sort": "safety",                   # model_prob desc
    },
    "MEMUR_V1": {
        "name": "MEMUR (orta risk)",
        "stop_pct": -0.20,
        "markets": {"KG_YOK", "UST_25", "ALT_25"},
        "fav_min": 0.66,
        "min_mp": 0.62, "min_odds": 1.22,
        "combo_cap": 3.20, "max_daily": 2, "max_open": 5,
        "max_tek": 1, "loss_streak": 4,
        "tek_stake": 0.05, "k3_stake": 0.04,
        "sort": "score",                    # signal_score desc
    },
    "AVCI_V1": {
        "name": "AVCI (risk sever, kazanma odaklı)",
        "stop_pct": -0.25,
        "markets": {"KG_YOK", "UST_25", "ALT_25"},
        "fav_min": 0.58,
        "min_mp": 0.55, "min_odds": 1.30,   # yüksek oran bandı (1.35-1.55 en az kötüydü)
        "combo_cap": 4.50, "max_daily": 3, "max_open": 6,
        "max_tek": 2, "loss_streak": 5,
        "tek_stake": 0.06, "k3_stake": 0.05,
        "sort": "hunt",                     # SHARP > edge > oran
    },
    # ── MODEL-AJANLARI: bağımsız Poisson gol modeli (independent_model) ──
    "HOCA_V1": {
        # ÇİFT-ONAY hipotezi: model + piyasa AYNI fikirdeyse oyna.
        # Backtest dersi: modelin doğru kullanımı teyit, tahmin değil.
        "name": "HOCA (Poisson çift-onay)",
        "stop_pct": -0.15,
        "markets": {"KG_YOK", "UST_25", "ALT_25"},
        "fav_min": 0.62,
        "min_mp": 0.62, "min_odds": 1.22,
        "combo_cap": 2.80, "max_daily": 2, "max_open": 4,
        "max_tek": 1, "loss_streak": 3,
        "tek_stake": 0.05, "k3_stake": 0.04,
        "sort": "safety",
        "mode": "confirm", "confirm_max_dev": 0.05,
    },
    "SIMYACI_V1": {
        # DEĞER hipotezi (KONTROL DENEYİ): model piyasadan >= +6p yüksek
        # dediğinde oyna. Backtest -%8 dedi — canlı kontrol grubu; kazanırsa
        # hipotez ayağa kalkar, kaybederse kanıt pekişir. Küçük stake.
        "name": "SİMYACI (model-değer deneyi)",
        "stop_pct": -0.25,
        "markets": {"KG_YOK", "UST_25", "ALT_25"},
        "fav_min": 0.50,
        "min_mp": 0.50, "min_odds": 1.40,
        "combo_cap": 4.00, "max_daily": 2, "max_open": 4,
        "max_tek": 2, "loss_streak": 4,
        "tek_stake": 0.04, "k3_stake": 0.03,
        "sort": "value",
        "mode": "value", "value_min_edge": 0.06,
    },
    # ── 😴 SEZON AJANLARI: kayıtlı ama UYKUDA (Ağustos'ta aktive edilecek) ──
    # MODEL_REGISTRY'de 13 model var; iki amiral gemisi burada ajan olarak
    # açıldı ki UNUTULMASIN. dormant=True → kasa hazır, kupon OYNAMAZ.
    # Aktivasyon (Ağustos): dormant kaldır + lig eşleme (T1/E0/SP1...) +
    # model sinyal hattını bağla. Alt-modeller (MONOVOX/DUOVOX/BTTS-*/OU25-*)
    # aktivasyonda filtre/bacak olarak bunlara bağlanır.
    "TRIVOX_V1": {
        "name": "TRIVOX (T1 uzmanı — sezon bekliyor)",
        "stop_pct": -0.15, "dormant": True,
        "markets": {"KG_YOK", "UST_25"}, "fav_min": 0.72,
        "min_mp": 0.66, "min_odds": 1.20,
        "combo_cap": 3.00, "max_daily": 2, "max_open": 4,
        "max_tek": 1, "loss_streak": 3,
        "tek_stake": 0.05, "k3_stake": 0.04, "sort": "safety",
    },
    "EUVOX_V1": {
        "name": "EUVOX (Avrupa DC — sezon bekliyor)",
        "stop_pct": -0.15, "dormant": True,
        "markets": {"KG_YOK", "UST_25", "ALT_25"}, "fav_min": 0.68,
        "min_mp": 0.64, "min_odds": 1.22,
        "combo_cap": 3.00, "max_daily": 2, "max_open": 4,
        "max_tek": 1, "loss_streak": 3,
        "tek_stake": 0.05, "k3_stake": 0.04, "sort": "safety",
    },
}

# Bağımsız model rating önbelleği (run_all içinde 1 kez kurulur)
_RATINGS = {"ts": None, "obj": None}


def _get_ratings():
    from datetime import datetime as _dt
    import independent_model as im
    now = _dt.utcnow()
    if _RATINGS["obj"] is not None and _RATINGS["ts"] is not None \
            and (now - _RATINGS["ts"]).total_seconds() < 600:
        return _RATINGS["obj"]
    _RATINGS["obj"] = im.build_current_ratings()
    _RATINGS["ts"] = now
    return _RATINGS["obj"]


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()


def ensure_portfolio(pid: str) -> None:
    prof = PROFILES[pid]
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
            (pid, prof["name"], INITIAL, INITIAL, INITIAL,
             pid.lower(), f"Agent ligi — {prof['name']}", now, now))
        conn.commit()
        try:
            conn.execute(
                "UPDATE paper_portfolio SET period_start_bankroll=?, "
                "period_start_date=?, period_status='active', "
                "monthly_target_pct=?, stop_loss_pct=?, locked_profit=0, "
                "completed_periods=0 WHERE portfolio_id=? "
                "AND period_start_date IS NULL",
                (INITIAL, now, TARGET_PCT, prof["stop_pct"], pid))
            conn.commit()
        except Exception:
            conn.rollback()
    finally:
        conn.close()


def _mbs(m: dict) -> int:
    v = m.get("mbs")
    try:
        return int(v) if v else 3
    except Exception:
        return 3


def _loss_streak(conn, pid: str, n: int) -> bool:
    rows = conn.execute(
        "SELECT status FROM paper_coupons WHERE portfolio_id=? "
        "AND status IN ('won','lost') ORDER BY settled_at DESC LIMIT ?",
        (pid, n)).fetchall()
    return len(rows) == n and all(r[0] == "lost" for r in rows)


def _sort_key(prof: dict):
    mode = prof["sort"]
    if mode == "hunt":
        return lambda s: (1 if "SHARP" in (s.get("signal_name") or "") else 0,
                          s.get("edge") or -9, s.get("odds") or 0)
    if mode == "score":
        return lambda s: (s.get("signal_score") or 0, s.get("model_prob") or 0)
    if mode == "value":
        return lambda s: (s.get("_dev") or -9, s.get("odds") or 0)
    return lambda s: (s.get("model_prob") or 0, s.get("signal_score") or 0)


def build_coupons(pid: str, eng: PaperEngine) -> list[dict]:
    prof = PROFILES[pid]
    tag = f"[{pid.split('_')[0]}]"
    if prof.get("dormant"):
        print(f"{tag} 😴 sezon bekliyor (Agustos'ta aktive edilecek) -> PAS")
        return []
    conn = db.connect()
    try:
        if _loss_streak(conn, pid, prof["loss_streak"]):
            print(f"{tag} {prof['loss_streak']} ardisik kayip -> PAS")
            return []
        today = _now()[:10]
        n_today = conn.execute(
            "SELECT COUNT(*) FROM paper_coupons WHERE portfolio_id=? AND session_date=?",
            (pid, today)).fetchone()[0]
        n_open = conn.execute(
            "SELECT COUNT(*) FROM paper_coupons WHERE portfolio_id=? AND status='open'",
            (pid,)).fetchone()[0]
        if n_today >= prof["max_daily"] or n_open >= prof["max_open"]:
            print(f"{tag} limit (bugun {n_today}/{prof['max_daily']}, "
                  f"acik {n_open}/{prof['max_open']}) -> PAS")
            return []
        rows = conn.execute(
            """
            SELECT * FROM matches_v2
            WHERE is_settled=0 AND kickoff_utc > ? AND closing_1 IS NOT NULL
              AND match_id NOT IN (
                  SELECT pb.match_id FROM paper_bets pb
                  JOIN paper_coupons pc ON pb.coupon_id=pc.coupon_id
                  WHERE pc.status='open' AND pc.portfolio_id=?
                    AND pb.match_id IS NOT NULL)
            ORDER BY kickoff_utc ASC LIMIT 200
            """, (_now(), pid)).fetchall()
        matches = [dict(r) for r in rows]
    finally:
        conn.close()

    per = eng.manage_period(pid)
    if not per["can_bet"]:
        print(f"{tag} donem kilidi ({per['status']}) -> PAS")
        return []
    bankroll = per["period_start_bankroll"]

    # Model modu (HOCA/SIMYACI): bağımsız Poisson gol modelini yükle
    mode = prof.get("mode")
    ratings = None
    if mode in ("confirm", "value"):
        try:
            ratings = _get_ratings()
        except Exception as e:
            print(f"{tag} model yuklenemedi ({e}) -> PAS")
            return []
    import independent_model as im
    _probs_cache: dict = {}

    picks: list[dict] = []
    for m in matches:
        try:
            sigs = eng.evaluate_match(m)
        except Exception:
            continue
        for s in sigs:
            s["_match"] = m
            mkt = s.get("market") or ""
            mp = s.get("model_prob") or 0
            if mkt == "KG_VAR":                    # tüm ajanlarda yasak (kanıt)
                continue
            if mkt == "1X2":
                if mp < prof["fav_min"]:
                    continue
            elif mkt not in prof["markets"]:
                continue
            if mp < prof["min_mp"] or (s.get("odds") or 0) < prof["min_odds"]:
                continue
            # ── MODEL FİLTRESİ (HOCA=çift-onay · SIMYACI=değer) ──
            if ratings is not None:
                mid = m.get("match_id")
                if mid not in _probs_cache:
                    try:
                        _probs_cache[mid] = ratings.predict(m)
                    except Exception:
                        _probs_cache[mid] = None
                ip = im.model_prob_for(_probs_cache[mid], mkt, s.get("pick"))
                if ip is None:                      # ikinci görüş yoksa oynamaz
                    continue
                dev = ip - mp
                s["_dev"] = dev
                if mode == "confirm" and abs(dev) > prof["confirm_max_dev"]:
                    continue
                if mode == "value" and dev < prof["value_min_edge"]:
                    continue
            picks.append(s)

    picks.sort(key=_sort_key(prof), reverse=True)
    coupons: list[dict] = []
    used: set = set()
    slots = prof["max_daily"] - 0

    # 1) TEK'ler (MBS=1) — kanıt: 1-2 ayak ezici üstün
    n_tek = 0
    for s in picks:
        if len(coupons) >= slots or n_tek >= prof["max_tek"]:
            break
        m = s["_match"]
        if _mbs(m) != 1 or m.get("match_id") in used:
            continue
        stake = round(bankroll * prof["tek_stake"], 2)
        coupons.append({
            "coupon_type": "A_TEK", "picks": [s], "stake": stake,
            "combined_odds": round(s["odds"], 3),
            "potential_return": round(stake * s["odds"], 2)})
        used.add(m.get("match_id"))
        n_tek += 1

    # 2) Kalan slotlara sıkı-filtreli 3'lüler (kombine tavanlı)
    while len(coupons) < slots:
        sel: list[dict] = []
        for s in picks:
            mid = s["_match"].get("match_id")
            if mid in used or any(p["_match"].get("match_id") == mid for p in sel):
                continue
            if _mbs(s["_match"]) > 3:
                continue
            co = 1.0
            for p in sel + [s]:
                co *= p["odds"]
            if co > prof["combo_cap"]:
                continue
            sel.append(s)
            if len(sel) == 3:
                break
        if len(sel) < 3:
            break
        co = 1.0
        for p in sel:
            co *= p["odds"]
        stake = round(bankroll * prof["k3_stake"], 2)
        coupons.append({
            "coupon_type": "A_K3", "picks": sel, "stake": stake,
            "combined_odds": round(co, 3),
            "potential_return": round(stake * co, 2)})
        for p in sel:
            used.add(p["_match"].get("match_id"))

    return coupons[:slots]


def run_profile(pid: str, place: bool = True) -> list[str]:
    ensure_portfolio(pid)
    eng = PaperEngine(pid)
    coupons = build_coupons(pid, eng)
    tag = f"[{pid.split('_')[0]}]"
    if not coupons:
        print(f"{tag} uygun sinyal yok -> PAS")
        return []
    for c in coupons:
        legs = ", ".join(
            f"{p['_match'].get('home_team','?')[:14]} {p['market']}:{p['pick']}@{p['odds']:.2f}"
            for p in c["picks"])
        print(f"{tag} {c['coupon_type']} oran {c['combined_odds']:.2f} "
              f"stake {c['stake']:.0f} TL -> {legs}")
    if not place:
        return []
    ids = eng.place_coupons(coupons, dry_run=False)
    print(f"{tag} {len(ids)} kupon yerlestirildi.")
    return ids


def run_all(place: bool = True) -> dict:
    out = {}
    for pid in PROFILES:
        try:
            out[pid] = run_profile(pid, place=place)
        except Exception as e:
            print(f"[{pid}] HATA: {e}")
            out[pid] = []
    return out


if __name__ == "__main__":
    run_all(place="--place" in sys.argv)
