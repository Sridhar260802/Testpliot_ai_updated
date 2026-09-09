from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import os

CHECKOUT_KEYWORDS = [
    "checkout", "cart", "add to cart", "buy now", "place order",
    "proceed to checkout", "payment", "billing address", "shipping address",
]

ANALYTICS_SIGNATURES = {
    "google_analytics": ["gtag(", "google-analytics.com", "googletagmanager.com/gtag"],
    "google_tag_manager": ["googletagmanager.com/gtm.js", "gtm.js"],
    "facebook_pixel": ["fbq(", "connect.facebook.net"],
    "hotjar": ["hotjar.com", "hj("],
    "segment": ["cdn.segment.com", "analytics.track("],
}


def cro_audit(url: str):
    """
    Real CRO audit: form usability (labels, required fields, field count),
    checkout-flow detection, CTA placement (above vs. below the fold, by
    DOM position), and analytics/conversion-tracking script detection.
    """

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=int(os.getenv("AUDIT_BROWSER_TIMEOUT", "15000")),
            )
            page.wait_for_timeout(int(os.getenv("AUDIT_RENDER_WAIT_MS", "500")))
            html = page.content()

            # CTA "above the fold" check: any button/CTA-like link within
            # the first screen height.
            cta_above_fold = page.evaluate(
                """
                () => {
                    const vh = window.innerHeight;
                    const els = Array.from(document.querySelectorAll('a, button'));
                    return els.some(el => {
                        const rect = el.getBoundingClientRect();
                        const text = (el.innerText || '').toLowerCase();
                        const looksLikeCta = /buy|sign up|start|subscribe|book|add to cart|contact|try|download|order|get started|shop/.test(text);
                        return looksLikeCta && rect.top < vh && rect.top >= 0;
                    });
                }
                """
            )

            browser.close()

        soup = BeautifulSoup(html, "html.parser")
        html_lower = html.lower()

        # ---------------- Forms ----------------
        forms = soup.find_all("form")
        form_reports = []
        for form in forms:
            inputs = form.find_all(["input", "textarea", "select"])
            visible_inputs = [
                i for i in inputs if i.get("type") not in ("hidden", "submit", "button")
            ]
            labeled = 0
            for inp in visible_inputs:
                input_id = inp.get("id")
                has_label = bool(input_id and form.find("label", attrs={"for": input_id}))
                has_placeholder = bool(inp.get("placeholder"))
                has_aria_label = bool(inp.get("aria-label"))
                if has_label or has_placeholder or has_aria_label:
                    labeled += 1

            required_fields = [i for i in visible_inputs if i.has_attr("required")]

            form_reports.append(
                {
                    "field_count": len(visible_inputs),
                    "labeled_field_count": labeled,
                    "required_field_count": len(required_fields),
                    "has_submit_button": bool(
                        form.find("button") or form.find("input", attrs={"type": "submit"})
                    ),
                }
            )

        has_forms = len(forms) > 0
        poorly_labeled_forms = [
            f for f in form_reports
            if f["field_count"] > 0 and f["labeled_field_count"] < f["field_count"]
        ]

        # ---------------- Checkout flow ----------------
        checkout_signals = [kw for kw in CHECKOUT_KEYWORDS if kw in html_lower]
        looks_like_ecommerce = len(checkout_signals) >= 2

        # ---------------- Analytics / conversion tracking ----------------
        detected_analytics = []
        for name, signatures in ANALYTICS_SIGNATURES.items():
            if any(sig in html_lower for sig in signatures):
                detected_analytics.append(name)
        has_conversion_tracking = len(detected_analytics) > 0

        # ---------------- Scoring ----------------
        issues = []
        recommendations = []
        score = 100

        if not cta_above_fold:
            score -= 25
            issues.append("No clear call-to-action visible above the fold.")
            recommendations.append(
                "Place a primary CTA button in the first screen users see, without scrolling."
            )

        if has_forms and poorly_labeled_forms:
            score -= 20
            issues.append(
                f"{len(poorly_labeled_forms)} form(s) have fields without labels or placeholders."
            )
            recommendations.append(
                "Add labels or placeholder text to every form field to reduce user drop-off."
            )

        if looks_like_ecommerce and "checkout" not in html_lower and "cart" not in html_lower:
            score -= 15
            issues.append("E-commerce signals found but no clear checkout/cart flow detected.")
            recommendations.append(
                "Make the checkout/cart path clearly labeled and easy to find."
            )

        if not has_conversion_tracking:
            score -= 20
            issues.append("No analytics or conversion-tracking script detected.")
            recommendations.append(
                "Add analytics (e.g. Google Analytics/Tag Manager) to measure conversions."
            )

        score = max(0, score)

        if not issues:
            recommendations.append(
                "CTA placement, forms, and conversion tracking look solid."
            )

        return {
            "cro_score": score,
            "cta_above_fold": bool(cta_above_fold),
            "form_count": len(forms),
            "forms": form_reports,
            "poorly_labeled_form_count": len(poorly_labeled_forms),
            "looks_like_ecommerce": looks_like_ecommerce,
            "checkout_signals_found": checkout_signals,
            "analytics_detected": detected_analytics,
            "has_conversion_tracking": has_conversion_tracking,
            "issues": issues,
            "recommendations": recommendations,
        }

    except Exception as e:
        return {
            "cro_score": 0,
            "cta_above_fold": False,
            "form_count": 0,
            "forms": [],
            "poorly_labeled_form_count": 0,
            "looks_like_ecommerce": False,
            "checkout_signals_found": [],
            "analytics_detected": [],
            "has_conversion_tracking": False,
            "issues": [str(e)],
            "recommendations": ["Verify the website URL or internet connection."],
            "error": str(e),
        }
