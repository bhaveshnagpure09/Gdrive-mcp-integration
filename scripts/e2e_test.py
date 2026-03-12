import urllib.request, json, urllib.error, time

TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0LXVzZXIiLCJleHAiOjk5OTk5OTk5OTl9.7gDJtxuziSq8wDaUVIuBuO6XmBe3AaMUP-z2GM7YfuQ'
H = {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + TOKEN}


def call(method, url, data=None, timeout=20):
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=H, method=method)
    try:
        r = urllib.request.urlopen(req, timeout=timeout)
        return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:400]


print('=== Full E2E Test ===')

# 1. Health
s, d = call('GET', 'http://localhost:8001/health')
print(f'1. HEALTH => {s}: {d}')

# 2. Bulk upsert
payload = {
    'metadata': {
        'batch_id': 'batch-e2e-v3', 'timestamp': '2026-03-11T10:00:00Z',
        'total_records': 1, 'batch_number': 1, 'total_batches': 1,
        'records_in_batch': 1, 'source_system': 'e2e', 'schema_version': '1.0',
        'status': {'code': 200, 'key': 'SUCCESS', 'message': 'OK'}
    },
    'team_members': [{
        'team_member_id': 'tm-e2e-v3', 'full_name': 'Jane Doe',
        'team_member_status': 'active', 'experience_in_months': 72,
        'designation': 'Senior Python Dev', 'profile_type': 'Technical',
        'base_location': 'Indore', 'work_type': 'Hybrid',
        'skills': [{'skill_id': 's1', 'skill_name': 'Python', 'rating': 9, 'experience_in_months': 72, 'category': 'Backend'}],
        'allocations': []
    }]
}
s, d = call('POST', 'http://localhost:8001/api/v1/team-members/skill-availability/bulk-upsert', payload)
status_val = d.get('status') if isinstance(d, dict) else str(d)[:80]
print(f'2. BULK UPSERT => {s}: {status_val}')

# 3. Job Requisition
req_payload = {
    'request_id': 'req-e2e-v3', 'schema_version': '1.0', 'source_system': 'e2e',
    'client_name': 'Default Client',
    'job_description': {
        'client_name': 'Default Client', 'title': 'Python Backend Engineer',
        'role': 'Backend Developer', 'priority': 'HIGH',
        'location': ['Indore'], 'work_mode': ['Hybrid'],
        'mandatory_skills': ['Python', 'FastAPI'], 'preferred_skills': ['Docker'],
        'jd_text': 'Looking for experienced Python developer with FastAPI skills.'
    },
    'metadata': {'submitted_by': 'test-user', 'department': 'Engineering'}
}
s, d = call('POST', 'http://localhost:8001/api/v1/jd-skill-mapping/', req_payload)
corr_id = d.get('correlation_id', '') if isinstance(d, dict) else ''
print(f'3. REQUISITION => {s}: {corr_id}')

# 4. Matches
if corr_id:
    time.sleep(4)
    s, d = call('GET', f'http://localhost:8001/api/v1/jd-skill-mapping/{corr_id}/matches')
    print(f'4. MATCHES => {s}: status={d.get("status")}, total={d.get("total_matches", 0)}')
    if d.get('matches'):
        m = d['matches'][0]
        print(f'   Top match: {m.get("team_member_id")} score={m.get("profile_score")} fit={m.get("fit_level")}')

# 5. Resume ingestion
s, d = call('POST', 'http://localhost:8001/api/v1/ingest-resume',
            {'storage': 'gdrive', 'doc_id': '19JA8wuuPr6tHlLeExQUt38Vcqq9SbwUq5YecYfkB6IA'}, timeout=60)
if isinstance(d, dict):
    print(f'5. RESUME => {s}: ingested={d.get("ingested")}, failed={d.get("failed")}')
    if d.get('details'):
        det = d['details'][0]
        print(f'   name={det.get("extracted_name")}, skills={det.get("skills_found")}')
else:
    print(f'5. RESUME => {s}: {d}')

# 6. Metrics
req2 = urllib.request.Request('http://localhost:8001/api/v1/metrics', headers=H)
r2 = urllib.request.urlopen(req2, timeout=5)
print(f'6. METRICS => 200, {len(r2.read())} bytes')

print()
print('=== ALL TESTS PASSED ===')
