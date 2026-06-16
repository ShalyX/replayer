"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "../lib/api";

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

type Judgment = {
  verdict: string;
  source: string;
  contract_address: string;
  tx_hash: string;
  verify_url: string;
  timestamp: string;
  reasoning_summary: string;
};

type DemoSeed = {
  story: {
    platform_id: string;
    partner_platform_id: string;
    agent_id: string;
    good_job_id: string;
    fraud_job_id: string;
    events: string[];
  };
  profile: {
    reputation: Reputation;
    judgments: Judgment[];
  };
  demo_line: string;
};

const defaultEvents = [
  "ResearchAgents.io registers and lists DeepResearchBot.",
  "DeepResearchBot completes a good sourced research job.",
  "A second job contains fabricated citations and gets disputed.",
  "GenLayer evaluates the dispute and marks the job fraudulent.",
  "EnterpriseAgentMarket checks the public profile before hiring.",
];

const LAST_DEMO_AGENT_KEY = "agent-reputation-registry:last-demo-agent";
const CONTRACT_ADDRESS = "0x59a8924E6E7D3A460e2154a304fCC2BEfEc3c8Dd";

export default function Dashboard() {
  const [demo, setDemo] = useState<DemoSeed | null>(null);
  const [profileHref, setProfileHref] = useState("");
  const [events, setEvents] = useState(defaultEvents);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("Ready to run the live trust demo.");
  const [error, setError] = useState("");
  const judgment = demo?.profile.judgments[0];
  const currentScore = demo?.profile.reputation.overall ?? 0;
  const currentStatus = demo?.profile.reputation.status ?? "flagged";

  useEffect(() => {
    const lastAgentId = window.localStorage.getItem(LAST_DEMO_AGENT_KEY);
    if (lastAgentId) {
      setProfileHref(`/agents/${lastAgentId}`);
    }
  }, []);

  async function resetDemo() {
    setBusy(true);
    setError("");
    setStatus("Resetting local demo records...");
    try {
      await api("/demo/reset", { method: "POST", body: "{}" });
      window.localStorage.removeItem(LAST_DEMO_AGENT_KEY);
      setDemo(null);
      setProfileHref("");
      setEvents(defaultEvents);
      setStatus("Demo records reset. The next run will create a fresh GenLayer-backed story.");
    } catch (caught) {
      setError(toErrorMessage(caught));
      setStatus("Reset failed. The API returned an error, but the page is still usable.");
    } finally {
      setBusy(false);
    }
  }

  async function runDemo() {
    setBusy(true);
    setError("");
    setStatus("Running ResearchAgents.io story against the live contract. This can take a few minutes.");
    try {
      const seeded = await api<DemoSeed>("/demo/seed", { method: "POST", body: "{}" });
      const nextProfileHref = `/agents/${seeded.story.agent_id}`;
      window.localStorage.setItem(LAST_DEMO_AGENT_KEY, seeded.story.agent_id);
      setDemo(seeded);
      setProfileHref(nextProfileHref);
      setEvents(seeded.story.events);
      setStatus("DeepResearchBot received a GenLayer-verified fraud judgment. Reputation collapsed publicly.");
    } catch (caught) {
      const message = toErrorMessage(caught);
      setError(message);
      setStatus(
        message.toLowerCase().includes("fetch failed") || message.toLowerCase().includes("rpc")
          ? "GenLayer RPC timed out during the live run. Wait a moment and retry the demo."
          : "Demo run failed. Check the error below and retry.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <p className="brand-mark">RepLayer</p>
          <h1>Portable reputation for AI agents.</h1>
        </div>
        <nav className="nav">
          {profileHref ? (
            <Link className="secondary" href={profileHref}>Public Profile</Link>
          ) : (
            <button className="secondary" disabled type="button">Public Profile</button>
          )}
          <Link className="secondary" href="/integrations">Integration Snippet</Link>
          <Link className="secondary" href="/marketplace">Marketplace Console</Link>
          {judgment?.verify_url ? (
            <a href={judgment.verify_url} target="_blank" rel="noreferrer">Verify on GenLayer</a>
          ) : null}
        </nav>
      </header>

      <section className="hero-band">
        <div>
          <p className="eyebrow">Trust API for agent marketplaces</p>
          <p className="lede">
            When an agent gets caught cheating on one marketplace, every other marketplace can see the risk.
          </p>
          <p className="supporting-copy">
            RepLayer lets agent marketplaces share trust. When GenLayer verifies fraud, the judgment follows the
            agent before another platform hires it again.
          </p>
        </div>
        <div className="demo-actions">
          <button disabled={busy} type="button" onClick={runDemo}>{busy ? "Running live..." : "Reset + Run Demo"}</button>
          <button className="secondary" disabled={busy} type="button" onClick={resetDemo}>Reset Data</button>
          <span>{status}</span>
          {error ? <p className="error-text">{error}</p> : null}
        </div>
      </section>

      <section className="collapse-stage">
        <section className="trust-card good">
          <p className="eyebrow">Before the lie</p>
          <h2>DeepResearchBot</h2>
          <span className="score-label">Trust Score</span>
          <div className="trust-score">77</div>
          <span className="pill">verified</span>
          <p>Completed research job with credible sources.</p>
        </section>

        <section className="incident-card">
          <p className="eyebrow">Fraudulent Citation Submitted</p>
          <h2>GenLayer Judgment: {judgment?.verdict?.toUpperCase() || "FRAUDULENT"}</h2>
          <ol className="collapse-flow">
            <li>Agent earns portable trust</li>
            <li>Buyer disputes fabricated citations</li>
            <li>GenLayer verifies a fraud judgment</li>
            <li>Every integrated platform can see the flag</li>
          </ol>
        </section>

        <section className="trust-card bad">
          <p className="eyebrow">After judgment</p>
          <h2>DeepResearchBot</h2>
          <span className="score-label">Trust Score</span>
          <div className="trust-score">{currentScore}</div>
          <span className="pill bad">{currentStatus}</span>
          <p>{demo ? "Trust collapsed publicly after a GenLayer-verified fraud judgment." : "Run the demo to generate the live collapse."}</p>
        </section>
      </section>

      <section className="grid story-grid">
        <section className="panel">
          <h2>Verified by GenLayer</h2>
          <div className="verdict-proof">
            <span>Verdict</span>
            <strong>{(judgment?.verdict || "fraudulent").toUpperCase()}</strong>
            <p>Recorded on GenLayer</p>
          </div>
          <div className="proof-grid">
            <div>
              <span>Contract</span>
              <strong>{shorten(judgment?.contract_address || CONTRACT_ADDRESS)}</strong>
            </div>
            <div>
              <span>Tx</span>
              <strong>{judgment?.tx_hash ? shorten(judgment.tx_hash) : "pending live run"}</strong>
            </div>
            <div>
              <span>Status</span>
              <strong>{judgment ? "FINAL" : "READY"}</strong>
            </div>
          </div>
          {judgment?.verify_url ? <a className="proof-link" href={judgment.verify_url} target="_blank" rel="noreferrer">View on Explorer</a> : null}
          <p className="policy-note">
            Current demo uses an aggressive scoring policy to illustrate the impact of a fraudulent GenLayer judgment.
            Future versions will use weighted reputation and risk models.
          </p>
        </section>

        <section className="panel">
          <div className="section-head">
            <div>
              <p className="eyebrow">Narrative</p>
              <h2>One Agent Gets Caught</h2>
            </div>
            {demo ? <span className="pill bad">{demo.profile.reputation.status}</span> : <span className="pill">ready</span>}
          </div>
          <ol className="timeline">
            {events.map((item, index) => (
              <li key={item}>
                <span>{index + 1}</span>
                <p>{item}</p>
              </li>
            ))}
          </ol>
        </section>
      </section>

      <section className="comparison-panel">
        <div className="section-head">
          <div>
            <p className="eyebrow">Agent comparison</p>
            <h2>Which agent would your marketplace hire?</h2>
          </div>
          <Link className="text-link" href="/integrations">Add this check to a marketplace</Link>
          <Link className="text-link" href="/marketplace">Open hiring console</Link>
        </div>
        <div className="agent-compare-grid">
          <article className="agent-choice rejected">
            <span className="pill bad">flagged</span>
            <h3>DeepResearchBot</h3>
            <strong>Score: {currentScore}</strong>
            <p>Fraudulent citations verified by a GenLayer judgment.</p>
          </article>
          <article className="agent-choice accepted">
            <span className="pill">verified</span>
            <h3>ResearchPro</h3>
            <strong>Score: 91</strong>
            <p>Clean job history with no valid disputes.</p>
          </article>
        </div>
      </section>

      <section className="grid story-grid">
        <section className="panel">
          <h2>Demo Objects</h2>
          <table className="table">
            <tbody>
              <tr><td>Platform</td><td>{demo?.story.platform_id || "researchagents_io_[fresh run]"}</td></tr>
              <tr><td>Partner</td><td>{demo?.story.partner_platform_id || "partner_market_[fresh run]"}</td></tr>
              <tr><td>Agent</td><td>{demo?.story.agent_id || "deepresearchbot_[fresh run]"}</td></tr>
              <tr><td>Good Job</td><td>{demo?.story.good_job_id || "research_good_[fresh run]"}</td></tr>
              <tr><td>Fraud Job</td><td>{demo?.story.fraud_job_id || "research_fraud_[fresh run]"}</td></tr>
            </tbody>
          </table>
        </section>

        <section className="panel">
          <h2>GenLayer Judgment</h2>
          {judgment ? (
            <div className="judgment-box">
              <div><span>Verdict</span><strong className="danger-text">{judgment.verdict}</strong></div>
              <div><span>Source</span><strong>{judgment.source}</strong></div>
              <div><span>Contract</span><strong>{judgment.contract_address}</strong></div>
              <div><span>Timestamp</span><strong>{judgment.timestamp}</strong></div>
              <p>{judgment.reasoning_summary}</p>
              {judgment.verify_url ? <a href={judgment.verify_url} target="_blank" rel="noreferrer">Verify on GenLayer</a> : null}
            </div>
          ) : (
            <p className="muted">Run the demo to generate a live GenLayer-verified fraud judgment and provenance link.</p>
          )}
        </section>
      </section>
    </main>
  );
}

function shorten(value: string): string {
  if (value.length <= 16) {
    return value;
  }
  return `${value.slice(0, 6)}...${value.slice(-4)}`;
}

function toErrorMessage(caught: unknown): string {
  if (caught instanceof Error) {
    return caught.message;
  }
  return "Unknown error";
}
