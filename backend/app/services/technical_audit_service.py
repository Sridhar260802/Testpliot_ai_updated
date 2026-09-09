from urllib.parse import urljoin, urlparse

import requests
import os
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

MAX_LINKS_TO_CHECK = 25


def _same_domain(base_url: str, link: str) -> bool:
    try:
        return urlparse(base_url).netloc == urlparse(link).netloc
    except Exception:
        return False


def _crawl_errors_and_redirects(url: str):
    """Real crawl: pulls internal links off the page and HEAD/GET-checks
    each one for broken links (4xx/5xx) and redirect chains (3xx)."""

    broken_links = []
    redirect_links = []
    checked = 0

    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(resp.text, "html.parser")

        links = set()
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if href.startswith(("#", "mailto:", "tel:", "javascript:")):
                continue
            full_url = urljoin(url, href)
            if _same_domain(url, full_url):
                links.add(full_url)

        for link in list(links)[:MAX_LINKS_TO_CHECK]:
            checked += 1
            try:
                r = requests.get(
                    link,
                    timeout=8,
                    allow_redirects=True,
                    headers={"User-Agent": "Mozilla/5.0"},
                )
                if r.history:
                    redirect_links.append(
                        {
                            "url": link,
                            "redirect_count": len(r.history),
                            "final_url": r.url,
                            "status_codes": [h.status_code for h in r.history] + [r.status_code],
                        }
                    )
                if r.status_code >= 400:
                    broken_links.append({"url": link, "status_code": r.status_code})
            except requests.RequestException as link_err:
                broken_links.append({"url": link, "status_code": None, "error": str(link_err)})

    except Exception as e:
        return {
            "links_checked": 0,
            "broken_links": [],
            "redirect_links": [],
            "error": str(e),
        }

    return {
        "links_checked": checked,
        "broken_links": broken_links,
        "redirect_links": redirect_links,
    }


def _caching_and_compression(url: str):
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        headers = {k.lower(): v for k, v in resp.headers.items()}

        cache_control = headers.get("cache-control")
        content_encoding = headers.get("content-encoding")
        compressed = content_encoding in ("gzip", "br", "deflate")

        return {
            "cache_control": cache_control,
            "has_cache_control": cache_control is not None,
            "content_encoding": content_encoding,
            "is_compressed": compressed,
        }
    except Exception as e:
        return {
            "cache_control": None,
            "has_cache_control": False,
            "content_encoding": None,
            "is_compressed": False,
            "error": str(e),
        }


def _core_web_vitals(url: str):
    """Captures real Largest Contentful Paint (LCP) and Cumulative Layout
    Shift (CLS) via the browser's own Performance/Layout-Instability APIs
    (no external Lighthouse/PSI API key required)."""

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            page.add_init_script(
                """
                window.__cwv = { lcp: 0, cls: 0 };
                try {
                    new PerformanceObserver((list) => {
                        const entries = list.getEntries();
                        const last = entries[entries.length - 1];
                        if (last) window.__cwv.lcp = last.renderTime || last.loadTime || 0;
                    }).observe({ type: 'largest-contentful-paint', buffered: true });
                } catch (e) {}
                try {
                    new PerformanceObserver((list) => {
                        for (const entry of list.getEntries()) {
                            if (!entry.hadRecentInput) window.__cwv.cls += entry.value;
                        }
                    }).observe({ type: 'layout-shift', buffered: true });
                } catch (e) {}
                """
            )

            page.goto(
                url,
                wait_until="load",
                timeout=int(os.getenv("AUDIT_BROWSER_TIMEOUT", "15000")),
            )
            page.wait_for_timeout(4000)

            cwv = page.evaluate("window.__cwv")

            nav_timing = page.evaluate(
                """
                () => {
                    const nav = performance.getEntriesByType('navigation')[0];
                    if (!nav) return null;
                    return {
                        ttfb_ms: Math.round(nav.responseStart - nav.requestStart),
                        dom_content_loaded_ms: Math.round(nav.domContentLoadedEventEnd - nav.startTime),
                        load_event_ms: Math.round(nav.loadEventEnd - nav.startTime)
                    };
                }
                """
            )

            browser.close()

        lcp_ms = round(cwv.get("lcp", 0)) if cwv else 0
        cls = round(cwv.get("cls", 0), 3) if cwv else 0

        return {
            "largest_contentful_paint_ms": lcp_ms,
            "cumulative_layout_shift": cls,
            "time_to_first_byte_ms": nav_timing.get("ttfb_ms") if nav_timing else None,
            "dom_content_loaded_ms": nav_timing.get("dom_content_loaded_ms") if nav_timing else None,
            "load_event_ms": nav_timing.get("load_event_ms") if nav_timing else None,
        }
    except Exception as e:
        return {
            "largest_contentful_paint_ms": None,
            "cumulative_layout_shift": None,
            "time_to_first_byte_ms": None,
            "dom_content_loaded_ms": None,
            "load_event_ms": None,
            "error": str(e),
        }


def technical_audit(url: str):
    """
    Real technical audit combining: broken links / crawl errors, redirect
    chains (301/302), caching & compression headers, and Core Web Vitals
    (LCP, CLS) captured directly from the browser.
    """

    crawl = _crawl_errors_and_redirects(url)
    caching = _caching_and_compression(url)
    vitals = _core_web_vitals(url)

    issues = []
    recommendations = []
    score = 100

    if crawl.get("broken_links"):
        score -= 25
        issues.append(f"{len(crawl['broken_links'])} broken internal link(s) found.")
        recommendations.append("Fix or remove broken internal links (404s/errors).")

    if crawl.get("redirect_links"):
        score -= 10
        issues.append(f"{len(crawl['redirect_links'])} internal link(s) go through a redirect.")
        recommendations.append(
            "Point internal links directly to the final URL instead of through a redirect."
        )

    if not caching.get("has_cache_control"):
        score -= 15
        issues.append("No Cache-Control header set on the main page response.")
        recommendations.append("Add Cache-Control headers to enable browser/CDN caching.")

    if not caching.get("is_compressed"):
        score -= 15
        issues.append("Response is not compressed (gzip/brotli).")
        recommendations.append("Enable gzip or Brotli compression on the server.")

    lcp = vitals.get("largest_contentful_paint_ms")
    if lcp is not None and lcp > 2500:
        score -= 20
        issues.append(f"Largest Contentful Paint is slow ({lcp} ms).")
        recommendations.append(
            "Optimize the largest above-the-fold element (image/text block) to load faster."
        )

    cls = vitals.get("cumulative_layout_shift")
    if cls is not None and cls > 0.1:
        score -= 15
        issues.append(f"Cumulative Layout Shift is high ({cls}).")
        recommendations.append(
            "Reserve space for images/ads/embeds to prevent layout shifts while loading."
        )

    score = max(0, score)

    if not issues:
        recommendations.append(
            "Crawlability, caching, and Core Web Vitals look healthy."
        )

    return {
        "technical_score": score,
        "crawl": crawl,
        "caching_and_compression": caching,
        "core_web_vitals": vitals,
        "issues": issues,
        "recommendations": recommendations,
    }
