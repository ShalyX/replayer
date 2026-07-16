import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, delete
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.ledger import append_event, projection_dict, rebuild_all_projections, rebuild_projection
from app.models import Agent, AgentReputationProjection, Platform


engine = create_engine("sqlite+pysqlite:///:memory:")
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
contract = "0x" + "30" * 20
tx = "0x" + "70" * 32


def event(db, **kwargs):
    metadata = {**kwargs.pop("metadata", {}), "contract_readback_verified": True}
    return append_event(db, contract_address=contract, transaction_hash=tx, metadata=metadata, **kwargs)


with Session() as db:
    db.add(Platform(id="market_c", name="Marketplace C"))
    db.add_all([
        Agent(id="agent_a", platform_id="market_c", name="Delegator Agent A"),
        Agent(id="agent_b", platform_id="market_c", name="Worker Agent B"),
    ])
    db.flush()

    common = {
        "delegation_id": "delegation_ab", "responsibility_case_id": "responsibility_ab",
        "principal_agent_id": "agent_a", "worker_agent_id": "agent_b",
        "outcome": "shared_responsibility", "impact_kind": "fabricated_sources",
    }
    for agent_id, role, bps in [("agent_a", "delegator", 3000), ("agent_b", "worker", 7000)]:
        event(
            db, event_id=f"provisional_{agent_id}", event_type="RESPONSIBILITY_JUDGMENT_PROVISIONAL",
            agent_id=agent_id, platform_id="market_c", job_id="job_ab", dispute_id="responsibility_ab",
            counterparty_id="agent_b" if agent_id == "agent_a" else "agent_a",
            provenance="genlayer_provisional", verification_status="provisional",
            metadata={**common, "role": role, "responsibility_bps": bps},
        )
    principal_provisional = projection_dict(rebuild_projection(db, "agent_a", "research_trust_v6"))
    worker_provisional = projection_dict(rebuild_projection(db, "agent_b", "research_trust_v6"))
    assert principal_provisional["trust_score"] == 68
    assert worker_provisional["trust_score"] == 65

    event(
        db, event_id="responsibility_appeal", event_type="RESPONSIBILITY_APPEALED",
        agent_id="agent_a", platform_id="market_c", job_id="job_ab", dispute_id="responsibility_ab",
        counterparty_id="agent_b", provenance="challenged", verification_status="appealed",
        references=["provisional_agent_a", "provisional_agent_b"], metadata=common,
    )
    principal_appealed = projection_dict(rebuild_projection(db, "agent_a", "research_trust_v6"))
    worker_appealed = projection_dict(rebuild_projection(db, "agent_b", "research_trust_v6"))
    assert principal_appealed["trust_score"] == 69
    assert worker_appealed["trust_score"] == 67

    for agent_id, role, bps in [("agent_a", "delegator", 3000), ("agent_b", "worker", 7000)]:
        event(
            db, event_id=f"liability_{agent_id}", event_type="LIABILITY_APPORTIONED",
            agent_id=agent_id, platform_id="market_c", job_id="job_ab", dispute_id="responsibility_ab",
            counterparty_id="agent_b" if agent_id == "agent_a" else "agent_a",
            provenance="genlayer_verified", verification_status="finalized",
            references=[f"responsibility_final_{agent_id}"],
            metadata={**common, "role": role, "responsibility_bps": bps},
        )
    principal_final = projection_dict(rebuild_projection(db, "agent_a", "research_trust_v6"))
    worker_final = projection_dict(rebuild_projection(db, "agent_b", "research_trust_v6"))
    assert (principal_final["trust_score"], principal_final["risk_score"]) == (61, 24)
    assert (worker_final["trust_score"], worker_final["risk_score"]) == (49, 42)
    assert principal_final["fraud_incidents"] == 0
    assert worker_final["fraud_incidents"] == 1
    assert principal_final["details"]["accountability_chain"][0]["responsibility_bps"] == 3000
    assert worker_final["details"]["accountability_chain"][0]["responsibility_bps"] == 7000

    expected = {
        "agent_a": (61, 24, 0),
        "agent_b": (49, 42, 1),
    }
    db.execute(delete(AgentReputationProjection))
    db.flush()
    rebuild_all_projections(db)
    replayed = {
        agent_id: projection_dict(rebuild_projection(db, agent_id, "research_trust_v6"))
        for agent_id in expected
    }
    actual = {
        agent_id: (row["trust_score"], row["risk_score"], row["fraud_incidents"])
        for agent_id, row in replayed.items()
    }
    assert actual == expected
    print("V3.0 passed: 30/70 liability applied distinctly and replay rebuilt both Passports")
