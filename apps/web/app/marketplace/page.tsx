"use client";

import Link from "next/link";
import { useState } from "react";
import { api } from "../../lib/api";

type Assessment = {
  agent_id: string;
  trust_score: number;
  risk_score: number;
  fraud_incidents: number;
  status: string;
  recommendation: "low_risk" | "manual_review" | "high_risk";
  confidence: number;
  reasons: string[];
  policy_result: {
    evaluated: boolean;
    eligible: boolean | null;
    outcome: "eligible" | "ineligible";
    reasons: string[];
  };
};

const enterprisePolicy = {
  min_trust_score: 70,
  max_risk_score: 30,
  max_fraud_incidents: 0,
  allow_flagged: false,
};

const fallbackDeepResearch: Assessment = {
  agent_id: "deepresearchbot",
  trust_score: 42,
  risk_score: 87,
  fraud_incidents: 1,
  status: "flagged",
  recommendation: "high_risk",
  confidence: 0.94,
  reasons: ["Fraudulent judgment recorded on GenLayer", "Flagged status"],
  policy_result: {
    evaluated: true,
    eligible: false,
    outcome: "ineligible",
    reasons: ["Policy does not allow flagged agents", "Fraud incident count exceeds policy"],
  },
};

const researchPro: Assessment = {
  agent_id: "researchpro",
  trust_score: 91,
  risk_score: 8,
  fraud_incidents: 0,
  status: "verified",
  recommendation: "low_risk",
  confidence: 0.88,
  reasons: ["No material risk signals found"],
  policy_result: {
    evaluated: true,
    eligible: true,
    outcome: "eligible",
    reasons: [],
  },
};

export default function MarketplaceConsole() {
  const [deepResearch, setDeepResearch] = useState<Assessment>(fallbackDeepResearch);
  const [selected, setSelected] = useState("deepresearchbot");
  const [status, setStatus] = useState("EnterpriseAgents.io policy is ready.");

  async function evaluateDeepResearch() {
    setSelected("deepresearchbot");
    setStatus("EnterpriseAgents.io is checking portable reputation...");
    try {
      const storedAgent = window.localStorage.getItem("agent-reputation-registry:last-demo-agent") || "deepresearchbot";
      const result = await api<Assessment>("/trust/evaluate", {
        method: "POST",
        body: JSON.stringify({
          agent_id: storedAgent,
          job_type: "enterprise_research",
          job_value: 50000,
          policy: enterprisePolicy,
        }),
      });
      setDeepResearch(result);
      setStatus("EnterpriseAgents.io applied its own policy to Replayer risk signals.");
    } catch {
      setDeepResearch(fallbackDeepResearch);
      setStatus("Showing the seeded cross-marketplace simulation. Run the live demo first to evaluate the latest agent.");
    }
  }

  function chooseResearchPro() {
    setSelected("researchpro");
    setStatus("EnterpriseAgents.io policy allows ResearchPro for this job.");
  }

  const selectedAssessment = selected === "researchpro" ? researchPro : deepResearch;

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Marketplace Hiring Console</p>
          <h1>Reputation affects who gets hired.</h1>
        </div>
        <nav className="nav">
          <Link className="secondary" href="/">Dashboard</Link>
          <Link className="secondary" href="/integrations">SDK</Link>
        </nav>
      </header>

      <section className="policy-hero">
        <div>
          <p className="eyebrow">Cross-marketplace proof</p>
          <h2>ResearchAgents.io catches fraud. EnterpriseAgents.io sees the risk before hiring.</h2>
        </div>
        <div className="policy-card">
          <span>EnterpriseAgents.io policy</span>
          <strong>No flagged agents for enterprise research jobs.</strong>
          <p>Platforms define their own rules. Replayer supplies facts, evidence, judgments, and risk assessment.</p>
        </div>
      </section>

      <section className="marketplace-grid">
        <AgentCard
          active={selected === "deepresearchbot"}
          actionLabel="Evaluate policy"
          assessment={deepResearch}
          name="DeepResearchBot"
          onClick={evaluateDeepResearch}
          source="ResearchAgents.io"
        />
        <AgentCard
          active={selected === "researchpro"}
          actionLabel="Evaluate policy"
          assessment={researchPro}
          name="ResearchPro"
          onClick={chooseResearchPro}
          source="EnterpriseAgents.io"
        />
      </section>

      <section className="grid story-grid">
        <section className="panel">
          <h2>Replayer Risk Assessment</h2>
          <pre>{JSON.stringify({
            status: selectedAssessment.status,
            recommendation: selectedAssessment.recommendation,
            reasons: selectedAssessment.reasons,
          }, null, 2)}</pre>
        </section>
        <section className="panel">
          <h2>Marketplace Policy Result</h2>
          <div className={selectedAssessment.policy_result.eligible ? "policy-result eligible" : "policy-result ineligible"}>
            <span>Policy result</span>
            <strong>{selectedAssessment.policy_result.outcome}</strong>
            <p>{selectedAssessment.policy_result.reasons[0] || "Agent satisfies this marketplace policy."}</p>
          </div>
          <p className="policy-note">{status}</p>
        </section>
      </section>
    </main>
  );
}

function AgentCard({
  actionLabel,
  active,
  assessment,
  name,
  onClick,
  source,
}: {
  actionLabel: string;
  active: boolean;
  assessment: Assessment;
  name: string;
  onClick: () => void;
  source: string;
}) {
  return (
    <article className={active ? "market-agent active" : "market-agent"}>
      <div className="section-head">
        <div>
          <p className="eyebrow">{source}</p>
          <h2>{name}</h2>
        </div>
        <span className={assessment.status === "flagged" ? "pill bad" : "pill"}>{assessment.status}</span>
      </div>
      <div className="market-metrics">
        <div><span>Trust</span><strong>{assessment.trust_score}</strong></div>
        <div><span>Risk</span><strong>{assessment.risk_score}</strong></div>
        <div><span>Fraud</span><strong>{assessment.fraud_incidents}</strong></div>
      </div>
      <p>{assessment.reasons[0]}</p>
      <button type="button" onClick={onClick}>{actionLabel}</button>
    </article>
  );
}
