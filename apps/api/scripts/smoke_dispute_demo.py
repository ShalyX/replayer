import json
import time

import requests


BASE_URL = "http://localhost:8000"
API_KEY = "dev-key"
HEADERS = {"x-api-key": API_KEY}


def post(path: str, payload: dict) -> dict:
    last_error = None
    for attempt in range(5):
        response = requests.post(f"{BASE_URL}{path}", json=payload, headers=HEADERS, timeout=300)
        if response.ok:
            return response.json()
        last_error = response.text
        time.sleep(4 + attempt * 2)
    raise RuntimeError(last_error)


def get(path: str) -> dict:
    response = requests.get(f"{BASE_URL}{path}", timeout=60)
    response.raise_for_status()
    return response.json()


suffix = int(time.time())
platform_id = f"platform_demo_{suffix}"
second_platform_id = f"platform_hiring_{suffix}"
agent_id = f"agent_research_{suffix}"
good_job_id = f"job_good_{suffix}"
bad_job_id = f"job_bad_{suffix}"

print("1. Platform registers")
print(json.dumps(post("/platforms/register", {
    "platform_id": platform_id,
    "platform_name": "AgentMarket Demo",
    "webhook_url": "https://example.com/webhooks/replayer",
}), indent=2))

print("2. Another platform registers for reputation lookup")
post("/platforms/register", {
    "platform_id": second_platform_id,
    "platform_name": "Second Market",
    "webhook_url": "https://example.com/webhooks/second-market",
})

print("3. Platform registers agent")
post("/agents/register", {
    "agent_id": agent_id,
    "platform_id": platform_id,
    "agent_name": "DeepResearchBot",
    "owner_wallet": "owner_wallet_demo",
    "capabilities": ["research", "citations", "market-analysis"],
    "metadata_uri": "https://example.com/agents/deepresearchbot.json",
})

print("4. Agent completes good job; reputation rises")
post("/jobs", {
    "job_id": good_job_id,
    "platform_id": platform_id,
    "requester_id": "buyer_good",
    "provider_agent_id": agent_id,
    "task_spec": "Research five reliable AI infrastructure companies with sources.",
    "category": "research",
    "payment_amount": 100,
    "currency": "USDC",
})
post(f"/jobs/{good_job_id}/deliverable", {
    "deliverable_id": f"deliv_good_{suffix}",
    "deliverable_uri": "https://example.com/deliverables/good.txt",
    "summary": "Submitted a complete sourced report.",
    "evidence_urls": ["https://example.com/source-good"],
})
post(f"/jobs/{good_job_id}/accept", {})
print(json.dumps(get(f"/agents/{agent_id}/reputation"), indent=2))

print("5. Bad deliverable disputed; GenLayer/mock evaluates; reputation drops")
post("/jobs", {
    "job_id": bad_job_id,
    "platform_id": platform_id,
    "requester_id": "buyer_bad",
    "provider_agent_id": agent_id,
    "task_spec": "Find top 20 Series A fintech startups in Brazil with sources.",
    "category": "research",
    "payment_amount": 100,
    "currency": "USDC",
})
post(f"/jobs/{bad_job_id}/deliverable", {
    "deliverable_id": f"deliv_bad_{suffix}",
    "deliverable_uri": "https://example.com/deliverables/bad.txt",
    "summary": "Submitted a report with weak citations.",
    "evidence_urls": ["https://example.com/source-bad"],
})
post(f"/jobs/{bad_job_id}/dispute", {
    "dispute_id": f"disp_bad_{suffix}",
    "claimant": "requester",
    "reason": "Several companies listed are not Series A and two sources are fabricated.",
    "evidence_uri": "https://example.com/disputes/bad.txt",
    "bond_amount": 10,
})
print(json.dumps(post(f"/jobs/{bad_job_id}/evaluate", {}), indent=2))

print("6. Another platform queries public reputation before hiring")
print(json.dumps(get(f"/agents/{agent_id}/profile"), indent=2))
