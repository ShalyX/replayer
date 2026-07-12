import json
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings


BASE_URL = "http://localhost:8000"
HEADERS = {"x-api-key": "dev-key"}


def post(path: str, payload: dict) -> dict:
    last_error = None
    for attempt in range(5):
        response = requests.post(f"{BASE_URL}{path}", headers=HEADERS, json=payload, timeout=300)
        if response.ok:
            return response.json()
        last_error = response.text
        time.sleep(4 + attempt * 2)
    raise RuntimeError(last_error)


def get(path: str) -> dict:
    response = requests.get(f"{BASE_URL}{path}", timeout=90)
    response.raise_for_status()
    return response.json()


def wait_for_judgment(path: str) -> dict:
    for attempt in range(20):
        response = requests.post(f"{BASE_URL}{path}", headers=HEADERS, json={}, timeout=300)
        if response.ok:
            return response.json()
        detail = response.text.lower()
        if "judgment" not in detail or "pending" not in detail:
            raise RuntimeError(response.text)
        print(f"Judgment pending; retry {attempt + 1}/20")
        time.sleep(15)
    raise RuntimeError("GenLayer judgment did not become readable within the demo polling window")


suffix = int(time.time())
platform_id = f"researchagents_io_{suffix}"
partner_platform_id = f"partner_market_{suffix}"
agent_id = f"deepresearchbot_{suffix}"
good_job_id = f"research_good_{suffix}"
fraud_job_id = f"research_fraud_{suffix}"

health = get("/health")
running_address = str(health.get("contract_address", ""))
if running_address.lower() != settings.genlayer_contract_address.lower():
    raise RuntimeError(
        "The API process is using stale GenLayer configuration. "
        f"API: {running_address or 'missing'}; .env: {settings.genlayer_contract_address}. "
        "Stop every process listening on port 8000 and restart npm run dev:api."
    )
if health.get("genlayer_mode") != "live":
    raise RuntimeError("The API is not running in live GenLayer mode")

print("Killer demo: Any agent platform can integrate this API and outsource trust, disputes, and portable reputation to GenLayer.")

post("/platforms/register", {
    "platform_id": platform_id,
    "platform_name": "ResearchAgents.io",
    "webhook_url": "https://researchagents.example/webhooks/replayer",
})
post("/platforms/register", {
    "platform_id": partner_platform_id,
    "platform_name": "EnterpriseAgentMarket",
    "webhook_url": "https://enterprise.example/webhooks/replayer",
})
post("/agents/register", {
    "agent_id": agent_id,
    "platform_id": platform_id,
    "agent_name": "DeepResearchBot",
    "owner_wallet": "researchagents_owner_wallet",
    "capabilities": ["research", "citations", "market-analysis"],
    "metadata_uri": "https://researchagents.example/agents/deepresearchbot.json",
})

post("/jobs", {
    "job_id": good_job_id,
    "platform_id": platform_id,
    "requester_id": "buyer_series_a",
    "provider_agent_id": agent_id,
    "task_spec": "Research five AI infrastructure companies with real sources.",
    "category": "research",
    "payment_amount": 100,
    "currency": "USDC",
})
post(f"/jobs/{good_job_id}/deliverable", {
    "deliverable_id": f"deliv_{good_job_id}",
    "deliverable_uri": "https://example.com",
    "summary": "Completed the research task with credible sources.",
    "evidence_urls": ["https://example.com"],
})
post(f"/jobs/{good_job_id}/accept", {})
print("After good job:")
print(json.dumps(get(f"/agents/{agent_id}/reputation"), indent=2))

post("/jobs", {
    "job_id": fraud_job_id,
    "platform_id": platform_id,
    "requester_id": "buyer_fintech",
    "provider_agent_id": agent_id,
    "task_spec": "Find top 20 Series A fintech startups in Brazil with citations.",
    "category": "research",
    "payment_amount": 250,
    "currency": "USDC",
})
post(f"/jobs/{fraud_job_id}/deliverable", {
    "deliverable_id": f"deliv_{fraud_job_id}",
    "deliverable_uri": "https://example.com",
    "summary": "Claims example.com verifies 20 real fintech companies and their Series A rounds.",
    "evidence_urls": ["https://example.com"],
})
post(f"/jobs/{fraud_job_id}/dispute", {
    "dispute_id": f"disp_{fraud_job_id}",
    "claimant": "requester",
    "reason": "The deliverable uses https://example.com as its only citation and claims that page verifies 20 Brazilian fintech companies and their Series A rounds. IANA reserves example.com for documentation examples; it contains no company or funding data. Presenting it as research evidence is a fabricated citation and deliberate deception.",
    "evidence_uri": "https://www.iana.org/help/example-domains",
    "bond_amount": 10,
})
judgment = wait_for_judgment(f"/jobs/{fraud_job_id}/evaluate")
print("After disputed fraudulent job:")
print(json.dumps(judgment, indent=2))

print("Partner platform queries before hiring:")
print(json.dumps(get(f"/agents/{agent_id}/profile"), indent=2))
print("Partner dashboard agent list:")
print(json.dumps(get(f"/platforms/{platform_id}/agents"), indent=2))
