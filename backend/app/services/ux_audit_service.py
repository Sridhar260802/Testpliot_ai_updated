import re

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import os

CTA_KEYWORDS = [
    "buy now", "sign up", "get started", "subscribe", "book now",
    "add to cart", "learn more", "contact us", "try free", "try now",
    "download", "request demo", "start free trial", "shop now", "order now",
]

VIEWPORTS = [
    {"name": "mobile", "width": 375, "height": 812},
    {"name": "tablet", "width": 768, "height": 1024},
    {"name": "desktop", "width": 1440, "height": 900},
]


def ux_audit(url: str):
    """
    Real UX audit: navigation/menu structure, CTA detection, footer
    presence, and mobile/tablet/desktop responsiveness (checked by
    actually rendering the page at each viewport and looking for
    horizontal overflow / hidden nav).
    """

    try:
        issues = []
        recommendations = []
        score = 100

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)

            # ---------------- Static structure (desktop render) ----------------
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=int(os.getenv("AUDIT_BROWSER_TIMEOUT", "15000")),
            )
            page.wait_for_timeout(int(os.getenv("AUDIT_RENDER_WAIT_MS", "500")))
            html = page.content()
            page.close()

            soup = BeautifulSoup(html, "html.parser")

            nav_elements = soup.find_all("nav")
            header = soup.find("header")
            footer = soup.find("footer")

            nav_links = []
            if nav_elements:
                for nav in nav_elements:
                    nav_links.extend(nav.find_all("a"))
            elif header:
                nav_links.extend(header.find_all("a"))

            has_navigation = len(nav_elements) > 0 or (
                header is not None and len(header.find_all("a")) >= 2
            )
            has_footer = footer is not None

            page_text = soup.get_text(" ", strip=True).lower()
            buttons_and_links_text = " ".join(
                el.get_text(" ", strip=True).lower()
                for el in soup.find_all(["a", "button"])
            )
            cta_hits = [kw for kw in CTA_KEYWORDS if kw in buttons_and_links_text]
            has_cta = len(cta_hits) > 0

            # ---------------- Responsiveness across viewports ----------------
            responsive_results = {}
            for vp in VIEWPORTS:
                vp_page = browser.new_page(
                    viewport={"width": vp["width"], "height": vp["height"]}
                )
                try:
                    vp_page.goto(
                        url,
                        wait_until="domcontentloaded",
                        timeout=int(os.getenv("AUDIT_BROWSER_TIMEOUT", "15000")),
                    )
                    vp_page.wait_for_timeout(int(os.getenv("AUDIT_RENDER_WAIT_MS", "500")))

                    scroll_width = vp_page.evaluate("document.documentElement.scrollWidth")
                    client_width = vp_page.evaluate("document.documentElement.clientWidth")
                    has_horizontal_scroll = scroll_width > client_width + 5

                    nav_visible = True
                    if nav_elements:
                        try:
                            nav_visible = vp_page.locator("nav").first.is_visible()
                        except Exception:
                            nav_visible = True

                    responsive_results[vp["name"]] = {
                        "width": vp["width"],
                        "horizontal_scroll_detected": has_horizontal_scroll,
                        "navigation_visible": nav_visible,
                    }
                except Exception as vp_err:
                    responsive_results[vp["name"]] = {
                        "width": vp["width"],
                        "error": str(vp_err),
                    }
                finally:
                    vp_page.close()

            browser.close()

        mobile_result = responsive_results.get("mobile", {})
        mobile_overflow = mobile_result.get("horizontal_scroll_detected", False)
        mobile_nav_visible = mobile_result.get("navigation_visible", True)

        # ---------------- Scoring ----------------
        if not has_navigation:
            score -= 20
            issues.append("No clear navigation menu (<nav> or header links) found.")
            recommendations.append(
                "Add a visible navigation menu so users can find key pages easily."
            )

        if not has_footer:
            score -= 10
            issues.append("No <footer> element found.")
            recommendations.append(
                "Add a footer with contact info, links, and legal pages."
            )

        if not has_cta:
            score -= 20
            issues.append("No clear call-to-action (CTA) text found on the page.")
            recommendations.append(
                "Add a clear CTA button (e.g. 'Get Started', 'Sign Up', 'Contact Us')."
            )

        if mobile_overflow:
            score -= 20
            issues.append("Horizontal scrolling detected on mobile viewport.")
            recommendations.append(
                "Fix elements that overflow the mobile viewport (e.g. fixed widths, unscaled images)."
            )

        if not mobile_nav_visible:
            score -= 15
            issues.append("Navigation menu is not visible/accessible on mobile viewport.")
            recommendations.append(
                "Add a mobile-friendly menu (e.g. hamburger menu) so navigation works on small screens."
            )

        score = max(0, score)

        if not issues:
            recommendations.append(
                "Navigation, CTAs, and responsiveness look solid across devices."
            )

        return {
            "ux_score": score,
            "has_navigation": has_navigation,
            "navigation_link_count": len(nav_links),
            "has_footer": has_footer,
            "has_cta": has_cta,
            "cta_keywords_found": cta_hits,
            "responsiveness": responsive_results,
            "mobile_horizontal_overflow": mobile_overflow,
            "mobile_navigation_visible": mobile_nav_visible,
            "issues": issues,
            "recommendations": recommendations,
        }

    except Exception as e:
        return {
            "ux_score": 0,
            "has_navigation": False,
            "navigation_link_count": 0,
            "has_footer": False,
            "has_cta": False,
            "cta_keywords_found": [],
            "responsiveness": {},
            "mobile_horizontal_overflow": None,
            "mobile_navigation_visible": None,
            "issues": [str(e)],
            "recommendations": ["Verify the website URL or internet connection."],
            "error": str(e),
        }
