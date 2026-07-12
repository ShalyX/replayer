# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

import json
from genlayer import *


class AgentReputationRegistry(gl.Contract):
    platforms: TreeMap[str, str]
    platform_owners: TreeMap[str, str]
    agents: TreeMap[str, str]
    jobs: TreeMap[str, str]
    deliverables: TreeMap[str, str]
    disputes: TreeMap[str, str]
    judgments: TreeMap[str, str]

    def __init__(self):
        pass

    @gl.public.write
    def register_platform(self, platform_id: str, name: str, webhook_url: str) -> None:
        if platform_id in self.platforms:
            raise Exception("Platform already exists")
        owner = gl.message.sender_address.as_hex
        self.platform_owners[platform_id] = owner
        self.platforms[platform_id] = json.dumps({
            "platform_id": platform_id,
            "owner": owner,
            "name": name,
            "webhook_url": webhook_url,
            "active": True,
        }, sort_keys=True)

    @gl.public.write
    def register_agent(self, agent_id: str, platform_id: str, owner_wallet: str, name: str, capabilities_json: str, metadata_uri: str) -> None:
        self._require_platform_owner(platform_id)
        if agent_id in self.agents:
            raise Exception("Agent already exists")
        self.agents[agent_id] = json.dumps({
            "agent_id": agent_id,
            "owner_wallet": owner_wallet,
            "platform_id": platform_id,
            "name": name,
            "capabilities_json": capabilities_json,
            "metadata_uri": metadata_uri,
            "status": "active",
        }, sort_keys=True)

    @gl.public.write
    def create_job(self, job_id: str, platform_id: str, requester_id: str, provider_agent_id: str, task_spec: str, category: str, payment_amount: str, currency: str) -> None:
        self._require_platform_owner(platform_id)
        if provider_agent_id not in self.agents:
            raise Exception("Unknown agent")
        if job_id in self.jobs:
            raise Exception("Job already exists")
        self.jobs[job_id] = json.dumps({
            "job_id": job_id,
            "requester_id": requester_id,
            "provider_agent_id": provider_agent_id,
            "platform_id": platform_id,
            "task_spec": task_spec,
            "category": category,
            "payment_amount": payment_amount,
            "currency": currency,
            "status": "created",
        }, sort_keys=True)

    @gl.public.write
    def submit_deliverable(self, deliverable_id: str, job_id: str, deliverable_url: str, summary: str, evidence_urls_json: str) -> None:
        job = self._get_job(job_id)
        self._require_platform_owner(str(job["platform_id"]))
        if str(job["status"]) != "created":
            raise Exception("Job not accepting deliverables")
        self.deliverables[job_id] = json.dumps({
            "deliverable_id": deliverable_id,
            "job_id": job_id,
            "deliverable_url": deliverable_url,
            "summary": summary,
            "evidence_urls_json": evidence_urls_json,
        }, sort_keys=True)
        job["status"] = "submitted"
        self.jobs[job_id] = json.dumps(job, sort_keys=True)

    @gl.public.write
    def accept_job(self, job_id: str) -> None:
        job = self._get_job(job_id)
        self._require_platform_owner(str(job["platform_id"]))
        if str(job["status"]) != "submitted":
            raise Exception("Job is not submitted")
        job["status"] = "accepted"
        self.jobs[job_id] = json.dumps(job, sort_keys=True)

    @gl.public.write
    def open_dispute(self, dispute_id: str, job_id: str, claimant: str, reason: str, evidence_url: str, bond_amount: str) -> None:
        job = self._get_job(job_id)
        self._require_platform_owner(str(job["platform_id"]))
        if str(job["status"]) != "submitted":
            raise Exception("Job is not disputable")
        self.disputes[job_id] = json.dumps({
            "dispute_id": dispute_id,
            "job_id": job_id,
            "claimant": claimant,
            "reason": reason,
            "evidence_url": evidence_url,
            "bond_amount": bond_amount,
            "status": "open",
        }, sort_keys=True)
        job["status"] = "disputed"
        self.jobs[job_id] = json.dumps(job, sort_keys=True)

    @gl.public.write
    def resolve_dispute(self, job_id: str) -> None:
        job = self._get_job(job_id)
        if str(job["status"]) != "disputed":
            raise Exception("Job is not disputed")
        deliverable = self._loads_required(self.deliverables[job_id], "Missing deliverable")
        dispute = self._loads_required(self.disputes[job_id], "Missing dispute")
        if str(dispute["status"]) != "open":
            raise Exception("Dispute is not open")
        judgment = self._evaluate_research_dispute(job, deliverable, dispute)
        dispute["status"] = "resolved"
        self.disputes[job_id] = json.dumps(dispute, sort_keys=True)
        self.judgments[job_id] = json.dumps(judgment, sort_keys=True)
        job["status"] = "judged_" + str(judgment["verdict"])
        self.jobs[job_id] = json.dumps(job, sort_keys=True)

    @gl.public.view
    def get_platform(self, platform_id: str) -> str:
        return self.platforms[platform_id]

    @gl.public.view
    def get_agent(self, agent_id: str) -> str:
        return self.agents[agent_id]

    @gl.public.view
    def get_job(self, job_id: str) -> str:
        return self.jobs[job_id]

    @gl.public.view
    def get_deliverable(self, job_id: str) -> str:
        return self.deliverables[job_id]

    @gl.public.view
    def get_dispute(self, job_id: str) -> str:
        return self.disputes[job_id]

    @gl.public.view
    def get_judgment(self, job_id: str) -> str:
        return self.judgments.get(job_id, "")

    def _require_platform_owner(self, platform_id: str) -> None:
        if platform_id not in self.platforms:
            raise Exception("Unknown platform")
        if self.platform_owners[platform_id] != gl.message.sender_address.as_hex:
            raise Exception("Only platform owner")

    def _get_job(self, job_id: str):
        return self._loads_required(self.jobs[job_id], "Unknown job")

    def _loads_required(self, value: str, message: str):
        if value == "":
            raise Exception(message)
        return json.loads(value)

    def _evaluate_research_dispute(self, job, deliverable, dispute):
        def evaluate() -> str:
            deliverable_text = gl.get_webpage(str(deliverable["deliverable_url"]), mode="text")
            dispute_evidence = ""
            if str(dispute["evidence_url"]) != "":
                dispute_evidence = gl.get_webpage(str(dispute["evidence_url"]), mode="text")
            source_notes = self._fetch_source_notes(str(deliverable["evidence_urls_json"]))
            task = self._evaluation_prompt(job, deliverable, dispute, deliverable_text, dispute_evidence, source_notes)
            result = gl.exec_prompt(task).replace("```json", "").replace("```", "")
            parsed = json.loads(result)
            return json.dumps(self._normalize_judgment(parsed), sort_keys=True)
        return json.loads(gl.eq_principle_strict_eq(evaluate))

    def _evaluation_prompt(self, job, deliverable, dispute, deliverable_text: str, dispute_evidence: str, source_notes: str) -> str:
        return (
            "You are evaluating whether an AI agent completed a research task.\n\n"
            "Task:\n" + str(job["task_spec"]) + "\n\n"
            "Deliverable summary:\n" + str(deliverable["summary"]) + "\n\n"
            "Deliverable text:\n" + deliverable_text[:12000] + "\n\n"
            "Evidence/source excerpts:\n" + source_notes[:12000] + "\n\n"
            "Dispute claim:\n" + str(dispute["reason"]) + "\n\n"
            "Dispute evidence:\n" + dispute_evidence[:6000] + "\n\n"
            "Return only valid JSON with verdict, confidence_bps, "
            "and reasoning_summary. Verdict must be satisfied, "
            "partially_satisfied, failed, fraudulent, or inconclusive."
        )

    def _fetch_source_notes(self, evidence_urls_json: str) -> str:
        try:
            urls = json.loads(evidence_urls_json)
        except Exception:
            raise Exception("evidence_urls_json must be a JSON array")
        notes = []
        for url in urls[:8]:
            if not isinstance(url, str):
                continue
            try:
                body = gl.get_webpage(url, mode="text")
                notes.append("URL: " + url + "\n" + body[:2500])
            except Exception as err:
                notes.append("URL: " + url + "\nFETCH_ERROR: " + str(err))
        return "\n\n".join(notes)

    def _normalize_judgment(self, raw):
        verdict = str(raw.get("verdict", "")).strip().lower()
        allowed = ["satisfied", "partially_satisfied", "failed", "fraudulent", "inconclusive"]
        if verdict not in allowed:
            verdict = "inconclusive"
        confidence_bps = int(raw.get("confidence_bps", 0))
        if confidence_bps < 0:
            confidence_bps = 0
        if confidence_bps > 10000:
            confidence_bps = 10000
        return {
            "verdict": verdict,
            "confidence_bps": confidence_bps,
            "reasoning_summary": str(raw.get("reasoning_summary", ""))[:1200],
        }
