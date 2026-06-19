"""
SUPERPOWER SİNYAL — konfluans + tarihsel kanıt (gerekçeli)
==========================================================
DÜRÜST TASARIM. Sistemin model_prob'u BAĞIMSIZ TAHMİN DEĞİL — iddaa oranının
vig'siz halidir (= piyasanın kendi fiyatı). Dolayısıyla "favori = edge" YANLIŞ.

Gerçek edge ancak çizgide OLMAYAN bilgiden gelir. SUPERPOWER skoru bu yüzden
3 bileşeni harmanlar ve ORTOGONAL teyit + TARİHSEL kanıta ağırlık verir:

  1) Piyasa güveni (model_prob)   — ağırlık DÜŞÜK (tek başına edge değil)
  2) Ortogonal teyitler           — ağırlık YÜKSEK (çizgide olmayan bilgi):
       • SHARP money (oran hareketi)  • H2H geçmişi  • çoklu-pazar uyumu
  3) Tarihsel kanıt (journal/data) — bu sinyal tipi geçmişte kazandı mı / +CLV mi?

Her öneri GEREKÇELİDİR (reasons listesi). Tarihsel veri yoksa skor düşer
ve gerekçe "veri yetersiz" der (sezon arası dürüstlüğü).

Kupon YERLEŞTİRMEZ — sadece gerekçeli sinyal sunar.
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

# bileşen ağırlıkları — ortogonal + tarihsel baskın (piyasa güveni düşük)
W_CONV = 25.0
W_ORTH = 35.0
W_HIST = 40.0


def _base_name(sn: str) -> str:
    return (sn or "").replace("_H2H", "")


def signal_scorecard(portfolio_id: str = "PAPER_V1") -> dict:
    """Settle olmuş paper_bets'ten sinyal-tipi karnesi (journal/data temelli)."""
    conn = db.connect()
    try:
        rows = [dict(r) for r in conn.execute(
            "SELECT signal_name, status, clv FROM paper_bets "
            "WHERE portfolio_id=? AND status IN ('won','lost')",
            (portfolio_id,)).fetchall()]
    finally:
        conn.close()
    acc: dict = {}
    for r in rows:
        names = {r.get("signal_name") or "?", _base_name(r.get("signal_name"))}
        for k in names:
            d = acc.setdefault(k, {"n": 0, "won": 0, "clv_sum": 0.0, "clv_n": 0})
            d["n"] += 1
            d["won"] += 1 if r["status"] == "won" else 0
            if r.get("clv") is not None:
                d["clv_sum"] += r["clv"]
                d["clv_n"] += 1
    return {
        k: {
            "n": d["n"],
            "win_rate": (d["won"] / d["n"] if d["n"] else None),
            "mean_clv": (d["clv_sum"] / d["clv_n"] if d["clv_n"] else None),
        }
        for k, d in acc.items()
    }


def _score_signal(s: dict, n_markets: int, sc: dict) -> dict:
    reasons: list[str] = []
    confirmers = 0
    mp = s.get("model_prob") or 0.0
    odds = s.get("odds") or 0.0
    sn = s.get("signal_name") or ""

    # 1) Piyasa güveni — tek başına EDGE DEĞİL
    conv = max(0.0, min(1.0, (mp - 0.50) / 0.35))
    reasons.append(
        f"Piyasa olasılığı %{mp*100:.0f} @ {odds:.2f} — tek başına EDGE DEĞİL, "
        f"piyasanın kendi vig'siz fiyatı")

    # 2) Ortogonal teyitler — çizgide OLMAYAN bilgi
    if "SHARP" in sn:
        confirmers += 1
        reasons.append("⚡ Sharp money: kapanışta oran bu yöne belirgin düştü "
                       "(çizgide olmayan bilgi — gerçek sinyal)")
    if "_H2H" in sn or sn.startswith("KG_H2H"):
        confirmers += 1
        reasons.append("🔁 H2H teyit: geçmiş karşılaşmalar bu yönü destekliyor")
    if n_markets >= 2:
        confirmers += 1
        reasons.append(f"🎯 Çoklu-pazar uyumu: aynı maçta {n_markets} farklı pazar "
                       f"aynı anda sinyal veriyor")
    orth = min(1.0, confirmers / 2.0)

    # 3) Tarihsel kanıt (journal/data)
    h = sc.get(sn) or sc.get(_base_name(sn)) or {}
    hist = {"n": h.get("n"), "win_rate": h.get("win_rate"), "mean_clv": h.get("mean_clv")}
    hist_norm = 0.5
    hist_positive = False
    if h.get("n"):
        wr, clv = h.get("win_rate"), h.get("mean_clv")
        parts = [f"n={h['n']}"]
        if wr is not None:
            parts.append(f"isabet %{wr*100:.0f}")
        if clv is not None:
            parts.append(f"CLV {clv*100:+.1f}%")
        reasons.append("📈 Tarihsel kanıt: " + ", ".join(parts))
        if clv is not None:
            hist_norm = max(0.0, min(1.0, 0.5 + clv * 10))   # +%5 CLV → ~1.0
            hist_positive = clv > 0
        elif wr is not None:
            hist_norm = max(0.0, min(1.0, wr))
            hist_positive = wr > 0.5
    else:
        reasons.append("ℹ️ Tarihsel veri yetersiz — temkinli değerlendir "
                       "(sezon arası / az örneklem)")

    score = W_CONV * conv + W_ORTH * orth + W_HIST * hist_norm

    # TIER — SUPERPOWER sadece gerçek konfluansta
    if score >= 70 and (confirmers >= 2 or (confirmers >= 1 and hist_positive)):
        tier = "SUPERPOWER"
    elif score >= 52:
        tier = "GÜÇLÜ"
    else:
        tier = "İZLE"

    return {"score": score, "tier": tier, "reasons": reasons,
            "confirmers": confirmers, "hist": hist, "hist_positive": hist_positive}


def superpower_signals(limit: int = 8, portfolio_id: str = "PAPER_V1") -> list[dict]:
    """Yaklaşan (başlamamış) maçlar için gerekçeli SUPERPOWER sinyalleri."""
    eng = PaperEngine(portfolio_id)
    sc = signal_scorecard(portfolio_id)
    conn = db.connect()
    now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    try:
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM matches_v2 WHERE is_settled=0 AND kickoff_utc > ? "
            "AND closing_1 IS NOT NULL ORDER BY kickoff_utc ASC LIMIT 300",
            (now,)).fetchall()]
    finally:
        conn.close()

    cand: list[dict] = []
    for m in rows:
        try:
            sigs = eng.evaluate_match(m)
        except Exception:
            sigs = []
        if not sigs:
            continue
        n_markets = len(set(s["market"] for s in sigs))
        for s in sigs:
            comp = _score_signal(s, n_markets, sc)
            comp["_m"] = m
            comp["_s"] = s
            cand.append(comp)

    cand.sort(key=lambda x: x["score"], reverse=True)

    out: list[dict] = []
    for c in cand[:limit]:
        s, m = c["_s"], c["_m"]
        out.append({
            "score": round(c["score"], 1), "tier": c["tier"],
            "home": m.get("home_team"), "away": m.get("away_team"),
            "league": m.get("league_code"), "kickoff": m.get("kickoff_utc"),
            "market": s["market"], "pick": s["pick"], "odds": s["odds"],
            "model_prob": s["model_prob"], "edge": s["edge"],
            "signal_name": s["signal_name"],
            "confirmers": c["confirmers"], "hist": c["hist"],
            "reasons": c["reasons"],
        })
    return out


if __name__ == "__main__":
    sigs = superpower_signals()
    print(f"SUPERPOWER sinyalleri: {len(sigs)}\n")
    for x in sigs:
        print(f"[{x['tier']}] skor {x['score']}  {x['home']} v {x['away']} "
              f"[{x['league']}]  {x['market']}:{x['pick']} @{x['odds']:.2f}")
        for r in x["reasons"]:
            print("    - " + r)
        print()
