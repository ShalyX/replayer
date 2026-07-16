"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
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

const LAST_DEMO_AGENT_KEY = "agent-reputation-registry:last-demo-agent";

export default function MarketplaceConsole() {
  const [agentId, setAgentId] = useState("");
  const [assessment, setAssessment] = useState<Assessment | null>(null);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("Enter an agent ID to query its current Passport.");
  const [error, setError] = useState("");

  useEffect(() => {
    const storedAgent = window.localStorage.getItem(LAST_DEMO_AGENT_KEY);
    if (storedAgent) setAgentId(storedAgent);
  }, []);

  async function evaluateAgent(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const requestedAgent = agentId.trim();
    if (!requestedAgent) return;
    setBusy(true);
    setError("");
    setAssessment(null);
    setStatus("Reading the current projection and applying this marketplace policy...");
    try {
      const result = await api<Assessment>("/trust/evaluate", {
        method: "POST",
        body: JSON.stringify({
          agent_id: requestedAgent,
          job_type: "enterprise_research",
          job_value: 50000,
          policy: enterprisePolicy,
        }),
      });
      setAssessment(result);
      setStatus("Policy evaluated from the current RepLayer projection.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Policy evaluation failed");
      setStatus("No assessment was produced. RepLayer never substitutes sample reputation data.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <p className="brand-mark">RepLayer</p>
          <h1>Marketplace hiring console</h1>
        </div>
        <nav className="nav">
          <Link className="secondary" href="/">Dashboard</Link>
          <Link className="secondary" href="/integrations">SDK</Link>
          <a className="secondary" href="https://github.com/ShalyX/replayer" target="_blank" rel="noreferrer">GitHub</a>
        </nav>
      </header>

      <section className="policy-hero">
        <div>
          <p className="eyebrow">Portable policy check</p>
          <h2>Query any registered agent before assigning work.</h2>
        </div>
        <div className="policy-card">
          <span>Current marketplace policy</span>
          <strong>Trust at least 70, risk at most 30, and no fraud incidents.</strong>
          <p>RepLayer supplies the event-derived projection. The marketplace owns this hiring rule.</p>
        </div>
      </section>

      <section className="grid story-grid">
        <form className="panel forms" onSubmit={evaluateAgent}>
          <h2>Evaluate Agent</h2>
          <label>
            Agent ID
            <input value={agentId} onChange={(event) => setAgentId(event.target.value)} placeholder="agent_..." required />
          </label>
          <button disabled={busy || !agentId.trim()} type="submit">{busy ? "Evaluating..." : "Evaluate policy"}</button>
          <p className="policy-note">{status}</p>
          {error ? <p className="error-text">{error}</p> : null}
        </form>

        <section className="panel">
          <h2>Policy Result</h2>
          {assessment ? (
            <div className={assessment.policy_result.eligible ? "policy-result eligible" : "policy-result ineligible"}>
              <span>{assessment.agent_id}</span>
              <strong>{assessment.policy_result.outcome}</strong>
              <p>{assessment.policy_result.reasons[0] || "Agent satisfies this marketplace policy."}</p>
            </div>
          ) : <p className="muted">No agent has been evaluated in this session.</p>}
        </section>
      </section>

      {assessment ? (
        <>
          <section className="marketplace-grid section-gap">
            <article className="market-agent active">
              <div className="section-head">
                <div><p className="eyebrow">Live Passport</p><h2>{assessment.agent_id}</h2></div>
                <span className={assessment.status === "flagged" ? "pill bad" : "pill"}>{assessment.status}</span>
              </div>
              <div className="market-metrics">
                <div><span>Trust</span><strong>{assessment.trust_score}</strong></div>
                <div><span>Risk</span><strong>{assessment.risk_score}</strong></div>
                <div><span>Fraud</span><strong>{assessment.fraud_incidents}</strong></div>
              </div>
              <p>{assessment.reasons[0] || "No material risk signals found."}</p>
              <Link className="text-link" href={`/agents/${encodeURIComponent(assessment.agent_id)}`}>Open Passport</Link>
            </article>
            <section className="panel">
              <h2>RepLayer Assessment</h2>
              <pre>{JSON.stringify({
                status: assessment.status,
                recommendation: assessment.recommendation,
                confidence: assessment.confidence,
                reasons: assessment.reasons,
              }, null, 2)}</pre>
            </section>
          </section>
          <ReputationTimeline events={assessment.timeline} />
        </>
      ) : null}
    </main>
  );
}
