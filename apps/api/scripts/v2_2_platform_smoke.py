import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.ledger import append_event, projection_dict, rebuild_platform_credibility, rebuild_projection
from app.models import Agent, Platform


engine = create_engine("sqlite+pysqlite:///:memory:")
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

with Session() as db:
    db.add_all([
        Platform(id="reliable", name="Reliable Market"), Platform(id="inaccurate", name="Inaccurate Market"),
        Agent(id="issuer_agent_a", platform_id="reliable", name="Issuer A"),
        Agent(id="issuer_agent_b", platform_id="inaccurate", name="Issuer B"),
        Agent(id="candidate_a", platform_id="reliable", name="Candidate A"),
        Agent(id="candidate_b", platform_id="inaccurate", name="Candidate B"),
    ])
    db.flush()
    append_event(db, event_id="identity_a", event_type="PLATFORM_IDENTITY_VERIFIED", agent_id="issuer_agent_a",
                 platform_id="reliable", provenance="platform_reported", verification_status="finalized")
    for index in range(5):
        attestation_id = f"history_a_{index}"
        append_event(db, event_id=attestation_id, event_type="REPUTATION_ATTESTED", agent_id="issuer_agent_a",
                     platform_id="reliable", provenance="platform_reported", verification_status="uncontested",
                     evidence_uri="ipfs://history", evidence_hash="0xhistory", metadata={"type": "jobs_completed", "value": 10})
        append_event(db, event_id=f"confirmation_a_{index}", event_type="COUNTERPARTY_CONFIRMED", agent_id="issuer_agent_a",
                     platform_id="inaccurate", provenance="counterparty_confirmed", verification_status="finalized",
                     evidence_uri="ipfs://confirm", evidence_hash="0xconfirm", references=[attestation_id],
                     metadata={"type": "jobs_completed", "value": 10, "attestation_event_id": attestation_id})
    append_event(db, event_id="bad_claim", event_type="REPUTATION_ATTESTED", agent_id="issuer_agent_b",
                 platform_id="inaccurate", provenance="platform_reported", verification_status="uncontested",
                 evidence_uri="ipfs://bad", evidence_hash="0xbad", metadata={"type": "jobs_completed", "value": 50})
    append_event(db, event_id="bad_challenge", event_type="EVENT_CHALLENGED", agent_id="issuer_agent_b",
                 platform_id="inaccurate", provenance="challenged", verification_status="pending", references=["bad_claim"])
    append_event(db, event_id="bad_judgment", event_type="ATTESTATION_JUDGMENT_FINALIZED", agent_id="issuer_agent_b",
                 platform_id="inaccurate", provenance="genlayer_verified", verification_status="finalized",
                 references=["bad_claim", "bad_challenge"], metadata={"outcome": "attestation_false", "valid_value": 0})
    reliable = rebuild_platform_credibility(db, "reliable")
    inaccurate = rebuild_platform_credibility(db, "inaccurate")
    assert reliable.credibility_score == 85
    assert inaccurate.credibility_score == 26
    append_event(db, event_id="new_a", event_type="REPUTATION_ATTESTED", agent_id="candidate_a", platform_id="reliable",
                 provenance="platform_reported", verification_status="uncontested", evidence_uri="ipfs://new-a", evidence_hash="0xa",
                 metadata={"type": "jobs_completed", "value": 50, "issuer_credibility_bps": 8500,
                           "credibility_projection_version": "platform_credibility_v1"})
    append_event(db, event_id="new_b", event_type="REPUTATION_ATTESTED", agent_id="candidate_b", platform_id="inaccurate",
                 provenance="platform_reported", verification_status="uncontested", evidence_uri="ipfs://new-b", evidence_hash="0xb",
                 metadata={"type": "jobs_completed", "value": 50, "issuer_credibility_bps": 2600,
                           "credibility_projection_version": "platform_credibility_v1"})
    rep_a = projection_dict(rebuild_projection(db, "candidate_a", "research_trust_v3"))
    rep_b = projection_dict(rebuild_projection(db, "candidate_b", "research_trust_v3"))
    assert rep_a["trust_score"] == 77 and rep_b["trust_score"] == 73
    print("V2.2 passed: reliable=85 restricted=26 identical_claim_trust=77_vs_73")
