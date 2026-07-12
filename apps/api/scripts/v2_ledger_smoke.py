from sqlalchemy import create_engine
from sqlalchemy.orm import Session
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import Base
from app.ledger import append_event, projection_dict, rebuild_projection
from app.models import Agent, Job, Platform

engine = create_engine("sqlite:///:memory:")
Base.metadata.create_all(engine)
with Session(engine) as db:
    db.add(Platform(id="platform_test", name="Test Platform"))
    db.add(Agent(id="agent_test", platform_id="platform_test", name="Research Bot"))
    db.add(Job(id="job_test", requester_id="buyer", provider_agent_id="agent_test", platform_id="platform_test", task_spec="Research", category="research"))
    db.flush()
    append_event(db, event_type="AGENT_REGISTERED", agent_id="agent_test", platform_id="platform_test", provenance="platform_reported", verification_status="finalized")
    append_event(db, event_type="JOB_ACCEPTED", agent_id="agent_test", platform_id="platform_test", job_id="job_test", provenance="counterparty_confirmed", verification_status="finalized")
    accepted = projection_dict(rebuild_projection(db, "agent_test"))
    assert accepted["trust_score"] == 74
    append_event(db, event_type="DISPUTE_OPENED", agent_id="agent_test", platform_id="platform_test", job_id="job_test", provenance="platform_reported", verification_status="pending")
    append_event(db, event_type="JUDGMENT_FINALIZED", agent_id="agent_test", platform_id="platform_test", job_id="job_test", provenance="genlayer_verified", verification_status="finalized", contract_address="0xcontract", transaction_hash="0xtx", metadata={"verdict": "fraudulent", "contract_readback_verified": True})
    flagged = projection_dict(rebuild_projection(db, "agent_test"))
    assert flagged["trust_score"] == 44
    assert flagged["risk_score"] == 63
    assert flagged["status"] == "flagged"
    assert flagged["fraud_incidents"] == 1
    print(flagged)
