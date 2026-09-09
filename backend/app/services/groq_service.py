import logging
import os

from dotenv import load_dotenv
import google.genai as genai

load_dotenv()

logger = logging.getLogger(__name__)

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
FALLBACK_MESSAGE = (
    "AI-written recommendations aren't available for this report right now. "
    "All test results above are unaffected — see the scores and module details "
    "for the full findings."
)


def generate_ai_suggestions(prompt: str) -> str:
    """Generate report recommendations with Gemini without breaking the audit."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.warning("GEMINI_API_KEY is not set — skipping AI suggestions.")
        return FALLBACK_MESSAGE

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config={"temperature": 0.3, "max_output_tokens": 1000},
        )
        text = getattr(response, "text", None)
        if not text:
            logger.warning("Gemini returned an empty response.")
            return FALLBACK_MESSAGE
        return text
    except Exception as exc:
        logger.error("Gemini request failed: %s", exc)
        return FALLBACK_MESSAGE
