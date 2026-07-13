import base58
import json
import os
import sys
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from eth_account import Account
from eth_account.messages import encode_defunct
from nacl.signing import SigningKey

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.identity import binding_message, registration_message


API_BASE = os.getenv("API_BASE", "http://localhost:8000").rstrip("/")
API_KEY = os.getenv("ADMIN_API_KEY") or os.getenv("API_KEY", "")
if not API_KEY:
    raise SystemExit("ADMIN_API_KEY or API_KEY is required")


def request(path, method="GET", body=None):
    last_error = ""
    for attempt in range(5):
        req = Request(
            API_BASE + path,
            method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"content-type": "application/json", "x-api-key": API_KEY},
        )
        try:
            with urlopen(req, timeout=600) as response:
                return json.loads(response.read())
        except HTTPError as exc:
            last_error = exc.read().decode()
            if exc.code not in {429, 502, 503, 504} or attempt == 4:
                raise RuntimeError(last_error) from exc
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(last_error)


def post(path, body):
    return request(path, "POST", body)


def ensure_post(path, body):
    try:
        return post(path, body)
    except RuntimeError as exc:
        if "already exists" in str(exc).lower():
            return {"idempotent_replay": True}
        raise


suffix = os.getenv("V2_3_ACCEPTANCE_SUFFIX", str(int(time.time())))
market_a = f"identity_market_a_{suffix}"
market_b = f"identity_market_b_{suffix}"
attacker_market = f"identity_attacker_{suffix}"
base_agent = f"base_agent_{suffix}"
solana_agent = f"solana_agent_{suffix}"
sybil_agent = f"sybil_agent_{suffix}"

for platform_id, name in [(market_a, "Marketplace A"), (market_b, "Marketplace B"), (attacker_market, "Attacker Market")]:
    ensure_post("/platforms/register", {"platform_id": platform_id, "platform_name": name})
for agent_id, platform_id, name in [
    (base_agent, market_a, "Base Research Agent"),
    (solana_agent, market_b, "Solana Research Agent"),
    (sybil_agent, attacker_market, "False Identity Claimant"),
]:
    ensure_post("/agents/register", {"agent_id": agent_id, "platform_id": platform_id, "agent_name": name})

evm = Account.create()
attacker = Account.create()
solana = SigningKey.generate()
base_identity = f"base:{evm.address}"
attacker_identity = f"base:{attacker.address}"
solana_identity = f"solana:{base58.b58encode(bytes(solana.verify_key)).decode()}"


def register_evm(agent_id, identity, signer, nonce):
    message = registration_message(agent_id, identity, nonce)
    signature = Account.sign_message(encode_defunct(text=message), signer.key).signature.hex()
    return post(f"/agents/{agent_id}/identities", {"identity": identity, "nonce": nonce, "signature": signature})


register_evm(base_agent, base_identity, evm, f"register-{suffix}-base")
register_evm(sybil_agent, attacker_identity, attacker, f"register-{suffix}-attacker")
solana_nonce = f"register-{suffix}-solana"
solana_message = registration_message(solana_agent, solana_identity, solana_nonce)
post(f"/agents/{solana_agent}/identities", {
    "identity": solana_identity,
    "nonce": solana_nonce,
    "signature": base58.b58encode(solana.sign(solana_message.encode()).signature).decode(),
})

link_nonce = f"link-{suffix}-legitimate"
link_message = binding_message(base_agent, solana_agent, link_nonce)
proposal = post("/identity-bindings", {
    "source_agent_id": base_agent,
    "target_agent_id": solana_agent,
    "source_identity": base_identity,
    "target_identity": solana_identity,
    "nonce": link_nonce,
    "source_signature": Account.sign_message(encode_defunct(text=link_message), evm.key).signature.hex(),
    "evidence_uri": "https://github.com/ShalyX/replayer",
    "evidence_hash": "v2.3-common-control",
})
proposal_id = proposal["proposal"]["event_id"]
linked = post(f"/identity-bindings/{proposal_id}/confirm", {
    "target_signature": base58.b58encode(solana.sign(link_message.encode()).signature).decode(),
    "evidence_uri": "https://github.com/ShalyX/replayer",
    "evidence_hash": "v2.3-dual-signature",
})

job_id = f"identity_job_{suffix}"
post("/jobs", {
    "job_id": job_id, "platform_id": market_a, "requester_id": "identity_buyer",
    "provider_agent_id": base_agent, "task_spec": "Produce a cited identity-security research brief.",
    "category": "research", "payment_amount": 100, "currency": "USDC",
})
post(f"/jobs/{job_id}/deliverable", {
    "deliverable_uri": "https://github.com/ShalyX/replayer",
    "summary": "Identity security brief with sources.", "evidence_urls": ["https://github.com/ShalyX/replayer"],
})
post(f"/jobs/{job_id}/accept", {})

false_nonce = f"link-{suffix}-false"
false_message = binding_message(sybil_agent, solana_agent, false_nonce)
false_proposal = post("/identity-bindings", {
    "source_agent_id": sybil_agent, "target_agent_id": solana_agent,
    "source_identity": attacker_identity, "target_identity": solana_identity,
    "nonce": false_nonce,
    "source_signature": Account.sign_message(encode_defunct(text=false_message), attacker.key).signature.hex(),
    "evidence_uri": "https://github.com/ShalyX/replayer",
    "evidence_hash": "false-identity-claim",
})
false_proposal_id = false_proposal["proposal"]["event_id"]
challenged = post(f"/identity-bindings/{false_proposal_id}/challenge", {
    "challenger_agent_id": solana_agent,
    "reason": "The target controller never signed or approved this binding. The claimant controls a different EVM key.",
    "evidence_uri": "https://github.com/ShalyX/replayer",
    "evidence_hash": "target-controller-denial",
})
assert challenged["resolution"]["event_type"] == "IDENTITY_LINK_REJECTED"

profile_a = request(f"/agents/{base_agent}/profile")
profile_b = request(f"/agents/{solana_agent}/profile")
profile_sybil = request(f"/agents/{sybil_agent}/profile")
assert profile_a["identity"]["canonical_agent_id"] == profile_b["identity"]["canonical_agent_id"]
assert profile_a["reputation"]["trust_score"] == profile_b["reputation"]["trust_score"]
assert sybil_agent not in profile_a["identity"]["linked_agents"]
assert profile_sybil["identity"]["linked_agents"] == [sybil_agent]

before = {
    "canonical": profile_a["identity"]["canonical_agent_id"],
    "members": profile_a["identity"]["linked_agents"],
    "trust": profile_a["reputation"]["trust_score"],
}
rebuilt = post("/admin/projections/rebuild", {})
after_profile = request(f"/agents/{solana_agent}/profile")
after = {
    "canonical": after_profile["identity"]["canonical_agent_id"],
    "members": after_profile["identity"]["linked_agents"],
    "trust": after_profile["reputation"]["trust_score"],
}
assert before == after
print(json.dumps({
    "status": "passed", "canonical_passport": before,
    "valid_link_transaction": linked["tx"]["tx_id"],
    "false_link_judgment_transaction": challenged["tx"]["tx_id"],
    "false_link_outcome": challenged["judgment"]["metadata"]["outcome"],
    "rebuilt_projections": rebuilt["rebuilt"],
}, indent=2))
