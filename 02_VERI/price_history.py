"""
📈 FİYAT GEÇMİŞİ — iddaa'nın açılış→kapanış hareketini biriktir
================================================================
NEDEN: Backtest'in en sağlam bulgusu şuydu — motorun sinyalleri iddaa
fiyatlarında her kesitte marj kadar kaybediyor (-%11,6 / -%12,7). Sorun
seçim değil, FİYAT. Adil fiyatla T1'de +%3,4 olan motor, iddaa fiyatında
-%9. Aradaki 12 puan ne modelle ne ligle kapanır; yalnızca daha iyi fiyat
yakalayarak kapanır (CLV).

Ama iddaa'nın fiyat geçmişi elimizde HİÇ yoktu (7.083 maçta açılış kaydı
sıfır). Bu modül onu biriktirir.

MALİYET: sıfır ek API çağrısı (veri zaten her fetch'te geliyordu, atılıyordu).
Yalnızca DEĞİŞEN fiyatlar yazılır → ~700-900 satır/gün, ~3 MB/ay.

GÜVENLİK: capture() asla exception fırlatmaz. Fiyat kaydı bozulsa bile
fetch zinciri etkilenmez.

ÖNCEDEN KAYITLI KARAR KURALI (~2 hafta sonra, ~2.400 maç):
  1. Fiyatlar hareket ediyor mu?      → maçların ≥%30'unda ≥0.05
  2. Yön tahmin edilebiliyor mu?      → bir özellik tabandan ≥8 puan sapmalı
                                        VE eğitim+sınavda birlikte tutmalı
  3. Erken oynamanın CLV kazancı      → ≥+3 puan
  4. Kural: (3) < +3 puan ise MİMAR KONSEPTİ REDDEDİLİR, tablo silinir.

    python price_history.py --stats     # birikim durumu
    python price_history.py --test      # aşama-B ölçümü (veri yeterliyse)
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

FIELDS = ("o1", "ox", "o2", "over25", "under25", "btts_yes", "btts_no")
MIN_MOVE = 0.005          # bu kadarlık fark bile "değişim" sayılır


def ensure_table(conn) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS odds_history ("
        "ts TEXT, iddaa_event_id TEXT, league_code TEXT, kickoff_utc TEXT, "
        "home_team TEXT, away_team TEXT, mbs INTEGER, "
        "o1 REAL, ox REAL, o2 REAL, over25 REAL, under25 REAL, "
        "btts_yes REAL, btts_no REAL, lead_h REAL)")
    conn.commit()
    for stmt in (
        "CREATE INDEX IF NOT EXISTS ix_oh_event ON odds_history (iddaa_event_id)",
        "CREATE INDEX IF NOT EXISTS ix_oh_ts ON odds_history (ts)",
    ):
        try:
            conn.execute(stmt)
            conn.commit()
        except Exception:
            conn.rollback()


def _last_snapshot(conn) -> dict:
    """Her event için en son yazılan fiyat seti (değişim filtresi için)."""
    out: dict = {}
    try:
        rows = conn.execute(
            "SELECT iddaa_event_id, o1, ox, o2, over25, under25, btts_yes, btts_no "
            "FROM odds_history WHERE ts > ? ORDER BY ts",
            ((datetime.utcnow().replace(microsecond=0).isoformat()[:10] + "T00:00:00"),)
        ).fetchall()
        for r in rows:
            out[str(r[0])] = tuple(
                (round(float(x), 3) if x is not None else None) for x in r[1:])
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    return out


def capture(results: list[dict]) -> int:
    """fetch_and_ingest'in ürettiği `results` listesinden fiyatları kaydet.
    Yalnızca ÖNCEKİNDEN FARKLI olanlar yazılır. Asla exception fırlatmaz."""
    if not results:
        return 0
    try:
        conn = db.connect()
    except Exception:
        return 0
    n = 0
    try:
        ensure_table(conn)
        last = _last_snapshot(conn)
        now = datetime.utcnow().isoformat()
        for r in results:
            try:
                ev = str(r.get("event_id") or "")
                if not ev:
                    continue
                o = r.get("odds") or {}
                vals = tuple(
                    (round(float(o[k]), 3) if o.get(k) not in (None, "") else None)
                    for k in ("1", "X", "2", "over25", "under25", "btts_yes", "btts_no"))
                if all(v is None for v in vals):
                    continue
                if last.get(ev) == vals:          # fiyat değişmemiş → yazma
                    continue
                lead = None
                ko = r.get("kickoff")
                if ko:
                    try:
                        lead = (datetime.fromisoformat(str(ko)[:19])
                                - datetime.utcnow()).total_seconds() / 3600.0
                    except Exception:
                        lead = None
                conn.execute(
                    "INSERT INTO odds_history (ts, iddaa_event_id, league_code, "
                    "kickoff_utc, home_team, away_team, mbs, o1, ox, o2, over25, "
                    "under25, btts_yes, btts_no, lead_h) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (now, ev, r.get("lig_code"), ko, r.get("home"), r.get("away"),
                     r.get("mbs")) + vals + (lead,))
                last[ev] = vals
                n += 1
            except Exception:
                continue
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return n


# ──────────────────────────────────────────────────────────────
# Birikim durumu ve aşama-B ölçümü
# ──────────────────────────────────────────────────────────────

def stats() -> dict:
    conn = db.connect()
    try:
        ensure_table(conn)
        r = conn.execute(
            "SELECT COUNT(*) n, COUNT(DISTINCT iddaa_event_id) ev, MIN(ts) ilk, "
            "MAX(ts) son FROM odds_history").fetchone()
        multi = conn.execute(
            "SELECT COUNT(*) c FROM (SELECT iddaa_event_id FROM odds_history "
            "GROUP BY iddaa_event_id HAVING COUNT(*) > 1) z").fetchone()[0]
        out = {"rows": r[0] or 0, "events": r[1] or 0, "first": r[2],
               "last": r[3], "multi": multi or 0}
        print(f"📈 FİYAT GEÇMİŞİ: {out['rows']} satır · {out['events']} maç · "
              f"{out['multi']} maçta birden fazla kayıt (hareket yakalandı)")
        if out["first"]:
            print(f"   {str(out['first'])[:16]} → {str(out['last'])[:16]}")
        need = 2400
        print(f"   Aşama-B testi için hedef: ~{need} sonuçlanmış maç "
              f"(şu an {out['multi']} hareketli maç)")
        return out
    finally:
        conn.close()


def test_stage_b() -> None:
    """Önceden kayıtlı karar kuralına göre Mimar konseptini ölç."""
    conn = db.connect()
    try:
        rows = conn.execute(
            "SELECT h.iddaa_event_id, MIN(h.ts) t0, MAX(h.ts) t1 FROM odds_history h "
            "GROUP BY h.iddaa_event_id HAVING COUNT(*) > 1").fetchall()
        print(f"hareketli maç: {len(rows)}")
        if len(rows) < 300:
            print("⏳ Aşama-B için veri henüz yetersiz (hedef ~2.400 sonuçlanmış maç).")
            return
        print("Aşama-B ölçümü hazır — analiz backtest.py çerçevesinden koşulacak.")
    finally:
        conn.close()


if __name__ == "__main__":
    if "--test" in sys.argv:
        test_stage_b()
    else:
        stats()
