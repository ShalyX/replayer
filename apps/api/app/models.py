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
