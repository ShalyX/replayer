import hashlib
import os
import time

import requests


base = os.getenv("REPLAYER_API_BASE", "http://localhost:8000").rstrip("/")
admin_key = os.getenv("ADMIN_API_KEY", "")
if not admin_key:
    raise SystemExit("ADMIN_API_KEY is required")
admin_headers = {"x-api-key": admin_key, "content-type": "application/json"}
suffix = str(int(time.time()))
reliable_id = f"reliable_market_{suffix}"
inaccurate_id = f"inaccurate_market_{suffix}"
market_c_id = f"market_c_{suffix}"
issuer_a = f"issuer_a_{suffix}"
issuer_b = f"issuer_b_{suffix}"
candidate_a = f"candidate_a_{suffix}"
candidate_b = f"candidate_b_{suffix}"
report_url = "https://raw.githubusercontent.com/ShalyX/replayer/main/docs/fixtures/attestation-50.md"
false_audit_url = "https://raw.githubusercontent.com/ShalyX/replayer/main/docs/fixtures/attestation-audit-zero.md"


def digest(value):
    return "0x" + hashlib.sha256(value.encode()).hexdigest()


def post(path, body, key=admin_key, timeout=900):
    response = requests.post(base + path, json=body, headers={"x-api-key": key, "content-type": "application/json"}, timeout=timeout)
    if not response.ok:
        raise RuntimeError(f"{path}: {response.status_code} {response.text}")
    return response.json()


def get(path):
    response = requests.get(base + path, timeout=120)
    if not response.ok:
        raise RuntimeError(f"{path}: {response.status_code} {response.text}")
    return response.json()


keys = {}
for platform_id, name in ((reliable_id, "Reliable Market"), (inaccurate_id, "Inaccurate Market"), (market_c_id, "Marketplace C")):
    registered = post("/platforms/register", {"platform_id": platform_id, "platform_name": name})
    keys[platform_id] = registered["api_key"]

for agent_id, platform_id in ((issuer_a, reliable_id), (issuer_b, inaccurate_id), (candidate_a, reliable_id), (candidate_b, inaccurate_id)):
    post("/agents/register", {"agent_id": agent_id, "platform_id": platform_id, "agent_name": agent_id}, keys[platform_id])

post(f"/platforms/{reliable_id}/verify-identity", {
    "agent_id": issuer_a, "evidence_uri": report_url, "evidence_hash": digest("reliable-identity"),
})

for index in range(3):
    attestation = post("/attestations", {
        "agent_id": issuer_a, "platform_id": reliable_id, "type": "jobs_completed", "value": 10,
        "period_start": "2026-01-01", "period_end": "2026-06-30",
        "evidence_uri": report_url, "evidence_hash": digest(f"reliable-history-{index}"),
    }, keys[reliable_id])
    post(f"/attestations/{attestation['event']['event_id']}/confirm", {
        "platform_id": market_c_id, "value": 10, "counterparty_id": f"auditor-{index}",
        "evidence_uri": report_url, "evidence_hash": digest(f"reliable-confirmation-{index}"),
    }, keys[market_c_id])

bad = post("/attestations", {
    "agent_id": issuer_b, "platform_id": inaccurate_id, "type": "jobs_completed", "value": 50,
    "period_start": "2026-01-01", "period_end": "2026-06-30",
    "evidence_uri": report_url, "evidence_hash": digest("false-claim"),
}, keys[inaccurate_id])
bad_id = bad["event"]["event_id"]
judged = post(f"/events/{bad_id}/challenge", {
    "challenger_id": issuer_b, "reason": "The independent audit proves none of the 50 jobs belong to this agent.",
    "evidence_uri": false_audit_url, "evidence_hash": digest("false-audit-zero"),
}, keys[inaccurate_id])
assert judged["judgment"]["metadata"]["outcome"] == "attestation_false", judged["judgment"]["metadata"]

reliable = get(f"/platforms/{reliable_id}/credibility")
inaccurate = get(f"/platforms/{inaccurate_id}/credibility")
assert reliable["credibility_score"] > inaccurate["credibility_score"]

claim_a = post("/attestations", {
    "agent_id": candidate_a, "platform_id": reliable_id, "type": "jobs_completed", "value": 50,
    "period_start": "2026-01-01", "period_end": "2026-06-30",
    "evidence_uri": report_url, "evidence_hash": digest("candidate-a-50"),
}, keys[reliable_id])
claim_b = post("/attestations", {
    "agent_id": candidate_b, "platform_id": inaccurate_id, "type": "jobs_completed", "value": 50,
    "period_start": "2026-01-01", "period_end": "2026-06-30",
    "evidence_uri": report_url, "evidence_hash": digest("candidate-b-50"),
}, keys[inaccurate_id])
assert claim_a["reputation"]["trust_score"] > claim_b["reputation"]["trust_score"]

passport_a = get(f"/agents/{candidate_a}/profile")
passport_b = get(f"/agents/{candidate_b}/profile")
print({
    "reliable_platform": reliable, "inaccurate_platform": inaccurate,
    "reliable_claim_trust": passport_a["reputation"]["trust_score"],
    "inaccurate_claim_trust": passport_b["reputation"]["trust_score"],
    "false_attestation_judgment_tx": judged["judgment"]["transaction_hash"],
    "marketplace_c_query": True,
})
