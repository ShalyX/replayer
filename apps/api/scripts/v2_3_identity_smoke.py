import base58
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eth_account import Account
from eth_account.messages import encode_defunct
from nacl.signing import SigningKey
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.identity import binding_message, registration_message, verify_identity_signature
from app.ledger import (
    append_event,
    identity_projection_dict,
    projection_dict,
    rebuild_all_identity_projections,
    rebuild_all_projections,
    rebuild_identity_projection,
    rebuild_projection,
)
from app.models import Agent, AgentIdentityProjection, AgentReputationProjection, Platform


engine = create_engine("sqlite+pysqlite:///:memory:")
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)


def snapshot(db):
    identities = rebuild_all_identity_projections(db)
    return sorted([
        (row.agent_id, row.canonical_agent_id, tuple(row.linked_agents), tuple(row.aliases), row.status)
        for row in identities
    ])


with Session() as db:
    db.add_all([
        Platform(id="market_a", name="Marketplace A"),
        Platform(id="market_b", name="Marketplace B"),
        Platform(id="attacker_market", name="Attacker Market"),
        Agent(id="base_agent", platform_id="market_a", name="Base Research Agent"),
        Agent(id="solana_agent", platform_id="market_b", name="Solana Research Agent"),
        Agent(id="sybil_agent", platform_id="attacker_market", name="False Claimant"),
    ])
    db.flush()

    evm = Account.create()
    solana = SigningKey.generate()
    attacker = Account.create()
    base_identity = f"base:{evm.address}"
    solana_identity = f"solana:{base58.b58encode(bytes(solana.verify_key)).decode()}"
    attacker_identity = f"base:{attacker.address}"

    for agent_id, identity, signer in [
        ("base_agent", base_identity, evm),
        ("sybil_agent", attacker_identity, attacker),
    ]:
        message = registration_message(agent_id, identity, f"nonce-{agent_id}")
        signature = Account.sign_message(encode_defunct(text=message), signer.key).signature.hex()
        verify_identity_signature(identity, message, signature)
    solana_registration = registration_message("solana_agent", solana_identity, "nonce-solana-agent")
    solana_signature = base58.b58encode(solana.sign(solana_registration.encode()).signature).decode()
    verify_identity_signature(solana_identity, solana_registration, solana_signature)

    registrations = [
        ("identity_base", "base_agent", "market_a", base_identity, base_identity.lower()),
        ("identity_solana", "solana_agent", "market_b", solana_identity, solana_identity.split(":", 1)[1]),
        ("identity_sybil", "sybil_agent", "attacker_market", attacker_identity, attacker_identity.lower()),
    ]
    for event_id, agent_id, platform_id, identity, controller in registrations:
        append_event(db, event_id=event_id, event_type="AGENT_IDENTITY_REGISTERED", agent_id=agent_id,
                     platform_id=platform_id, provenance="platform_reported", verification_status="finalized",
                     category="agent_identity", metadata={"identity": identity.lower() if identity.startswith("base:") else identity,
                                                          "controller": controller})

    link_message = binding_message("base_agent", "solana_agent", "link-nonce-123")
    source_signature = Account.sign_message(encode_defunct(text=link_message), evm.key).signature.hex()
    target_signature = base58.b58encode(solana.sign(link_message.encode()).signature).decode()
    verify_identity_signature(base_identity, link_message, source_signature)
    verify_identity_signature(solana_identity, link_message, target_signature)
    link_metadata = {
        "source_agent_id": "base_agent", "target_agent_id": "solana_agent",
        "source_identity": base_identity.lower(), "target_identity": solana_identity,
        "controller_proof": "dual_signature",
    }
    append_event(db, event_id="valid_proposal", event_type="IDENTITY_BINDING_PROPOSED", agent_id="base_agent",
                 platform_id="market_a", counterparty_id="solana_agent", category="agent_identity",
                 provenance="platform_reported", verification_status="pending", metadata=link_metadata)
    append_event(db, event_id="valid_confirmation", event_type="CONTROLLER_CONFIRMED", agent_id="solana_agent",
                 platform_id="market_b", counterparty_id="base_agent", category="agent_identity",
                 provenance="counterparty_confirmed", verification_status="finalized", references=["valid_proposal"],
                 metadata=link_metadata)
    append_event(db, event_id="valid_link", event_type="IDENTITY_LINKED", agent_id="base_agent",
                 platform_id="market_a", counterparty_id="solana_agent", category="agent_identity",
                 provenance="counterparty_confirmed", verification_status="finalized",
                 references=["valid_proposal", "valid_confirmation"], metadata=link_metadata)

    false_metadata = {
        "source_agent_id": "sybil_agent", "target_agent_id": "solana_agent",
        "source_identity": attacker_identity.lower(), "target_identity": solana_identity,
    }
    append_event(db, event_id="false_proposal", event_type="IDENTITY_BINDING_PROPOSED", agent_id="sybil_agent",
                 platform_id="attacker_market", counterparty_id="solana_agent", category="agent_identity",
                 provenance="platform_reported", verification_status="pending", metadata=false_metadata)
    append_event(db, event_id="false_challenge", event_type="IDENTITY_CHALLENGED", agent_id="sybil_agent",
                 platform_id="attacker_market", counterparty_id="solana_agent", category="agent_identity",
                 provenance="challenged", verification_status="pending", references=["false_proposal"])
    append_event(db, event_id="false_judgment", event_type="IDENTITY_JUDGMENT_FINALIZED", agent_id="sybil_agent",
                 platform_id="attacker_market", counterparty_id="solana_agent", category="agent_identity",
                 provenance="genlayer_verified", verification_status="finalized",
                 references=["false_proposal", "false_challenge"], metadata={"outcome": "identity_link_false"})
    append_event(db, event_id="false_rejected", event_type="IDENTITY_LINK_REJECTED", agent_id="sybil_agent",
                 platform_id="attacker_market", counterparty_id="solana_agent", category="agent_identity",
                 provenance="superseded", verification_status="superseded",
                 references=["false_proposal", "false_judgment"], metadata=false_metadata)

    append_event(db, event_id="accepted_base", event_type="JOB_ACCEPTED", agent_id="base_agent",
                 platform_id="market_a", provenance="platform_reported", verification_status="finalized")
    append_event(db, event_id="history_solana", event_type="REPUTATION_ATTESTED", agent_id="solana_agent",
                 platform_id="market_b", provenance="platform_reported", verification_status="uncontested",
                 evidence_uri="ipfs://history", evidence_hash="0xhistory",
                 metadata={"type": "jobs_completed", "value": 9, "issuer_credibility_bps": 5000,
                           "credibility_projection_version": "platform_credibility_v1"})

    rebuild_all_projections(db)
    identity_a = identity_projection_dict(rebuild_identity_projection(db, "base_agent"))
    identity_b = identity_projection_dict(rebuild_identity_projection(db, "solana_agent"))
    identity_sybil = identity_projection_dict(rebuild_identity_projection(db, "sybil_agent"))
    assert identity_a["canonical_agent_id"] == identity_b["canonical_agent_id"] == "base_agent"
    assert identity_a["linked_agents"] == ["base_agent", "solana_agent"]
    assert identity_sybil["linked_agents"] == ["sybil_agent"]
    passport_a = projection_dict(rebuild_projection(db, "base_agent", "research_trust_v4"))
    passport_b = projection_dict(rebuild_projection(db, "solana_agent", "research_trust_v4"))
    assert passport_a["trust_score"] == passport_b["trust_score"] == 77

    before = snapshot(db)
    db.execute(delete(AgentIdentityProjection))
    db.execute(delete(AgentReputationProjection))
    db.flush()
    rebuild_all_projections(db)
    after = snapshot(db)
    assert before == after
    print("V2.3 passed: aliases linked, canonical trust=77, false identity rejected, replay identical")
