import hashlib
import os
import time

import requests


base = os.getenv("REPLAYER_API_BASE", "http://localhost:8000").rstrip("/")
admin_key = os.getenv("ADMIN_API_KEY", "")
if not admin_key:
    raise SystemExit("ADMIN_API_KEY is required")

headers = {"x-api-key": admin_key, "content-type": "application/json"}
suffix = str(int(time.time()))
platform_a = f"market_a_{suffix}"
platform_b = f"market_b_{suffix}"
platform_c = f"market_c_{suffix}"
agent_id = f"researchpro_{suffix}"
report_url = "https://raw.githubusercontent.com/ShalyX/replayer/main/docs/fixtures/attestation-50.md"
audit_url = "https://raw.githubusercontent.com/ShalyX/replayer/main/docs/fixtures/attestation-audit-32.md"


def post(path, body, key=admin_key):
    response = requests.post(base + path, json=body, headers={**headers, "x-api-key": key}, timeout=900)
    if not response.ok:
        raise RuntimeError(f"{path}: {response.status_code} {response.text}")
    return response.json()


keys = {}
for platform_id, name in ((platform_a, "Marketplace A"), (platform_b, "Marketplace B"), (platform_c, "Marketplace C")):
    result = post("/platforms/register", {"platform_id": platform_id, "platform_name": name})
    keys[platform_id] = result["api_key"]

post("/agents/register", {
    "agent_id": agent_id, "platform_id": platform_a, "agent_name": "ResearchPro",
    "capabilities": ["research", "citations"],
}, keys[platform_a])

attested = post("/attestations", {
    "agent_id": agent_id, "platform_id": platform_a, "type": "jobs_completed", "value": 50,
    "category": "research", "period_start": "2026-01-01", "period_end": "2026-06-30",
    "evidence_uri": report_url, "evidence_hash": "0x" + hashlib.sha256(b"attestation-50").hexdigest(),
}, keys[platform_a])
attestation_id = attested["event"]["event_id"]
assert attested["reputation"]["trust_score"] == 76

confirmed = post(f"/attestations/{attestation_id}/confirm", {
    "platform_id": platform_b, "value": 30, "counterparty_id": "marketplace_b_auditor",
    "evidence_uri": report_url, "evidence_hash": "0x" + hashlib.sha256(b"confirmation-30").hexdigest(),
}, keys[platform_b])
assert confirmed["reputation"]["trust_score"] == 81

challenged = post(f"/events/{attestation_id}/challenge", {
    "challenger_id": agent_id,
    "reason": "The platform reported 50 completed jobs, but the independent audit proves exactly 32 are valid.",
    "evidence_uri": audit_url, "evidence_hash": "0x" + hashlib.sha256(b"audit-32").hexdigest(),
}, keys[platform_a])
metadata = challenged["judgment"]["metadata"]
assert metadata["outcome"] == "attestation_partially_valid", metadata
assert int(metadata["valid_value"]) == 32, metadata
assert challenged["reputation"]["trust_score"] == 78

passport = requests.get(base + f"/agents/{agent_id}/profile", timeout=120).json()
history = passport["reputation"]["details"]["verified_work_history"]
assert history[-1]["value"] == 32 and history[-1]["provenance"] == "genlayer_verified"
print({
    "agent_id": agent_id, "attestation_event_id": attestation_id,
    "judgment_event_id": challenged["judgment"]["event_id"],
    "transaction_hash": challenged["judgment"]["transaction_hash"],
    "reported_trust": 76, "confirmed_trust": 81, "corrected_trust": 78,
    "valid_jobs": 32, "marketplace_c_passport": True,
})
