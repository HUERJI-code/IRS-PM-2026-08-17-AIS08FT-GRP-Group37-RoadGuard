"""Remove source bookkeeping while retaining business text and source classification."""
import re


def clean_text(text: str) -> str:
    return re.sub(
        r'^(?:classification|Sources|Implementation sources|\u6765\u6e90)\s*[:\uff1a].*$',
        '', text, flags=re.M,
    ).strip()
