import json
import os
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen


API_BASE = os.getenv("API_BASE", "http://localhost:8000").rstrip("/")
API_KEY = os.getenv("ADMIN_API_KEY") or os.getenv("API_KEY", "")
if not API_KEY:
    raise SystemExit("ADMIN_API_KEY or API_KEY is required")


def request(path, method="GET", body=None, allow_error=False):
    req = Request(
        API_BASE + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"content-type": "application/json", "x-api-key": API_KEY},
    )
    try:
        with urlopen(req, timeout=700) as response:
            return response.status, json.loads(response.read())
    except HTTPError as exc:
        payload = exc.read().decode()
        if allow_error:
            try:
                return exc.code, json.loads(payload)
            except json.JSONDecodeError:
                return exc.code, {"detail": payload}
        raise RuntimeError(payload) from exc


def post(path, body=None):
    return request(path, "POST", body or {})[1]


suffix = os.getenv("V3_ACCEPTANCE_SUFFIX", str(int(time.time())))
platform_id = f"delegation_market_{suffix}"
principal_id = f"agent_a_{suffix}"
worker_id = f"agent_b_{suffix}"
job_id = f"delegated_research_{suffix}"
delegation_id = f"delegation_ab_{suffix}"

post("/platforms/register", {"platform_id": platform_id, "platform_name": "Agent Supply Chain Market"})
for agent_id, name in [(principal_id, "Principal Research Agent A"), (worker_id, "Worker Research Agent B")]:
    post("/agents/register", {
        "agent_id": agent_id, "platform_id": platform_id, "agent_name": name,
        "capabilities": ["research", "citations"],
    })
post("/jobs", {
    "job_id": job_id, "platform_id": platform_id, "requester_id": "buyer_v3",
    "provider_agent_id": principal_id,
    "task_spec": "Research three active climate grants using verifiable official citations.",
    "category": "research", "payment_amount": 300, "currency": "USDC",
})
post("/delegations", {
    "delegation_id": delegation_id, "principal_agent_id": principal_id,
    "worker_agent_id": worker_id, "platform_id": platform_id, "job_id": job_id,
    "authority_scope": "Worker must use official, verifiable sources and must not fabricate citations. Principal must review every citation before submitting. The signed accountability clause assigns 70% to the worker for fabrication and 30% to the principal for passing fabricated work without review.",
    "permitted_tools": ["web_search", "http_get"],
    "permitted_actions": ["research", "cite_sources"],
    "spending_limit": 25, "currency": "USDC", "allow_subdelegation": False,
    "disclosure_required": True, "principal_signature": f"signed:{principal_id}:{delegation_id}",
    "evidence_uri": "https://www.grants.gov/", "evidence_hash": "0xscope30a70b",
})
post(f"/delegations/{delegation_id}/accept", {
    "worker_signature": f"signed:{worker_id}:{delegation_id}",
    "evidence_uri": "https://www.grants.gov/", "evidence_hash": "0xaccept70b",
})
post(f"/delegations/{delegation_id}/output", {
    "output_uri": "https://example.com/delegated-climate-grants",
    "summary": "The worker claims example.com is an official grants source; the principal passes it through without review.",
    "evidence_urls": ["https://www.iana.org/help/example-domains", "https://www.grants.gov/"],
    "evidence_hash": "0xfabricatedcitations",
})
opened = post(f"/delegations/{delegation_id}/responsibility-dispute", {
    "claimant_id": "buyer_v3",
    "reason": "Agent B fabricated citations and Agent A submitted them despite its signed review duty.",
    "evidence_uri": "https://www.iana.org/help/example-domains",
    "evidence_hash": "0xresponsibilityevidence",
})

appeal = None
for _ in range(25):
    status, payload = request(f"/delegations/{delegation_id}/responsibility/appeal", "POST", {
        "appellant_id": principal_id,
        "reason": "Re-evaluate the signed review duty and explicit 30/70 accountability clause.",
        "evidence_uri": "https://www.grants.gov/", "evidence_hash": "0xresponsibilityappeal",
    }, allow_error=True)
    if status == 200:
        appeal = payload
        break
    if status != 409:
        raise RuntimeError(json.dumps(payload))
    time.sleep(3)
if appeal is None:
    raise SystemExit("Responsibility judgment did not enter an appealable state")

resolution = None
for _ in range(int(os.getenv("V3_FINALITY_POLLS", "80"))):
    status, payload = request(
        f"/delegations/{delegation_id}/responsibility/appeal/resolve", "POST", {}, allow_error=True
    )
    if status == 200:
        resolution = payload
        break
    if status != 409 or "not final" not in str(payload.get("detail", "")).lower():
        raise RuntimeError(json.dumps(payload))
    time.sleep(int(os.getenv("V3_FINALITY_INTERVAL", "15")))
if resolution is None:
    raise SystemExit("Appealed responsibility transaction did not finalize")

assert resolution["outcome"] == "shared_responsibility"
assert resolution["delegator_responsibility_bps"] == 3000
assert resolution["worker_responsibility_bps"] == 7000
principal_before = request(f"/agents/{principal_id}/reputation?projection=research_trust_v6")[1]
worker_before = request(f"/agents/{worker_id}/reputation?projection=research_trust_v6")[1]
post("/admin/projections/rebuild")
principal_after = request(f"/agents/{principal_id}/reputation?projection=research_trust_v6")[1]
worker_after = request(f"/agents/{worker_id}/reputation?projection=research_trust_v6")[1]
for before, after in [(principal_before, principal_after), (worker_before, worker_after)]:
    for field in ("trust_score", "risk_score", "status", "fraud_incidents"):
        assert before[field] == after[field]

print(json.dumps({
    "status": "passed", "delegation_id": delegation_id,
    "responsibility_case_id": opened["responsibility_case_id"],
    "transaction_hash": resolution["protocol"]["transaction_hash"],
    "outcome": resolution["outcome"], "delegator_bps": 3000, "worker_bps": 7000,
    "principal_trust": principal_after["trust_score"], "worker_trust": worker_after["trust_score"],
    "replay_identical": True,
}, indent=2))
