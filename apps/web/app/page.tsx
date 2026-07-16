"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "../lib/api";

type Reputation = {
  agent_id: string;
  overall: number;
  risk_score: number;
  fraud_incidents: number;
  status: string;
  projection: string;
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

type Profile = {
  agent: { id: string; name: string; platform_id: string };
  reputation: Reputation;
  judgments: Judgment[];
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
  accepted: { reputation: Reputation };
  profile: Profile;
};

type DemoRun = {
  run_id: string;
  status: "pending" | "running" | "completed" | "failed";
  result?: DemoSeed;
  error?: string;
};

type Health = {
  ok: boolean;
  genlayer_mode: string;
  source_of_truth: string;
  contract_address: string;
  counts: { platforms: number; agents: number; jobs: number };
};

const LAST_DEMO_AGENT_KEY = "agent-reputation-registry:last-demo-agent";

export default function Dashboard() {
  const [demo, setDemo] = useState<DemoSeed | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("Checking the live RepLayer runtime...");
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    async function loadRuntime() {
      try {
        const runtime = await api<Health>("/health");
        if (active) setHealth(runtime);
      } catch (caught) {
        if (active) {
          setError(toErrorMessage(caught));
          setStatus("Runtime health could not be loaded.");
        }
        return;
      }
      const lastAgentId = window.localStorage.getItem(LAST_DEMO_AGENT_KEY);
      if (lastAgentId) {
        try {
          const lastProfile = await api<Profile>(`/agents/${encodeURIComponent(lastAgentId)}/profile`);
          if (active) setProfile(lastProfile);
        } catch (caught) {
          window.localStorage.removeItem(LAST_DEMO_AGENT_KEY);
          if (active) {
            setError(toErrorMessage(caught));
            setStatus("The saved Passport is no longer available. Live runtime health is still shown.");
          }
          return;
        }
      }
      if (active) setStatus(lastAgentId ? "Loaded the latest live Passport from RepLayer." : "Live runtime ready. No demo run is loaded.");
    }
    void loadRuntime();
    return () => { active = false; };
  }, []);

  async function resetView() {
    setBusy(true);
    setError("");
    try {
      await api("/demo/reset", { method: "POST", body: "{}" });
      window.localStorage.removeItem(LAST_DEMO_AGENT_KEY);
      setDemo(null);
      setProfile(null);
      setStatus("Demo view cleared. Append-only ledger history was preserved.");
    } catch (caught) {
      setError(toErrorMessage(caught));
      setStatus("The view could not be reset.");
    } finally {
      setBusy(false);
    }
  }

  async function runDemo() {
    setBusy(true);
    setError("");
    setDemo(null);
    setProfile(null);
    setStatus("Submitting the live demonstration flow to GenLayer...");
    try {
      const started = await api<DemoRun>("/demo/runs", { method: "POST", body: "{}" });
      let run = started;
      for (let attempt = 0; attempt < 180 && run.status !== "completed" && run.status !== "failed"; attempt += 1) {
        setStatus(`GenLayer consensus is running. Check ${attempt + 1}...`);
        await new Promise((resolve) => window.setTimeout(resolve, 5000));
        run = await api<DemoRun>(`/demo/runs/${started.run_id}`);
      }
      if (run.status === "failed") throw new Error(run.error || "Live GenLayer demo failed");
      if (run.status !== "completed" || !run.result) throw new Error("The live run did not finish within the polling window.");
      window.localStorage.setItem(LAST_DEMO_AGENT_KEY, run.result.story.agent_id);
      setDemo(run.result);
      setProfile(run.result.profile);
      setStatus("Live demo completed and the resulting Passport was read back from RepLayer.");
    } catch (caught) {
      setError(toErrorMessage(caught));
      setStatus("No demo result was produced. The UI will not substitute sample data.");
    } finally {
      setBusy(false);
    }
  }

  const judgment = profile?.judgments[0];
  const profileHref = profile ? `/agents/${encodeURIComponent(profile.agent.id)}` : "";

  return (
    <main className="shell">
      <header className="topbar">
        <div><p className="brand-mark">RepLayer</p><h1>Event-sourced trust for AI agents</h1></div>
        <nav className="nav">
          {profileHref ? <Link className="secondary" href={profileHref}>Current Passport</Link> : null}
          <Link className="secondary" href="/marketplace">Marketplace Console</Link>
          <Link className="secondary" href="/integrations">Integrate</Link>
          <Link className="secondary" href="/pilot">Runtime</Link>
          <a className="secondary" href="https://github.com/ShalyX/replayer" target="_blank" rel="noreferrer">GitHub</a>
        </nav>
      </header>

      <section className="hero-band">
        <div>
          <p className="eyebrow">GenLayer-backed accountability</p>
          <p className="lede">Reputation follows verified events, identity, due process, and responsibility across marketplaces.</p>
          <p className="supporting-copy">Run the explicit demonstration below or query an existing agent. Production views never invent a verdict when the API or contract is unavailable.</p>
        </div>
        <div className="demo-actions">
          <button disabled={busy} type="button" onClick={runDemo}>{busy ? "Running live..." : "Run Live Demo"}</button>
          <button className="secondary" disabled={busy} type="button" onClick={resetView}>Clear View</button>
          <span>{status}</span>
          {error ? <p className="error-text">{error}</p> : null}
        </div>
      </section>

      <section className="grid story-grid">
        <section className="panel">
          <h2>Runtime Source of Truth</h2>
          {health ? (
            <table className="table"><tbody>
              <tr><th>Mode</th><td>{health.genlayer_mode}</td></tr>
              <tr><th>Authority</th><td>{health.source_of_truth.replaceAll("_", " ")}</td></tr>
              <tr><th>Contract</th><td>{health.contract_address}</td></tr>
              <tr><th>Indexed entities</th><td>{health.counts.platforms} platforms / {health.counts.agents} agents / {health.counts.jobs} jobs</td></tr>
            </tbody></table>
          ) : <p className="muted">Runtime health is unavailable.</p>}
        </section>
        <section className="panel">
          <h2>Current Passport</h2>
          {profile ? (
            <table className="table"><tbody>
              <tr><th>Agent</th><td>{profile.agent.name} <span className="muted">{profile.agent.id}</span></td></tr>
              <tr><th>Projection</th><td>{profile.reputation.projection}</td></tr>
              <tr><th>Trust / Risk</th><td>{profile.reputation.overall} / {profile.reputation.risk_score}</td></tr>
              <tr><th>Status</th><td><span className={profile.reputation.status === "flagged" ? "pill bad" : "pill"}>{profile.reputation.status}</span></td></tr>
            </tbody></table>
          ) : <p className="muted">No Passport is loaded. Run the live demo or use the marketplace console with an existing agent ID.</p>}
        </section>
      </section>

      {profile ? (
        <>
          <section className="collapse-stage">
            <section className="trust-card good">
              <p className="eyebrow">Before disputed outcome</p>
              <h2>{profile.agent.name}</h2>
              <span className="score-label">Trust Score</span>
              <div className="trust-score">{demo?.accepted.reputation.overall ?? "-"}</div>
              <p>{demo ? "Read from the accepted-job projection." : "The prior demo stage is not loaded in this session."}</p>
            </section>
            <section className="incident-card">
              <p className="eyebrow">GenLayer outcome</p>
              <h2>{judgment ? judgment.verdict.replaceAll("_", " ") : "No finalized judgment"}</h2>
              <p>{judgment?.reasoning_summary || "This Passport has no indexed judgment summary."}</p>
            </section>
            <section className="trust-card bad">
              <p className="eyebrow">Current projection</p>
              <h2>{profile.agent.name}</h2>
              <span className="score-label">Trust Score</span>
              <div className="trust-score">{profile.reputation.overall}</div>
              <span className={profile.reputation.status === "flagged" ? "pill bad" : "pill"}>{profile.reputation.status}</span>
            </section>
          </section>

          <section className="grid story-grid">
            <section className="panel">
              <h2>Judgment Provenance</h2>
              {judgment ? (
                <div className="judgment-box">
                  <div><span>Verdict</span><strong>{judgment.verdict}</strong></div>
                  <div><span>Contract</span><strong>{judgment.contract_address}</strong></div>
                  <div><span>Transaction</span><strong>{judgment.tx_hash}</strong></div>
                  <div><span>Timestamp</span><strong>{judgment.timestamp}</strong></div>
                  {judgment.verify_url ? <a href={judgment.verify_url} target="_blank" rel="noreferrer">Verify on GenLayer</a> : null}
                </div>
              ) : <p className="muted">No finalized GenLayer judgment is indexed for this Passport.</p>}
            </section>
            <section className="panel">
              <h2>Run Events</h2>
              {demo ? (
                <ol className="timeline">{demo.story.events.map((item, index) => <li key={`${index}-${item}`}><span>{index + 1}</span><p>{item}</p></li>)}</ol>
              ) : <p className="muted">The current Passport was restored from the API; run-specific narration is not persisted as reputation data.</p>}
            </section>
          </section>
        </>
      ) : null}

      <section className="why-section">
        <div className="section-head"><div><p className="eyebrow">Protocol layers</p><h2>One ledger, several derived views</h2></div></div>
        <div className="why-grid">
          <article className="card"><span>Outcome Truth</span><strong>Disputed work becomes consensus-backed events.</strong></article>
          <article className="card"><span>Identity Continuity</span><strong>Aliases resolve to a canonical Passport.</strong></article>
          <article className="card"><span>Due Process</span><strong>Appeals remain provisional until finalization.</strong></article>
          <article className="card"><span>Accountability</span><strong>Delegated liability is apportioned by responsibility.</strong></article>
        </div>
      </section>
    </main>
  );
}

function toErrorMessage(caught: unknown): string {
  return caught instanceof Error ? caught.message : "Unknown error";
}
