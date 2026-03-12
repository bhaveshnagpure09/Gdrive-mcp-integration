"""
Quick test to verify the relevance filter:
  1. Submit an AI/ML requisition -> should return ONLY AI/ML candidates
  2. Submit a QA requisition -> should return ONLY QA candidates
"""
import urllib.request, urllib.error, json, time
from datetime import datetime

TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0LXVzZXIiLCJleHAiOjk5OTk5OTk5OTl9.7gDJtxuziSq8wDaUVIuBuO6XmBe3AaMUP-z2GM7YfuQ"
H = {"Content-Type": "application/json", "Authorization": "Bearer " + TOKEN}
BASE = "http://localhost:8001/api/v1"


def call(method, url, data=None):
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=H, method=method)
    try:
        r = urllib.request.urlopen(req, timeout=30)
        return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:500]


def submit_requisition(title, role, mandatory, preferred, jd_text):
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    payload = {
        "request_id": f"req-filter-test-{ts}",
        "schema_version": "1.0",
        "source_system": "relevance-test",
        "client_name": "InfoBeans HR",
        "job_description": {
            "client_name": "InfoBeans HR",
            "title": title,
            "role": role,
            "priority": "HIGH",
            "location": ["Pune", "Indore"],
            "work_mode": ["hybrid"],
            "mandatory_skills": mandatory,
            "preferred_skills": preferred,
            "jd_text": jd_text,
        },
        "metadata": {"submitted_by": "test-user", "department": "Engineering"},
    }
    s, d = call("POST", f"{BASE}/jd-skill-mapping/", payload)
    if isinstance(d, dict):
        return d.get("correlation_id", "")
    raise RuntimeError(f"Submit failed ({s}): {d}")


def poll_results(corr_id, wait=30):
    print(f"  Waiting {wait}s for pipeline...", flush=True)
    time.sleep(wait)
    s, d = call("GET", f"{BASE}/jd-skill-mapping/{corr_id}/matches")
    return d


# ── Test 1: AI/ML role ──────────────────────────────────────────────────────
print("\n=== Test 1: AI/ML Engineer ===")
corr = submit_requisition(
    title="AI/ML Engineer",
    role="Machine Learning Engineer",
    mandatory=["Machine Learning", "Python", "Deep Learning"],
    preferred=["TensorFlow", "NLP", "PyTorch"],
    jd_text=(
        "We need an AI/ML engineer with strong Python and deep learning expertise. "
        "Must have experience building ML models, training neural networks, "
        "and deploying AI solutions in production."
    ),
)
print(f"  Submitted: {corr}")
res = poll_results(corr, wait=30)
status = res.get("status")
total = res.get("total_matches", 0)
msg = res.get("message", "")
print(f"  Status: {status} | Total matched: {total}")
if msg:
    print(f"  Message: {msg}")
for i, m in enumerate(res.get("matches", [])[:5]):
    print(
        f"  [{i+1}] {m.get('full_name')} | "
        f"match={m.get('match_percentage')}% | "
        f"vec={m.get('vector_similarity')} | "
        f"skill={m.get('skill_score')} | "
        f"skills={m.get('skills_matched')}"
    )


# ── Test 2: QA Engineer role ────────────────────────────────────────────────
print("\n=== Test 2: QA Engineer ===")
corr2 = submit_requisition(
    title="Senior QA Engineer",
    role="QA Engineer",
    mandatory=["Manual Testing", "API Testing", "QA Methodologies"],
    preferred=["Automation Testing", "Selenium", "Performance Testing"],
    jd_text=(
        "Looking for a Senior QA engineer with strong manual testing and API testing skills. "
        "Must have experience with test planning, writing test cases, and defect management. "
        "Knowledge of automation frameworks is a plus."
    ),
)
print(f"  Submitted: {corr2}")
res2 = poll_results(corr2, wait=30)
status2 = res2.get("status")
total2 = res2.get("total_matches", 0)
msg2 = res2.get("message", "")
print(f"  Status: {status2} | Total matched: {total2}")
if msg2:
    print(f"  Message: {msg2}")
for i, m in enumerate(res2.get("matches", [])[:5]):
    print(
        f"  [{i+1}] {m.get('full_name')} | "
        f"match={m.get('match_percentage')}% | "
        f"vec={m.get('vector_similarity')} | "
        f"skill={m.get('skill_score')} | "
        f"skills={m.get('skills_matched')}"
    )


print("\n=== Relevance Filter Test Complete ===")
