type Reputation = {
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
  trust_score?: number;
  risk_score?: number;
  projection_version?: string;
  calculated_at?: string;
  completed_jobs?: number;
  successful_jobs?: number;
  fraud_incidents?: number;
};

export function ReputationPanel({ reputation }: { reputation: Reputation }) {
  const rows = [
    ["Status", reputation.status],
    ["Risk Score", reputation.risk_score ?? reputation.fraud_risk],
    ["Projection", reputation.projection_version ?? "legacy"],
    ["Completed Jobs", reputation.completed_jobs ?? reputation.completion_rate],
    ["Successful Jobs", reputation.successful_jobs ?? reputation.platform_verified_jobs],
    ["Fraud Incidents", reputation.fraud_incidents ?? reputation.valid_dispute_count],
    ["Delivery", reputation.delivery_reliability],
    ["Completion", reputation.completion_rate],
    ["Research Accuracy", reputation.research_accuracy],
    ["Citation Quality", reputation.citation_quality],
    ["Disputes", reputation.dispute_count],
    ["Valid Disputes", reputation.valid_dispute_count],
    ["Fraud Risk", reputation.fraud_risk],
    ["Platform Jobs", reputation.platform_verified_jobs],
    ["GenLayer Jobs", reputation.genlayer_verified_jobs],
  ];

  return (
    <section className="panel">
      <h2>Reputation</h2>
      <div className="score">
        <strong>{reputation.trust_score ?? reputation.overall}</strong>
      </div>
      <div className="rows">
        {rows.map(([label, value]) => (
          <div className="row" key={label}>
            <span>{label}</span>
            <strong>{value}</strong>
          </div>
        ))}
      </div>
    </section>
  );
}
