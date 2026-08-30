"""
🔍 GERİYE DÖNÜK SONUÇ DENETİMİ — metrikler doğru olsun
=======================================================
Kayıtlı her bahsi, kayıtlı SKORDAN yeniden hesaplar ve DB'deki durumla
karşılaştırır. Uyuşmazlık varsa düzeltir ve kuponu yeniden çözer.

NEDEN GEREKLİ (2026-08-30 dersi): settle motoru bilmediği pazara "void"
diyordu. KIRMIZI TAKIM'ın kombine bahisleri (ör. "2 ve Var") KAZANMIŞ
olsa bile VOID yazılıyordu — Banfield 2-3 River Plate bunun canlı örneği.
Bu tür sessiz hatalar tüm metrikleri bozar; bu betik onları yakalar.

İLKE: skor kaynaktan gelir, yorum bizden. Skoru değiştirmeyiz; yalnızca
skordan çıkan SONUCU düzeltiriz. Her düzeltme journal'a yazılır.

    python verify_settlements.py --dry    # sadece raporla
    python verify_settlements.py          # düzelt
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


def outcome(market: str, pick: str, hs: int, aws: int) -> str | None:
    """Skordan sonucu türet. None → bu pazar skordan çözülemez (ör. ilk yarı)."""
    total = hs + aws
    btts = hs > 0 and aws > 0
    res = "1" if hs > aws else ("0" if hs == aws else "2")
    m = (market or "").upper()
    p = (pick or "").strip()

    if m.startswith("HT_") or m in ("HT_FT", "HT_1X2"):
        return None                       # yarı skoru gerekiyor — elimizde yok
    if " ve " in p:
        a, b = [x.strip() for x in p.split(" ve ", 1)]
        au, bu = a.upper(), b.upper()
        if au in ("1", "0", "X", "2"):
            ok_a = res == ("0" if au == "X" else au)
        elif au in ("ÜST", "UST"):
            ok_a = total > 2.5
        elif au == "ALT":
            ok_a = total < 2.5
        else:
            return None
        if bu in ("ÜST", "UST"):
            ok_b = total > 2.5
        elif bu == "ALT":
            ok_b = total < 2.5
        elif bu == "VAR":
            ok_b = btts
        elif bu == "YOK":
            ok_b = not btts
        else:
            return None
        return "won" if (ok_a and ok_b) else "lost"
    if m == "TOTAL_GOALS" or p.endswith("gol"):
        pl = p.replace("gol", "").strip()
        try:
            if "+" in pl:
                return "won" if total >= int(pl.replace("+", "")) else "lost"
            lo, hi = [int(x) for x in pl.split("-")]
            return "won" if lo <= total <= hi else "lost"
        except Exception:
            return None
    if m == "1X2":
        return "won" if p in (res, "X" if res == "0" else res) else "lost"
    if m == "KG_VAR":
        return "won" if (p.upper() == "VAR" and btts) else "lost"
    if m == "KG_YOK":
        return "won" if (p.upper() == "YOK" and not btts) else "lost"
    if m == "ALT_25":
        return "won" if (p.upper() == "ALT" and total < 2.5) else "lost"
    if m == "UST_25":
        return "won" if (p.upper() in ("UST", "ÜST") and total > 2.5) else "lost"
    return None


def run(dry: bool = False) -> None:
    conn = db.connect()
    try:
        rows = conn.execute(
            "SELECT pb.bet_id, pb.coupon_id, pb.market, pb.pick, pb.status, "
            "pb.home_score, pb.away_score, pb.home_team, pb.away_team, "
            "pc.portfolio_id, m.home_score, m.away_score, m.status "
            "FROM paper_bets pb "
            "JOIN paper_coupons pc ON pc.coupon_id = pb.coupon_id "
            "LEFT JOIN matches_v2 m ON m.match_id = pb.match_id "
            # NOT: 'open' kuponlar da denetlenir — void bir ayak açık kuponu
            # da yanlış etkileyebilir. Maç durumu VOID olanlara DOKUNULMAZ
            # (iddaa gerçekten iptal etmiş = meşru iade).
            "WHERE COALESCE(m.status,'') <> 'VOID'").fetchall()
        wrong, unsettleable, checked = [], 0, 0
        for r in rows:
            hs = r[5] if r[5] is not None else r[10]
            aws = r[6] if r[6] is not None else r[11]
            if hs is None or aws is None:
                continue
            exp = outcome(r[2], r[3], int(hs), int(aws))
            if exp is None:
                unsettleable += 1
                continue
            checked += 1
            if r[4] != exp:
                wrong.append({
                    "bet_id": r[0], "coupon_id": r[1], "pid": r[9],
                    "market": r[2], "pick": r[3], "was": r[4], "should": exp,
                    "score": f"{hs}-{aws}", "home": r[7], "away": r[8],
                    "hs": int(hs), "aws": int(aws),
                })
        print(f"🔍 DENETİM: {checked} bahis kontrol edildi · "
              f"{unsettleable} çözülemez (ilk yarı vb.) · {len(wrong)} UYUŞMAZLIK")
        if not wrong:
            print("✅ Tüm sonuçlar doğru.")
            return
        import collections
        by = collections.Counter((w["pid"], w["was"], w["should"]) for w in wrong)
        for (pid, was, should), n in by.most_common():
            print(f"   {pid:12s} {was:5s} → {should:5s} : {n}")
        print("\n  örnekler:")
        for w in wrong[:8]:
            print(f"   {w['home'][:18]:18s}-{w['away'][:18]:18s} "
                  f"{w['market']:9s} {w['pick']:10s} {w['score']:5s} "
                  f"{w['was']} → {w['should']}")
        if dry:
            print("\n(dry-run — değişiklik yok)")
            return

        now = datetime.utcnow().isoformat()
        touched = set()
        for w in wrong:
            conn.execute(
                "UPDATE paper_bets SET status=?, home_score=?, away_score=?, "
                "result=?, settled_at=COALESCE(settled_at,?) WHERE bet_id=?",
                (w["should"], w["hs"], w["aws"], w["score"], now, w["bet_id"]))
            touched.add((w["coupon_id"], w["pid"]))
        conn.commit()
        print(f"\n✅ {len(wrong)} bahis düzeltildi.")

        # etkilenen kuponları yeniden çöz
        fixed_c = 0
        for cid, pid in touched:
            bets = conn.execute(
                "SELECT status, odds FROM paper_bets WHERE coupon_id=?",
                (cid,)).fetchall()
            c = conn.execute(
                "SELECT stake, combined_odds FROM paper_coupons WHERE coupon_id=?",
                (cid,)).fetchone()
            if not bets or not c:
                continue
            live = [b for b in bets if b[0] in ("won", "lost")]
            if not live:
                st, ret = "void", float(c[0])
            elif all(b[0] == "won" for b in live):
                eff = 1.0
                for b in live:
                    eff *= float(b[1] or 1)
                st = "won"
                ret = round(float(c[0]) * eff, 2)
            else:
                st, ret = "lost", 0.0
            conn.execute(
                "UPDATE paper_coupons SET status=?, actual_return=?, pnl=?, "
                "settled_at=COALESCE(settled_at,?) WHERE coupon_id=?",
                (st, ret, ret - float(c[0]), now, cid))
            fixed_c += 1
        conn.commit()
        print(f"✅ {fixed_c} kupon yeniden çözüldü.")

        pids = sorted({p for _, p in touched})
        try:
            import uuid
            for pid in pids:
                conn.execute(
                    "INSERT INTO paper_journal (journal_id, portfolio_id, "
                    "entry_date, entry_type, title, content, created_at) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (str(uuid.uuid4()), pid, now[:10], "DATA_FIX",
                     "🔍 SONUÇ DENETİMİ — yanlış sonuçlanan bahisler düzeltildi",
                     f"Settle motoru bilmediği pazara 'void' diyordu; kombine "
                     f"pazarlar (ör. '2 ve Var') kazanmış olsa bile void "
                     f"yazılıyordu. Skorlardan yeniden hesaplanıp düzeltildi.",
                     now))
                conn.commit()
        except Exception:
            conn.rollback()
    finally:
        conn.close()

    from recompute_portfolio import recompute
    for pid in pids:
        r = recompute(pid, verbose=False)
        print(f"   ↻ {pid:12s} kasa {r.get('bankroll',0):.0f} TL · "
              f"{r.get('played',0)} karar")


if __name__ == "__main__":
    run(dry="--dry" in sys.argv)
