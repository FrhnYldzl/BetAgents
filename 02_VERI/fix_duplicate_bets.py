"""
🔧 ÇİFT BAHİS TEMİZLİĞİ (tek seferlik veri düzeltmesi)
=======================================================
Hata: fade (TERS) ve popular (POPÜLER) modları kendi aday kaynağını
kullandığı için "bu maçta zaten açık pozisyonum var" filtresini atlıyordu.
Sonuç: aynı bahis günlerce yeniden kuruldu (Ferencvaros KG_YOK 3 kez,
Barcelona 2 kez...). Kazanan bir tekrar, karneyi 3 kat şişiriyordu.

Düzeltme ilkesi: SİLMEK YOK. Fazladan kayıtlar `void` (iade) yapılır —
satır arşivde kalır, ama sayaçlara ve orana girmez (recompute yalnız
won/lost sayar). Her portföyün journal'ına ne yapıldığı yazılır.

Kural: her (portföy, maç, pazar, seçim) üçlüsünün EN ERKEN kuponu geçerli,
sonrakiler iade. Sadece TEK ayaklı kuponlarda uygulanır (kombine kuponda
ayak kesişimi normaldir).

    python fix_duplicate_bets.py --dry     # sadece raporla
    python fix_duplicate_bets.py           # uygula
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import db


def run(dry: bool = False) -> None:
    conn = db.connect()
    try:
        rows = conn.execute(
            "SELECT pc.coupon_id, pc.portfolio_id, pc.status, pc.created_at, "
            "pc.combined_odds, COUNT(pb.bet_id) nlegs, "
            "MIN(pb.match_id) mid, MIN(pb.market) mk, MIN(pb.pick) pk "
            "FROM paper_coupons pc JOIN paper_bets pb ON pb.coupon_id=pc.coupon_id "
            "GROUP BY pc.coupon_id, pc.portfolio_id, pc.status, pc.created_at, "
            "pc.combined_odds").fetchall()
        singles = [r for r in rows if r[5] == 1 and r[2] in ("open", "won", "lost")]
        singles.sort(key=lambda r: str(r[3]))
        seen, dupes = set(), []
        for r in singles:
            key = (r[1], r[6], r[7], r[8])
            if key in seen:
                dupes.append(r)
            else:
                seen.add(key)
        if not dupes:
            print("✅ tekrarlanan bahis yok.")
            return
        by_pid: dict = {}
        for d in dupes:
            by_pid.setdefault(d[1], []).append(d)
        print(f"🔧 {len(dupes)} fazladan kupon bulundu:")
        for pid, lst in by_pid.items():
            w = sum(1 for x in lst if x[2] == "won")
            o = sum(1 for x in lst if x[2] == "open")
            print(f"   {pid:12s} {len(lst)} adet (kazanan {w}, açık {o})")
        if dry:
            print("\n(dry-run — hiçbir şey değiştirilmedi)")
            return

        now = datetime.utcnow().isoformat()
        for pid, lst in by_pid.items():
            for d in lst:
                conn.execute(
                    "UPDATE paper_coupons SET status='void', pnl=0, "
                    "actual_return=stake, settled_at=COALESCE(settled_at,?), "
                    "reasoning=COALESCE(reasoning,'') || ' | ÇİFT KAYIT — iade "
                    "(aynı bahis daha erken kuponda mevcut)' WHERE coupon_id=?",
                    (now, d[0]))
                conn.execute(
                    "UPDATE paper_bets SET status='void' WHERE coupon_id=?", (d[0],))
        # DERS (PG abort-chain): once DUZELTMEYI commit et, journal SONRA.
        # Journal INSERT'i patlarsa rollback tum void'leri geri aliyordu.
        conn.commit()
        import uuid as _uuid
        for pid, lst in by_pid.items():
            try:
                conn.execute(
                    "INSERT INTO paper_journal (journal_id, portfolio_id, entry_date, "
                    "entry_type, title, content, created_at) VALUES (?,?,?,?,?,?,?)",
                    (str(_uuid.uuid4()), pid, now[:10], "DATA_FIX",
                     "🔧 VERİ DÜZELTMESİ — çift bahis iadesi",
                     f"{len(lst)} kupon iade edildi: aynı (maç·pazar·seçim) "
                     f"birden fazla kez kurulmuştu. Kök neden: aday kaynağı motor "
                     f"dışı olan modlarda 'açık pozisyon' filtresi atlanıyordu; "
                     f"kilit eklendi. Kayıtlar silinmedi, iade edildi.", now))
                conn.commit()
            except Exception as ex:
                conn.rollback()
                print(f"   (journal yazilamadi {pid}: {ex})")
        print(f"\n✅ {len(dupes)} kupon iade edildi (silinmedi).")
    finally:
        conn.close()

    from recompute_portfolio import recompute
    for pid in sorted(by_pid):
        r = recompute(pid, verbose=False)
        print(f"   ↻ {pid:12s} kasa {r.get('bankroll',0):.0f} TL · "
              f"{r.get('played',0)} karar kuponu")


if __name__ == "__main__":
    run(dry="--dry" in sys.argv)
