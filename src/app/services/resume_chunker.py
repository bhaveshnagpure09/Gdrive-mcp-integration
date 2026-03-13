"""Resume section chunker.

Splits a raw (scrubbed) resume text into meaningful sections so that each
section can receive its own embedding.  This gives the retrieval pipeline
fine-grained signal instead of one coarse "whole-document" vector.

Sections produced
-----------------
- skills        : technical / soft skills block
- experience    : work-history narrative text
- projects      : project descriptions
- education     : degrees / institutions
- certifications: certificates / courses
- summary       : professional summary / objective
- full_profile  : the concatenated structured header (designation, YOE, skills
                  list) — used as a catch-all for very short or unstructured
                  resumes
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Section header patterns (order matters — more specific first)
# ---------------------------------------------------------------------------
_HEADER_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("certifications", re.compile(
        r"(?:^|\n)\s*(?:certifications?|certificates?|courses?|professional\s+development)"
        r"\s*[:\-]?\s*\n",
        re.IGNORECASE,
    )),
    ("education", re.compile(
        r"(?:^|\n)\s*(?:education|academic\s+background|academic\s+qualifications?|"
        r"degrees?)\s*[:\-]?\s*\n",
        re.IGNORECASE,
    )),
    ("projects", re.compile(
        r"(?:^|\n)\s*(?:projects?|key\s+projects?|selected\s+projects?|portfolio)"
        r"\s*[:\-]?\s*\n",
        re.IGNORECASE,
    )),
    ("experience", re.compile(
        r"(?:^|\n)\s*(?:work\s+experience|professional\s+experience|employment\s+history|"
        r"career\s+history|experience)\s*[:\-]?\s*\n",
        re.IGNORECASE,
    )),
    ("skills", re.compile(
        r"(?:^|\n)\s*(?:technical\s+skills?|skills?\s+&\s+technologies|core\s+competencies|"
        r"skills?|technologies?|key\s+skills?)\s*[:\-]?\s*\n",
        re.IGNORECASE,
    )),
    ("summary", re.compile(
        r"(?:^|\n)\s*(?:professional\s+summary|summary|profile|objective|about\s+me|"
        r"career\s+objective)\s*[:\-]?\s*\n",
        re.IGNORECASE,
    )),
]


@dataclass
class ResumeChunk:
    """A single section extracted from a resume."""

    section_type: str          # e.g. "skills", "experience", "education" …
    text: str                  # section text (already PII-scrubbed)
    candidate_id: str = ""     # set by caller after extraction
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class ResumeChunker:
    """Splits a PII-scrubbed resume into labelled section chunks."""

    # Minimum character length for a section to be considered useful
    _MIN_SECTION_LEN = 30

    @classmethod
    def chunk(cls, scrubbed_text: str, parsed_fields: dict | None = None) -> list[ResumeChunk]:
        """Return a list of :class:`ResumeChunk` objects for *scrubbed_text*.

        Always produces at least one chunk (``full_profile``) even if no
        section headers are detected.
        """
        parsed_fields = parsed_fields or {}
        chunks: list[ResumeChunk] = []

        sections = cls._split_by_headers(scrubbed_text)

        for section_type, text in sections.items():
            text = text.strip()
            if len(text) >= cls._MIN_SECTION_LEN:
                chunks.append(ResumeChunk(section_type=section_type, text=text))

        # Always add a structured "full_profile" chunk from parsed fields
        fp_text = cls._build_full_profile(scrubbed_text, parsed_fields)
        if fp_text:
            chunks.append(ResumeChunk(section_type="full_profile", text=fp_text))

        # Fall back if nothing was detected
        if not chunks:
            chunks.append(ResumeChunk(section_type="full_profile", text=scrubbed_text[:3000]))

        return chunks

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @classmethod
    def _split_by_headers(cls, text: str) -> dict[str, str]:
        """Detect section headers and split text accordingly.

        Returns a dict of {section_type: section_body} with no duplicates.
        Later occurrences of the same section type are appended.
        """
        # Find all header match positions
        hits: list[tuple[int, int, str]] = []  # (start, end, section_type)
        for section_type, pattern in _HEADER_PATTERNS:
            for m in pattern.finditer(text):
                hits.append((m.start(), m.end(), section_type))

        if not hits:
            return {}

        # Sort by position
        hits.sort(key=lambda h: h[0])

        sections: dict[str, list[str]] = {}
        for idx, (start, end, sec_type) in enumerate(hits):
            # Text runs from end-of-header to start-of-next-header (or EOF)
            body_start = end
            body_end = hits[idx + 1][0] if idx + 1 < len(hits) else len(text)
            body = text[body_start:body_end].strip()
            if body:
                sections.setdefault(sec_type, []).append(body)

        return {k: "\n\n".join(v) for k, v in sections.items()}

    @staticmethod
    def _build_full_profile(scrubbed_text: str, parsed_fields: dict) -> str:
        """Build a concise structured profile string from parsed fields."""
        name        = parsed_fields.get("name", "")
        designation = parsed_fields.get("designation", "")
        exp_months  = parsed_fields.get("experience_months", 0)
        skills      = parsed_fields.get("skills") or []
        skills_str  = ", ".join(skills[:25])

        lines = []
        if name:        lines.append(f"Name: {name}")
        if designation: lines.append(f"Role: {designation}")
        if exp_months:  lines.append(f"Experience: {exp_months} months ({exp_months // 12} years)")
        if skills_str:  lines.append(f"Skills: {skills_str}")
        # Append first 500 chars of free text as context
        if scrubbed_text:
            lines.append("Profile: " + scrubbed_text[:500].replace("\n", " "))
        return "\n".join(lines)
