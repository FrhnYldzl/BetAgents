"""
🟠 TURUNCU TAKIM — AJAN: iddaa fiyatı × bağımsız skor modeli
============================================================
DATA  : matches_v2 (geçmiş goller, güncel program) + market_odds (iddaa
        fiyatları) — diğer takımlarla AYNI veritabanı, yalnız OKUMA.
MODEL : turuncu_model — takım gücünden Dixon-Coles skor dağılımı.
AJAN  : bu modül — her ajan kendi hipotezine göre aday seçer. Kupon
        yerleştirme, kapanış ve risk kuralları sistemin ortak hattıdır.

Beş ajan, beş hipotez — sahada hangisi ayakta kalacak:
  TEMEL    ana pazarlar (1X2 · A/Ü 2,5 · KG). Belgenin sırası: bağımsız
           görüş önce ANA pazarda iddaa'yı yenmeli.
  DAR      dar kombineler (etkin skor ≤ 2,2) — belgenin "avantaj" tezi:
           az skora dayanan pazarı bahisçi zor fiyatlar.
  GENİŞ    geniş kombineler (etkin skor ≥ 3) — model hatasına dayanıklı.
  GOLBANT  toplam gol bantları (0-1 / 2-3 / 4-5 / 6+).
  HARMAN   model ile iddaa'nın marjsız fiyatının harmanı — belgenin
           uyarısına cevap: "yüksek edge çoğu zaman modelin hatasıdır."

Ortak kurallar: yalnız TEK maç (akümülatör yok — belge §1.1), edge tavanı
%25 (belge §8), iddaa'nın MBS kuralı gerçek (tek başına oynanamayan maç
oynanmaz), maç başına en fazla bir seçim.

İZOLASYON: diğer takımların modüllerini import etmez; hiçbir tabloya
yazmaz (kuponu sistemin ortak motoru yerleştirir). --kur yalnız Turuncu
portföylerini açar.

    python turuncu_agent.py --adaylar   # bugünkü adaylar (kuru koşu, salt okuma)
    python turuncu_agent.py --kur       # Turuncu portföylerini aç
"""
from __future__ import annotations

import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import db
import turuncu_model as TM

# Harman için pazarın TAM grubu gerekir (marj ancak böyle çıkarılır).
BOY = {"1X2": 3, "OU2.5": 2, "BTTS": 2, "1X2_OU": 6, "1X2_BTTS": 6,
       "OU_BTTS": 4, "TOTAL_GOALS": 4}
# Ana pazarlar kâğıt defterine sistemin kodlarıyla yazılır (kapanış ve CLV
# bu kodları tanır). Kombine ve gol bandı etiketleri olduğu gibi kalır.
KAGIT = {("1X2", "1"): ("1X2", "1"), ("1X2", "0"): ("1X2", "0"),
         ("1X2", "2"): ("1X2", "2"),
         ("OU2.5", "Üst"): ("UST_25", "UST"), ("OU2.5", "Alt"): ("ALT_25", "ALT"),
         ("BTTS", "Var"): ("KG_VAR", "VAR"), ("BTTS", "Yok"): ("KG_YOK", "YOK")}


def _simdi() -> str:
    return datetime.utcnow().isoformat()


def _fiyatlar() -> dict:
    """iddaa'nın ŞU ANKİ fiyatı (canli_fiyat — veri katmanı).

    ⚠️ 19.09 DERSİ (kullanıcı: "HARMAN'ın oranları yanlış gibi"): ilk sürüm
    fiyatı pazar defterinin (market_odds) SON SATIRINDAN okuyordu; o satır
    günlerce eski olabiliyor (bkz. canli_fiyat.py). Çağrı başarısızsa
    istisna yükselir → ajan 🔴 TIKANIKLIK yazar."""
    import canli_fiyat
    return canli_fiyat.fiyatlar()


def _program(conn) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT match_id, external_id_iddaa idd, league_code lg, home_team h, "
        "away_team a, kickoff_utc ko, mbs FROM matches_v2 "
        "WHERE is_settled=0 AND external_id_iddaa IS NOT NULL "
        "AND kickoff_utc > ? AND league_code IN (" +
        ",".join("'" + l + "'" for l in TM.LIGLER) + ")",
        (_simdi(),)).fetchall()]


_VERI: dict = {"ts": None, "v": None}


def _veri(taze_sn: int = 120) -> tuple[dict, list]:
    """Canlı fiyat + program, 2 dk önbellekli: bir worker döngüsünde beş
    ajan üç kez (kalkan, teşhis, koşu) aday üretir. Fiyat iddaa'dan canlı
    geldiği için önbellek en fazla 2 dk eski olabilir — defterin günlerce
    eski satırıyla karıştırılmasın."""
    simdi = datetime.utcnow()
    if (_VERI["v"] is not None and _VERI["ts"] is not None
            and (simdi - _VERI["ts"]).total_seconds() < taze_sn):
        return _VERI["v"]
    fiyat = _fiyatlar()
    conn = db.connect()
    try:
        program = _program(conn)
    finally:
        conn.close()
    v = (fiyat, program)
    _VERI.update(ts=simdi, v=v)
    return v


def adaylar(prof: dict, tag: str = "[TURUNCU]") -> list[dict]:
    """Profilin hipotezine uyan adaylar — agents.build_coupons çağırır."""
    model = TM.guncel_model()
    fiyat, program = _veri()
    pazarlar = tuple(prof.get("tur_pazar") or ())
    min_e = float(prof.get("min_edge", 0.06))
    max_e = float(prof.get("max_edge", 0.25))
    lo, hi = float(prof.get("min_odds", 1.01)), float(prof.get("max_odds", 50.0))
    e_min, e_max = prof.get("etkin_min"), prof.get("etkin_max")
    w = prof.get("harman")
    picks: list[dict] = []
    goruldu: set = set()
    modelsiz = fiyatsiz = 0
    for m in program:
        ev = str(m["idd"])
        if ev in goruldu:
            continue
        goruldu.add(ev)
        oran = fiyat.get(ev)
        if not oran:
            fiyatsiz += 1
            continue
        par = model["ligler"].get(m["lg"])
        th = TM.takim(model, m["lg"], m["h"])
        ta = TM.takim(model, m["lg"], m["a"])
        lm = TM.tahmin(par, th, ta) if (par and th and ta) else None
        if not lm:
            modelsiz += 1
            continue
        f = TM.fiyatla(TM.matris(lm[0], lm[1], par["rho"]))
        en = None
        for mk in pazarlar:
            grup = {sel: o for (k, sel), o in oran.items()
                    if k == mk and sel in f.get(mk, {})}
            if not grup:
                continue
            olas = {sel: f[mk][sel][0] for sel in grup}
            if w is not None:
                if len(grup) != BOY.get(mk):
                    continue
                s = sum(1.0 / o for o in grup.values())
                b = {sel: (max(olas[sel], 1e-9) ** w) *
                          (((1.0 / grup[sel]) / s) ** (1 - w)) for sel in grup}
                t = sum(b.values())
                olas = {sel: v / t for sel, v in b.items()}
            for sel, o in grup.items():
                p, etkin = olas[sel], f[mk][sel][1]
                edge = p * o - 1
                if not (min_e <= edge <= max_e) or not (lo <= o <= hi):
                    continue
                if e_min is not None and etkin < e_min:
                    continue
                if e_max is not None and etkin > e_max:
                    continue
                if en is None or edge > en[0]:
                    en = (edge, mk, sel, o, p, etkin)
        if not en:
            continue
        edge, mk, sel, o, p, etkin = en
        kmk, ksel = KAGIT.get((mk, sel), (mk, sel))
        picks.append({
            "market": kmk, "pick": ksel, "odds": o,
            "model_prob": p, "implied_prob": 1.0 / o, "edge": p - 1.0 / o,
            "signal_score": edge, "signal_name": "TURUNCU_DC",
            "_etkin": round(etkin, 2), "_lam": round(lm[0], 3),
            "_mu": round(lm[1], 3),
            "_match": {"match_id": m["match_id"], "external_id_iddaa": m["idd"],
                       "home_team": m["h"],
                       "away_team": m["a"], "league_code": m["lg"],
                       "kickoff_utc": m["ko"], "mbs": m["mbs"]},
        })
    picks.sort(key=lambda x: -x["signal_score"])
    print(f"{tag} 🟠 {len(picks)} aday · {len(goruldu)} maç tarandı "
          f"({modelsiz} modelsiz, {fiyatsiz} fiyatsız)")
    return picks


def kur() -> None:
    """Turuncu portföylerini aç: kasa 1.000 ₺, yürürlükteki dönem, pencere
    ŞİMDİ. Portföy varsa dokunmaz; yalnız dönem alanı boşsa doldurur —
    yoksa sistem toplamlarına (dönem başından) hiç girmezler."""
    import agents
    tur = [p for p, v in agents.PROFILES.items() if v.get("takim") == "turuncu"]
    for pid in tur:
        agents.ensure_portfolio(pid)
    conn = db.connect()
    try:
        era = conn.execute("SELECT MAX(COALESCE(era_no,1)) FROM paper_portfolio "
                           "WHERE era_start IS NOT NULL").fetchone()[0] or 1
        simdi = _simdi()
        for pid in tur:
            conn.execute("UPDATE paper_portfolio SET era_no=?, era_start=? "
                         "WHERE portfolio_id=? AND era_start IS NULL",
                         (era, simdi, pid))
        conn.commit()
        for pid in tur:
            r = conn.execute("SELECT current_bankroll, era_no, era_start FROM "
                             "paper_portfolio WHERE portfolio_id=?", (pid,)).fetchone()
            print(f"  🟠 {pid:12s} kasa {float(r[0] or 0):,.0f} ₺ · dönem {r[1]} · "
                  f"pencere {str(r[2])[:16]}")
    finally:
        conn.close()


def iptal(once: str, gerekce: str, uygula: bool = False) -> None:
    """Turuncu'nun `once`'den önce kurulmuş AÇIK kuponlarını iptal et (void).

    Sistemin kendi 'tüm ayaklar void' kapanışıyla aynı biçim: kupon void,
    actual_return = stake, pnl = 0; ayaklar void. Kasa DEĞİŞMEZ (bahis
    kurulurken kasadan düşülmüyor) ve kasa mutabakatı bozulmaz. Portföy
    sayaçlarına dokunulmaz — geçersiz girdiyle kurulmuş kupon oynanmış
    sayılmaz. Önce yedek: yedek_turuncu_iptal.json. Yalnız TURUNCU."""
    import json
    import agents
    tur = [p for p, v in agents.PROFILES.items() if v.get("takim") == "turuncu"]
    conn = db.connect()
    try:
        kup = [dict(r) for r in conn.execute(
            "SELECT * FROM paper_coupons WHERE status='open' AND created_at < ? "
            "AND portfolio_id IN (" + ",".join("?" * len(tur)) + ")",
            (once, *tur)).fetchall()]
        ids = [k["coupon_id"] for k in kup]
        bah = [dict(r) for r in conn.execute(
            "SELECT * FROM paper_bets WHERE coupon_id IN (" +
            ",".join("?" * len(ids)) + ")", tuple(ids)).fetchall()] if ids else []
        for b in bah:
            print(f"  {b['portfolio_id']:11s} {str(b['home_team'])[:14]:14s}-"
                  f"{str(b['away_team'])[:14]:14s} {b['market']:11s} "
                  f"{str(b['pick']):11s} @{float(b['odds']):.2f}")
        print(f"  {len(kup)} kupon · {len(bah)} ayak · gerekçe: {gerekce}")
        if not uygula or not ids:
            print("  KURU KOŞU — yazmak için --uygula" if ids else "  iptal edilecek kupon yok")
            return
        yedek = THIS_DIR / "yedek_turuncu_iptal.json"
        onceki = json.loads(yedek.read_text(encoding="utf-8")) if yedek.exists() else []
        onceki.append({"ts": _simdi(), "gerekce": gerekce, "kuponlar": kup, "ayaklar": bah})
        yedek.write_text(json.dumps(onceki, ensure_ascii=False, default=str, indent=1),
                         encoding="utf-8")
        simdi = _simdi()
        yer = ",".join("?" * len(ids))
        conn.execute("UPDATE paper_bets SET status='void', settled_at=?, "
                     "reason=COALESCE(reason,'') || ? WHERE coupon_id IN (" + yer + ")",
                     (simdi, " · ⛔ İPTAL: " + gerekce, *ids))
        conn.execute("UPDATE paper_coupons SET status='void', settled_at=?, "
                     "actual_return=stake, pnl=0 WHERE coupon_id IN (" + yer + ")",
                     (simdi, *ids))
        conn.commit()
        for pid in sorted({k["portfolio_id"] for k in kup}):
            n = sum(1 for k in kup if k["portfolio_id"] == pid)
            agents._journal(conn, pid, f"⛔ {n} kupon iptal (void)",
                            gerekce + " · kasa değişmedi · yedek: yedek_turuncu_iptal.json")
        conn.commit()
        print(f"  ✅ {len(ids)} kupon void · yedek {yedek.name}")
    finally:
        conn.close()


if __name__ == "__main__":
    if "--kur" in sys.argv:
        kur()
    elif "--iptal" in sys.argv:
        i = sys.argv.index("--iptal")
        iptal(sys.argv[i + 1],
              "fiyat pazar defterinin bayat satırından okundu (ör. Sevilla 10,50 "
              "— iddaa'da ~8,4); ajan canlı fiyatla yeniden karar verecek",
              uygula="--uygula" in sys.argv)
    else:
        import agents
        for pid, prof in agents.PROFILES.items():
            if prof.get("takim") != "turuncu":
                continue
            ps = adaylar(prof, f"[{pid.split('_')[0]}]")
            for p in ps[:6]:
                mm = p["_match"]
                print(f"     {str(mm['kickoff_utc'])[5:16]} {mm['league_code']:4s} "
                      f"{str(mm['home_team'])[:16]:16s}-{str(mm['away_team'])[:16]:16s} "
                      f"{p['market']:11s} {str(p['pick']):11s} oran {p['odds']:5.2f} "
                      f"model %{p['model_prob']*100:4.1f} edge {p['signal_score']*100:+5.1f}% "
                      f"etkin {p['_etkin']} mbs {mm['mbs']}")
