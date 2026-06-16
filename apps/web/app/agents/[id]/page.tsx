import Link from "next/link";
import { ReputationPanel } from "../../../components/ReputationPanel";
import { api } from "../../../lib/api";

type Profile = {
  agent: { id: string; name: string; platform_id: string; capabilities: string[]; status: string };
  reputation: any;
  jobs: Array<{ id: string; status: string; task_spec: string; category: string }>;
  disputes: Array<{ id: string; job_id: string; reason: string; status: string }>;
  judgments: Array<{
    id: string;
    job_id: string;
    verdict: string;
    reasoning_summary: string;
    source: string;
    contract_address: string;
    tx_hash: string;
    verify_url: string;
    timestamp: string;
  }>;
};

export default async function AgentProfile({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const profile = await api<Profile>(`/agents/${id}/profile`);

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <p className="brand-mark">RepLayer</p>
          <h1>{profile.agent.name}</h1>
        </div>
        <nav className="nav">
          <Link className="secondary" href="/">Dashboard</Link>
          <Link className="secondary" href="/integrations">Integration</Link>
          {profile.judgments.find((judgment) => judgment.verify_url) ? (
            <a href={profile.judgments.find((judgment) => judgment.verify_url)?.verify_url} target="_blank" rel="noreferrer">
              Verify on GenLayer
            </a>
          ) : null}
        </nav>
      </header>

      <section className="grid">
        <ReputationPanel reputation={profile.reputation} />
        <section className="panel">
          <h2>Job History</h2>
          <table className="table">
            <thead><tr><th>Job</th><th>Status</th><th>Task</th></tr></thead>
            <tbody>{profile.jobs.map((job) => <tr key={job.id}><td>{job.id}</td><td><span className="pill">{job.status}</span></td><td>{job.task_spec}</td></tr>)}</tbody>
          </table>
        </section>
      </section>

      <section className="grid section-gap">
        <section className="panel">
          <h2>Dispute History</h2>
          <table className="table">
            <tbody>{profile.disputes.map((dispute) => <tr key={dispute.id}><td>{dispute.job_id}</td><td>{dispute.reason}</td><td>{dispute.status}</td></tr>)}</tbody>
          </table>
        </section>
        <section className="panel">
          <h2>Judgments</h2>
          <table className="table">
            <tbody>
              {profile.judgments.map((judgment) => (
                <tr key={judgment.id}>
                  <td><span className={judgment.verdict === "fraudulent" ? "pill bad" : "pill"}>{judgment.verdict}</span></td>
                  <td>{judgment.source}</td>
                  <td>
                    {judgment.reasoning_summary}
                    {judgment.tx_hash ? <small className="tx-meta">tx {judgment.tx_hash.slice(0, 10)}... · {judgment.timestamp}</small> : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </section>
    </main>
  );
}
