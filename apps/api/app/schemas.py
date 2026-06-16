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
