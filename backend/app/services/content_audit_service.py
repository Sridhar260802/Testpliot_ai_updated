import re
from collections import Counter

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import os


def _flesch_reading_ease(text: str) -> float:
    """Lightweight Flesch Reading Ease approximation (no external deps)."""

    words = re.findall(r"[A-Za-z']+", text)
    sentences = re.split(r"[.!?]+", text)
    sentences = [s for s in sentences if s.strip()]

    word_count = len(words)
    sentence_count = max(len(sentences), 1)

    def _count_syllables(word: str) -> int:
        word = word.lower()
        vowels = "aeiouy"
        count = 0
        prev_was_vowel = False
        for ch in word:
            is_vowel = ch in vowels
            if is_vowel and not prev_was_vowel:
                count += 1
            prev_was_vowel = is_vowel
        if word.endswith("e") and count > 1:
            count -= 1
        return max(count, 1)

    syllable_count = sum(_count_syllables(w) for w in words) or 1
    word_count = word_count or 1

    score = (
        206.835
        - 1.015 * (word_count / sentence_count)
        - 84.6 * (syllable_count / word_count)
    )
    return round(max(0, min(100, score)), 1)


def content_audit(url: str):
    """
    Real content audit: thin content detection, duplicate-paragraph
    detection within the page, a readability score, and heading/paragraph
    structure signals used to flag content-freshness opportunities.
    """

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=int(os.getenv("AUDIT_BROWSER_TIMEOUT", "15000")),
            )
            page.wait_for_timeout(int(os.getenv("AUDIT_RENDER_WAIT_MS", "500")))
            html = page.content()
            browser.close()

        soup = BeautifulSoup(html, "html.parser")

        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        paragraphs = [
            p.get_text(" ", strip=True)
            for p in soup.find_all("p")
            if p.get_text(strip=True)
        ]
        headings = [
            h.get_text(" ", strip=True)
            for h in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
        ]

        body_text = soup.get_text(" ", strip=True)
        word_count = len(re.findall(r"[A-Za-z0-9']+", body_text))

        # ---------------- Thin content ----------------
        thin_content = word_count < 300
        thin_content_severity = (
            "HIGH" if word_count < 150 else ("MEDIUM" if thin_content else "OK")
        )

        # ---------------- Duplicate paragraphs on the page ----------------
        normalized = [re.sub(r"\s+", " ", p.lower()).strip() for p in paragraphs]
        counts = Counter(normalized)
        duplicate_paragraphs = [
            text for text, n in counts.items() if n > 1 and len(text) > 40
        ]

        # ---------------- Readability ----------------
        readability_score = _flesch_reading_ease(body_text) if body_text else 0
        if readability_score >= 60:
            readability_label = "Easy to read"
        elif readability_score >= 30:
            readability_label = "Fairly difficult"
        else:
            readability_label = "Difficult to read"

        # ---------------- Structure / freshness signals ----------------
        no_headings = len(headings) == 0
        single_h1 = len(soup.find_all("h1")) == 1
        multiple_h1 = len(soup.find_all("h1")) > 1

        issues = []
        recommendations = []
        score = 100

        if thin_content:
            score -= 30
            issues.append(f"Thin content detected ({word_count} words on page).")
            recommendations.append(
                "Expand the page to at least 300 words of unique, relevant content."
            )

        if duplicate_paragraphs:
            score -= 20
            issues.append(
                f"{len(duplicate_paragraphs)} duplicate paragraph(s) found on the page."
            )
            recommendations.append(
                "Remove or rewrite repeated paragraphs to avoid diluting content quality."
            )

        if no_headings:
            score -= 15
            issues.append("No heading tags (H1-H6) found.")
            recommendations.append(
                "Add a clear heading structure to organize content for readers and search engines."
            )

        if multiple_h1:
            score -= 10
            issues.append("Multiple H1 tags found on the page.")
            recommendations.append("Use a single H1 tag per page for clarity.")

        if readability_score < 30 and body_text:
            score -= 15
            issues.append("Content readability is difficult for average readers.")
            recommendations.append(
                "Shorten sentences and use simpler words to improve readability."
            )

        score = max(0, score)

        if not issues:
            recommendations.append(
                "Content structure and depth look healthy. Keep it updated regularly."
            )

        return {
            "content_score": score,
            "word_count": word_count,
            "paragraph_count": len(paragraphs),
            "heading_count": len(headings),
            "thin_content": thin_content,
            "thin_content_severity": thin_content_severity,
            "duplicate_paragraph_count": len(duplicate_paragraphs),
            "duplicate_paragraphs_sample": duplicate_paragraphs[:3],
            "readability_score": readability_score,
            "readability_label": readability_label,
            "single_h1": single_h1,
            "multiple_h1": multiple_h1,
            "no_headings": no_headings,
            "issues": issues,
            "recommendations": recommendations,
        }

    except Exception as e:
        return {
            "content_score": 0,
            "word_count": 0,
            "paragraph_count": 0,
            "heading_count": 0,
            "thin_content": True,
            "thin_content_severity": "UNKNOWN",
            "duplicate_paragraph_count": 0,
            "duplicate_paragraphs_sample": [],
            "readability_score": 0,
            "readability_label": "N/A",
            "single_h1": False,
            "multiple_h1": False,
            "no_headings": True,
            "issues": [str(e)],
            "recommendations": ["Verify the website URL or internet connection."],
            "error": str(e),
        }
