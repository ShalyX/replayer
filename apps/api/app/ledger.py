from __future__ import annotations

from datetime import datetime
from math import sqrt
from typing import Iterable

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .models import (
    AgentReputationProjection,
    ProjectionVersion,
    PlatformCredibilityProjection,
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
    "EVENT_SUPERSEDED", "POLICY_EVALUATED", "REPUTATION_ATTESTED",
    "COUNTERPARTY_CONFIRMED", "ATTESTATION_JUDGMENT_FINALIZED", "PLATFORM_IDENTITY_VERIFIED",
}
PROVENANCE = {
    "platform_reported", "counterparty_confirmed", "genlayer_provisional",
    "genlayer_verified", "challenged", "superseded",
}
VERIFICATION_STATUSES = {"pending", "provisional", "finalized", "appealed", "superseded", "uncontested"}


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


def rebuild_projection(db: Session, agent_id: str, projection: str = "research_trust_v1") -> AgentReputationProjection:
    if projection == "research_trust_v3":
        return rebuild_projection_v3(db, agent_id)
    if projection == "research_trust_v2":
        return rebuild_projection_v2(db, agent_id)
    if projection != "research_trust_v1":
        raise ValueError(f"Unsupported projection: {projection}")
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
    projections = [rebuild_projection(db, agent_id) for agent_id in agent_ids]
    db.execute(delete(AgentReputationProjection).where(
        AgentReputationProjection.projection_name == "research_trust",
        AgentReputationProjection.projection_version == "v2",
    ))
    projections.extend(rebuild_projection_v2(db, agent_id) for agent_id in agent_ids)
    db.execute(delete(AgentReputationProjection).where(
        AgentReputationProjection.projection_name == "research_trust",
        AgentReputationProjection.projection_version == "v3",
    ))
    projections.extend(rebuild_projection_v3(db, agent_id) for agent_id in agent_ids)
    rebuild_all_platform_credibility(db)
    return projections


def rebuild_platform_credibility(db: Session, platform_id: str) -> PlatformCredibilityProjection:
    events = db.scalars(select(ReputationEvent).order_by(ReputationEvent.occurred_at, ReputationEvent.event_id)).all()
    by_id = {event.event_id: event for event in events}
    references = db.scalars(select(ReputationEventReference)).all()
    refs_by_event: dict[str, list[str]] = {}
    for reference in references:
        refs_by_event.setdefault(reference.event_id, []).append(reference.referenced_event_id)
    issued = [event for event in events if event.platform_id == platform_id and event.event_type == "REPUTATION_ATTESTED" and event.provenance == "platform_reported"]
    issued_ids = {event.event_id for event in issued}
    confirmation_events = [
        event for event in events if event.event_type == "COUNTERPARTY_CONFIRMED"
        and any(reference in issued_ids for reference in refs_by_event.get(event.event_id, []))
    ]
    confirmations = len(confirmation_events)
    judgments = [
        event for event in events if event.event_type == "ATTESTATION_JUDGMENT_FINALIZED"
        and any(reference in issued_ids for reference in refs_by_event.get(event.event_id, []))
    ]
    challenges = len(judgments)
    partial = sum(event.event_metadata.get("outcome") == "attestation_partially_valid" for event in judgments)
    false = sum(event.event_metadata.get("outcome") == "attestation_false" for event in judgments)
    valid = sum(event.event_metadata.get("outcome") == "attestation_valid" for event in judgments)
    inconclusive = sum(event.event_metadata.get("outcome") == "inconclusive" for event in judgments)
    verified_identity_events = [
        event for event in events if event.platform_id == platform_id and event.event_type == "PLATFORM_IDENTITY_VERIFIED"
        and event.verification_status == "finalized"
    ]
    verified_identity = bool(verified_identity_events)
    score = 50 + (15 if verified_identity else 0)
    score += min(10, len(issued))
    score += min(15, confirmations * 3)
    score += valid * 5
    score -= challenges * 2 + partial * 10 + false * 23 + inconclusive * 3
    score = max(0, min(100, score))
    overturns = partial + false
    status = "trusted" if score >= 75 else "established" if score >= 60 else "restricted" if score < 35 else "developing"
    row = db.scalars(select(PlatformCredibilityProjection).where(
        PlatformCredibilityProjection.platform_id == platform_id,
        PlatformCredibilityProjection.projection_version == "v1",
    )).first()
    if not row:
        row = PlatformCredibilityProjection(platform_id=platform_id, projection_version="v1")
        db.add(row)
    row.credibility_score = score
    row.status = status
    row.attestations_issued = len(issued)
    row.confirmations_received = confirmations
    row.challenges = challenges
    row.overturns = overturns
    row.verified_identity = verified_identity
    relevant_events = issued + confirmation_events + judgments + verified_identity_events
    row.last_event_id = relevant_events[-1].event_id if relevant_events else None
    row.calculated_at = datetime.utcnow()
    row.details = {
        "valid_judgments": valid, "partial_overturns": partial, "false_attestations": false,
        "inconclusive_judgments": inconclusive,
        "challenge_overturn_rate": round(overturns / challenges, 4) if challenges else 0,
        "credibility_bps": score * 100,
        "contribution_cap": max(1, min(8, 2 + (score * 6 // 100))),
    }
    ensure_platform_projection_version(db)
    db.flush()
    return row


def rebuild_all_platform_credibility(db: Session) -> list[PlatformCredibilityProjection]:
    platform_ids = db.scalars(select(ReputationEvent.platform_id).distinct()).all()
    db.execute(delete(PlatformCredibilityProjection).where(PlatformCredibilityProjection.projection_version == "v1"))
    return [rebuild_platform_credibility(db, platform_id) for platform_id in platform_ids]


def ensure_platform_projection_version(db: Session) -> None:
    existing = db.scalars(select(ProjectionVersion).where(
        ProjectionVersion.projection_name == "platform_credibility", ProjectionVersion.version == "v1"
    )).first()
    if not existing:
        db.add(ProjectionVersion(projection_name="platform_credibility", version="v1", configuration={
            "initial_score": 50, "verified_identity": 15, "confirmation": 3,
            "partial_overturn": -12, "false_attestation": -25,
            "historical_weighting": "snapshot_at_attestation_creation",
        }))


def rebuild_projection_v2(db: Session, agent_id: str) -> AgentReputationProjection:
    events = db.scalars(
        select(ReputationEvent)
        .where(ReputationEvent.agent_id == agent_id)
        .order_by(ReputationEvent.occurred_at, ReputationEvent.event_id)
    ).all()
    events = [event for event in events if not event.contract_address or event.event_metadata.get("contract_readback_verified") is True]
    superseded = {
        reference.referenced_event_id
        for reference in db.scalars(select(ReputationEventReference).where(
            ReputationEventReference.event_id.in_([event.event_id for event in events if event.event_type == "EVENT_SUPERSEDED"])
        )).all()
    }
    challenged = {
        reference.referenced_event_id
        for reference in db.scalars(select(ReputationEventReference).where(
            ReputationEventReference.event_id.in_([event.event_id for event in events if event.event_type == "EVENT_CHALLENGED"])
        )).all()
    }

    base = rebuild_projection(db, agent_id, "research_trust_v1")
    trust = base.trust_score
    work_history = []
    for event in events:
        if event.event_type not in {"REPUTATION_ATTESTED", "COUNTERPARTY_CONFIRMED"}:
            continue
        metadata = event.event_metadata
        value = max(0, min(10_000, int(metadata.get("value") or 0)))
        target = str(metadata.get("attestation_event_id") or event.event_id)
        is_superseded = event.event_id in superseded or target in superseded
        is_challenged = event.event_id in challenged or target in challenged
        contribution = 0
        if not is_superseded and metadata.get("type") == "jobs_completed" and event.evidence_uri and event.evidence_hash:
            diminishing = min(6, int(sqrt(value)))
            if event.provenance == "genlayer_verified":
                contribution = min(10, diminishing + 3)
            elif event.provenance == "counterparty_confirmed":
                contribution = min(5, diminishing)
            else:
                contribution = min(6, diminishing)
            if is_challenged:
                contribution //= 2
        trust += contribution
        work_history.append({
            "event_id": event.event_id,
            "type": metadata.get("type"),
            "value": value,
            "platform_id": event.platform_id,
            "provenance": "superseded" if is_superseded else event.provenance,
            "verification_status": "superseded" if is_superseded else event.verification_status,
            "contribution": contribution,
            "references": [target] if target != event.event_id else [],
        })
    trust = max(0, min(100, trust))
    projection_row = db.scalars(select(AgentReputationProjection).where(
        AgentReputationProjection.agent_id == agent_id,
        AgentReputationProjection.projection_name == "research_trust",
        AgentReputationProjection.projection_version == "v2",
    )).first()
    if not projection_row:
        projection_row = AgentReputationProjection(agent_id=agent_id, projection_name="research_trust", projection_version="v2")
        db.add(projection_row)
    projection_row.trust_score = trust
    projection_row.risk_score = base.risk_score
    projection_row.status = base.status
    projection_row.completed_jobs = base.completed_jobs
    projection_row.successful_jobs = base.successful_jobs
    projection_row.disputes = base.disputes
    projection_row.fraud_incidents = base.fraud_incidents
    projection_row.last_event_id = events[-1].event_id if events else None
    projection_row.calculated_at = datetime.utcnow()
    projection_row.details = {**base.details, "verified_work_history": work_history, "attestation_projection": True}
    ensure_projection_version_v2(db)
    db.flush()
    return projection_row


def ensure_projection_version_v2(db: Session) -> None:
    existing = db.scalars(select(ProjectionVersion).where(
        ProjectionVersion.projection_name == "research_trust", ProjectionVersion.version == "v2"
    )).first()
    if not existing:
        db.add(ProjectionVersion(
            projection_name="research_trust", version="v2", configuration={
                "attestation_type": "jobs_completed", "reported_cap": 6,
                "confirmed_cap": 5, "genlayer_verified_cap": 10,
                "requires_evidence_uri": True, "requires_evidence_hash": True,
                "diminishing_returns": "floor(sqrt(value))", "superseded_weight": 0,
            },
        ))


def rebuild_projection_v3(db: Session, agent_id: str) -> AgentReputationProjection:
    events = db.scalars(
        select(ReputationEvent).where(ReputationEvent.agent_id == agent_id)
        .order_by(ReputationEvent.occurred_at, ReputationEvent.event_id)
    ).all()
    events = [event for event in events if not event.contract_address or event.event_metadata.get("contract_readback_verified") is True]
    event_ids = [event.event_id for event in events]
    references = db.scalars(select(ReputationEventReference).where(ReputationEventReference.event_id.in_(event_ids))).all()
    refs_by_event: dict[str, list[str]] = {}
    for reference in references:
        refs_by_event.setdefault(reference.event_id, []).append(reference.referenced_event_id)
    superseded = {
        reference for event in events if event.event_type == "EVENT_SUPERSEDED"
        for reference in refs_by_event.get(event.event_id, [])
    }
    challenged = {
        reference for event in events if event.event_type == "EVENT_CHALLENGED"
        for reference in refs_by_event.get(event.event_id, [])
    }
    base = rebuild_projection(db, agent_id, "research_trust_v1")
    trust = base.trust_score
    work_history = []
    for event in events:
        if event.event_type not in {"REPUTATION_ATTESTED", "COUNTERPARTY_CONFIRMED"}:
            continue
        metadata = event.event_metadata
        value = max(0, min(10_000, int(metadata.get("value") or 0)))
        target = str(metadata.get("attestation_event_id") or event.event_id)
        is_superseded = event.event_id in superseded or target in superseded
        is_challenged = event.event_id in challenged or target in challenged
        credibility_bps = max(0, min(10_000, int(metadata.get("issuer_credibility_bps") or 5000)))
        contribution = 0
        if not is_superseded and metadata.get("type") == "jobs_completed" and event.evidence_uri and event.evidence_hash:
            diminishing = min(10, int(sqrt(value)))
            if event.provenance == "genlayer_verified":
                cap = 10
                contribution = min(cap, diminishing + 3)
            elif event.provenance == "counterparty_confirmed":
                cap = max(1, min(6, 1 + credibility_bps * 5 // 10_000))
                contribution = min(cap, diminishing)
            else:
                cap = max(1, min(8, 2 + credibility_bps * 6 // 10_000))
                contribution = min(cap, diminishing)
            if is_challenged:
                contribution //= 2
        trust += contribution
        work_history.append({
            "event_id": event.event_id, "type": metadata.get("type"), "value": value,
            "platform_id": event.platform_id,
            "provenance": "superseded" if is_superseded else event.provenance,
            "verification_status": "superseded" if is_superseded else event.verification_status,
            "contribution": contribution, "issuer_credibility_bps": credibility_bps,
            "credibility_projection_version": metadata.get("credibility_projection_version") or "platform_credibility_v1",
            "references": refs_by_event.get(event.event_id, []),
        })
    trust = max(0, min(100, trust))
    row = db.scalars(select(AgentReputationProjection).where(
        AgentReputationProjection.agent_id == agent_id,
        AgentReputationProjection.projection_name == "research_trust",
        AgentReputationProjection.projection_version == "v3",
    )).first()
    if not row:
        row = AgentReputationProjection(agent_id=agent_id, projection_name="research_trust", projection_version="v3")
        db.add(row)
    row.trust_score = trust
    row.risk_score = base.risk_score
    row.status = base.status
    row.completed_jobs = base.completed_jobs
    row.successful_jobs = base.successful_jobs
    row.disputes = base.disputes
    row.fraud_incidents = base.fraud_incidents
    row.last_event_id = events[-1].event_id if events else None
    row.calculated_at = datetime.utcnow()
    row.details = {**base.details, "verified_work_history": work_history, "platform_weighted": True}
    ensure_projection_version_v3(db)
    db.flush()
    return row


def ensure_projection_version_v3(db: Session) -> None:
    existing = db.scalars(select(ProjectionVersion).where(
        ProjectionVersion.projection_name == "research_trust", ProjectionVersion.version == "v3"
    )).first()
    if not existing:
        db.add(ProjectionVersion(projection_name="research_trust", version="v3", configuration={
            "platform_credibility_projection": "platform_credibility_v1",
            "weighting": "snapshot", "reported_cap_range": [1, 8],
            "confirmed_cap_range": [1, 6], "genlayer_verified_cap": 10,
        }))


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
