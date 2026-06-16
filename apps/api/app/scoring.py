from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Agent, Job, ReputationSnapshot, new_id


def verdict_deltas(verdict: str) -> dict[str, int]:
    if verdict == "satisfied":
        return {
            "delivery_reliability": 2,
            "research_accuracy": 2,
            "citation_quality": 2,
            "completion_rate": 1,
            "valid_dispute_count": 0,
            "fraud_risk": 0,
        }
    if verdict == "partially_satisfied":
        return {
            "delivery_reliability": 0,
            "research_accuracy": -1,
            "citation_quality": -1,
            "completion_rate": 1,
            "valid_dispute_count": 0,
            "fraud_risk": 0,
        }
    if verdict == "failed":
        return {
            "delivery_reliability": -3,
            "research_accuracy": -3,
            "citation_quality": -3,
            "completion_rate": 0,
            "valid_dispute_count": 1,
            "fraud_risk": 0,
        }
    if verdict == "fraudulent":
        return {
            "delivery_reliability": -5,
            "research_accuracy": -10,
            "citation_quality": -10,
            "completion_rate": 0,
            "valid_dispute_count": 1,
            "fraud_risk": 10,
        }
    return {
        "delivery_reliability": 0,
        "research_accuracy": 0,
        "citation_quality": 0,
        "completion_rate": 0,
        "valid_dispute_count": 0,
        "fraud_risk": 0,
    }


def compute_overall(snapshot: ReputationSnapshot) -> int:
    def n(value: int | None) -> int:
        return int(value or 0)

    score = (
        70
        + n(snapshot.delivery_reliability) * 4
        + n(snapshot.completion_rate) * 3
        + n(snapshot.research_accuracy) * 2
        + n(snapshot.citation_quality) * 2
        - n(snapshot.fraud_risk) * 8
        - n(snapshot.valid_dispute_count) * 5
    )
    return max(0, min(100, score))


def current_snapshot(db: Session, agent_id: str) -> ReputationSnapshot:
    snapshot = db.scalars(
        select(ReputationSnapshot)
        .where(ReputationSnapshot.agent_id == agent_id)
        .order_by(ReputationSnapshot.created_at.desc())
    ).first()
    if snapshot:
        return snapshot
    agent = db.get(Agent, agent_id)
    status = agent.status if agent else "unknown"
    snapshot = ReputationSnapshot(
        id=new_id("snap"),
        agent_id=agent_id,
        reason="initial",
        status=status,
        delivery_reliability=0,
        research_accuracy=0,
        citation_quality=0,
        completion_rate=0,
        dispute_count=0,
        valid_dispute_count=0,
        fraud_risk=0,
        platform_verified_jobs=0,
        genlayer_verified_jobs=0,
    )
    snapshot.overall = compute_overall(snapshot)
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot


def snapshot_dict(snapshot: ReputationSnapshot) -> dict:
    return {
        "agent_id": snapshot.agent_id,
        "overall": snapshot.overall,
        "delivery_reliability": snapshot.delivery_reliability,
        "research_accuracy": snapshot.research_accuracy,
        "citation_quality": snapshot.citation_quality,
        "completion_rate": snapshot.completion_rate,
        "dispute_count": snapshot.dispute_count,
        "valid_dispute_count": snapshot.valid_dispute_count,
        "fraud_risk": snapshot.fraud_risk,
        "platform_verified_jobs": snapshot.platform_verified_jobs,
        "genlayer_verified_jobs": snapshot.genlayer_verified_jobs,
        "status": snapshot.status,
    }


def apply_deltas(db: Session, agent_id: str, job_id: str | None, reason: str, deltas: dict[str, int]) -> ReputationSnapshot:
    prev = current_snapshot(db, agent_id)
    snapshot = ReputationSnapshot(
        id=new_id("snap"),
        agent_id=agent_id,
        job_id=job_id,
        reason=reason,
        delivery_reliability=prev.delivery_reliability + int(deltas.get("delivery_reliability", 0)),
        research_accuracy=prev.research_accuracy + int(deltas.get("research_accuracy", 0)),
        citation_quality=prev.citation_quality + int(deltas.get("citation_quality", 0)),
        completion_rate=prev.completion_rate + int(deltas.get("completion_rate", 0)),
        dispute_count=prev.dispute_count + int(deltas.get("dispute_count", 0)),
        valid_dispute_count=prev.valid_dispute_count + int(deltas.get("valid_dispute_count", 0)),
        fraud_risk=prev.fraud_risk + int(deltas.get("fraud_risk", 0)),
        platform_verified_jobs=prev.platform_verified_jobs + int(deltas.get("platform_verified_jobs", 0)),
        genlayer_verified_jobs=prev.genlayer_verified_jobs + int(deltas.get("genlayer_verified_jobs", 0)),
        status="flagged" if prev.fraud_risk + int(deltas.get("fraud_risk", 0)) >= 10 else prev.status,
    )
    snapshot.overall = compute_overall(snapshot)
    db.add(snapshot)
    agent = db.get(Agent, agent_id)
    if agent:
        agent.status = snapshot.status
    db.commit()
    db.refresh(snapshot)
    return snapshot


def score_acceptance(db: Session, job: Job) -> ReputationSnapshot:
    return apply_deltas(
        db,
        job.provider_agent_id,
        job.id,
        "accepted_job",
        {"delivery_reliability": 1, "completion_rate": 1, "platform_verified_jobs": 1},
    )


def mock_judgment(reason: str, summary: str) -> dict:
    text = f"{reason} {summary}".lower()
    if any(term in text for term in ["fabricated", "fake", "deception", "fraud"]):
        verdict = "fraudulent"
    elif any(term in text for term in ["wrong", "not series a", "failed", "irrelevant"]):
        verdict = "failed"
    elif any(term in text for term in ["weak", "incomplete", "partial", "missing"]):
        verdict = "partially_satisfied"
    else:
        verdict = "satisfied"
    return {
        "verdict": verdict,
        "confidence_bps": 8200,
        "reasoning_summary": "Deterministic mock evaluator matched dispute language and deliverable summary.",
        "score_deltas": verdict_deltas(verdict),
    }
