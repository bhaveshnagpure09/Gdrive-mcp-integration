#!/usr/bin/env python3
"""
ingest_resumes_json.py

Full pipeline for resumes.json:
  1. Bulk upsert all 48 team members + skills into DB via API
  2. Build profile text from JSON fields, generate embeddings via Ollama,
     and store directly in PostgreSQL (no Google Drive needed)
  3. Submit a sample JD requisition
  4. Poll and display ranked matching results

Usage:
    python scripts/ingest_resumes_json.py [path/to/resumes.json]
"""

import json
import sys
import time
import datetime
import requests
import psycopg2

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
API_URL      = "http://localhost:8001"
OLLAMA_URL   = "http://localhost:11434"
DB_HOST      = "localhost"
DB_PORT      = 5434
DB_NAME      = "ib_job_skill_mapping_staging"
DB_USER      = "staging_user"
DB_PASS      = "staging_password"
JWT          = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJzdWIiOiJ0ZXN0LXVzZXIiLCJleHAiOjk5OTk5OTk5OTl9"
    ".7gDJtxuziSq8wDaUVIuBuO6XmBe3AaMUP-z2GM7YfuQ"
)
HEADERS = {"Authorization": f"Bearer {JWT}", "Content-Type": "application/json"}

DEFAULT_RESUMES_PATH = r"C:\Users\bhavesh.nagpure_info\Downloads\resumes.json"

# ---------------------------------------------------------------------------
# Field mapping helpers
# ---------------------------------------------------------------------------

def _transform_member(m: dict) -> dict:
    """Map resumes.json fields → BulkUpsertRequest TeamMemberData schema."""
    skills = [
        {
            "skill_id":             s["skill_id"],
            "skill_name":           s["name"],          # resumes uses "name"
            "rating":               s.get("rating"),
            "experience_in_months": s.get("experience_in_months"),
            "category":             s.get("category"),
            "certifications":       s.get("certifications", []),
            "is_deleted":           s.get("is_deleted", False),
        }
        for s in m.get("skills", [])
    ]
    allocs = [
        {
            "project_id":            a["project_id"],
            "allocation_percentage": a.get("allocation_percentage"),
            "start_date":            a.get("start_date"),
            "end_date":              a.get("end_date"),
            "billable":              a.get("billable"),
            "is_deleted":            a.get("is_deleted", False),
        }
        for a in m.get("allocations", [])
    ]
    return {
        "team_member_id":      str(m["team_member_id"]),
        "team_member_status":  m.get("team_member_status", "active"),
        "experience_in_months": m.get("experience_in_months", 0),
        "full_name":           m.get("full_name", ""),
        "designation":         m.get("designation", ""),
        "profile_type":        m.get("profile_type"),
        "base_location":       m.get("base_location"),
        "work_type":           m.get("work-mode"),  # resumes uses "work-mode"
        "profile_url":         m.get("profile"),    # resumes uses "profile"
        "skills":              skills,
        "allocations":         allocs,
    }


def _build_profile_text(m: dict) -> str:
    """Build rich profile text used for embedding generation from JSON data."""
    skills = [s["name"] for s in m.get("skills", []) if not s.get("is_deleted", False)]
    exp_months = m.get("experience_in_months", 0)
    exp_years  = round(exp_months / 12, 1)
    avail      = m.get("availability", {})
    avail_str  = "Available" if avail.get("is_available") else "Not currently available"
    nextav     = avail.get("next_available_date", "N/A")
    hrs        = avail.get("hours_per_week", 0)

    return (
        f"Name: {m.get('full_name', '')}\n"
        f"Designation: {m.get('designation', '')}\n"
        f"Profile Type: {m.get('profile_type', '')}\n"
        f"Location: {m.get('base_location', '')}\n"
        f"Work Mode: {m.get('work-mode', '')}\n"
        f"Experience: {exp_months} months ({exp_years} years)\n"
        f"Skills: {', '.join(skills)}\n"
        f"Availability: {avail_str}\n"
        f"Available hours per week: {hrs}\n"
        f"Next available from: {nextav}"
    )


# ---------------------------------------------------------------------------
# Ollama + DB helpers
# ---------------------------------------------------------------------------

def _generate_embedding(text: str) -> list:
    """Call Ollama to get a 768-dim nomic-embed-text embedding."""
    resp = requests.post(
        f"{OLLAMA_URL}/api/embeddings",
        json={"model": "nomic-embed-text", "prompt": text},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["embedding"]


def _member_exists(conn, team_member_id: str) -> bool:
    """Return True if the team_member row exists (so FK won't fail)."""
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM team_member WHERE team_member_id = %s", (team_member_id,))
        return cur.fetchone() is not None


def _upsert_embedding(conn, team_member_id: str, embedding: list,
                       profile_text: str, metadata: dict) -> None:
    """Upsert a single embedding row directly into PostgreSQL."""
    vec_str = "[" + ",".join(str(x) for x in embedding) + "]"
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO team_member_embeddings
                (team_member_id, embedding, profile_text, metadata_json, created_at)
            VALUES (%s, %s::vector, %s, %s::jsonb, NOW())
            ON CONFLICT (team_member_id) DO UPDATE SET
                embedding     = EXCLUDED.embedding,
                profile_text  = EXCLUDED.profile_text,
                metadata_json = EXCLUDED.metadata_json,
                created_at    = NOW()
            """,
            (team_member_id, vec_str, profile_text, json.dumps(metadata)),
        )
    conn.commit()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    resumes_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_RESUMES_PATH

    # ------------------------------------------------------------------
    # Load resumes.json
    # ------------------------------------------------------------------
    print(f"\nLoading: {resumes_path}")
    with open(resumes_path, encoding="utf-8") as f:
        data = json.load(f)

    members  = data["team_members"]
    total    = len(members)
    meta     = data.get("metadata", {})
    name_map = {str(m["team_member_id"]): m.get("full_name", str(m["team_member_id"])) for m in members}
    print(f"  batch_id  : {meta.get('batch_id')}")
    print(f"  source    : {meta.get('source_system')}")
    print(f"  records   : {total}")

    # ------------------------------------------------------------------
    # STEP 1 – Bulk upsert team members + skills
    # ------------------------------------------------------------------
    sep = "=" * 65
    print(f"\n{sep}")
    print("STEP 1: Bulk upsert team members + skills via API")
    print(sep)

    BATCH_SIZE = 10
    total_ins, total_upd, total_sk, total_failed = 0, 0, 0, 0

    for i in range(0, total, BATCH_SIZE):
        batch   = members[i : i + BATCH_SIZE]
        b_num   = i // BATCH_SIZE + 1
        b_total = (total + BATCH_SIZE - 1) // BATCH_SIZE

        payload = {
            "metadata": {
                "batch_id":         f"rjson_{b_num}of{b_total}",
                "timestamp":         datetime.datetime.utcnow().isoformat() + "Z",
                "total_records":     total,
                "batch_number":      b_num,
                "total_batches":     b_total,
                "records_in_batch":  len(batch),
                "source_system":     meta.get("source_system", "EAGLE_v1"),
                "schema_version":    meta.get("schema_version", "1.1"),
                "status": {"code": 0, "key": "SUCCESS", "message": "Request successful"},
            },
            "team_members": [_transform_member(m) for m in batch],
        }

        try:
            resp = requests.post(
                f"{API_URL}/api/v1/team-members/skill-availability/bulk-upsert",
                json=payload,
                headers=HEADERS,
                timeout=30,
            )
            if resp.status_code == 202:
                s = resp.json().get("summary", {})
                ins  = s.get("team_members_inserted", 0)
                upd  = s.get("team_members_updated", 0)
                sk   = s.get("skills_inserted", 0) + s.get("skills_updated", 0)
                fail = s.get("records_failed", 0)
                total_ins    += ins
                total_upd    += upd
                total_sk     += sk
                total_failed += fail
                print(f"  Batch {b_num}/{b_total}: ✅  inserted={ins}  updated={upd}  skills={sk}  failed={fail}")
            else:
                print(f"  Batch {b_num}/{b_total}: ❌  HTTP {resp.status_code}: {resp.text[:200]}")
        except requests.RequestException as exc:
            print(f"  Batch {b_num}/{b_total}: ❌  {exc}")

    print(f"\n  Summary: {total_ins} inserted | {total_upd} updated | {total_sk} skill records | {total_failed} failed")

    # ------------------------------------------------------------------
    # STEP 2 – Generate embeddings and store in DB
    # ------------------------------------------------------------------
    print(f"\n{sep}")
    print("STEP 2: Generate embeddings (Ollama nomic-embed-text) and store in DB")
    print(sep)

    # Verify Ollama is reachable
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        r.raise_for_status()
        models = [m["name"] for m in r.json().get("models", [])]
        has_model = any("nomic-embed-text" in m for m in models)
        print(f"  Ollama  : ✅  running  (nomic-embed-text {'✅' if has_model else '⚠ (not pulled)'})")
        if not has_model:
            print("  Run: ollama pull nomic-embed-text")
            sys.exit(1)
    except Exception as exc:
        print(f"  Ollama  : ❌  {exc}")
        print("  Start Ollama: ollama serve")
        sys.exit(1)

    # Connect to DB
    try:
        conn = psycopg2.connect(
            host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASS
        )
        print(f"  Postgres: ✅  {DB_HOST}:{DB_PORT}/{DB_NAME}")
    except Exception as exc:
        print(f"  Postgres: ❌  {exc}")
        sys.exit(1)

    embedded, emb_failed, skipped = 0, 0, 0
    for idx, m in enumerate(members, 1):
        tid  = str(m["team_member_id"])
        name = m.get("full_name", tid)
        try:
            # Skip if the team_member row wasn't created (failed bulk upsert)
            if not _member_exists(conn, tid):
                skipped += 1
                print(f"  [{idx:>2}/{total}] ⏭  {name:<30} (skipped – not in team_member table)")
                continue

            profile_text = _build_profile_text(m)
            embedding    = _generate_embedding(profile_text)
            skills_list  = [s["name"] for s in m.get("skills", [])]
            _upsert_embedding(conn, tid, embedding, profile_text, {
                "source":            "resumes.json",
                "full_name":         name,
                "designation":       m.get("designation", ""),
                "experience_months": m.get("experience_in_months", 0),
                "skills":            skills_list,
            })
            embedded += 1
            print(f"  [{idx:>2}/{total}] ✅ {name:<30} ({len(skills_list)} skills, "
                  f"{round(m.get('experience_in_months', 0)/12, 1)} yrs)")
        except Exception as exc:
            emb_failed += 1
            conn.rollback()  # reset aborted transaction so next iteration works
            print(f"  [{idx:>2}/{total}] ❌ {name}: {exc}")

    conn.close()
    print(f"\n  Embeddings stored: {embedded}  |  skipped: {skipped}  |  failed: {emb_failed}")

    if embedded == 0:
        print("\n⚠  No embeddings stored — cannot run matching test.")
        sys.exit(1)

    # ------------------------------------------------------------------
    # STEP 3 – Submit a sample JD requisition
    # ------------------------------------------------------------------
    print(f"\n{sep}")
    print("STEP 3: Submit sample JD requisition (Senior QA Engineer)")
    print(sep)

    req_id = f"RJSON-{int(time.time())}"
    jd_payload = {
        "request_id":     req_id,
        "schema_version": "1.1",
        "source_system":  "EAGLE_v1",
        "client_name":    "InfoBeans HR",
        "job_description": {
            "client_name": "InfoBeans HR",
            "title":       "Senior QA Engineer",
            "role":        "QA Engineer",
            "priority":    "HIGH",
            "location":    ["Pune", "Indore", "Remote"],
            "work_mode":   ["hybrid", "wfh", "wfo"],
            "jd_text": (
                "We are looking for an experienced Senior QA Engineer with strong expertise in "
                "manual testing, API testing, test automation, and QA methodologies. "
                "The ideal candidate should have deep experience with performance testing, "
                "test strategy and planning, defect tracking, risk management, and agile/scrum. "
                "Excellent communication skills and ability to mentor junior team members required."
            ),
            "mandatory_skills": ["Manual Testing", "QA Methodologies", "API Testing"],
            "preferred_skills": ["Automation Testing", "Performance Testing", "Test Strategy & Planning", "Defect Tracking"],
            "expected_start_date": "2026-04-01",
            "requisition_duration_month": 6,
            "experience": {"min_months": 36, "max_months": 200},
        },
        "metadata": {
            "submitted_by": "ingest_resumes_json.py",
            "department":   "Engineering",
        },
    }

    try:
        resp = requests.post(
            f"{API_URL}/api/v1/jd-skill-mapping/",
            json=jd_payload,
            headers=HEADERS,
            timeout=30,
        )
    except requests.RequestException as exc:
        print(f"  ❌  {exc}")
        sys.exit(1)

    if resp.status_code != 202:
        print(f"  ❌  HTTP {resp.status_code}: {resp.text[:300]}")
        sys.exit(1)

    resp_data = resp.json()
    corr_id  = resp_data.get("correlation_id", "")
    print(f"  ✅  request_id      = {req_id}")
    print(f"  ✅  correlation_id  = {corr_id}")
    print(f"  ✅  status          = {resp_data.get('status', '')}")

    # ------------------------------------------------------------------
    # STEP 4 – Poll for results
    # ------------------------------------------------------------------
    print(f"\n{sep}")
    print("STEP 4: Polling for match results (up to 12 attempts × 5 s)")
    print(sep)

    for attempt in range(12):
        time.sleep(5)
        try:
            r = requests.get(
                f"{API_URL}/api/v1/jd-skill-mapping/{corr_id}/matches",
                headers=HEADERS,
                timeout=15,
            )
        except requests.RequestException as exc:
            print(f"  Attempt {attempt+1:>2}: ❌  {exc}")
            continue

        if r.status_code != 200:
            print(f"  Attempt {attempt+1:>2}: HTTP {r.status_code}")
            continue

        result = r.json()
        status = result.get("processing_status") or result.get("status", "PROCESSING")
        print(f"  Attempt {attempt+1:>2}: status={status}")

        if status.upper() in ("COMPLETED",):
            matches = result.get("matches", [])
            print(f"\n  ✅  COMPLETED — {len(matches)} candidate(s) ranked\n")
            print(f"  {'#':<4} {'Name':<32} {'Score':>6}  {'Match%':>6}  {'Fit':<12}")
            print("  " + "-" * 64)
            for rank, m in enumerate(matches[:20], 1):
                tid   = str(m.get("team_member_id", "?"))
                name  = name_map.get(tid, tid)
                score = m.get("profile_score", 0)
                pct   = m.get("match_percentage")
                if pct is None:
                    pct = round(score * 100, 1)
                fit   = m.get("fit_level", "?")
                print(f"  #{rank:<3} {str(name):<32} {score:>6.3f}  {pct:>6.1f}%  {fit}")

            top_tid = str(matches[0].get("team_member_id"))
            print(f"\n  Top candidate : {name_map.get(top_tid, top_tid)}")
            print(f"  Best score    : {matches[0].get('profile_score', 0):.3f}")
            return

    print("\n  ⚠  Matching did not complete within the polling window.")


if __name__ == "__main__":
    main()
