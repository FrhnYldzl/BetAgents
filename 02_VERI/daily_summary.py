"""Quick daily summary — run from CLI."""
import sqlite3, sys
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")
conn = sqlite3.connect("bahis_agent.db")
conn.row_factory = sqlite3.Row

now_utc = datetime.utcnow()
fmt = now_utc.strftime("%Y-%m-%d %H:%M")
print("=== BUGUNUN KUPONU OZETI ===")
print("Zaman (UTC):", fmt)
print()

coupons = conn.execute("""
    SELECT coupon_type, combined_odds, stake, potential_return
    FROM paper_coupons
    WHERE portfolio_id='PAPER_V1' AND status='open'
    ORDER BY created_at DESC
""").fetchall()

total_stake = 0
total_potential = 0
for c in coupons:
    ctype = c["coupon_type"]
    odds  = c["combined_odds"]
    stk   = c["stake"] or 0
    pot   = c["potential_return"] or 0
    total_stake += stk
    total_potential += pot
    print(f"  {ctype:15} | {odds:.3f}x | Stake:{stk:.0f} TL | Getiri:{pot:.0f} TL")

print()
pct = (total_potential - total_stake) / total_stake * 100 if total_stake else 0
print(f"  Toplam stake    : {total_stake:.0f} TL")
print(f"  Toplam potansiyel: {total_potential:.0f} TL  (+{pct:.1f}%)")
print()

print("=== BUGUNUN MACLARI (is_settled=0, May 29) ===")
rows = conn.execute("""
    SELECT home_team, away_team, kickoff_utc, league_code,
           closing_1, closing_X, closing_2
    FROM matches_v2
    WHERE is_settled=0
      AND kickoff_utc >= '2026-05-29'
      AND kickoff_utc < '2026-05-30'
    ORDER BY kickoff_utc
""").fetchall()

print(len(rows), "mac:")
for m in rows:
    ko = (m["kickoff_utc"] or "")[:16].replace("T", " ")
    h = m["home_team"]; a = m["away_team"]
    o1 = m["closing_1"]; ox = m["closing_X"]; o2 = m["closing_2"]
    print(f"  {ko}  {h} vs {a}  [1:{o1} X:{ox} 2:{o2}]")

conn.close()
