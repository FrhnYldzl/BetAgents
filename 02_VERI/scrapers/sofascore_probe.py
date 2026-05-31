"""
Sofascore API keşif probe — Playwright network interception (iddaa yöntemi).
Cloudflare'i gerçek tarayıcı geçer; yakalanan /api/v1 çağrılarından şema çıkarılır.

Kullanım:
  python sofascore_probe.py                 # headless dene
  python sofascore_probe.py --headed        # görünür tarayıcı (Cloudflare için daha sağlam)
"""
from __future__ import annotations
import sys, json, re
from pathlib import Path
from playwright.sync_api import sync_playwright

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

MATCH_URL = "https://www.sofascore.com/tr/football/match/slavia-mozyr-belshina-bobruisk/crbsirb"
OUT = Path(__file__).resolve().parent / "sofascore_capture.json"
HEADED = "--headed" in sys.argv

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

captured = []  # {url, status, keys, body?}


def _grab(resp):
    u = resp.url
    if "sofascore.com/api/v1/" not in u:
        return
    rec = {"url": u, "status": resp.status}
    try:
        if "json" in (resp.headers or {}).get("content-type", ""):
            b = resp.json()
            if isinstance(b, dict):
                rec["keys"] = list(b.keys())
                rec["body"] = b
            else:
                rec["keys"] = "[list]"
    except Exception:
        pass
    captured.append(rec)


def direct(page, url):
    """Sayfanın KENDİ fetch()'i ile çek → page JS bağlamı Cloudflare çerezlerini taşır → 200."""
    try:
        res = page.evaluate(
            """async (u) => {
                try {
                    const r = await fetch(u, {headers: {'Accept':'application/json'}});
                    let body = null;
                    try { body = await r.json(); } catch(e) {}
                    return {status: r.status, body: body};
                } catch(e) { return {status: 'ERR', body: null}; }
            }""",
            url,
        )
        return res.get("status"), res.get("body")
    except Exception as e:
        return "ERR", str(e)[:120]


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=not HEADED,
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx = browser.new_context(user_agent=UA, locale="tr-TR",
                                  viewport={"width": 1366, "height": 768})
        page = ctx.new_page()
        page.on("response", _grab)
        print(f"[1] Maç sayfası açılıyor (headed={HEADED})...")
        page.goto(MATCH_URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(9000)  # XHR'lerin atması için

        # event id'yi yakalanan çağrılardan bul
        ev_id = None
        for c in captured:
            m = re.search(r"/api/v1/event/(\d+)(?:$|[/?])", c["url"])
            if m:
                ev_id = m.group(1); break
        if not ev_id and captured:
            for c in captured:
                b = c.get("body") or {}
                if isinstance(b, dict) and isinstance(b.get("event"), dict) and b["event"].get("id"):
                    ev_id = str(b["event"]["id"]); break
        print(f"[2] Yakalanan /api/v1 çağrısı: {len(captured)}  | event id: {ev_id}")

        direct_results = {}
        if ev_id:
            base = "https://api.sofascore.com/api/v1/event/" + ev_id
            for name, ep in [
                ("event", base),
                ("statistics", base + "/statistics"),
                ("lineups", base + "/lineups"),
                ("graph", base + "/graph"),
                ("incidents", base + "/incidents"),
                ("h2h", base + "/h2h/events"),
                ("pregame-form", base + "/pregame-form"),
            ]:
                st, body = direct(page, ep)
                direct_results[name] = {"status": st,
                                        "keys": (list(body.keys()) if isinstance(body, dict) else None),
                                        "body": body if isinstance(body, dict) else None}
                print(f"    {name:14} -> {st}")
        browser.close()

    OUT.write_text(json.dumps(
        {"match_url": MATCH_URL, "event_id": ev_id,
         "captured_calls": [{"url": c["url"], "status": c["status"], "keys": c.get("keys")} for c in captured],
         "direct": {k: {"status": v["status"], "keys": v["keys"]} for k, v in direct_results.items()},
         "samples": direct_results},
        ensure_ascii=False, indent=2), encoding="utf-8")
    ok = sum(1 for c in captured if c["status"] == 200)
    print(f"[3] Kaydedildi: {OUT.name}  | 200-yakalanan: {ok}/{len(captured)}")
    return len(captured), ok


if __name__ == "__main__":
    run()
