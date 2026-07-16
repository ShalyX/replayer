from pydantic import BaseModel, Field


class PlatformRegister(BaseModel):
    platform_id: str | None = None
    platform_name: str
    owner_wallet: str = ""
    webhook_url: str = ""


class AgentRegister(BaseModel):
    agent_id: str | None = None
    platform_id: str
    agent_name: str
    owner_wallet: str = ""
    capabilities: list[str] = Field(default_factory=list)
    metadata_uri: str = ""


class JobCreate(BaseModel):
    job_id: str | None = None
    platform_id: str
    requester_id: str
    provider_agent_id: str
    task_spec: str
    category: str = "research"
    payment_amount: float = 0
    currency: str = "USDC"


class DeliverableSubmit(BaseModel):
    deliverable_id: str | None = None
    deliverable_uri: str
    summary: str = ""
    evidence_urls: list[str] = Field(default_factory=list)


class DisputeOpen(BaseModel):
    dispute_id: str | None = None
    claimant: str = "requester"
    reason: str
    evidence_uri: str = ""
    bond_amount: float = 0


class AppealSubmit(BaseModel):
    appellant_id: str = "agent_owner"
    reason: str
    evidence_uri: str
    evidence_hash: str = ""
    bond_amount: str = ""


class AttestationCreate(BaseModel):
    agent_id: str
    platform_id: str
    type: str
    value: int = Field(ge=1, le=10_000)
    category: str = "research"
    period_start: str
    period_end: str
    evidence_uri: str
    evidence_hash: str


class AttestationConfirm(BaseModel):
    platform_id: str
    value: int = Field(ge=1, le=10_000)
    counterparty_id: str = ""
    evidence_uri: str
    evidence_hash: str


class EventChallenge(BaseModel):
    challenger_id: str = "agent_owner"
    reason: str
    evidence_uri: str
    evidence_hash: str = ""


class PlatformIdentityVerify(BaseModel):
    agent_id: str
    evidence_uri: str
    evidence_hash: str


class AgentIdentityRegister(BaseModel):
    identity: str
    nonce: str = Field(min_length=8, max_length=160)
    signature: str
    evidence_uri: str = ""
    evidence_hash: str = ""


class IdentityBindingPropose(BaseModel):
    source_agent_id: str
    target_agent_id: str
    source_identity: str
    target_identity: str
    nonce: str = Field(min_length=8, max_length=160)
    source_signature: str
    evidence_uri: str = ""
    evidence_hash: str = ""


class IdentityBindingConfirm(BaseModel):
    target_signature: str
    evidence_uri: str = ""
    evidence_hash: str = ""


class IdentityBindingChallenge(BaseModel):
    challenger_agent_id: str
    reason: str
    evidence_uri: str
    evidence_hash: str = ""


class DelegationCreate(BaseModel):
    delegation_id: str | None = None
    principal_agent_id: str
    worker_agent_id: str
    platform_id: str
    job_id: str
    parent_delegation_id: str | None = None
    authority_scope: str = Field(min_length=10, max_length=5000)
    permitted_tools: list[str] = Field(default_factory=list)
    permitted_actions: list[str] = Field(default_factory=list)
    spending_limit: float = Field(default=0, ge=0)
    currency: str = "USDC"
    allow_subdelegation: bool = False
    disclosure_required: bool = True
    principal_signature: str
    evidence_uri: str
    evidence_hash: str


class DelegationAccept(BaseModel):
    worker_signature: str
    evidence_uri: str = ""
    evidence_hash: str = ""


class DelegatedOutputSubmit(BaseModel):
    output_uri: str
    summary: str = ""
    evidence_urls: list[str] = Field(default_factory=list)
    evidence_hash: str


class ResponsibilityDisputeOpen(BaseModel):
    claimant_id: str
    reason: str
    evidence_uri: str
    evidence_hash: str = ""


class ResponsibilityAppealSubmit(BaseModel):
    appellant_id: str
    reason: str
    evidence_uri: str
    evidence_hash: str = ""
    bond_amount: str = ""


class ReputationOut(BaseModel):
    agent_id: str
    overall: int
    delivery_reliability: int
    research_accuracy: int
    citation_quality: int
    completion_rate: int
    dispute_count: int
    valid_dispute_count: int
    fraud_risk: int
    platform_verified_jobs: int
    genlayer_verified_jobs: int
    status: str


class JudgmentOut(BaseModel):
    job_id: str
    verdict: str
    confidence_bps: int
    reasoning_summary: str
    score_deltas: dict
    source: str
    contract_address: str = ""
    tx_hash: str = ""
    verify_url: str = ""
    timestamp: str = ""


class TrustPolicy(BaseModel):
    min_trust_score: int = 70
    max_risk_score: int = 30
    max_fraud_incidents: int = 0
    allow_flagged: bool = False


class TrustEvaluateRequest(BaseModel):
    agent_id: str
    job_type: str = "research"
    job_value: float = 0
    policy: TrustPolicy | None = None
