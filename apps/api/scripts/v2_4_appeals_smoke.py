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


def verified_event(db, **kwargs):
    metadata = {**kwargs.pop("metadata", {}), "contract_readback_verified": True}
    return append_event(db, contract_address="0x" + "24" * 20, metadata=metadata, **kwargs)


with Session() as db:
    db.add(Platform(id="appeals_market", name="Appeals Market"))
    db.add(Agent(id="appeal_agent", platform_id="appeals_market", name="Appealable Research Agent"))
    db.flush()

    verified_event(
        db, event_id="accepted_job", event_type="JOB_ACCEPTED", agent_id="appeal_agent",
        platform_id="appeals_market", job_id="job_appeal", provenance="platform_reported",
        verification_status="finalized",
    )
    verified_event(
        db, event_id="provisional_fraud", event_type="JUDGMENT_PROVISIONAL",
        agent_id="appeal_agent", platform_id="appeals_market", job_id="job_appeal",
        dispute_id="dispute_appeal", provenance="genlayer_provisional",
        verification_status="provisional", transaction_hash="0x" + "11" * 32,
        metadata={"verdict": "fraudulent", "confidence_bps": 7800},
    )
    provisional = projection_dict(rebuild_projection(db, "appeal_agent", "research_trust_v5"))
    assert provisional["trust_score"] == 66
    assert provisional["risk_score"] == 30
    assert provisional["status"] == "review"
    assert provisional["fraud_incidents"] == 0

    verified_event(
        db, event_id="appeal_submitted", event_type="APPEAL_SUBMITTED",
        agent_id="appeal_agent", platform_id="appeals_market", job_id="job_appeal",
        dispute_id="dispute_appeal", provenance="challenged", verification_status="appealed",
        references=["provisional_fraud"], transaction_hash="0x" + "22" * 32,
        metadata={"original_verdict": "fraudulent", "protocol_round": 1},
    )
    appealed = projection_dict(rebuild_projection(db, "appeal_agent", "research_trust_v5"))
    assert appealed["trust_score"] == 70
    assert appealed["risk_score"] == 24
    assert appealed["details"]["provisional_impacts"][0]["status"] == "appealed"

    verified_event(
        db, event_id="appeal_resolved", event_type="APPEAL_RESOLVED",
        agent_id="appeal_agent", platform_id="appeals_market", job_id="job_appeal",
        dispute_id="dispute_appeal", provenance="genlayer_verified", verification_status="finalized",
        references=["provisional_fraud", "appeal_submitted"],
        metadata={"original_verdict": "fraudulent", "final_verdict": "satisfied"},
    )
    verified_event(
        db, event_id="judgment_overturned", event_type="JUDGMENT_OVERTURNED",
        agent_id="appeal_agent", platform_id="appeals_market", job_id="job_appeal",
        dispute_id="dispute_appeal", provenance="genlayer_verified", verification_status="finalized",
        references=["provisional_fraud", "appeal_submitted", "appeal_resolved"],
        metadata={"original_verdict": "fraudulent", "final_verdict": "satisfied"},
    )
    verified_event(
        db, event_id="provisional_superseded", event_type="EVENT_SUPERSEDED",
        agent_id="appeal_agent", platform_id="appeals_market", job_id="job_appeal",
        dispute_id="dispute_appeal", provenance="superseded", verification_status="superseded",
        references=["provisional_fraud"],
    )
    verified_event(
        db, event_id="final_satisfied", event_type="JUDGMENT_FINALIZED",
        agent_id="appeal_agent", platform_id="appeals_market", job_id="job_appeal",
        dispute_id="dispute_appeal", provenance="genlayer_verified", verification_status="finalized",
        references=["provisional_fraud", "appeal_submitted", "appeal_resolved", "judgment_overturned"],
        transaction_hash="0x" + "11" * 32,
        metadata={"verdict": "satisfied", "appeal_outcome": "overturned", "protocol_round": 1},
    )
    finalized = projection_dict(rebuild_projection(db, "appeal_agent", "research_trust_v5"))
    assert finalized["trust_score"] == 79
    assert finalized["risk_score"] == 13
    assert finalized["fraud_incidents"] == 0
    assert finalized["details"]["pending_judgments"] == 0

    expected = (finalized["trust_score"], finalized["risk_score"], finalized["status"], finalized["fraud_incidents"])
    db.execute(delete(AgentReputationProjection))
    db.flush()
    rebuild_all_projections(db)
    replayed = projection_dict(rebuild_projection(db, "appeal_agent", "research_trust_v5"))
    actual = (replayed["trust_score"], replayed["risk_score"], replayed["status"], replayed["fraud_incidents"])
    assert actual == expected
    print("V2.4 passed: provisional discounted, appeal softened impact, overturn finalized, replay identical")
