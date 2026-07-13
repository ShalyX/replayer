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
        API_BASE + path,
        method=method,
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


suffix = os.getenv("V2_4_ACCEPTANCE_SUFFIX", str(int(time.time())))
platform_id = f"due_process_market_{suffix}"
agent_id = os.getenv("V2_4_RESUME_AGENT_ID", f"appealable_agent_{suffix}")
job_id = os.getenv("V2_4_RESUME_JOB_ID", f"appealable_job_{suffix}")
dispute_id = f"appealable_dispute_{suffix}"

resuming = bool(os.getenv("V2_4_RESUME_JOB_ID"))
if not resuming:
    post("/platforms/register", {"platform_id": platform_id, "platform_name": "Due Process Market"})
    post("/agents/register", {
        "agent_id": agent_id, "platform_id": platform_id, "agent_name": "Appealable Research Agent",
    })
    post("/jobs", {
        "job_id": job_id, "platform_id": platform_id, "requester_id": "buyer_due_process",
        "provider_agent_id": agent_id,
        "task_spec": "Identify three verified renewable-energy grants and cite official sources.",
        "category": "research", "payment_amount": 100, "currency": "USDC",
    })
    post(f"/jobs/{job_id}/deliverable", {
        "deliverable_uri": "https://example.com/due-process-deliverable",
        "summary": "Three grant claims with citations; the claimant disputes whether one source supports the claim.",
        "evidence_urls": ["https://www.energy.gov/", "https://www.grants.gov/"],
    })
    post(f"/jobs/{job_id}/dispute", {
        "dispute_id": dispute_id, "claimant": "buyer_due_process",
        "reason": "One cited source allegedly does not support the reported grant and requires validator review.",
        "evidence_uri": "https://www.grants.gov/", "bond_amount": 10,
    })
appeal_payload = {
    "appellant_id": "agent_owner", "reason": "The official grants index confirms the disputed program.",
    "evidence_uri": "https://www.grants.gov/", "evidence_hash": "0xappeal",
}
appeal = None
for _ in range(20):
    status, payload = request(f"/jobs/{job_id}/appeal", "POST", appeal_payload, allow_error=True)
    if status == 200:
        appeal = payload
        break
    if status != 409 or "not been indexed" not in str(payload.get("detail", "")).lower():
        raise RuntimeError(json.dumps(payload))
    time.sleep(3)
if appeal is None:
    raise SystemExit("Provisional GenLayer judgment was not readable before the appeal window closed")
provisional = appeal["provisional_reputation"]
assert provisional["details"]["pending_judgments"] == 1
assert provisional["fraud_incidents"] == 0
assert appeal["appeal"]["event_type"] == "APPEAL_SUBMITTED"

duplicate_status, _ = request(f"/jobs/{job_id}/appeal", "POST", {
    "reason": "duplicate", "evidence_uri": "https://www.grants.gov/",
}, allow_error=True)
assert duplicate_status == 409

resolution = None
for _ in range(int(os.getenv("V2_4_FINALITY_POLLS", "80"))):
    status, payload = request(f"/jobs/{job_id}/appeal/resolve", "POST", {}, allow_error=True)
    if status == 200:
        resolution = payload
        break
    if status != 409 or "not final" not in str(payload.get("detail", "")).lower():
        raise RuntimeError(json.dumps(payload))
    time.sleep(int(os.getenv("V2_4_FINALITY_INTERVAL", "15")))
if resolution is None:
    raise SystemExit("Appealed GenLayer transaction did not finalize within the configured polling window")

assert resolution["outcome"]["event_type"] in {"JUDGMENT_UPHELD", "JUDGMENT_OVERTURNED"}
assert resolution["event"]["event_type"] == "JUDGMENT_FINALIZED"
assert resolution["event"]["transaction_hash"].startswith("0x")
before = request(f"/agents/{agent_id}/reputation?projection=research_trust_v5")[1]
post("/admin/projections/rebuild")
after = request(f"/agents/{agent_id}/reputation?projection=research_trust_v5")[1]
for field in ("trust_score", "risk_score", "status", "fraud_incidents"):
    assert before[field] == after[field]
assert before["details"]["pending_judgments"] == 0

print(json.dumps({
    "status": "passed", "agent_id": agent_id, "job_id": job_id,
    "provisional_transaction": appeal["protocol"]["transaction_hash"],
    "appeal_outcome": resolution["outcome"]["event_type"],
    "final_verdict": resolution["judgment"]["verdict"],
    "protocol_round": resolution["protocol"].get("round", 0),
    "final_trust": after["trust_score"], "final_risk": after["risk_score"],
    "replay_identical": True,
}, indent=2))
