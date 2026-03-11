import pytest
from app.core.pii_scrubber import PIIScrubber

def test_scrub_email():
    text = "Contact me at test@example.com"
    scrubbed = PIIScrubber.scrub(text)
    assert "[REDACTED_EMAIL]" in scrubbed

def test_scrub_phone():
    text = "Call me at 1234567890"
    scrubbed = PIIScrubber.scrub(text)
    assert "REDACTED_PHONE" in scrubbed