from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from .database import Base


JsonType = JSON().with_variant(JSONB, "postgresql")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


class Platform(Base):
    __tablename__ = "platforms"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    owner_wallet: Mapped[str] = mapped_column(String(160), default="")
    webhook_url: Mapped[str] = mapped_column(Text, default="")
    api_key_hash: Mapped[str] = mapped_column(String(160), default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    platform_id: Mapped[str] = mapped_column(ForeignKey("platforms.id"), nullable=False)
    owner_wallet: Mapped[str] = mapped_column(String(160), default="")
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    capabilities: Mapped[list] = mapped_column(JsonType, default=list)
    metadata_uri: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    platform: Mapped[Platform] = relationship()


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    requester_id: Mapped[str] = mapped_column(String(120), nullable=False)
    provider_agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False)
    platform_id: Mapped[str] = mapped_column(ForeignKey("platforms.id"), nullable=False)
    task_spec: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(80), default="research")
    payment_amount: Mapped[float] = mapped_column(Numeric(18, 6), default=0)
    currency: Mapped[str] = mapped_column(String(20), default="USDC")
    status: Mapped[str] = mapped_column(String(60), default="created")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    agent: Mapped[Agent] = relationship()
    platform: Mapped[Platform] = relationship()


class Deliverable(Base):
    __tablename__ = "deliverables"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), unique=True, nullable=False)
    deliverable_uri: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="")
    evidence_urls: Mapped[list] = mapped_column(JsonType, default=list)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    job: Mapped[Job] = relationship()


class Dispute(Base):
    __tablename__ = "disputes"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), unique=True, nullable=False)
    claimant: Mapped[str] = mapped_column(String(80), default="requester")
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_uri: Mapped[str] = mapped_column(Text, default="")
    bond_amount: Mapped[float] = mapped_column(Numeric(18, 6), default=0)
    status: Mapped[str] = mapped_column(String(60), default="open")
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    job: Mapped[Job] = relationship()


class Judgment(Base):
    __tablename__ = "judgments"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), unique=True, nullable=False)
    dispute_id: Mapped[str] = mapped_column(ForeignKey("disputes.id"), nullable=False)
    verdict: Mapped[str] = mapped_column(String(60), nullable=False)
    confidence_bps: Mapped[int] = mapped_column(Integer, default=0)
    reasoning_summary: Mapped[str] = mapped_column(Text, default="")
    score_deltas: Mapped[dict] = mapped_column(JsonType, default=dict)
    source: Mapped[str] = mapped_column(String(40), default="mock")
    contract_address: Mapped[str] = mapped_column(String(80), default="")
    tx_hash: Mapped[str] = mapped_column(String(120), default="")
    verify_url: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    job: Mapped[Job] = relationship()
    dispute: Mapped[Dispute] = relationship()


class ReputationSnapshot(Base):
    __tablename__ = "reputation_snapshots"
    __table_args__ = (UniqueConstraint("agent_id", "job_id", "reason", name="uq_snapshot_event"),)

    id: Mapped[str] = mapped_column(String(80), primary_key=True, default=lambda: new_id("snap"))
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False)
    job_id: Mapped[str | None] = mapped_column(ForeignKey("jobs.id"), nullable=True)
    reason: Mapped[str] = mapped_column(String(80), default="manual")
    overall: Mapped[int] = mapped_column(Integer, default=70)
    delivery_reliability: Mapped[int] = mapped_column(Integer, default=0)
    research_accuracy: Mapped[int] = mapped_column(Integer, default=0)
    citation_quality: Mapped[int] = mapped_column(Integer, default=0)
    completion_rate: Mapped[int] = mapped_column(Integer, default=0)
    dispute_count: Mapped[int] = mapped_column(Integer, default=0)
    valid_dispute_count: Mapped[int] = mapped_column(Integer, default=0)
    fraud_risk: Mapped[int] = mapped_column(Integer, default=0)
    platform_verified_jobs: Mapped[int] = mapped_column(Integer, default=0)
    genlayer_verified_jobs: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(40), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    agent: Mapped[Agent] = relationship()
    job: Mapped[Job] = relationship()


class ReputationEvent(Base):
    __tablename__ = "reputation_events"

    id: Mapped[str] = mapped_column(String(80), primary_key=True, default=lambda: new_id("rep_evt_row"))
    event_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False, index=True)
    platform_id: Mapped[str] = mapped_column(ForeignKey("platforms.id"), nullable=False, index=True)
    job_id: Mapped[str | None] = mapped_column(ForeignKey("jobs.id"), nullable=True, index=True)
    dispute_id: Mapped[str | None] = mapped_column(ForeignKey("disputes.id"), nullable=True, index=True)
    counterparty_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    provenance: Mapped[str] = mapped_column(String(40), nullable=False)
    verification_status: Mapped[str] = mapped_column(String(40), nullable=False)
    evidence_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_hash: Mapped[str | None] = mapped_column(String(100), nullable=True)
    contract_address: Mapped[str | None] = mapped_column(String(80), nullable=True)
    transaction_hash: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    block_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    indexed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    event_metadata: Mapped[dict] = mapped_column("metadata", JsonType, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class ReputationEventReference(Base):
    __tablename__ = "reputation_event_references"
    __table_args__ = (UniqueConstraint("event_id", "referenced_event_id", "relationship_type", name="uq_event_reference"),)

    id: Mapped[str] = mapped_column(String(80), primary_key=True, default=lambda: new_id("rep_ref"))
    event_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    referenced_event_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    relationship_type: Mapped[str] = mapped_column(String(40), default="references")


class IndexerCheckpoint(Base):
    __tablename__ = "indexer_checkpoints"

    contract_address: Mapped[str] = mapped_column(String(80), primary_key=True)
    last_processed_block: Mapped[int] = mapped_column(Integer, default=0)
    last_processed_event_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ProjectionVersion(Base):
    __tablename__ = "projection_versions"
    __table_args__ = (UniqueConstraint("projection_name", "version", name="uq_projection_version"),)

    id: Mapped[str] = mapped_column(String(80), primary_key=True, default=lambda: new_id("projection_version"))
    projection_name: Mapped[str] = mapped_column(String(80), nullable=False)
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    configuration: Mapped[dict] = mapped_column(JsonType, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AgentReputationProjection(Base):
    __tablename__ = "agent_reputation_projections"
    __table_args__ = (UniqueConstraint("agent_id", "projection_name", "projection_version", name="uq_agent_projection"),)

    id: Mapped[str] = mapped_column(String(80), primary_key=True, default=lambda: new_id("projection"))
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False, index=True)
    projection_name: Mapped[str] = mapped_column(String(80), nullable=False)
    projection_version: Mapped[str] = mapped_column(String(40), nullable=False)
    trust_score: Mapped[int] = mapped_column(Integer, default=70)
    risk_score: Mapped[int] = mapped_column(Integer, default=10)
    status: Mapped[str] = mapped_column(String(40), default="active")
    completed_jobs: Mapped[int] = mapped_column(Integer, default=0)
    successful_jobs: Mapped[int] = mapped_column(Integer, default=0)
    disputes: Mapped[int] = mapped_column(Integer, default=0)
    fraud_incidents: Mapped[int] = mapped_column(Integer, default=0)
    last_event_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    calculated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    details: Mapped[dict] = mapped_column(JsonType, default=dict)


class DemoRun(Base):
    __tablename__ = "demo_runs"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    status: Mapped[str] = mapped_column(String(40), default="pending", index=True)
    result: Mapped[dict] = mapped_column(JsonType, default=dict)
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
