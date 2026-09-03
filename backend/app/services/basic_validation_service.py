"""
Basic-tier content & image validation.

These checks are intentionally lightweight (plain requests + BeautifulSoup,
no Playwright browser launch) so the Basic plan stays fast and cheap to run,
in contrast to the browser-driven checks used by the Standard/Premium tiers.
"""

import requests
from bs4 import BeautifulSoup


def basic_content_validation(url: str):
    """
    Basic content checks: page loads, has a title, has a meta description,
    has at least one heading, and has a reasonable amount of text content.
    """

    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")

        title = soup.title.string.strip() if soup.title and soup.title.string else ""
        meta_description = soup.find("meta", attrs={"name": "description"})
        headings = soup.find_all(["h1", "h2", "h3"])

        text_content = soup.get_text(separator=" ", strip=True)
        word_count = len(text_content.split())

        issues = []
        recommendations = []

        if not title:
            issues.append("Missing <title> tag.")
            recommendations.append("Add a unique, descriptive <title> tag to every page.")

        if not meta_description or not meta_description.get("content", "").strip():
            issues.append("Missing meta description.")
            recommendations.append(
                "Write a 120-155 character meta description summarizing the page."
            )

        if not headings:
            issues.append("No heading tags (h1/h2/h3) found.")
            recommendations.append(
                "Structure the page with h1/h2/h3 headings to help readers and search engines."
            )

        if word_count < 100:
            issues.append("Thin content: page has fewer than 100 words.")
            recommendations.append(
                "Expand the page to at least a few hundred words of unique, useful content."
            )

        if not recommendations:
            recommendations.append("Content looks solid. Keep it updated regularly.")

        score = 100 - (len(issues) * 20)
        score = max(score, 0)

        return {
            "content_score": score,
            "title": title,
            "has_meta_description": bool(meta_description),
            "heading_count": len(headings),
            "word_count": word_count,
            "issues": issues,
            "recommendations": recommendations,
            "status": "PASS" if not issues else "FAIL",
        }

    except Exception as e:
        return {
            "content_score": 0,
            "title": "",
            "has_meta_description": False,
            "heading_count": 0,
            "word_count": 0,
            "issues": [f"Could not validate content: {str(e)}"],
            "recommendations": ["Verify the website URL or internet connection."],
            "status": "FAIL",
        }


def basic_image_validation(url: str):
    """
    Basic image checks: counts images, flags images missing alt text,
    and flags images missing a usable src attribute.
    """

    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")

        images = soup.find_all("img")
        total_images = len(images)

        missing_alt = 0
        missing_src = 0

        for img in images:
            alt = img.get("alt")
            src = img.get("src")

            if not alt or not alt.strip():
                missing_alt += 1

            if not src or not src.strip():
                missing_src += 1

        issues = []
        recommendations = []

        if missing_alt:
            issues.append(f"{missing_alt} image(s) missing alt text.")
            recommendations.append(
                "Add descriptive alt text to every image for accessibility and image SEO."
            )

        if missing_src:
            issues.append(f"{missing_src} image(s) missing a src attribute.")
            recommendations.append(
                "Make sure every <img> tag has a valid, working src attribute."
            )

        if not recommendations:
            recommendations.append("Images look well optimized. No action needed.")

        if total_images == 0:
            score = 100
        else:
            penalised = missing_alt + missing_src
            score = max(100 - int((penalised / (total_images * 2)) * 100), 0)

        return {
            "image_score": score,
            "total_images": total_images,
            "missing_alt": missing_alt,
            "missing_src": missing_src,
            "issues": issues,
            "recommendations": recommendations,
            "status": "PASS" if not issues else "FAIL",
        }

    except Exception as e:
        return {
            "image_score": 0,
            "total_images": 0,
            "missing_alt": 0,
            "missing_src": 0,
            "issues": [f"Could not validate images: {str(e)}"],
            "recommendations": ["Verify the website URL or internet connection."],
            "status": "FAIL",
        }