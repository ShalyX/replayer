"use client";

import { useMemo, useState } from "react";
import type { ReactNode } from "react";

type EvidenceJob = {
  id: string;
  platform_id: string;
  requester_id: string;
  task_spec: string;
  category: string;
  payment_amount: number;
  currency: string;
  status: string;
};

type EvidenceDeliverable = {
  id: string;
  deliverable_uri: string;
  summary: string;
  evidence_urls: string[];
};

type EvidenceDispute = {
  id: string;
  claimant: string;
  reason: string;
  evidence_uri: string;
  bond_amount: number;
  status: string;
};

type EvidenceJudgment = {
  id: string;
  verdict: string;
  reasoning_summary: string;
  source: string;
  contract_address: string;
  tx_hash: string;
  verify_url: string;
  timestamp: string;
};

export type TimelineEvent = {
  id?: string;
  type?: string;
  date: string;
  marker: string;
  title: string;
  detail: string;
  severity: "neutral" | "success" | "warning" | "danger";
  verify_url?: string;
  evidence?: {
    job?: EvidenceJob;
    deliverable?: EvidenceDeliverable;
    dispute?: EvidenceDispute;
    judgment?: EvidenceJudgment;
    policy?: {
      platform: string;
      result: string;
      reason: string;
    };
  };
};

export function ReputationTimeline({
  title = "Trust history, not just a score.",
  events,
}: {
  title?: string;
  events: TimelineEvent[];
}) {
  const initialIndex = useMemo(() => {
    const riskIndex = events.findIndex((event) => event.severity === "danger");
    return riskIndex >= 0 ? riskIndex : 0;
  }, [events]);
  const [selectedIndex, setSelectedIndex] = useState(initialIndex);
  const selectedEvent = events[selectedIndex] || events[0];

  if (!events.length) {
    return (
      <section className="timeline-panel">
        <div className="section-head">
          <div>
            <p className="eyebrow">Reputation timeline</p>
            <h2>{title}</h2>
          </div>
        </div>
        <p className="policy-note">No reputation events yet.</p>
      </section>
    );
  }

  return (
    <section className="timeline-panel">
      <div className="section-head">
        <div>
          <p className="eyebrow">Reputation timeline</p>
          <h2>{title}</h2>
        </div>
      </div>
      <div className="timeline-workbench">
        <ol className="audit-timeline">
          {events.map((event, index) => (
            <li className={`audit-event ${event.severity} ${index === selectedIndex ? "active" : ""}`} key={event.id || `${event.date}-${event.title}-${index}`}>
              <button className="audit-event-button" type="button" onClick={() => setSelectedIndex(index)}>
                <span className="audit-date">{event.date}</span>
                <span className="audit-marker">{event.marker}</span>
                <span>
                  <strong>{event.title}</strong>
                  <small>{event.detail}</small>
                </span>
              </button>
            </li>
          ))}
        </ol>
        <EvidenceExplorer event={selectedEvent} />
      </div>
    </section>
  );
}

function EvidenceExplorer({ event }: { event: TimelineEvent }) {
  const evidence = event.evidence || {};
  const judgmentLink = evidence.judgment?.verify_url || event.verify_url;

  return (
    <aside className="evidence-explorer">
      <div>
        <p className="eyebrow">Evidence explorer</p>
        <h3>{event.title}</h3>
        <p>{event.detail}</p>
      </div>

      {evidence.job ? (
        <EvidenceBlock title="Job">
          <EvidenceRow label="Job ID" value={evidence.job.id} />
          <EvidenceRow label="Task" value={evidence.job.task_spec} />
          <EvidenceRow label="Status" value={evidence.job.status} />
          <EvidenceRow label="Value" value={`${evidence.job.payment_amount} ${evidence.job.currency}`} />
        </EvidenceBlock>
      ) : null}

      {evidence.deliverable ? (
        <EvidenceBlock title="Deliverable">
          <EvidenceRow label="Summary" value={evidence.deliverable.summary || evidence.deliverable.deliverable_uri} />
          <EvidenceRow label="URI" value={evidence.deliverable.deliverable_uri} href={evidence.deliverable.deliverable_uri} />
          {evidence.deliverable.evidence_urls.map((url) => (
            <EvidenceRow href={url} key={url} label="Evidence URL" value={url} />
          ))}
        </EvidenceBlock>
      ) : null}

      {evidence.dispute ? (
        <EvidenceBlock title="Dispute">
          <EvidenceRow label="Dispute ID" value={evidence.dispute.id} />
          <EvidenceRow label="Reason" value={evidence.dispute.reason} />
          <EvidenceRow label="Status" value={evidence.dispute.status} />
          <EvidenceRow label="Evidence" value={evidence.dispute.evidence_uri} href={evidence.dispute.evidence_uri} />
        </EvidenceBlock>
      ) : null}

      {evidence.judgment ? (
        <EvidenceBlock title="Judgment">
          <EvidenceRow label="Verdict" value={evidence.judgment.verdict} />
          <EvidenceRow label="Source" value={evidence.judgment.source} />
          <EvidenceRow label="Reasoning" value={evidence.judgment.reasoning_summary} />
          <EvidenceRow label="Contract" value={evidence.judgment.contract_address || "Not recorded"} />
          <EvidenceRow label="Tx Hash" value={evidence.judgment.tx_hash || "Not recorded"} />
        </EvidenceBlock>
      ) : null}

      {evidence.policy ? (
        <EvidenceBlock title="Marketplace Policy">
          <EvidenceRow label="Platform" value={evidence.policy.platform} />
          <EvidenceRow label="Result" value={evidence.policy.result} />
          <EvidenceRow label="Reason" value={evidence.policy.reason} />
        </EvidenceBlock>
      ) : null}

      {judgmentLink ? (
        <a className="explorer-link" href={judgmentLink} target="_blank" rel="noreferrer">
          View on GenLayer Explorer
        </a>
      ) : null}
    </aside>
  );
}

function EvidenceBlock({ children, title }: { children: ReactNode; title: string }) {
  return (
    <section className="evidence-block">
      <h4>{title}</h4>
      <div>{children}</div>
    </section>
  );
}

function EvidenceRow({ href, label, value }: { href?: string; label: string; value: string }) {
  return (
    <div className="evidence-row">
      <span>{label}</span>
      {href ? (
        <a href={href} target="_blank" rel="noreferrer">{shorten(value)}</a>
      ) : (
        <strong>{value}</strong>
      )}
    </div>
  );
}

function shorten(value: string) {
  if (value.length <= 42) {
    return value;
  }
  return `${value.slice(0, 24)}...${value.slice(-10)}`;
}
