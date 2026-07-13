import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.ledger import append_event, projection_dict, rebuild_projection
from app.models import Agent, Platform


engine = create_engine("sqlite+pysqlite:///:memory:")
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

with Session() as db:
    db.add_all([
        Platform(id="market_a", name="Marketplace A"),
        Platform(id="market_b", name="Marketplace B"),
        Agent(id="researchpro", platform_id="market_a", name="ResearchPro"),
    ])
    db.flush()
    append_event(db, event_id="attestation_50", event_type="REPUTATION_ATTESTED", agent_id="researchpro",
                 platform_id="market_a", category="research", provenance="platform_reported",
                 verification_status="uncontested", evidence_uri="ipfs://attestation", evidence_hash="0xattestation",
                 metadata={"type": "jobs_completed", "value": 50})
    reported = projection_dict(rebuild_projection(db, "researchpro", "research_trust_v2"))
    append_event(db, event_id="confirmation_30", event_type="COUNTERPARTY_CONFIRMED", agent_id="researchpro",
                 platform_id="market_b", category="research", provenance="counterparty_confirmed",
                 verification_status="finalized", evidence_uri="ipfs://confirmation", evidence_hash="0xconfirmation",
                 references=["attestation_50"],
                 metadata={"type": "jobs_completed", "value": 30, "attestation_event_id": "attestation_50"})
    confirmed = projection_dict(rebuild_projection(db, "researchpro", "research_trust_v2"))
    append_event(db, event_id="challenge", event_type="EVENT_CHALLENGED", agent_id="researchpro",
                 platform_id="market_a", provenance="challenged", verification_status="pending",
                 references=["attestation_50"], metadata={"reason": "Only 32 jobs are valid"})
    append_event(db, event_id="judgment", event_type="ATTESTATION_JUDGMENT_FINALIZED", agent_id="researchpro",
                 platform_id="market_a", provenance="genlayer_verified", verification_status="finalized",
                 references=["attestation_50", "challenge"],
                 metadata={"outcome": "attestation_partially_valid", "valid_value": 32})
    append_event(db, event_id="superseded", event_type="EVENT_SUPERSEDED", agent_id="researchpro",
                 platform_id="market_a", provenance="superseded", verification_status="superseded",
                 references=["attestation_50"])
    append_event(db, event_id="corrected_32", event_type="REPUTATION_ATTESTED", agent_id="researchpro",
                 platform_id="market_a", provenance="genlayer_verified", verification_status="finalized",
                 evidence_uri="ipfs://attestation", evidence_hash="0xattestation",
                 references=["attestation_50", "judgment"], metadata={"type": "jobs_completed", "value": 32})
    corrected = projection_dict(rebuild_projection(db, "researchpro", "research_trust_v2"))
    assert (reported["trust_score"], confirmed["trust_score"], corrected["trust_score"]) == (76, 81, 78)
    assert corrected["details"]["verified_work_history"][-1]["value"] == 32
    print("V2.1 projection passed: reported=76 confirmed=81 corrected=78 valid_jobs=32")
