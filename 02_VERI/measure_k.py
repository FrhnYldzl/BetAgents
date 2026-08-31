"""
🔬 k ÖLÇÜMÜ — "edge tahminimiz gerçekten sıralıyor mu?"
========================================================
Ajanların TAMAMI edge'i nokta tahmini gibi kullanıyor: eşiği geçen oynanır.
Ama bu ancak ê'nin gerçek e'yi DOĞRU SIRALAMASI hâlinde anlamlıdır. Ne kadar
doğru sıraladığı tek bir sayıdır:

    k = τ²/(τ²+σ²)      (güvenilirlik oranı — shrinkage.py'de türetildi)

    k ≈ 1  → tahmin neredeyse hatasız; ham edge'i doğrudan eşikle
    k ≈ 0  → tahmin gürültü; hiçbir eşik işe yaramaz
    k < 0  → tahmin TERS sıralıyor; yüksek edge daha kötü sonuç veriyor

Ölçüm yöntemi (klasik hatalı-değişken zayıflaması):
    gerçekleşen getiri  =  α + k · (tahmin edilen edge)  + γ · oran
    → eğim k'nın ta kendisidir.

ORAN KONTROLÜ ŞART: kontrolsüz bir negatif k, yalnızca "uzun oranlar
kaybettirir" (favori-uzunoran sapması) bulgusunun yeniden keşfi olabilir.
γ terimi bunu ayırır.

──────────────────────────────────────────────────────────────────────
BİRİM: BAHİS (kupon değil). Kupon düzeyinde ölçüm ajanın kazancını verir;
bizim sorumuz "p̂ kalibre mi" olduğu için AYAK düzeyi doğru birimdir.
    e = oran × model_prob − 1        (getiri cinsinden edge — TEK tanım)
    r = (oran − 1) kazandıysa, −1 kaybettiyse
`edge` kolonu KULLANILMAZ: motor ailesinde olasılık farkı (mp − 1/oran),
kombo ailesinde başka ölçek — iki aile karşılaştırılamaz hâle gelirdi.
VOID ve açık bahisler dışarıda.

    python measure_k.py                # canlı DB (paper_bets)
    python measure_k.py --proxy        # DB yoksa: backtest CSV'leri
    python measure_k.py --min-n 50     # aile başına asgari örneklem
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import shrinkage
from shrinkage import Shrinker, estimate_k, fmt_fit

REPO = THIS_DIR.parent
LOG_DIR = REPO / "07_LOG_VE_RAPORLAR"


# ══════════════════════════════════════════════════════════════
# Aile tasnifi — UI'dan bağımsız, agents.PROFILES'tan türetilir
# ══════════════════════════════════════════════════════════════

def family_of(pid: str) -> str:
    if pid in ("OPUS5_V1",):
        return "İNSAN"
    if pid in ("PAPER_V1",):
        return "ARŞİV"
    try:
        import agents
        prof = agents.PROFILES.get(pid)
    except Exception:
        prof = None
    if not prof:
        return "DİĞER"
    if prof.get("mode") == "multiplier":
        return "KIRMIZI (kombo)"
    return "MAVİ (motor)"


# ══════════════════════════════════════════════════════════════
# Veri kaynakları
# ══════════════════════════════════════════════════════════════

def load_live() -> list[dict]:
    """Kapanmış paper_bets kayıtları."""
    import db
    conn = db.connect()
    try:
        rows = conn.execute(
            "SELECT portfolio_id, market, odds, model_prob, status, settled_at "
            "FROM paper_bets WHERE status IN ('won','lost') "
            "AND odds > 1.01 AND model_prob > 0"
        ).fetchall()
    finally:
        conn.close()
    out = []
    for r in rows:
        d = dict(r)
        o = float(d["odds"])
        mp = float(d["model_prob"])
        if not (0 < mp < 1) or o <= 1.01:
            continue
        won = (d["status"] == "won")
        out.append({
            "pid": d["portfolio_id"], "fam": family_of(d["portfolio_id"]),
            "mkt": d.get("market"), "o": o,
            "e": o * mp - 1.0,
            "r": (o - 1.0) if won else -1.0,
            "won": won, "date": str(d.get("settled_at") or "")[:10],
        })
    return out


def load_proxy() -> list[dict]:
    """DB yoksa: backtest CSV'leri (motor ailesi sinyalleri — VEKİL).
    ⚠️ Bunlar kombo bahisleri DEĞİL; kombo ailesine genellenemez."""
    specs = [("backtest_bets.csv", "model_prob", "backtest_v1"),
             ("multi_league_bets.csv", "p_calibrated", "multi_league")]
    out = []
    for fname, pcol, tag in specs:
        path = LOG_DIR / fname
        if not path.exists():
            continue
        for r in csv.DictReader(open(path, encoding="utf-8")):
            try:
                p = float(r[pcol])
                o = float(r["market_odds"])
                won = str(r["won"]).strip().lower() in ("true", "1", "yes")
            except Exception:
                continue
            if not (0 < p < 1) or o <= 1.01:
                continue
            out.append({
                "pid": tag, "fam": "VEKİL (motor backtest)",
                "mkt": r.get("selection"), "o": o,
                "e": o * p - 1.0,
                "r": (o - 1.0) if won else -1.0,
                "won": won, "date": r.get("match_date", "")[:10],
            })
    return out


# ══════════════════════════════════════════════════════════════
# Raporlama
# ══════════════════════════════════════════════════════════════

def quintile_table(rows: list[dict], title: str) -> None:
    """En okunaklı kanıt: tahmin dilimleri × gerçekleşen getiri.
    k negatifse burada TEK DÜZE AZALAN bir desen görünür."""
    if len(rows) < 25:
        return
    d = sorted(rows, key=lambda x: x["e"])
    q = len(d) // 5
    print(f"\n  {title} — tahmin edilen edge dilimlerine göre")
    print(f"    {'dilim':7s} {'n':>5s} {'ort.tahmin':>11s} {'ort.GERÇEK':>11s} "
          f"{'fark':>9s} {'ort.oran':>9s} {'isabet':>8s}")
    for i in range(5):
        g = d[i * q:(i + 1) * q] if i < 4 else d[4 * q:]
        if not g:
            continue
        me = sum(x["e"] for x in g) / len(g)
        mr = sum(x["r"] for x in g) / len(g)
        mo = sum(x["o"] for x in g) / len(g)
        hw = sum(1 for x in g if x["won"]) / len(g)
        print(f"    Q{i + 1:<6d} {len(g):5d} {me * 100:>+10.1f}% {mr * 100:>+10.1f}% "
              f"{(mr - me) * 100:>+8.1f}p {mo:>9.2f} {hw * 100:>7.1f}%")


def verdict_for(fit: dict | None) -> str:
    if not fit:
        return "ÖLÇÜLEMEDİ"
    if fit.get("degenerate_lo"):
        return ("⛔ k ≤ 0 — edge sıralaması bilgi TAŞIMIYOR. Hiçbir edge eşiği "
                "kârlı seçim yapamaz; eşiği yükseltmek de işe yaramaz.")
    if fit.get("degenerate_hi"):
        return ("⛔ k ≥ 1 — MODEL BU VERİYE OTURMUYOR. Sonuç 'edge sıralaması "
                "harika' DEĞİLDİR: k=τ²/(τ²+σ²) tanımı gereği [0,1] "
                "aralığındadır. Önce edge tanımını düzelt (marjlı edge "
                "kullanılıyorsa varyansın çoğu marj farkıdır, tahmin "
                "hatası değil).")
    if fit["ci_lo"] <= 0 <= fit["ci_hi"]:
        return ("⚠️ k sıfırdan ayırt edilemiyor — kanıt yetersiz. "
                "Daha çok kapanmış bahis gerek.")
    if fit["k"] < 0.35:
        return ("🟡 k düşük — yalnızca ÇOK yüksek ham edge'ler sonsalda "
                "pozitife çıkar. Mevcut %8 eşiği fazla gevşek.")
    return "🟢 k anlamlı pozitif — edge sıralaması çalışıyor."


def threshold_advice(fit: dict, n_cands: tuple[int, ...] = (20, 100, 221, 299)) -> None:
    if not fit or fit["degenerate"]:
        return
    sh = Shrinker.from_fit(fit, min_pi=0.55)
    print(f"\n  ÖNERİLEN HAM EDGE EŞİĞİ (π* ≥ %55 için) — aday sayısına göre:")
    print(f"    {'aday N':>8s} {'gereken ham edge':>18s}   (şu anki sabit eşik: %8)")
    for n in n_cands:
        need = sh.required_edge(n)
        if need is None:
            continue
        print(f"    {n:>8d} {need * 100:>17.1f}%")
    print(f"    σ(tahmin hatası) = {sh.sigma * 100:.1f} puan · "
          f"μ₀ = {sh.mu0 * 100:+.1f}%")


def main() -> None:
    proxy = "--proxy" in sys.argv
    min_n = 30
    for i, a in enumerate(sys.argv):
        if a == "--min-n" and i + 1 < len(sys.argv):
            min_n = int(sys.argv[i + 1])

    rows: list[dict] = []
    src = ""
    if not proxy:
        try:
            rows = load_live()
            src = "CANLI (paper_bets)"
        except Exception as exc:
            print(f"⚠️  Canlı DB okunamadı: {exc}")
            print("    → vekil veriye düşülüyor (--proxy)\n")
    if not rows:
        rows = load_proxy()
        src = "VEKİL (backtest CSV — motor ailesi, kombo DEĞİL)"

    if not rows:
        print("Veri bulunamadı. Canlı DB için 02_VERI/bahis_agent.db veya "
              "DATABASE_URL gerekli.")
        return

    print("=" * 78)
    print(f"  🔬 k ÖLÇÜMÜ — kaynak: {src}")
    print(f"  kapanmış bahis: {len(rows)}")
    print("=" * 78)

    # ── 1) HAVUZ ────────────────────────────────────────────────
    fit_all = estimate_k(rows, control_odds=True)
    fit_raw = estimate_k(rows, control_odds=False)
    print("\n【 HAVUZ — tüm bahisler 】")
    print("  " + fmt_fit(fit_raw, "oran kontrolsüz"))
    print("  " + fmt_fit(fit_all, "ORAN KONTROLLÜ"))
    if fit_all and fit_all.get("odds_beta") is not None:
        print(f"  {'':22s} γ(oran) = {fit_all['odds_beta']:+.3f}  "
              f"(anlamlıysa negatif k oran etkisidir, edge değil)")
    quintile_table(rows, "HAVUZ")
    print(f"\n  → HÜKÜM: {verdict_for(fit_all)}")
    if fit_all:
        threshold_advice(fit_all)

    # ── 2) AİLE BAZINDA ─────────────────────────────────────────
    fams: dict[str, list[dict]] = {}
    for r in rows:
        fams.setdefault(r["fam"], []).append(r)
    if len(fams) > 1:
        print("\n" + "=" * 78)
        print("  AİLE BAZINDA — k her aile için AYRI ölçülmeli.")
        print("  (Bir ailenin k'sını diğerine devretmek, 53672f1'de yakalanan")
        print("   'ölçülmemiş katsayı devralma' hatasının aynısıdır.)")
        print("=" * 78)
        for fam, rs in sorted(fams.items(), key=lambda x: -len(x[1])):
            f = estimate_k(rs, control_odds=True) if len(rs) >= min_n else None
            print("\n  " + fmt_fit(f, fam))
            if f:
                quintile_table(rs, fam)
                print(f"    → {verdict_for(f)}")
            elif len(rs) < min_n:
                print(f"    → n={len(rs)} < {min_n}: HENÜZ ÖLÇÜLEMEZ. "
                      f"Bu aile ölçüm için çalışmaya devam etmeli.")

    # ── 3) AJAN BAZINDA (özet) ──────────────────────────────────
    pids: dict[str, list[dict]] = {}
    for r in rows:
        pids.setdefault(r["pid"], []).append(r)
    ok = {p: rs for p, rs in pids.items() if len(rs) >= min_n}
    if ok:
        print("\n" + "=" * 78)
        print(f"  AJAN BAZINDA (n ≥ {min_n})")
        print("=" * 78)
        for pid, rs in sorted(ok.items(), key=lambda x: -len(x[1])):
            print("  " + fmt_fit(estimate_k(rs, control_odds=True), pid))
    skipped = sorted(p for p, rs in pids.items() if len(rs) < min_n)
    if skipped:
        print(f"\n  (n<{min_n} olduğu için atlanan ajanlar: {', '.join(skipped)})")

    print("\n" + "=" * 78)
    print("  SONRAKİ ADIM: k pozitif ve anlamlıysa → KÖLN konseptini")
    print("  backtest.py ile sına:   python backtest.py KOLN EDGE_Q5 EDGE_Q1")
    print("=" * 78)


if __name__ == "__main__":
    main()
