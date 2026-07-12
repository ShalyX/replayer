from __future__ import annotations

from datetime import datetime
from typing import Iterable

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .models import (
    AgentReputationProjection,
    ProjectionVersion,
    ReputationEvent,
    ReputationEventReference,
    new_id,
)

PROJECTION_NAME = "research_trust"
PROJECTION_VERSION = "v1"
PROJECTION_ID = f"{PROJECTION_NAME}_{PROJECTION_VERSION}"

EVENT_TYPES = {
    "AGENT_REGISTERED", "JOB_CREATED", "DELIVERABLE_SUBMITTED", "JOB_ACCEPTED",
    "JOB_COMPLETED", "DISPUTE_OPENED", "JUDGMENT_PROVISIONAL", "JUDGMENT_FINALIZED",
    "FRAUD_CONFIRMED", "AGENT_CLEARED", "EVENT_ATTESTED", "EVENT_CHALLENGED",
    "EVENT_SUPERSEDED", "POLICY_EVALUATED",
}
PROVENANCE = {
    "platform_reported", "counterparty_confirmed", "genlayer_provisional",
    "genlayer_verified", "challenged", "superseded",
}
VERIFICATION_STATUSES = {"pending", "provisional", "finalized", "appealed", "superseded"}


def append_event(
    db: Session,
    *,
    event_type: str,
    agent_id: str,
    platform_id: str,
    provenance: str,
    verification_status: str,
    event_id: str | None = None,
    job_id: str | None = None,
    dispute_id: str | None = None,
    counterparty_id: str | None = None,
    category: str | None = None,
    evidence_uri: str | None = None,
    evidence_hash: str | None = None,
    references: Iterable[str] = (),
    contract_address: str | None = None,
    transaction_hash: str | None = None,
    block_number: int | None = None,
    occurred_at: datetime | None = None,
    metadata: dict | None = None,
) -> ReputationEvent:
    if event_type not in EVENT_TYPES:
        raise ValueError(f"Unsupported reputation event type: {event_type}")
    if provenance not in PROVENANCE:
        raise ValueError(f"Unsupported event provenance: {provenance}")
    if verification_status not in VERIFICATION_STATUSES:
        raise ValueError(f"Unsupported verification status: {verification_status}")
    event_id = event_id or new_id("rep_evt")
    existing = db.scalars(select(ReputationEvent).where(ReputationEvent.event_id == event_id)).first()
    if existing:
        return existing
    event = ReputationEvent(
        event_id=event_id,
        event_type=event_type,
        agent_id=agent_id,
        platform_id=platform_id,
        job_id=job_id,
        dispute_id=dispute_id,
        counterparty_id=counterparty_id,
        category=category,
        provenance=provenance,
        verification_status=verification_status,
        evidence_uri=evidence_uri,
        evidence_hash=evidence_hash,
        contract_address=contract_address,
        transaction_hash=transaction_hash,
        block_number=block_number,
        occurred_at=occurred_at or datetime.utcnow(),
        indexed_at=datetime.utcnow(),
        event_metadata=metadata or {},
    )
    db.add(event)
    db.flush()
    for referenced in references:
        db.add(ReputationEventReference(event_id=event_id, referenced_event_id=referenced))
    return event


def event_dict(db: Session, event: ReputationEvent) -> dict:
    references = db.scalars(
        select(ReputationEventReference).where(ReputationEventReference.event_id == event.event_id)
    ).all()
    return {
        "event_id": event.event_id,
        "event_type": event.event_type,
        "agent_id": event.agent_id,
        "platform_id": event.platform_id,
        "job_id": event.job_id,
        "dispute_id": event.dispute_id,
        "counterparty_id": event.counterparty_id,
        "category": event.category,
        "provenance": event.provenance,
        "verification_status": event.verification_status,
        "evidence_uri": event.evidence_uri,
        "evidence_hash": event.evidence_hash,
        "references": [item.referenced_event_id for item in references],
        "contract_address": event.contract_address,
        "transaction_hash": event.transaction_hash,
        "block_number": event.block_number,
        "occurred_at": event.occurred_at.isoformat(),
        "indexed_at": event.indexed_at.isoformat(),
        "metadata": event.event_metadata,
    }


def rebuild_projection(db: Session, agent_id: str) -> AgentReputationProjection:
    all_events = db.scalars(
        select(ReputationEvent)
        .where(ReputationEvent.agent_id == agent_id)
        .order_by(ReputationEvent.occurred_at, ReputationEvent.event_id)
    ).all()
    events = [
        event for event in all_events
        if not event.contract_address or event.event_metadata.get("contract_readback_verified") is True
    ]
    trust, risk = 70, 10
    completed = successful = disputes = fraud = 0
    counted_disputes: set[str] = set()
    verified_platforms: set[str] = set()
    last_finalized = None
    for event in events:
        if (
            event.dispute_id
            and event.dispute_id not in counted_disputes
            and event.event_type in {"DISPUTE_OPENED", "JUDGMENT_PROVISIONAL", "JUDGMENT_FINALIZED"}
        ):
            risk += 8
            disputes += 1
            counted_disputes.add(event.dispute_id)
        if event.event_type == "JOB_ACCEPTED":
            trust += 4
            completed += 1
            successful += 1
            verified_platforms.add(event.platform_id)
        elif event.event_type == "JOB_COMPLETED":
            completed += 1
        elif event.event_type == "JUDGMENT_FINALIZED" and event.provenance == "genlayer_verified":
            verdict = str(event.event_metadata.get("verdict", ""))
            last_finalized = event.event_id
            if verdict == "satisfied":
                trust += 5
                risk -= 5
            elif verdict == "partially_satisfied":
                trust -= 5
                risk += 8
            elif verdict == "failed":
                trust -= 15
                risk += 20
            elif verdict == "fraudulent":
                trust -= 30
                risk += 45
                fraud += 1
        elif event.event_type == "AGENT_CLEARED":
            trust += 10
            risk -= 20
    trust = max(0, min(100, trust))
    risk = max(0, min(100, risk))
    status = "flagged" if fraud or risk >= 60 else "review" if risk >= 35 else "active"
    projection = db.scalars(select(AgentReputationProjection).where(
        AgentReputationProjection.agent_id == agent_id,
        AgentReputationProjection.projection_name == PROJECTION_NAME,
        AgentReputationProjection.projection_version == PROJECTION_VERSION,
    )).first()
    if not projection:
        projection = AgentReputationProjection(
            agent_id=agent_id, projection_name=PROJECTION_NAME, projection_version=PROJECTION_VERSION
        )
        db.add(projection)
    projection.trust_score = trust
    projection.risk_score = risk
    projection.status = status
    projection.completed_jobs = completed
    projection.successful_jobs = successful
    projection.disputes = disputes
    projection.fraud_incidents = fraud
    projection.last_event_id = events[-1].event_id if events else None
    projection.calculated_at = datetime.utcnow()
    projection.details = {
        "verified_platforms": sorted(verified_platforms),
        "last_finalized_judgment_event_id": last_finalized,
        "event_count": len(events),
    }
    ensure_projection_version(db)
    db.flush()
    return projection


def rebuild_all_projections(db: Session) -> list[AgentReputationProjection]:
    agent_ids = db.scalars(select(ReputationEvent.agent_id).distinct()).all()
    db.execute(delete(AgentReputationProjection).where(
        AgentReputationProjection.projection_name == PROJECTION_NAME,
        AgentReputationProjection.projection_version == PROJECTION_VERSION,
    ))
    return [rebuild_projection(db, agent_id) for agent_id in agent_ids]


def ensure_projection_version(db: Session) -> None:
    existing = db.scalars(select(ProjectionVersion).where(
        ProjectionVersion.projection_name == PROJECTION_NAME,
        ProjectionVersion.version == PROJECTION_VERSION,
    )).first()
    if not existing:
        db.add(ProjectionVersion(
            projection_name=PROJECTION_NAME,
            version=PROJECTION_VERSION,
            configuration={
                "initial_trust": 70, "initial_risk": 10, "job_accepted_trust": 4,
                "fraudulent_trust": -30, "fraudulent_risk": 45,
            },
        ))


def projection_dict(projection: AgentReputationProjection) -> dict:
    success_rate = round((projection.successful_jobs / projection.completed_jobs) * 100, 2) if projection.completed_jobs else 0
    return {
        "agent_id": projection.agent_id,
        "projection": f"{projection.projection_name}_{projection.projection_version}",
        "projection_name": projection.projection_name,
        "projection_version": projection.projection_version,
        "trust_score": projection.trust_score,
        "overall": projection.trust_score,
        "risk_score": projection.risk_score,
        "status": projection.status,
        "completed_jobs": projection.completed_jobs,
        "successful_jobs": projection.successful_jobs,
        "success_rate": success_rate,
        "disputes": projection.disputes,
        "fraud_incidents": projection.fraud_incidents,
        "last_event_id": projection.last_event_id,
        "calculated_at": projection.calculated_at.isoformat(),
        "details": projection.details,
        "delivery_reliability": projection.successful_jobs,
        "research_accuracy": projection.trust_score,
        "citation_quality": max(0, projection.trust_score - projection.fraud_incidents * 10),
        "completion_rate": projection.completed_jobs,
        "dispute_count": projection.disputes,
        "valid_dispute_count": projection.fraud_incidents,
        "fraud_risk": projection.risk_score,
        "platform_verified_jobs": projection.successful_jobs,
        "genlayer_verified_jobs": projection.fraud_incidents,
    }
