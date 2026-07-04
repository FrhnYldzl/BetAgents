"""Portföy sayaçlarını paper_coupons kaynağından authoritative yeniden hesapla.

Sayaçlar (total/won/bankroll...) settle sırasında artımlı güncellenir; artımlı
sayaçlar zamanla kayabilir (ör. void yolu, eski migration). Bu modül kaynak-
gerçekten (kupon satırları) yeniden türetir:
  - total_coupons = KARAR verilen kupon (won+lost; void HARİÇ — bahis hiç olmadı)
  - bankroll      = initial + Σpnl(won/lost)   (void pnl=0 → etkisiz)

auto_settle her settle sonrası çağırır → sayaçlar her zaman doğru.
CLI: python recompute_portfolio.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import db


def recompute(portfolio_id: str = "PAPER_V1", verbose: bool = True) -> dict:
    conn = db.connect()
    try:
        row = conn.execute(
            "SELECT initial_bankroll, peak_bankroll FROM paper_portfolio "
            "WHERE portfolio_id=?", (portfolio_id,)).fetchone()
        if row is None:
            return {}
        init = row[0] or 0.0
        peak0 = row[1]

        # Void kuponları normalize et: pnl=0, iade (push)
        conn.execute(
            "UPDATE paper_coupons SET pnl=0, actual_return=stake "
            "WHERE status='void' AND portfolio_id=?", (portfolio_id,))

        wl = conn.execute(
            "SELECT status, stake, actual_return, pnl FROM paper_coupons "
            "WHERE status IN ('won','lost') AND portfolio_id=?",
            (portfolio_id,)).fetchall()
        staked = sum((r["stake"] or 0) for r in wl)
        ret    = sum((r["actual_return"] or 0) for r in wl)
        pnl    = sum((r["pnl"] or 0) for r in wl)
        won    = sum(1 for r in wl if r["status"] == "won")
        played = len(wl)
        voids = conn.execute(
            "SELECT COUNT(*) FROM paper_coupons WHERE status='void' AND portfolio_id=?",
            (portfolio_id,)).fetchone()[0]

        # DİKKAT: kazanma durumu pb.STATUS'ta ('won'/'lost'/'void');
        # pb.result skor stringidir ("2-1") — eski script bunu karıştırıyordu.
        bets = conn.execute(
            "SELECT pb.status FROM paper_bets pb "
            "JOIN paper_coupons pc ON pb.coupon_id = pc.coupon_id "
            "WHERE pc.status IN ('won','lost') AND pc.portfolio_id=?",
            (portfolio_id,)).fetchall()
        total_bets = sum(1 for b in bets if b["status"] in ("won", "lost"))
        total_wins = sum(1 for b in bets if b["status"] == "won")

        new_bankroll = init + pnl
        peak = max(peak0 or init, new_bankroll)

        conn.execute(
            """
            UPDATE paper_portfolio SET
                current_bankroll=?, peak_bankroll=?,
                total_staked=?, total_return=?,
                total_coupons=?, won_coupons=?,
                total_bets=?, total_wins=?
            WHERE portfolio_id=?
            """,
            (new_bankroll, peak, staked, ret, played, won,
             total_bets, total_wins, portfolio_id))
        conn.commit()

        out = {"bankroll": round(new_bankroll, 2), "pnl": round(pnl, 2),
               "played": played, "won": won, "voids": voids,
               "bets": total_bets, "bet_wins": total_wins,
               "staked": round(staked, 1), "returned": round(ret, 1)}
        if verbose:
            print("=== AUTHORITATIVE PORTFÖY (paper_coupons kaynaklı) ===")
            print(f"  Başlangıç:   {init:.2f} TL   Settled PnL: {pnl:+.2f} TL")
            print(f"  Bankroll:    {new_bankroll:.2f} TL  (peak {peak:.2f})")
            print(f"  Kupon: {played} karar (kazanan {won})  ·  void {voids}")
            print(f"  Bet:   {total_bets} (kazanan {total_wins})  ·  "
                  f"staked {staked:.0f} → dönüş {ret:.0f}")
        return out
    finally:
        conn.close()


if __name__ == "__main__":
    recompute()
