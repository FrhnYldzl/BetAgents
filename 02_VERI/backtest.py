"""
🧪 PROOF OF CONCEPT — ajan kurmadan önce 9 sezon üzerinde sınama
================================================================
KURUMSAL AŞAMA: hiçbir ajan, geriye dönük testten geçmeden kurulmaz.
    KONSEPT  →  BACKTEST (bu modül)  →  KARAR  →  CANLI AJAN

Veri: closing_source='Pinnacle' tarihsel arşiv (2017-2026, 6 lig, ~18.000
maç). Bu veri iddaa'nın lig-etiketi kirliliğinden etkilenmez.

Gerçekçilik: Pinnacle marjı %3, iddaa marjı ligine göre %13.9-17.8.
Her oran, o ligin ÖLÇÜLEN iddaa marjıyla iddaa fiyatına çevrilir:
    o_iddaa = o_pinnacle × (pinnacle_overround / iddaa_overround)
Yani "Pinnacle'da kazanırdı" değil, "iddaa'da ne olurdu" ölçülür.

Metrikler skor tablosuyla AYNI: isabet · ortalama oran · gereken isabet ·
fark (edge) · flat ROI · Wilson alt sınırı · kanıt durumu · kaç kupon gerek.
Ayrıca EĞİTİM/SINAV ayrımı (2024 öncesi / sonrası) — kalıcılık testi.

Sonuçlar `backtest_runs` tablosuna arşivlenir.

    python backtest.py --list           # tanımlı konseptler
    python backtest.py YALNIZ           # tek konsept
    python backtest.py --all            # hepsi
"""
from __future__ import annotations

import json
import math
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
from paper_engine import PaperEngine

SPLIT_DATE = "2024-01-01"          # eğitim / sınav sınırı
BIG_LEAGUES = {"T1", "E0", "SP1", "I1", "D1", "F1"}
FALLBACK_IDDAA_OVERROUND = 1.153   # büyük lig ortalaması (ölçülen)


# ══════════════════════════════════════════════════════════════
# İstatistik (skor tablosuyla birebir aynı formüller)
# ══════════════════════════════════════════════════════════════

def wilson_lb(k: int, n: int, z: float = 1.96) -> float:
    if n <= 0:
        return 0.0
    p = k / n
    d = 1 + z * z / n
    return (p + z * z / (2 * n)) / d - z * math.sqrt(
        p * (1 - p) / n + z * z / (4 * n * n)) / d


def coupons_needed(p_true: float, p_break: float) -> int | None:
    if p_true <= p_break:
        return None
    for n in range(5, 3001):
        if wilson_lb(round(p_true * n), n) > p_break:
            return n
    return None


def score(bets: list[dict], label: str = "") -> dict:
    """bets: [{'o': iddaa_orani, 'won': bool, 'date': 'YYYY-MM-DD'}]"""
    n = len(bets)
    if not n:
        return {"n": 0, "label": label}
    w = sum(1 for b in bets if b["won"])
    avg = sum(b["o"] for b in bets) / n
    p0 = 1 / avg if avg else 1
    hit = w / n
    roi = sum(((b["o"] - 1) if b["won"] else -1) for b in bets) / n * 100
    lb = wilson_lb(w, n)
    return {
        "label": label, "n": n, "won": w, "hit": hit * 100, "avg_odds": avg,
        "breakeven": p0 * 100, "edge": (hit - p0) * 100, "roi": roi,
        "lb": lb * 100, "proven": bool(lb > p0),
        "need": coupons_needed(hit, p0) if hit > p0 else None,
        "pnl_100": sum(((b["o"] - 1) * 100 if b["won"] else -100) for b in bets),
    }


def fmt(s: dict) -> str:
    if not s.get("n"):
        return f"  {s.get('label',''):32s} veri yok"
    pv = ("✅ KANIT" if s["proven"] else
          (f"{s['need']} kupon gerek" if s["need"] else "edge yok"))
    return (f"  {s['label']:32s} n={s['n']:<5d} isabet=%{s['hit']:>5.1f} "
            f"oran={s['avg_odds']:.2f} gereken=%{s['breakeven']:>5.1f} "
            f"fark={s['edge']:+6.1f}p ROI={s['roi']:+7.2f}%  {pv}")


# ══════════════════════════════════════════════════════════════
# Tarihsel evren: sinyaller + ajan kalabalığı
# ══════════════════════════════════════════════════════════════

def _outcome(m: dict, market: str, pick: str):
    h, a = m.get("home_score"), m.get("away_score")
    if h is None or a is None:
        return None
    t = h + a
    if market == "1X2":
        return pick == ("1" if h > a else ("2" if a > h else "X"))
    if market == "UST_25":
        return t > 2.5
    if market == "ALT_25":
        return t < 2.5
    if market == "KG_VAR":
        return h > 0 and a > 0
    if market == "KG_YOK":
        return not (h > 0 and a > 0)
    return None


def _iddaa_conversion(conn) -> dict:
    """Lig başına: pinnacle_overround / iddaa_overround (ölçülen)."""
    conv = {}
    for lg in BIG_LEAGUES:
        p = conn.execute(
            "SELECT AVG(1.0/closing_over25 + 1.0/closing_under25) m FROM matches_v2 "
            "WHERE closing_source='Pinnacle' AND league_code=? "
            "AND closing_over25>1.01 AND closing_under25>1.01", (lg,)).fetchone()
        i = conn.execute(
            "SELECT COUNT(*) n, AVG(1.0/closing_over25 + 1.0/closing_under25) m "
            "FROM matches_v2 WHERE closing_source='iddaa' AND league_code=? "
            "AND closing_over25>1.01 AND closing_under25>1.01", (lg,)).fetchone()
        pin = float(p[0] or 1.035)
        idd = float(i[1]) if (i[0] or 0) >= 25 else FALLBACK_IDDAA_OVERROUND
        conv[lg] = (pin / idd, (idd - 1) * 100)
    return conv


def build_universe(verbose: bool = True) -> list[dict]:
    """Her tarihsel maç için: sinyaller + hangi ajanların seçtiği (kalabalık).
    Simülasyona giren ajanlar: motor tabanlı profiller + CESUR (orta band).
    (fade/popular/council tarihsel yazar verisi olmadığı için hariç — bu,
    kalabalık sayısını HAFİF eksik gösterir, yani test muhafazakârdır.)"""
    import agents
    conn = db.connect()
    conv = _iddaa_conversion(conn)
    if verbose:
        print("LİG DÖNÜŞÜMÜ (ölçülen iddaa marjı):")
        for lg, (c, m) in sorted(conv.items()):
            print(f"  {lg:4s} iddaa marj %{m:4.1f}  → oran çarpanı ×{c:.3f}")
    rows = conn.execute(
        "SELECT * FROM matches_v2 WHERE closing_source='Pinnacle' AND is_settled=1 "
        "AND home_score IS NOT NULL AND closing_1>1.01 AND league_code IN "
        "('" + "','".join(sorted(BIG_LEAGUES)) + "') ORDER BY kickoff_utc").fetchall()
    conn.close()
    ms = [dict(r) for r in rows]
    if verbose:
        print(f"MAÇ: {len(ms)}  ({str(ms[0]['kickoff_utc'])[:7]} → "
              f"{str(ms[-1]['kickoff_utc'])[:7]})")

    eng = PaperEngine("KURUCU_V2")
    # simülasyona girecek profiller (kendi aday kaynağı olanlar hariç)
    sim = {k: v for k, v in agents.PROFILES.items()
           if not v.get("mode") and not v.get("dormant") and not v.get("retired")}
    if verbose:
        print(f"SİMÜLE EDİLEN AJAN: {len(sim)} → {', '.join(sorted(sim))}")

    out = []
    for m in ms:
        lg = m.get("league_code")
        c = conv.get(lg, (0.88, 17.6))[0]
        try:
            sigs = eng.evaluate_match(m)
        except Exception:
            continue
        for s in sigs:
            mkt, mp = s.get("market"), float(s.get("model_prob") or 0)
            o_pin = float(s.get("odds") or 0)
            if o_pin < 1.02 or mkt == "KG_VAR":
                continue
            won = _outcome(m, mkt, s.get("pick"))
            if won is None:
                continue
            # bu sinyali kaç ajan seçerdi?
            takers = []
            for pid, prof in sim.items():
                lgs = prof.get("leagues")
                if lgs and lg not in lgs:
                    continue
                if mkt == "1X2":
                    if mp < prof["fav_min"]:
                        continue
                elif mkt not in prof["markets"]:
                    continue
                if mp < prof["min_mp"] or o_pin < prof["min_odds"]:
                    continue
                if prof.get("max_odds") and o_pin > prof["max_odds"]:
                    continue
                takers.append(pid)
            out.append({
                "date": str(m["kickoff_utc"])[:10], "lg": lg, "mkt": mkt,
                "pick": s.get("pick"), "mp": mp, "o_pin": o_pin,
                "o": o_pin * c, "won": bool(won), "crowd": len(takers),
                "takers": takers,
            })
    if verbose:
        print(f"SİNYAL: {len(out)}")
    return out


# ══════════════════════════════════════════════════════════════
# KONSEPTLER — her yeni ajan fikri buraya bir fonksiyon olarak girer
# ══════════════════════════════════════════════════════════════

def c_yalniz(u: list[dict]) -> list[dict]:
    """👤 YALNIZ: yalnız TEK ajanın seçtiği bahisler + kanıtlı filtreler."""
    return [x for x in u if x["crowd"] == 1 and x["o"] >= 1.45
            and x["lg"] in BIG_LEAGUES]


def c_yalniz_ham(u):
    """YALNIZ (filtresiz) — kalabalık etkisini saf ölçmek için."""
    return [x for x in u if x["crowd"] == 1]


def c_kalabalik(u):
    """Kontrol: 2+ ajanın buluştuğu bahisler."""
    return [x for x in u if x["crowd"] >= 2]


def c_hepsi(u):
    """Kontrol: motorun tüm sinyalleri."""
    return list(u)

def c_secilen(u):
    """Kontrol: en az bir ajanın seçtiği her bahis."""
    return [x for x in u if x["crowd"] >= 1]


# ── 🧠 KÖLN AİLESİ — "tercihin olasılığı" konsepti ────────────────────
# TEZ: ajanlar edge'i NOKTA TAHMİNİ gibi kullanıyor. Oysa (a) tahmin
# gürültülü, (b) argmax gürültünün yukarı saptığı adayı seçiyor. KÖLN
# aynı aday havuzundan, ham edge yerine SONSAL edge ile seçer.
# Matematik shrinkage.py'de; burada yalnız geçmişte SINANIYOR.
#
# WALK-FORWARD: k YALNIZ eğitim döneminde (2024 öncesi) ölçülür, sınav
# dönemine uygulanır. Sınav satırı gerçek testtir; eğitim satırı örnek-içidir.

def _edge_of(x: dict) -> float:
    """Getiri cinsinden edge — measure_k.py ile AYNI tanım."""
    return x["o"] * x["mp"] - 1.0


def _fit_on_train(u: list[dict]):
    """k'yı yalnız eğitim döneminden ölç (sızıntısız)."""
    import shrinkage
    train = [{"e": _edge_of(x), "o": x["o"],
              "r": (x["o"] - 1.0) if x["won"] else -1.0}
             for x in u if x["date"] < SPLIT_DATE]
    return shrinkage.estimate_k(train, control_odds=True), len(train)


def _daily_counts(u: list[dict]) -> dict:
    """Gün başına aday sayısı — seçicinin laneti cezası buna bağlı."""
    c: dict = {}
    for x in u:
        c[x["date"]] = c.get(x["date"], 0) + 1
    return c


def _koln(u: list[dict], use_selection_penalty: bool, min_pi: float,
          label: str) -> list[dict]:
    import shrinkage
    fit, n_train = _fit_on_train(u)
    if not fit:
        print(f"  [{label}] eğitim örneklemi yetersiz (n={n_train}) → seçim yok")
        return []
    print(f"  [{label}] eğitimde ölçülen k = {fit['k_raw']:+.3f} "
          f"±{fit['se_k']:.3f} (t={fit['t']:+.2f}, n={n_train})  "
          f"μ₀={fit['mu0'] * 100:+.1f}%")
    if fit["degenerate"]:
        print(f"  [{label}] ⛔ k ≤ 0 → edge sıralaması bilgi taşımıyor. "
              f"HİÇBİR BAHİS SEÇİLMEDİ. Bu bir arıza değil, konseptin hükmü.")
        return []
    sh = shrinkage.Shrinker.from_fit(fit, min_pi=min_pi)
    counts = _daily_counts(u)
    out = []
    for x in u:
        n_c = counts.get(x["date"], 1) if use_selection_penalty else 1
        if sh.judge(_edge_of(x), n_candidates=n_c)["bet"]:
            out.append(x)
    print(f"  [{label}] {len(u)} adaydan {len(out)} seçildi "
          f"(σ={sh.sigma * 100:.1f}p, π*≥{min_pi:.0%}"
          f"{', seçim cezası AÇIK' if use_selection_penalty else ', seçim cezası KAPALI'})")
    return out


def c_koln(u):
    """🧠 KÖLN: seçicinin laneti + küçültme + π*≥%55 (tam konsept)."""
    return _koln(u, use_selection_penalty=True, min_pi=0.55, label="KOLN")


def c_koln_ham(u):
    """🧠 KÖLN-HAM: yalnız küçültme (seçim cezası KAPALI) — hangi katmanın
    iş yaptığını ayırmak için."""
    return _koln(u, use_selection_penalty=False, min_pi=0.55, label="KOLN_HAM")


def c_edge_q5(u):
    """🚫 Kontrol: ham edge'in EN YÜKSEK beşte biri — ajanların bugün fiilen
    yaptığı seçim. KÖLN'ün yenmesi gereken taban budur."""
    d = sorted(u, key=_edge_of)
    return d[4 * (len(d) // 5):]


def c_edge_q1(u):
    """🚫 Kontrol: ham edge'in EN DÜŞÜK beşte biri. k<0 ise bu dilim Q5'i
    YENER — vekil veride görülen tersine sıralamanın 9 sezonluk sınavı."""
    d = sorted(u, key=_edge_of)
    return d[:len(d) // 5]


CONCEPTS = {
    "YALNIZ": (c_yalniz, "👤 Yalnız seçim + oran≥1.45 + büyük lig"),
    "YALNIZ_HAM": (c_yalniz_ham, "👤 Yalnız seçim (filtresiz)"),
    "KALABALIK": (c_kalabalik, "🚫 Kontrol: 2+ ajan buluşması"),
    "SECILEN": (c_secilen, "🔎 Kontrol: en az 1 ajanın seçtikleri"),
    "HEPSI": (c_hepsi, "🌐 Kontrol: motorun tüm sinyalleri"),
    "KOLN": (c_koln, "🧠 KÖLN: seçim cezası + küçültme + π*≥%55"),
    "KOLN_HAM": (c_koln_ham, "🧠 KÖLN: yalnız küçültme (katman ayrımı)"),
    "EDGE_Q5": (c_edge_q5, "🚫 Kontrol: en yüksek edge %20 (bugünkü davranış)"),
    "EDGE_Q1": (c_edge_q1, "🚫 Kontrol: en düşük edge %20 (ters sıralama testi)"),
}


# ══════════════════════════════════════════════════════════════
# Koşum + arşiv
# ══════════════════════════════════════════════════════════════

def run(name: str, u: list[dict], store: bool = True) -> dict:
    fn, desc = CONCEPTS[name]
    bets = fn(u)
    total = score(bets, f"{name} · TÜMÜ")
    tr = score([b for b in bets if b["date"] < SPLIT_DATE], "  eğitim (2017-2023)")
    te = score([b for b in bets if b["date"] >= SPLIT_DATE], "  SINAV (2024-2026)")
    print(f"\n=== {name} — {desc} ===")
    print(fmt(total))
    print(fmt(tr))
    print(fmt(te))
    verdict = "RED"
    if total.get("n", 0) >= 100 and total.get("roi", -9) > 0:
        if te.get("n", 0) >= 40 and te.get("roi", -9) > 0 and tr.get("roi", -9) > 0:
            verdict = "GEÇTİ"
        else:
            verdict = "ŞÜPHELİ (kalıcılık yok)"
    print(f"  → HÜKÜM: {verdict}")
    res = {"concept": name, "desc": desc, "total": total, "train": tr,
           "test": te, "verdict": verdict, "ts": datetime.utcnow().isoformat()}
    if store:
        try:
            conn = db.connect()
            conn.execute("CREATE TABLE IF NOT EXISTS backtest_runs "
                         "(ts TEXT, concept TEXT, verdict TEXT, payload TEXT)")
            conn.execute("INSERT INTO backtest_runs (ts, concept, verdict, payload) "
                         "VALUES (?,?,?,?)",
                         (res["ts"], name, verdict, json.dumps(res, ensure_ascii=False)))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"  (arşivlenemedi: {e})")
    return res


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--list" in sys.argv:
        for k, (_, d) in CONCEPTS.items():
            print(f"  {k:12s} {d}")
        return
    names = args or (list(CONCEPTS) if "--all" in sys.argv else ["YALNIZ"])
    u = build_universe()
    print("\n" + "=" * 70)
    for nm in names:
        if nm not in CONCEPTS:
            print(f"bilinmeyen konsept: {nm}")
            continue
        run(nm, u)
    # kalabalık dağılımı (bağlam)
    import collections
    c = collections.Counter(x["crowd"] for x in u)
    print("\nKALABALIK DAĞILIMI:", dict(sorted(c.items())[:6]))


if __name__ == "__main__":
    main()
