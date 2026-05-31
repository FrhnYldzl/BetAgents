"""Portföy sayaçlarını paper_coupons kaynağından authoritative yeniden hesapla."""
import sqlite3, sys
sys.stdout.reconfigure(encoding="utf-8")
conn = sqlite3.connect("bahis_agent.db")
conn.row_factory = sqlite3.Row

init = conn.execute("SELECT initial_bankroll FROM paper_portfolio WHERE portfolio_id='PAPER_V1'").fetchone()[0]

# Void kuponları temizle: pnl=0, actual_return=stake (push/iade)
conn.execute("UPDATE paper_coupons SET pnl=0, actual_return=stake WHERE status='void'")
conn.commit()

# Staked/return SADECE won+lost (void = bahis hiç olmadı, hariç)
wl = conn.execute("""
    SELECT status, stake, actual_return, pnl
    FROM paper_coupons WHERE status IN ('won','lost')
""").fetchall()
staked = sum((r["stake"] or 0) for r in wl)
ret    = sum((r["actual_return"] or 0) for r in wl)
pnl    = sum((r["pnl"] or 0) for r in wl)
won    = sum(1 for r in wl if r["status"] == "won")
played = len(wl)
voids  = conn.execute("SELECT COUNT(*) FROM paper_coupons WHERE status='void'").fetchone()[0]

# Bet sayaçları (sadece won/lost kuponlardaki ayaklar)
bets = conn.execute("""
    SELECT pb.result FROM paper_bets pb
    JOIN paper_coupons pc ON pb.coupon_id = pc.coupon_id
    WHERE pc.status IN ('won','lost')
""").fetchall()
total_bets = sum(1 for b in bets if b["result"] not in (None, "", "void"))
total_wins = sum(1 for b in bets if b["result"] == "won")

new_bankroll = init + pnl
peak = conn.execute("SELECT peak_bankroll FROM paper_portfolio WHERE portfolio_id='PAPER_V1'").fetchone()[0]
peak = max(peak or init, new_bankroll)

conn.execute("""
    UPDATE paper_portfolio SET
        current_bankroll=?, peak_bankroll=?,
        total_staked=?, total_return=?,
        total_coupons=?, won_coupons=?,
        total_bets=?, total_wins=?
    WHERE portfolio_id='PAPER_V1'
""", (new_bankroll, peak, staked, ret, played, won, total_bets, total_wins))
conn.commit()

print("=== AUTHORITATIVE PORTFÖY (paper_coupons kaynaklı) ===")
print(f"  Başlangıç:     {init:.2f} TL")
print(f"  Settled PnL:   {pnl:+.2f} TL")
print(f"  Bankroll:      {new_bankroll:.2f} TL")
print(f"  Staked: {staked:.0f}  Return: {ret:.0f}")
print(f"  Oynanan: {played} kupon (kazanan: {won})  Void: {voids}")
print(f"  Bet: {total_bets} (kazanan: {total_wins})")
print(f"  Tutarlılık: {'OK' if abs(new_bankroll-(init+pnl))<0.01 else 'HATA'}")
conn.close()
