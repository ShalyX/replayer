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

export type PlatformRegisterInput = {
  platform_id?: string;
  platform_name: string;
  owner_wallet?: string;
  webhook_url?: string;
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

  registerPlatform(input: PlatformRegisterInput) {
    return this.request("/platforms/register", "POST", input);
  }

  registerAgent(input: AgentRegisterInput) {
    return this.request("/agents/register", "POST", input);
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

  getReputation(agentId: string): Promise<Reputation> {
    return this.request(`/agents/${encodeURIComponent(agentId)}/reputation`, "GET");
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
