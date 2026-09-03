"""
Shared Playwright stealth helpers.

Render (and most cloud hosts) run from datacenter IP ranges that
Cloudflare and similar bot-protection services treat with more
suspicion than a residential/home IP. On top of that, a default
headless Chromium instance exposes a few obvious automation signals
(navigator.webdriver, missing plugins, a generic user-agent) that
bot-detection scripts check for.

These helpers don't guarantee bypassing strong protection (Cloudflare
Turnstile in particular can still block a headless browser no matter
what), but they remove the easy, common signals so more sites go
through cleanly.

Use launch_stealth_browser(p) instead of p.chromium.launch(...), and
new_stealth_page(browser, **kwargs) instead of browser.new_page(...).
Any kwargs you'd normally pass to new_page (e.g. viewport=...) still
work — they're merged in.
"""

STEALTH_LAUNCH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-dev-shm-usage",
    "--no-sandbox",
]

STEALTH_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Removes / patches the most common headless-detection signals that
# site-side JS checks for before the page's own scripts run.
STEALTH_INIT_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
window.chrome = { runtime: {} };
"""


def launch_stealth_browser(p, headless: bool = True):
    """Drop-in replacement for p.chromium.launch(headless=True)."""
    return p.chromium.launch(headless=headless, args=STEALTH_LAUNCH_ARGS)


def new_stealth_page(browser, **kwargs):
    """
    Drop-in replacement for browser.new_page(...). Sets a realistic
    user-agent (unless the caller already passed one) and patches
    common automation signals before any page script runs.
    """
    kwargs.setdefault("user_agent", STEALTH_USER_AGENT)
    page = browser.new_page(**kwargs)
    page.add_init_script(STEALTH_INIT_SCRIPT)
    return page


def is_bot_blocked(html: str, status_code: int = None) -> bool:
    """
    Heuristic check for a Cloudflare/anti-bot interstitial page instead
    of real content, so callers can report an honest error rather than
    silently scoring an empty challenge page.
    """
    if status_code == 403:
        return True
    if not html:
        return False
    lowered = html.lower()
    markers = [
        "just a moment",
        "checking your browser",
        "cf-browser-verification",
        "attention required! | cloudflare",
        "please enable cookies",
        "cf-chl-",
    ]
    return any(marker in lowered for marker in markers)