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
};

export function ReputationPanel({ reputation }: { reputation: Reputation }) {
  const rows = [
    ["Status", reputation.status],
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
        <strong>{reputation.overall}</strong>
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
