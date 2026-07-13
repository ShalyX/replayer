export type Reputation = {
  agent_id: string;
  overall: number;
  delivery_reliability: number;
  research_accuracy: number;
  citation_quality: number;
  completion_rate: number;
  dispute_count: number;
  valid_dispute_count: number;
  fraud_risk: number;
  platform_verified_jobs: number;
  genlayer_verified_jobs: number;
  status: string;
};

export type EventProvenance = "platform_reported" | "counterparty_confirmed" | "genlayer_provisional" | "genlayer_verified" | "challenged" | "superseded";
export type VerificationStatus = "pending" | "provisional" | "finalized" | "appealed" | "superseded" | "uncontested";

export type AgentIdentityProjection = {
  agent_id: string;
  canonical_agent_id: string;
  projection: "agent_identity_v1";
  projection_version: "v1";
  status: "unlinked" | "verified" | "linked";
  linked_agents: string[];
  aliases: string[];
  controllers: string[];
  last_event_id: string | null;
  calculated_at: string;
  details: Record<string, unknown>;
};

export type AgentIdentityRegistrationInput = {
  identity: string;
  nonce: string;
  signature: string;
  evidence_uri?: string;
  evidence_hash?: string;
};

export type IdentityBindingProposalInput = {
  source_agent_id: string;
  target_agent_id: string;
  source_identity: string;
  target_identity: string;
  nonce: string;
  source_signature: string;
  evidence_uri?: string;
  evidence_hash?: string;
};

export type IdentityBindingConfirmationInput = {
  target_signature: string;
  evidence_uri?: string;
  evidence_hash?: string;
};

export type IdentityBindingChallengeInput = {
  challenger_agent_id: string;
  reason: string;
  evidence_uri: string;
  evidence_hash?: string;
};

export type AttestationInput = {
  agent_id: string;
  platform_id: string;
  type: "jobs_completed";
  value: number;
  category?: string;
  period_start: string;
  period_end: string;
  evidence_uri: string;
  evidence_hash: string;
};

export type AttestationConfirmationInput = {
  platform_id: string;
  value: number;
  counterparty_id?: string;
  evidence_uri: string;
  evidence_hash: string;
};

export type EventChallengeInput = {
  challenger_id?: string;
  reason: string;
  evidence_uri: string;
  evidence_hash?: string;
};

export type ReputationEvent = {
  event_id: string;
  event_type: string;
  agent_id: string;
  platform_id: string;
  job_id: string | null;
  dispute_id: string | null;
  counterparty_id: string | null;
  category: string | null;
  provenance: EventProvenance;
  verification_status: VerificationStatus;
  evidence_uri: string | null;
  evidence_hash: string | null;
  references: string[];
  contract_address: string | null;
  transaction_hash: string | null;
  block_number: number | null;
  occurred_at: string;
  indexed_at: string;
  metadata: Record<string, unknown>;
};

export type ReputationProjection = {
  agent_id: string;
  projection: string;
  projection_version: string;
  trust_score: number;
  risk_score: number;
  status: string;
  completed_jobs: number;
  successful_jobs: number;
  disputes: number;
  fraud_incidents: number;
  calculated_at: string;
};

export type GenLayerJudgment = Judgment & {
  source: "genlayer";
  contract_address: string;
  tx_hash: string;
};

export type Judgment = {
  id: string;
  job_id: string;
  dispute_id: string;
  verdict: string;
  confidence_bps: number;
  reasoning_summary: string;
  score_deltas: Record<string, number>;
  source: string;
  contract_address: string;
  tx_hash: string;
  verify_url: string;
  timestamp: string;
};

export type Job = {
  id: string;
  platform_id: string;
  requester_id: string;
  provider_agent_id: string;
  task_spec: string;
  category: string;
  payment_amount: number;
  currency: string;
  status: string;
};

export type Deliverable = {
  id: string;
  job_id: string;
  deliverable_uri: string;
  summary: string;
  evidence_urls: string[];
};

export type Dispute = {
  id: string;
  job_id: string;
  claimant: string;
  reason: string;
  evidence_uri: string;
  bond_amount: number;
  status: string;
};

export type TimelineEvidence = {
  job?: Job;
  deliverable?: Deliverable;
  dispute?: Dispute;
  judgment?: Judgment;
  policy?: {
    platform: string;
    result: string;
    reason: string;
  };
};

export type PlatformRegisterInput = {
  platform_id?: string;
  platform_name: string;
  owner_wallet?: string;
  webhook_url?: string;
};

export type Platform = {
  id: string;
  name: string;
  owner_wallet: string;
  webhook_url: string;
};

export type PlatformRegisterResult = {
  platform: Platform;
  api_key: string;
  api_key_warning: string;
  tx: unknown;
};

export type PlatformApiKeyResult = {
  platform: Platform;
  api_key: string;
  api_key_warning: string;
};

export type PlatformCredibility = {
  platform_id: string;
  projection: "platform_credibility_v1";
  credibility_score: number;
  credibility_bps: number;
  status: "trusted" | "established" | "developing" | "restricted";
  attestations_issued: number;
  confirmations_received: number;
  challenges: number;
  overturns: number;
  verified_identity: boolean;
  calculated_at: string;
  details: Record<string, unknown>;
};

export type AgentRegisterInput = {
  agent_id?: string;
  platform_id: string;
  agent_name: string;
  owner_wallet?: string;
  capabilities?: string[];
  metadata_uri?: string;
};

export type JobCreateInput = {
  job_id?: string;
  platform_id: string;
  requester_id: string;
  provider_agent_id: string;
  task_spec: string;
  category?: string;
  payment_amount?: number;
  currency?: string;
};

export type DeliverableInput = {
  deliverable_id?: string;
  deliverable_uri: string;
  summary?: string;
  evidence_urls?: string[];
};

export type DisputeInput = {
  dispute_id?: string;
  claimant?: string;
  reason: string;
  evidence_uri?: string;
  bond_amount?: number;
};

export type AppealInput = {
  appellant_id?: string;
  reason: string;
  evidence_uri: string;
  evidence_hash?: string;
  bond_amount?: string;
};

export type JudgmentLifecycleEvent = {
  event_id: string;
  event_type: "JUDGMENT_PROVISIONAL" | "APPEAL_SUBMITTED" | "APPEAL_RESOLVED" | "JUDGMENT_UPHELD" | "JUDGMENT_OVERTURNED" | "JUDGMENT_FINALIZED" | "EVENT_SUPERSEDED";
  dispute_id: string;
  verdict?: string;
  verification_status: VerificationStatus;
  provenance: EventProvenance;
  transaction_hash?: string;
  contract_address?: string;
  references: string[];
  occurred_at: string;
};

export type TrustPolicy = {
  min_trust_score?: number;
  max_risk_score?: number;
  max_fraud_incidents?: number;
  allow_flagged?: boolean;
};

export type TrustEvaluateInput = {
  agent_id: string;
  job_type?: string;
  job_value?: number;
  policy?: TrustPolicy;
};

export type ReputationTimelineEvent = {
  id: string;
  type: string;
  date: string;
  timestamp: string;
  marker: string;
  title: string;
  detail: string;
  severity: "neutral" | "success" | "warning" | "danger";
  verify_url: string;
  evidence: TimelineEvidence;
};

export type TrustEvaluation = {
  agent_id: string;
  job_type: string;
  job_value: number;
  trust_score: number;
  risk_score: number;
  fraud_incidents: number;
  status: string;
  recommendation: "low_risk" | "manual_review" | "high_risk";
  confidence: number;
  reasons: string[];
  latest_judgment: Judgment | null;
  timeline: ReputationTimelineEvent[];
  policy_result: {
    evaluated: boolean;
    eligible: boolean | null;
    outcome: "eligible" | "ineligible";
    reasons: string[];
    policy: TrustPolicy | null;
  };
};

export class AgentReputationClient {
  private readonly baseUrl: string;
  private readonly apiKey?: string;

  constructor({ baseUrl, apiKey }: { baseUrl: string; apiKey?: string }) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
    this.apiKey = apiKey;
  }

  registerPlatform(input: PlatformRegisterInput): Promise<PlatformRegisterResult> {
    return this.request("/platforms/register", "POST", input);
  }

  rotatePlatformApiKey(platformId: string): Promise<PlatformApiKeyResult> {
    return this.request(`/platforms/${encodeURIComponent(platformId)}/api-key`, "POST", {});
  }

  getPlatformCredibility(platformId: string): Promise<PlatformCredibility> {
    return this.request(`/platforms/${encodeURIComponent(platformId)}/credibility`, "GET");
  }

  verifyPlatformIdentity(platformId: string, input: { agent_id: string; evidence_uri: string; evidence_hash: string }) {
    return this.request(`/platforms/${encodeURIComponent(platformId)}/verify-identity`, "POST", input);
  }

  checkAuth(): Promise<{ ok: boolean; type: "admin" | "platform"; platform_id: string | null }> {
    return this.request("/auth/check", "GET");
  }

  registerAgent(input: AgentRegisterInput) {
    return this.request("/agents/register", "POST", input);
  }

  registerAgentIdentity(agentId: string, input: AgentIdentityRegistrationInput) {
    return this.request(`/agents/${encodeURIComponent(agentId)}/identities`, "POST", input);
  }

  proposeIdentityBinding(input: IdentityBindingProposalInput) {
    return this.request("/identity-bindings", "POST", input);
  }

  confirmIdentityBinding(proposalEventId: string, input: IdentityBindingConfirmationInput) {
    return this.request(`/identity-bindings/${encodeURIComponent(proposalEventId)}/confirm`, "POST", input);
  }

  challengeIdentityBinding(proposalEventId: string, input: IdentityBindingChallengeInput) {
    return this.request(`/identity-bindings/${encodeURIComponent(proposalEventId)}/challenge`, "POST", input);
  }

  getAgentIdentity(agentId: string): Promise<AgentIdentityProjection> {
    return this.request(`/agents/${encodeURIComponent(agentId)}/identity`, "GET");
  }

  resolveIdentity(identity: string): Promise<{ identity: AgentIdentityProjection; reputation: ReputationProjection; passport_url: string }> {
    return this.request(`/identities/resolve?identity=${encodeURIComponent(identity)}`, "GET");
  }

  createJob(input: JobCreateInput) {
    return this.request("/jobs", "POST", input);
  }

  submitDeliverable(jobId: string, input: DeliverableInput) {
    return this.request(`/jobs/${encodeURIComponent(jobId)}/deliverable`, "POST", input);
  }

  openDispute(jobId: string, input: DisputeInput) {
    return this.request(`/jobs/${encodeURIComponent(jobId)}/dispute`, "POST", input);
  }

  acceptJob(jobId: string) {
    return this.request(`/jobs/${encodeURIComponent(jobId)}/accept`, "POST", {});
  }

  evaluateJob(jobId: string) {
    return this.request(`/jobs/${encodeURIComponent(jobId)}/evaluate`, "POST", {});
  }

  appealJob(jobId: string, input: AppealInput) {
    return this.request(`/jobs/${encodeURIComponent(jobId)}/appeal`, "POST", input);
  }

  resolveJobAppeal(jobId: string) {
    return this.request(`/jobs/${encodeURIComponent(jobId)}/appeal/resolve`, "POST", {});
  }

  createAttestation(input: AttestationInput) {
    return this.request("/attestations", "POST", input);
  }

  confirmAttestation(eventId: string, input: AttestationConfirmationInput) {
    return this.request(`/attestations/${encodeURIComponent(eventId)}/confirm`, "POST", input);
  }

  challengeEvent(eventId: string, input: EventChallengeInput) {
    return this.request(`/events/${encodeURIComponent(eventId)}/challenge`, "POST", input);
  }

  getReputation(agentId: string): Promise<Reputation> {
    return this.request(`/agents/${encodeURIComponent(agentId)}/reputation?projection=research_trust_v5`, "GET");
  }

  getAgentEvents(agentId: string, options: { limit?: number } = {}): Promise<{ agent_id: string; events: ReputationEvent[] }> {
    const limit = options.limit ?? 100;
    return this.request(`/agents/${encodeURIComponent(agentId)}/events?limit=${limit}`, "GET");
  }

  getReputationEvent(eventId: string): Promise<ReputationEvent> {
    return this.request(`/events/${encodeURIComponent(eventId)}`, "GET");
  }

  getAgentReputation(agentId: string, projection = "research_trust_v5"): Promise<ReputationProjection> {
    return this.request(`/agents/${encodeURIComponent(agentId)}/reputation?projection=${encodeURIComponent(projection)}`, "GET");
  }

  getIndexerHealth(): Promise<{ status: string; contract_address: string; last_processed_block: number; last_sync_at: string | null; lag: number }> {
    return this.request("/health/indexer", "GET");
  }

  evaluateTrust(input: TrustEvaluateInput): Promise<TrustEvaluation> {
    return this.request("/trust/evaluate", "POST", input);
  }

  getHistory(agentId: string) {
    return this.request(`/agents/${encodeURIComponent(agentId)}/history`, "GET");
  }

  listPlatformAgents(platformId: string) {
    return this.request(`/platforms/${encodeURIComponent(platformId)}/agents`, "GET");
  }

  private async request(path: string, method: string, body?: unknown) {
    const response = await fetch(`${this.baseUrl}${path}`, {
      method,
      headers: {
        "content-type": "application/json",
        ...(this.apiKey ? { "x-api-key": this.apiKey } : {}),
      },
      body: method === "GET" ? undefined : JSON.stringify(body ?? {}),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || data.error || "Agent Reputation API request failed");
    }
    return data;
  }
}
