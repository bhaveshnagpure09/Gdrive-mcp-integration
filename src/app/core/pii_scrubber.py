"""PII scrubbing utilities for resume text."""

import re

# ---------------------------------------------------------------------------
# Regex patterns for common PII
# ---------------------------------------------------------------------------
_PATTERNS: list[tuple[str, str, int]] = [
    # (label, pattern, re_flags)
    ("email",   r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", 0),
    ("phone_10", r"\b\d{10}\b", 0),
    ("phone_intl", r"\+?\d[\d\-\s().]{8,}\d", 0),
    # Aadhaar (12-digit Indian national ID) – common in Indian resumes
    ("aadhaar", r"\b\d{4}\s?\d{4}\s?\d{4}\b", 0),
    # PAN card – optional in resumes
    ("pan",     r"\b[A-Z]{5}\d{4}[A-Z]\b", 0),
    # Passport number (Indian format: letter + 7 digits)
    ("passport", r"\b[A-Z]\d{7}\b", 0),
    # LinkedIn / GitHub / personal URLs that may expose identity
    ("linkedin_url", r"https?://(?:www\.)?linkedin\.com/in/[\w\-]+/?", re.IGNORECASE),
    ("github_url",   r"https?://(?:www\.)?github\.com/[\w\-]+/?", re.IGNORECASE),
]

_COMPILED: list[tuple[str, re.Pattern]] = [
    (label, re.compile(pattern, flags)) for label, pattern, flags in _PATTERNS
]


class PIIScrubber:
    """Removes or masks PII from raw resume text before further processing."""

    @staticmethod
    def scrub(text: str) -> str:
        """Return *text* with all detected PII replaced by labelled placeholders."""
        for label, pattern in _COMPILED:
            placeholder = f"[REDACTED_{label.upper()}]"
            text = pattern.sub(placeholder, text)
        return text

    @staticmethod
    def build_profile_text(
        *,
        designation: str = "",
        location: str = "",
        work_mode: str = "",
        experience_months: int = 0,
        skills: list[str] | None = None,
        certifications: list[str] | None = None,
        resume_text: str = "",
    ) -> str:
        """Construct the structured profile text used for embedding generation.

        Args:
            designation: Job title / role of the candidate.
            location: Base location.
            work_mode: Preferred work mode (remote / hybrid / onsite).
            experience_months: Total experience in months.
            skills: List of skill names.
            certifications: List of certification names.
            resume_text: Raw (scrubbed) resume content from Google Drive.

        Returns:
            Formatted profile text string.
        """
        skills_str = ", ".join(skills) if skills else ""
        certs_str = ", ".join(certifications) if certifications else ""
        return (
            f"Designation: {designation}\n"
            f"Location: {location}\n"
            f"Work Mode: {work_mode}\n"
            f"Experience: {experience_months} months\n"
            f"Skills: {skills_str}\n"
            f"Certifications: {certs_str}\n"
            f"Resume Content: {resume_text}"
        )


class ResumeParser:
    """Extracts structured candidate data from raw resume text."""

    # InfoBeans template: name follows "PROUD MEMBER OF" — single line only
    _NAME_AFTER_PROUD = re.compile(
        r"PROUD MEMBER OF[^\S\r\n]*\r?\n[^\S\r\n]*([A-Z][a-z]+(?:[^\S\r\n]+[A-Z][a-z]+)+)[^\S\r\n]*\r?$",
        re.MULTILINE,
    )
    # Fallback: first standalone Title-Case line (2–3 words, purely alphabetic)
    _NAME_STANDALONE = re.compile(
        r"^([A-Z][a-zA-Z]+(?:[ \t]+[A-Z][a-zA-Z]+){1,2})[^\S\r\n]*\r?$", re.MULTILINE
    )

    _DESIGNATION_RE = re.compile(
        r"(?:Senior|Junior|Sr\.?|Jr\.?|Lead|Principal|Staff|Associate|Mid)?"
        r"\s*(?:Software|Backend|Frontend|Full[\s\-]?Stack|Python|Java|Data|AI|ML"
        r"|DevOps|Cloud|Project|Product|QA|Test|Solution|System|Platform)?"
        r"\s*(?:Engineer|Developer|Architect|Manager|Lead|Analyst|Scientist"
        r"|Consultant|Specialist|Designer)\b",
        re.IGNORECASE,
    )

    _EXPERIENCE_YRS = re.compile(
        r"(\d+)\+?\s*years?\s*(?:of\s*)?(?:experience|exp\.?)", re.IGNORECASE
    )

    _SKILLS_SECTION = re.compile(
        r"(?:Technical\s+)?Skills?[:\-\s]+\n(.*?)(?=\n{2,}|\Z)", re.IGNORECASE | re.DOTALL
    )
    # Inline comma/pipe-separated skills on one line (e.g. "Skills: Python, FastAPI, SQL")
    _SKILLS_INLINE = re.compile(
        r"(?:Technical\s+)?Skills?[:\-\s]+([^\n]+)", re.IGNORECASE
    )

    @classmethod
    def extract_name(cls, text: str) -> str:
        m = cls._NAME_AFTER_PROUD.search(text)
        if m:
            return m.group(1).strip()
        for m in cls._NAME_STANDALONE.finditer(text[:1000]):
            candidate = m.group(1).strip()
            # Must have at least 2 words and not look like a section header
            words = candidate.split()
            if 2 <= len(words) <= 4 and all(w.isalpha() for w in words):
                return candidate
        return ""

    @classmethod
    def name_to_team_member_id(cls, name: str) -> str:
        if not name:
            return ""
        return re.sub(r"[^a-z0-9]+", "_", name.lower().strip()).strip("_")

    @classmethod
    def extract_designation(cls, text: str) -> str:
        m = cls._DESIGNATION_RE.search(text[:2000])
        if m:
            return m.group(0).strip()
        return ""

    @classmethod
    def extract_experience_months(cls, text: str) -> int:
        m = cls._EXPERIENCE_YRS.search(text)
        if m:
            return int(m.group(1)) * 12
        return 0

    @classmethod
    def extract_skills(cls, text: str) -> list[str]:
        """Extract skills from Skills section or inline skill line."""
        raw = ""
        m = cls._SKILLS_SECTION.search(text)
        if m:
            raw = m.group(1)
        else:
            m = cls._SKILLS_INLINE.search(text)
            if m:
                raw = m.group(1)
        if not raw:
            return []
        parts = re.split(r"[,\n\r•|/\\]+", raw)
        skills: list[str] = []
        for p in parts:
            s = p.strip().strip("-•").strip()
            if 2 <= len(s) <= 50 and not re.search(r"\d{4}", s):
                skills.append(s)
        return skills[:30]

    @classmethod
    def extract_all(cls, text: str) -> dict:
        """Run all extractors and return a structured dict."""
        name = cls.extract_name(text)
        return {
            "name": name,
            "team_member_id": cls.name_to_team_member_id(name),
            "designation": cls.extract_designation(text),
            "experience_months": cls.extract_experience_months(text),
            "skills": cls.extract_skills(text),
        }