"""Full workflow test: Upsert → Ingest → Requisition → Matches → Vector DB check."""
import urllib.request, json, urllib.error, time, datetime, subprocess

TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0LXVzZXIiLCJleHAiOjk5OTk5OTk5OTl9.7gDJtxuziSq8wDaUVIuBuO6XmBe3AaMUP-z2GM7YfuQ'
H = {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + TOKEN}
BASE = 'http://localhost:8001'
API = BASE + '/api/v1'


def call(method, url, data=None, timeout=30):
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=H, method=method)
    try:
        r = urllib.request.urlopen(req, timeout=timeout)
        return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"error": raw.decode()[:400]}


ts = datetime.datetime.now().strftime('%H%M%S')

# ─── STEP 1: Bulk Upsert 3 team members ──────────────────────────────────────
print('\n=== STEP 1: Upsert 3 Team Members ===')
s, d = call('POST', API + '/team-members/skill-availability/bulk-upsert', {
    'metadata': {
        'batch_id': 'batch-demo-' + ts,
        'timestamp': '2026-03-11T10:00:00Z',
        'total_records': 3, 'batch_number': 1, 'total_batches': 1,
        'records_in_batch': 3, 'source_system': 'demo', 'schema_version': '1.0',
        'status': {'code': 200, 'key': 'SUCCESS', 'message': 'OK'}
    },
    'team_members': [
        {
            'team_member_id': 'tm-python-' + ts,
            'full_name': 'Alice Python Expert',
            'team_member_status': 'active',
            'experience_in_months': 84,
            'designation': 'Senior Python Engineer',
            'profile_type': 'Technical',
            'base_location': 'Indore',
            'work_type': 'Hybrid',
            'skills': [
                {'skill_id': 's1', 'skill_name': 'Python', 'rating': 9, 'experience_in_months': 84, 'category': 'Backend'},
                {'skill_id': 's2', 'skill_name': 'FastAPI', 'rating': 9, 'experience_in_months': 48, 'category': 'Backend'},
                {'skill_id': 's3', 'skill_name': 'PostgreSQL', 'rating': 8, 'experience_in_months': 60, 'category': 'Database'},
                {'skill_id': 's4', 'skill_name': 'Docker', 'rating': 7, 'experience_in_months': 36, 'category': 'DevOps'},
            ],
            'allocations': []
        },
        {
            'team_member_id': 'tm-java-' + ts,
            'full_name': 'Bob Java Developer',
            'team_member_status': 'active',
            'experience_in_months': 60,
            'designation': 'Java Backend Developer',
            'profile_type': 'Technical',
            'base_location': 'Mumbai',
            'work_type': 'Remote',
            'skills': [
                {'skill_id': 's5', 'skill_name': 'Java', 'rating': 9, 'experience_in_months': 60, 'category': 'Backend'},
                {'skill_id': 's6', 'skill_name': 'Spring Boot', 'rating': 8, 'experience_in_months': 48, 'category': 'Framework'},
                {'skill_id': 's7', 'skill_name': 'MySQL', 'rating': 7, 'experience_in_months': 48, 'category': 'Database'},
            ],
            'allocations': []
        },
        {
            'team_member_id': 'tm-fullstack-' + ts,
            'full_name': 'Carol Fullstack Dev',
            'team_member_status': 'active',
            'experience_in_months': 48,
            'designation': 'Fullstack Developer',
            'profile_type': 'Technical',
            'base_location': 'Pune',
            'work_type': 'Onsite',
            'skills': [
                {'skill_id': 's8', 'skill_name': 'Python', 'rating': 7, 'experience_in_months': 36, 'category': 'Backend'},
                {'skill_id': 's9', 'skill_name': 'React', 'rating': 8, 'experience_in_months': 48, 'category': 'Frontend'},
                {'skill_id': 's10', 'skill_name': 'FastAPI', 'rating': 6, 'experience_in_months': 24, 'category': 'Backend'},
            ],
            'allocations': []
        }
    ]
})
summ = d.get('summary', {}) if isinstance(d, dict) else {}
print(f'  HTTP {s}: {d.get("status") if isinstance(d, dict) else d}')
print(f'  Inserted: {summ.get("team_members_inserted")} members, {summ.get("skills_inserted")} skills')

# ─── STEP 2: Resume Ingestion ─────────────────────────────────────────────────
print('\n=== STEP 2: Resume Ingestion (Google Doc) ===')
s, d = call('POST', API + '/ingest-resume',
            {'storage': 'gdrive', 'doc_id': '19JA8wuuPr6tHlLeExQUt38Vcqq9SbwUq5YecYfkB6IA'},
            timeout=60)
print(f'  HTTP {s}: ingested={d.get("ingested")}, failed={d.get("failed")}')
for det in d.get('details', []):
    status = det.get('status')
    name = det.get('extracted_name', 'N/A')
    skills = det.get('skills_found', 0)
    reason = det.get('reason', '')
    print(f'  doc={det.get("doc_id")[:12]}... => {status} | name={name} | skills={skills} | {reason}')

# ─── STEP 3: Check Vectors in DB ──────────────────────────────────────────────
print('\n=== STEP 3: Vector DB State ===')
res = subprocess.run(
    ['docker', 'exec', 'ib-job-skill-mapping-system-postgres-1',
     'psql', '-U', 'staging_user', '-d', 'ib_job_skill_mapping_staging', '-c',
     'SELECT team_member_id, LENGTH(profile_text) AS txt_len, created_at FROM team_member_embeddings ORDER BY created_at DESC LIMIT 8;'],
    capture_output=True, text=True
)
print(res.stdout.strip())

# ─── STEP 4: Submit JD Requisition ────────────────────────────────────────────
print('\n=== STEP 4: Submit JD Requisition ===')
req_id = 'req-demo-' + ts
s, d = call('POST', API + '/jd-skill-mapping/', {
    'request_id': req_id,
    'schema_version': '1.0',
    'source_system': 'demo',
    'client_name': 'Default Client',
    'job_description': {
        'client_name': 'Default Client',
        'title': 'Senior Python Backend Engineer',
        'role': 'Backend Developer',
        'priority': 'HIGH',
        'location': ['Indore'],
        'work_mode': ['Hybrid'],
        'experience': {'min_months': 48, 'max_months': 120},
        'mandatory_skills': ['Python', 'FastAPI', 'PostgreSQL'],
        'preferred_skills': ['Docker', 'Redis', 'Kubernetes'],
        'jd_text': (
            'We are seeking a Senior Python Backend Engineer with strong expertise in FastAPI and PostgreSQL. '
            'The ideal candidate should have 4+ years of experience building scalable REST APIs, '
            'working with relational databases, and deploying applications with Docker. '
            'Experience with asynchronous programming, Redis caching, and microservices is a plus.'
        )
    },
    'metadata': {
        'submitted_by': 'demo-user',
        'department': 'Engineering'
    }
})
corr_id = d.get('correlation_id', '') if isinstance(d, dict) else ''
print(f'  HTTP {s}: correlation_id={corr_id}')
print(f'  Status: {d.get("status") if isinstance(d, dict) else d}')

# ─── STEP 5: Poll for Matches ─────────────────────────────────────────────────
print('\n=== STEP 5: Matching & Ranking Results ===')
if corr_id:
    for attempt in range(6):
        time.sleep(3)
        s, d = call('GET', API + '/jd-skill-mapping/' + corr_id + '/matches')
        status = d.get('status') if isinstance(d, dict) else 'ERROR'
        print(f'  Attempt {attempt+1}: HTTP {s}, status={status}')
        if status == 'COMPLETED':
            total = d.get('total_matches', 0)
            print(f'  COMPLETED: {total} match(es) found')
            print()
            for i, m in enumerate(d.get('matches', []), 1):
                pct = round(m.get('match_percentage', 0), 1) if m.get('match_percentage') else 'N/A'
                score = round(m.get('profile_score', 0), 4)
                fit = m.get('fit_level', 'N/A')
                avail = m.get('availability_match', False)
                print(f'  Rank #{i}: {m.get("team_member_id")}')
                print(f'    profile_score={score}, match_pct={pct}%, fit={fit}, available={avail}')
                print(f'    Explanation: {m.get("explanation", [])[0] if m.get("explanation") else "none"}')
            break
        elif status not in ('QUEUED_FOR_PROCESSING', 'PROCESSING', 'PENDING'):
            print(f'  Final status: {status}')
            print(f'  Response: {d}')
            break
    else:
        print('  Timed out waiting for COMPLETED status')

print('\n=== WORKFLOW TEST COMPLETE ===')
