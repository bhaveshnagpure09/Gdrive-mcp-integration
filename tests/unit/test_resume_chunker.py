"""Unit tests for ResumeChunker — section splitting and ranking validity."""

import pytest
from app.services.resume_chunker import ResumeChunker, ResumeChunk


# ---------------------------------------------------------------------------
# Sample resumes
# ---------------------------------------------------------------------------

STRUCTURED_RESUME = """
John Doe
Senior Software Engineer

Professional Summary:

Results-driven engineer with 8 years of experience building distributed systems.

Skills:
Python, FastAPI, PostgreSQL, Redis, Docker, Kubernetes, AWS

Work Experience:

Tech Corp - Senior Engineer (2019-2024)
Designed and implemented microservices architecture serving 10M daily requests.
Led a team of 5 engineers, reducing deployment time by 40%.

Acme Inc - Software Engineer (2016-2019)
Built REST APIs used by internal tooling teams.

Projects:

Job Matching System: AI-powered candidate-to-job matching using LangGraph and vector DBs.
Data Pipeline: Real-time ETL pipeline processing 500k events/day using Kafka and Flink.

Education:

B.Sc. Computer Science, State University (2016)

Certifications:

AWS Certified Solutions Architect (2022)
Google Cloud Professional Data Engineer (2023)
"""

MINIMAL_RESUME = "Experienced developer with Python and Django. 3 years experience."

SKILLS_ONLY_RESUME = """
Technical Skills:
Python, Java, SQL, Docker, Kubernetes, React, Node.js
"""


# ---------------------------------------------------------------------------
# Tests: basic chunking
# ---------------------------------------------------------------------------

def test_chunk_returns_list_of_resume_chunks():
    chunks = ResumeChunker.chunk(STRUCTURED_RESUME)
    assert isinstance(chunks, list)
    assert all(isinstance(c, ResumeChunk) for c in chunks)
    assert len(chunks) > 0


def test_chunk_detects_skills_section():
    chunks = ResumeChunker.chunk(STRUCTURED_RESUME)
    types = {c.section_type for c in chunks}
    assert "skills" in types, f"Expected 'skills' section in {types}"


def test_chunk_detects_experience_section():
    chunks = ResumeChunker.chunk(STRUCTURED_RESUME)
    types = {c.section_type for c in chunks}
    assert "experience" in types, f"Expected 'experience' section in {types}"


def test_chunk_detects_education_section():
    chunks = ResumeChunker.chunk(STRUCTURED_RESUME)
    types = {c.section_type for c in chunks}
    assert "education" in types, f"Expected 'education' section in {types}"


def test_chunk_detects_certifications_section():
    chunks = ResumeChunker.chunk(STRUCTURED_RESUME)
    types = {c.section_type for c in chunks}
    assert "certifications" in types, f"Expected 'certifications' section in {types}"


def test_chunk_detects_projects_section():
    chunks = ResumeChunker.chunk(STRUCTURED_RESUME)
    types = {c.section_type for c in chunks}
    assert "projects" in types, f"Expected 'projects' section in {types}"


def test_chunk_always_produces_full_profile():
    """full_profile chunk must always be present."""
    chunks = ResumeChunker.chunk(STRUCTURED_RESUME)
    types = {c.section_type for c in chunks}
    assert "full_profile" in types


def test_chunk_minimal_resume_has_full_profile():
    """Even a minimal one-liner produces at least a full_profile chunk."""
    chunks = ResumeChunker.chunk(MINIMAL_RESUME)
    assert len(chunks) >= 1
    assert any(c.section_type == "full_profile" for c in chunks)


def test_chunk_text_not_empty():
    """No chunk should have an empty text body."""
    chunks = ResumeChunker.chunk(STRUCTURED_RESUME)
    for c in chunks:
        assert c.text.strip(), f"Chunk '{c.section_type}' has empty text"


def test_chunk_preserves_skills_content():
    """The skills chunk should contain the actual skill names."""
    chunks = ResumeChunker.chunk(STRUCTURED_RESUME)
    skill_chunks = [c for c in chunks if c.section_type == "skills"]
    assert skill_chunks, "No skills chunk found"
    skill_text = skill_chunks[0].text.lower()
    assert "python" in skill_text or "fastapi" in skill_text


def test_chunk_with_parsed_fields_enriches_full_profile():
    """Passing parsed_fields should embed designation/YOE in full_profile."""
    parsed = {
        "designation": "Senior Software Engineer",
        "experience_months": 96,
        "skills": ["Python", "Docker"],
        "name": "John Doe",
    }
    chunks = ResumeChunker.chunk(STRUCTURED_RESUME, parsed_fields=parsed)
    fp = next((c for c in chunks if c.section_type == "full_profile"), None)
    assert fp is not None
    assert "Senior Software Engineer" in fp.text or "Python" in fp.text


def test_chunk_section_types_are_known_values():
    """All section types should be from the known vocabulary."""
    known = {"skills", "experience", "projects", "education", "certifications", "summary", "full_profile"}
    chunks = ResumeChunker.chunk(STRUCTURED_RESUME)
    for c in chunks:
        assert c.section_type in known, f"Unknown section type: '{c.section_type}'"


def test_chunk_candidate_id_default_empty():
    chunks = ResumeChunker.chunk(MINIMAL_RESUME)
    for c in chunks:
        assert c.candidate_id == ""  # caller sets it later


def test_chunk_skills_only_resume():
    chunks = ResumeChunker.chunk(SKILLS_ONLY_RESUME)
    assert len(chunks) >= 1
    types = {c.section_type for c in chunks}
    assert "skills" in types or "full_profile" in types


# ---------------------------------------------------------------------------
# Tests: ranking-critical behaviour
# ---------------------------------------------------------------------------

def test_skills_chunk_text_length():
    """Skills chunk should be non-trivially long (at least 10 chars)."""
    parsed = {"skills": ["Python", "Docker"]}
    chunks = ResumeChunker.chunk(STRUCTURED_RESUME, parsed_fields=parsed)
    skill_chunks = [c for c in chunks if c.section_type == "skills"]
    if skill_chunks:
        assert len(skill_chunks[0].text) >= 10


def test_multiple_section_chunks():
    """A rich resume produces multiple distinct chunk types."""
    chunks = ResumeChunker.chunk(STRUCTURED_RESUME)
    types = {c.section_type for c in chunks}
    # Should have at least 4 distinct section types
    assert len(types) >= 4, f"Only {len(types)} section types: {types}"
