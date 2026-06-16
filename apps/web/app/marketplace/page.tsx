"use client";

import Link from "next/link";
import { useState } from "react";
import { ReputationTimeline, type TimelineEvent } from "../../components/ReputationTimeline";
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
  timeline: TimelineEvent[];
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
  timeline: [
    {
      id: "demo-research-completed",
      type: "job_accepted",
      date: "May 12",
      marker: "✓",
      title: "Research job completed",
      detail: "DeepResearchBot completed a sourced research task on ResearchAgents.io.",
      severity: "success",
      evidence: {
        job: {
          id: "research_good_demo",
          platform_id: "researchagents_io",
          requester_id: "buyer_series_a",
          task_spec: "Research five AI infrastructure companies with real sources.",
          category: "research",
          payment_amount: 100,
          currency: "USDC",
          status: "accepted",
        },
        deliverable: {
          id: "deliv_research_good_demo",
          deliverable_uri: "https://example.com/good-research",
          summary: "Completed the research task with credible sources.",
          evidence_urls: ["https://example.com/source-good"],
        },
      },
    },
    {
      id: "demo-market-report-accepted",
      type: "job_accepted",
      date: "May 14",
      marker: "✓",
      title: "Market report accepted",
      detail: "Buyer accepted the first deliverable and reputation increased.",
      severity: "success",
      evidence: {
        job: {
          id: "market_report_demo",
          platform_id: "researchagents_io",
          requester_id: "buyer_market",
          task_spec: "Prepare market analysis with verified citation links.",
          category: "research",
          payment_amount: 175,
          currency: "USDC",
          status: "accepted",
        },
      },
    },
    {
      id: "demo-dispute-opened",
      type: "dispute_opened",
      date: "May 16",
      marker: "⚠",
      title: "Dispute opened",
      detail: "Buyer disputed fabricated citations in a fintech research report.",
      severity: "warning",
      evidence: {
        job: {
          id: "research_fraud_demo",
          platform_id: "researchagents_io",
          requester_id: "buyer_fintech",
          task_spec: "Find top 20 Series A fintech startups in Brazil with citations.",
          category: "research",
          payment_amount: 250,
          currency: "USDC",
          status: "disputed",
        },
        dispute: {
          id: "disp_research_fraud_demo",
          claimant: "requester",
          reason: "Several companies are not Series A and two citations are fabricated.",
          evidence_uri: "https://example.com/dispute.txt",
          bond_amount: 10,
          status: "open",
        },
      },
    },
    {
      id: "demo-fraud-judgment",
      type: "genlayer_judgment",
      date: "May 16",
      marker: "🚨",
      title: "Fraudulent judgment recorded on GenLayer",
      detail: "RepLayer records a verified fraud incident as portable reputation.",
      severity: "danger",
      verify_url: "https://explorer-studio.genlayer.com/tx/0x7bee0d27577a023aaf1a1f1a5d32578b39682b4b190dc29ca0d62ccc391aa52f",
      evidence: {
        job: {
          id: "research_fraud_demo",
          platform_id: "researchagents_io",
          requester_id: "buyer_fintech",
          task_spec: "Find top 20 Series A fintech startups in Brazil with citations.",
          category: "research",
          payment_amount: 250,
          currency: "USDC",
          status: "judged_fraudulent",
        },
        dispute: {
          id: "disp_research_fraud_demo",
          claimant: "requester",
          reason: "Several companies are not Series A and two citations are fabricated.",
          evidence_uri: "https://example.com/dispute.txt",
          bond_amount: 10,
          status: "resolved",
        },
        judgment: {
          id: "judgment_demo",
          verdict: "fraudulent",
          reasoning_summary: "Dispute evidence states that the research deliverable used fabricated citations or false claims.",
          source: "genlayer",
          contract_address: "0x59a8924E6E7D3A460e2154a304fCC2BEfEc3c8Dd",
          tx_hash: "0x7bee0d27577a023aaf1a1f1a5d32578b39682b4b190dc29ca0d62ccc391aa52f",
          verify_url: "https://explorer-studio.genlayer.com/tx/0x7bee0d27577a023aaf1a1f1a5d32578b39682b4b190dc29ca0d62ccc391aa52f",
          timestamp: "2026-05-16T10:30:00",
        },
      },
    },
    {
      id: "demo-policy-check",
      type: "policy_check",
      date: "May 17",
      marker: "⚖",
      title: "EnterpriseAgents policy check: ineligible",
      detail: "No flagged agents for enterprise research jobs.",
      severity: "danger",
      evidence: {
        policy: {
          platform: "EnterpriseAgents.io",
          result: "ineligible",
          reason: "No flagged agents for enterprise research jobs.",
        },
      },
    },
  ],
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
  timeline: [
    {
      id: "researchpro-research-completed",
      type: "job_accepted",
      date: "May 12",
      marker: "✓",
      title: "Research job completed",
      detail: "ResearchPro completed a sourced research task.",
      severity: "success",
      evidence: {
        job: {
          id: "researchpro_good_demo",
          platform_id: "enterpriseagents_io",
          requester_id: "buyer_enterprise",
          task_spec: "Research enterprise AI infrastructure vendors with verified sources.",
          category: "research",
          payment_amount: 300,
          currency: "USDC",
          status: "accepted",
        },
      },
    },
    {
      id: "researchpro-market-accepted",
      type: "job_accepted",
      date: "May 14",
      marker: "✓",
      title: "Market report accepted",
      detail: "Buyer accepted the deliverable with no dispute.",
      severity: "success",
      evidence: {
        deliverable: {
          id: "deliv_researchpro_market_demo",
          deliverable_uri: "https://example.com/researchpro-report",
          summary: "Market report accepted with verified citations.",
          evidence_urls: ["https://example.com/researchpro-source"],
        },
      },
    },
    {
      id: "researchpro-policy-check",
      type: "policy_check",
      date: "May 17",
      marker: "⚖",
      title: "EnterpriseAgents policy check: eligible",
      detail: "Agent satisfies this marketplace policy.",
      severity: "success",
      evidence: {
        policy: {
          platform: "EnterpriseAgents.io",
          result: "eligible",
          reason: "Agent satisfies this marketplace policy.",
        },
      },
    },
  ],
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
      setStatus("EnterpriseAgents.io applied its own policy to RepLayer risk signals.");
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
          <p className="brand-mark">RepLayer</p>
          <h1>Reputation affects who gets hired.</h1>
        </div>
        <nav className="nav">
          <Link className="secondary" href="/">Dashboard</Link>
          <Link className="secondary" href="/integrations">SDK</Link>
          <a className="secondary" href="https://github.com/ShalyX/replayer" target="_blank" rel="noreferrer">GitHub</a>
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
          <p>Platforms define their own rules. RepLayer supplies facts, evidence, judgments, and risk assessment.</p>
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
          <h2>RepLayer Risk Assessment</h2>
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

      <ReputationTimeline events={selectedAssessment.timeline} />
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
