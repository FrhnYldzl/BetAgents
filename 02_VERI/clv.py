"""
CLV — CLOSING LINE VALUE (Faz 0: Truth Meter)
=============================================
Her paper-bahis için: GİRİŞ oranı (paper_bets.odds, kupon yerleştirilince) vs
KAPANIŞ oranı (matches_v2.closing_*, maç başlamadan son değer).

    CLV% = (giriş_oranı / kapanış_oranı) - 1
      > 0  → kapanıştan İYİ fiyat yakaladık (çizgiyi yendik)  = EDGE işareti
      < 0  → kapanıştan kötü fiyat (çizgiyi kaybettik)

NOT: Hem giriş hem kapanış aynı kitabın (iddaa) oranı → bu "intra-iddaa CLV":
"iddaa'nın kendi kapanışından daha iyi bir an/seçim yakaladık mı?" ölçer.
Yasal kısıt nedeniyle (sadece iddaa) doğru pratik metrik budur. Sharp-book
(Pinnacle) CLV'si değil — yorumlarken bunu akılda tut.

Kullanım:
    python clv.py            # kolonları ekle + backfill + özet
    python clv.py --summary  # sadece özet yazdır
"""
from __future__ import annotations

import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import db

# (market, pick) → matches_v2 kapanış kolonu
CLOSING_COL = {
    ("1X2", "1"):      "closing_1",
    ("1X2", "X"):      "closing_X",
    ("1X2", "2"):      "closing_2",
    ("KG_VAR", "VAR"): "closing_btts_yes",
    ("KG_YOK", "YOK"): "closing_btts_no",
    ("UST_25", "UST"): "closing_over25",
    ("ALT_25", "ALT"): "closing_under25",
}


def _row_get(row: dict, col: str):
    """Dialect-güvenli erişim (PG mixed-case 'closing_X' sorunu için)."""
    for k in (col, col.lower(), col.upper()):
        if k in row and row[k] is not None:
            return row[k]
    return None


def _to_float(v):
    try:
        f = float(v)
        return f if f > 1.0 else None   # geçerli ondalık oran > 1.0
    except (TypeError, ValueError):
        return None


def ensure_columns(conn) -> None:
    """paper_bets'e closing_odds + clv kolonlarını idempotent ekle."""
    for col, typ in (("closing_odds", "REAL"), ("clv", "REAL")):
        try:
            conn.execute(f"ALTER TABLE paper_bets ADD COLUMN {col} {typ}")
            conn.commit()
        except Exception:
            conn.rollback()


def closing_for(match_row: dict, market: str, pick: str):
    """Bir bahis için kapanış oranını matches_v2 satırından çek."""
    col = CLOSING_COL.get((market, pick))
    if not col:
        return None
    return _to_float(_row_get(match_row, col))


def backfill_clv(portfolio_id: str | None = None, verbose: bool = False) -> dict:
    """
    clv IS NULL olan, maçı BAŞLAMIŞ (kapanış kesinleşmiş) bahisler için
    closing_odds + clv hesapla ve yaz. Idempotent — tekrar tekrar çağrılabilir.
    """
    conn = db.connect()
    n_done = 0
    n_skip = 0
    try:
        ensure_columns(conn)

        q = "SELECT * FROM paper_bets WHERE clv IS NULL AND match_id IS NOT NULL"
        params: tuple = ()
        if portfolio_id:
            q += " AND portfolio_id=?"
            params = (portfolio_id,)
        bets = [dict(b) for b in conn.execute(q, params).fetchall()]

        for bet in bets:
            mid = bet.get("match_id")
            entry = _to_float(bet.get("odds"))
            if entry is None:
                n_skip += 1
                continue

            mrow = conn.execute(
                "SELECT * FROM matches_v2 WHERE match_id=?", (mid,)
            ).fetchone()
            if mrow is None:
                n_skip += 1
                continue
            mrow = dict(mrow)

            # Kapanış kesinleşmiş mi? maç başladı/bitti olmalı.
            settled = mrow.get("is_settled") in (1, True)
            started = bool((mrow.get("status") or "").upper() not in ("NS", "", None))
            if not (settled or started):
                n_skip += 1
                continue

            closing = closing_for(mrow, bet.get("market", ""), bet.get("pick", ""))
            if closing is None:
                n_skip += 1
                continue

            clv = round(entry / closing - 1.0, 5)
            conn.execute(
                "UPDATE paper_bets SET closing_odds=?, clv=? WHERE bet_id=?",
                (round(closing, 3), clv, bet["bet_id"]),
            )
            n_done += 1
            if verbose:
                print(f"  {bet.get('market')}/{bet.get('pick')} "
                      f"giris {entry:.2f} -> kapanis {closing:.2f}  CLV {clv*100:+.1f}%")

        conn.commit()
    finally:
        conn.close()
    return {"computed": n_done, "skipped": n_skip}


def clv_summary(portfolio_id: str | None = None) -> dict:
    """CLV karne: ortalama, medyan, beat-rate, pazar/lig kırılımı."""
    conn = db.connect()
    try:
        ensure_columns(conn)
        q = "SELECT market, league, clv FROM paper_bets WHERE clv IS NOT NULL"
        params: tuple = ()
        if portfolio_id:
            q += " AND portfolio_id=?"
            params = (portfolio_id,)
        rows = [dict(r) for r in conn.execute(q, params).fetchall()]
    finally:
        conn.close()

    def _agg(vals):
        if not vals:
            return {"n": 0, "mean": None, "median": None, "beat_rate": None}
        vals = sorted(vals)
        n = len(vals)
        mean = sum(vals) / n
        mid = n // 2
        median = vals[mid] if n % 2 else (vals[mid - 1] + vals[mid]) / 2
        beat = sum(1 for v in vals if v > 0) / n
        return {"n": n, "mean": mean, "median": median, "beat_rate": beat}

    all_clv = [r["clv"] for r in rows]
    by_market: dict[str, list] = {}
    by_league: dict[str, list] = {}
    for r in rows:
        by_market.setdefault(r.get("market") or "?", []).append(r["clv"])
        by_league.setdefault(r.get("league") or "?", []).append(r["clv"])

    return {
        "overall": _agg(all_clv),
        "by_market": {k: _agg(v) for k, v in sorted(by_market.items())},
        "by_league": {k: _agg(v) for k, v in sorted(by_league.items())},
    }


def recent_bets(portfolio_id: str | None = None, limit: int = 20) -> list[dict]:
    """En son CLV hesaplanmış bahisler (settle/başlama tarihine göre yeni→eski)."""
    conn = db.connect()
    try:
        ensure_columns(conn)
        q = ("SELECT home_team, away_team, league, market, pick, odds, "
             "closing_odds, clv, kickoff_utc, result "
             "FROM paper_bets WHERE clv IS NOT NULL")
        params: tuple = ()
        if portfolio_id:
            q += " AND portfolio_id=?"
            params = (portfolio_id,)
        q += " ORDER BY kickoff_utc DESC LIMIT ?"
        rows = [dict(r) for r in conn.execute(q, params + (limit,)).fetchall()]
    finally:
        conn.close()
    return rows


def _print_summary(s: dict) -> None:
    o = s["overall"]
    print("=" * 60)
    print("CLV KARNE (Closing Line Value)")
    print("=" * 60)
    if not o["n"]:
        print("Henuz CLV hesaplanabilir bahis yok (maclar baslayinca dolar).")
        return
    print(f"Toplam CLV'li bahis : {o['n']}")
    print(f"Ortalama CLV        : {o['mean']*100:+.2f}%")
    print(f"Medyan CLV          : {o['median']*100:+.2f}%")
    print(f"Beat-rate (CLV>0)   : {o['beat_rate']*100:.0f}%")
    print(f"Yorum: ortalama CLV {'POZITIF -> edge isareti' if o['mean'] > 0 else 'negatif -> edge yok'}"
          f"  (>=150 bahiste anlamli)")
    print("\n--- Pazar bazli ---")
    for k, a in s["by_market"].items():
        if a["n"]:
            print(f"  {k:8s} n={a['n']:4d}  ort {a['mean']*100:+.2f}%  beat {a['beat_rate']*100:.0f}%")
    print("\n--- Lig bazli ---")
    for k, a in s["by_league"].items():
        if a["n"]:
            print(f"  {k:8s} n={a['n']:4d}  ort {a['mean']*100:+.2f}%  beat {a['beat_rate']*100:.0f}%")


if __name__ == "__main__":
    summary_only = "--summary" in sys.argv
    if not summary_only:
        res = backfill_clv(verbose="--verbose" in sys.argv)
        print(f"[backfill] hesaplanan={res['computed']}  atlanan={res['skipped']}\n")
    _print_summary(clv_summary())
