# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

import json
from genlayer import *


class ReputationEventLedger(gl.Contract):
    events: TreeMap[str, str]
    event_order: TreeMap[str, str]
    ledger_metadata: TreeMap[str, str]
    disputes: TreeMap[str, str]
    judgments: TreeMap[str, str]
    responsibility_cases: TreeMap[str, str]

    def __init__(self):
        pass

    @gl.public.write
    def append_platform_event(self, event_json: str) -> None:
        event = self._object(event_json)
        allowed = ["AGENT_REGISTERED", "JOB_CREATED", "DELIVERABLE_SUBMITTED", "JOB_ACCEPTED", "JOB_COMPLETED", "EVENT_ATTESTED", "REPUTATION_ATTESTED", "PLATFORM_IDENTITY_VERIFIED", "AGENT_IDENTITY_REGISTERED", "IDENTITY_BINDING_PROPOSED", "IDENTITY_CONTROLLER_ROTATED", "IDENTITY_OWNERSHIP_TRANSFERRED", "IDENTITY_UNLINKED", "DELEGATION_CREATED", "DELEGATION_ACCEPTED", "AUTHORITY_SCOPE_GRANTED", "SPENDING_LIMIT_SET", "WORK_SUBDELEGATED", "DELEGATED_OUTPUT_SUBMITTED"]
        if str(event.get("event_type", "")) not in allowed:
            raise gl.vm.UserError("[EXPECTED] Unsupported platform event")
        event["provenance"] = "platform_reported"
        if event["event_type"] == "REPUTATION_ATTESTED":
            event["verification_status"] = "uncontested"
        elif event["event_type"] == "IDENTITY_BINDING_PROPOSED":
            event["verification_status"] = "pending"
        else:
            event["verification_status"] = "finalized"
        self._append(event)

    @gl.public.write
    def confirm_attestation(self, event_json: str) -> None:
        event = self._object(event_json)
        original_id = str(event.get("attestation_event_id", ""))
        if original_id not in self.events:
            raise gl.vm.UserError("[EXPECTED] Unknown attestation")
        event["event_type"] = "COUNTERPARTY_CONFIRMED"
        event["provenance"] = "counterparty_confirmed"
        event["verification_status"] = "finalized"
        event["references"] = [original_id]
        self._append(event)

    @gl.public.write
    def confirm_identity_binding(self, confirmation_json: str) -> None:
        confirmation = self._object(confirmation_json)
        proposal_id = str(confirmation.get("proposal_event_id", ""))
        if proposal_id not in self.events:
            raise gl.vm.UserError("[EXPECTED] Unknown identity binding proposal")
        proposal = json.loads(self.events[proposal_id])
        proposal_metadata = proposal.get("metadata", {})
        confirmation_event_id = str(confirmation["confirmation_event_id"])
        link_event_id = str(confirmation["link_event_id"])
        shared_metadata = {
            "source_agent_id": str(proposal_metadata.get("source_agent_id", proposal.get("agent_id", ""))),
            "target_agent_id": str(proposal_metadata.get("target_agent_id", proposal.get("counterparty_id", ""))),
            "source_identity": str(proposal_metadata.get("source_identity", "")),
            "target_identity": str(proposal_metadata.get("target_identity", "")),
            "nonce": str(proposal_metadata.get("nonce", "")),
            "controller_proof": "dual_signature",
            "target_controller": str(confirmation.get("metadata", {}).get("target_controller", "")),
            "target_signature_hash": str(confirmation.get("metadata", {}).get("target_signature_hash", "")),
        }
        self._append({
            "event_id": confirmation_event_id,
            "event_type": "CONTROLLER_CONFIRMED",
            "agent_id": shared_metadata["target_agent_id"],
            "platform_id": str(confirmation["platform_id"]),
            "counterparty_id": shared_metadata["source_agent_id"],
            "category": "agent_identity",
            "provenance": "counterparty_confirmed",
            "verification_status": "finalized",
            "evidence_uri": str(confirmation.get("evidence_uri", "")),
            "evidence_hash": str(confirmation.get("evidence_hash", "")),
            "references": [proposal_id],
            "metadata": shared_metadata,
        })
        self._append({
            "event_id": link_event_id,
            "event_type": "IDENTITY_LINKED",
            "agent_id": shared_metadata["source_agent_id"],
            "platform_id": str(proposal["platform_id"]),
            "counterparty_id": shared_metadata["target_agent_id"],
            "category": "agent_identity",
            "provenance": "counterparty_confirmed",
            "verification_status": "finalized",
            "references": [proposal_id, confirmation_event_id],
            "metadata": shared_metadata,
        })

    @gl.public.write
    def challenge_identity_binding(self, challenge_json: str) -> None:
        challenge = self._object(challenge_json)
        proposal_id = str(challenge.get("proposal_event_id", ""))
        if proposal_id not in self.events:
            raise gl.vm.UserError("[EXPECTED] Unknown identity binding proposal")
        proposal = json.loads(self.events[proposal_id])
        challenge["event_type"] = "IDENTITY_CHALLENGED"
        challenge["provenance"] = "challenged"
        challenge["verification_status"] = "pending"
        challenge["references"] = [proposal_id]
        self._append(challenge)
        evaluation_payload = json.dumps({
            "binding_proposal": proposal,
            "challenge_reason": challenge.get("metadata", {}).get("reason", ""),
            "challenge_evidence_uri": challenge.get("evidence_uri", ""),
            "challenge_evidence_hash": challenge.get("evidence_hash", ""),
        }, sort_keys=True)

        def evaluate() -> str:
            raw = gl.nondet.exec_prompt(
                "Evaluate whether two claimed AI-agent identities are controlled by the same legitimate controller. "
                "Inspect the supplied identity claims, signature-proof metadata, challenge, and external evidence. "
                "Return only JSON with outcome (identity_link_valid, identity_link_false, or inconclusive), "
                "confidence_bps (0-10000), and reasoning_summary. Treat missing or contradictory proof as inconclusive.\n\n"
                + evaluation_payload,
                response_format="json",
            )
            parsed = json.loads(raw) if isinstance(raw, str) else raw
            outcome = str(parsed.get("outcome", "inconclusive")).lower()
            if outcome not in ["identity_link_valid", "identity_link_false", "inconclusive"]:
                outcome = "inconclusive"
            return json.dumps({
                "outcome": outcome,
                "confidence_bps": max(0, min(10000, int(parsed.get("confidence_bps", 0)))),
                "reasoning_summary": str(parsed.get("reasoning_summary", ""))[:1200],
            }, sort_keys=True)

        judgment = json.loads(gl.eq_principle.prompt_comparative(
            evaluate,
            principle=(
                "The outcome must match exactly. Confidence may differ by at most 1500 basis points. "
                "Reasoning must identify materially the same controller proof, ownership conflict, or missing evidence."
            ),
        ))
        metadata = proposal.get("metadata", {})
        judgment["source_agent_id"] = str(metadata.get("source_agent_id", proposal.get("agent_id", "")))
        judgment["target_agent_id"] = str(metadata.get("target_agent_id", proposal.get("counterparty_id", "")))
        judgment_event_id = str(challenge["metadata"]["judgment_event_id"])
        self._append({
            "event_id": judgment_event_id,
            "event_type": "IDENTITY_JUDGMENT_FINALIZED",
            "agent_id": judgment["source_agent_id"],
            "platform_id": str(proposal["platform_id"]),
            "counterparty_id": judgment["target_agent_id"],
            "category": "agent_identity",
            "provenance": "genlayer_verified",
            "verification_status": "finalized",
            "evidence_uri": str(challenge.get("evidence_uri", "")),
            "evidence_hash": str(challenge.get("evidence_hash", "")),
            "references": [proposal_id, str(challenge["event_id"])],
            "metadata": judgment,
        })
        resolution_type = "IDENTITY_LINK_FINALIZED" if judgment["outcome"] == "identity_link_valid" else "IDENTITY_LINK_REJECTED"
        resolution_provenance = "genlayer_verified" if resolution_type == "IDENTITY_LINK_FINALIZED" else "superseded"
        resolution_status = "finalized" if resolution_type == "IDENTITY_LINK_FINALIZED" else "superseded"
        self._append({
            "event_id": str(challenge["metadata"]["resolution_event_id"]),
            "event_type": resolution_type,
            "agent_id": judgment["source_agent_id"],
            "platform_id": str(proposal["platform_id"]),
            "counterparty_id": judgment["target_agent_id"],
            "category": "agent_identity",
            "provenance": resolution_provenance,
            "verification_status": resolution_status,
            "evidence_uri": str(challenge.get("evidence_uri", "")),
            "evidence_hash": str(challenge.get("evidence_hash", "")),
            "references": [proposal_id, judgment_event_id],
            "metadata": {
                "source_agent_id": judgment["source_agent_id"],
                "target_agent_id": judgment["target_agent_id"],
                "outcome": judgment["outcome"],
                "judgment_event_id": judgment_event_id,
            },
        })

    @gl.public.write
    def challenge_attestation(self, challenge_json: str) -> None:
        challenge = self._object(challenge_json)
        original_id = str(challenge.get("attestation_event_id", ""))
        if original_id not in self.events:
            raise gl.vm.UserError("[EXPECTED] Unknown attestation")
        original = json.loads(self.events[original_id])
        original_value = int(original.get("metadata", {}).get("value", 0))
        challenge["event_type"] = "EVENT_CHALLENGED"
        challenge["provenance"] = "challenged"
        challenge["verification_status"] = "pending"
        challenge["references"] = [original_id]
        self._append(challenge)

        evaluation_payload = json.dumps({
            "attestation": original,
            "challenge_reason": challenge.get("metadata", {}).get("reason", ""),
            "challenge_evidence_uri": challenge.get("evidence_uri", ""),
            "challenge_evidence_hash": challenge.get("evidence_hash", ""),
        }, sort_keys=True)

        def evaluate() -> str:
            raw = gl.nondet.exec_prompt(
                "Evaluate a challenged marketplace reputation attestation using the supplied evidence. "
                "Return only JSON with outcome (attestation_valid, attestation_partially_valid, "
                "attestation_false, or inconclusive), valid_value as a non-negative integer no greater "
                "than the reported value, confidence_bps (0-10000), and reasoning_summary.\n\n" + evaluation_payload,
                response_format="json",
            )
            parsed = json.loads(raw) if isinstance(raw, str) else raw
            outcome = str(parsed.get("outcome", "inconclusive")).lower()
            if outcome not in ["attestation_valid", "attestation_partially_valid", "attestation_false", "inconclusive"]:
                outcome = "inconclusive"
            valid_value = max(0, min(original_value, int(parsed.get("valid_value", 0))))
            if outcome == "attestation_valid":
                valid_value = original_value
            if outcome == "attestation_false":
                valid_value = 0
            return json.dumps({
                "outcome": outcome,
                "valid_value": valid_value,
                "reported_value": original_value,
                "confidence_bps": max(0, min(10000, int(parsed.get("confidence_bps", 0)))),
                "reasoning_summary": str(parsed.get("reasoning_summary", ""))[:1200],
            }, sort_keys=True)

        judgment = json.loads(gl.eq_principle.prompt_comparative(
            evaluate,
            principle=(
                "The outcome must match exactly. Valid values may differ by at most 2. "
                "Confidence may differ by at most 1500 basis points. Reasoning must identify "
                "materially the same evidence and discrepancy."
            ),
        ))
        judgment_event_id = str(challenge["metadata"]["judgment_event_id"])
        self._append({
            "event_id": judgment_event_id,
            "event_type": "ATTESTATION_JUDGMENT_FINALIZED",
            "agent_id": str(original["agent_id"]),
            "platform_id": str(original["platform_id"]),
            "category": str(original.get("category", "research")),
            "provenance": "genlayer_verified",
            "verification_status": "finalized",
            "evidence_uri": str(challenge.get("evidence_uri", "")),
            "evidence_hash": str(challenge.get("evidence_hash", "")),
            "references": [original_id, str(challenge["event_id"])],
            "metadata": judgment,
        })
        if judgment["outcome"] in ["attestation_partially_valid", "attestation_false"]:
            self._append({
                "event_id": str(challenge["metadata"]["superseded_event_id"]),
                "event_type": "EVENT_SUPERSEDED",
                "agent_id": str(original["agent_id"]),
                "platform_id": str(original["platform_id"]),
                "category": str(original.get("category", "research")),
                "provenance": "superseded",
                "verification_status": "superseded",
                "references": [original_id],
                "metadata": {"judgment_event_id": judgment_event_id},
            })
        if judgment["valid_value"] > 0 and judgment["outcome"] == "attestation_partially_valid":
            replacement_metadata = dict(original.get("metadata", {}))
            replacement_metadata["value"] = int(judgment["valid_value"])
            replacement_metadata["corrects_event_id"] = original_id
            self._append({
                "event_id": str(challenge["metadata"]["replacement_event_id"]),
                "event_type": "REPUTATION_ATTESTED",
                "agent_id": str(original["agent_id"]),
                "platform_id": str(original["platform_id"]),
                "category": str(original.get("category", "research")),
                "provenance": "genlayer_verified",
                "verification_status": "finalized",
                "evidence_uri": str(original.get("evidence_uri", "")),
                "evidence_hash": str(original.get("evidence_hash", "")),
                "references": [original_id, judgment_event_id],
                "metadata": replacement_metadata,
            })

    @gl.public.write
    def open_challenge(self, event_json: str) -> None:
        event = self._object(event_json)
        event["event_type"] = "EVENT_CHALLENGED"
        event["provenance"] = "challenged"
        event["verification_status"] = "pending"
        self._append(event)

    @gl.public.write
    def evaluate_dispute(self, dispute_json: str) -> None:
        dispute = self._object(dispute_json)
        dispute_payload = json.dumps(dispute, sort_keys=True)
        dispute_id = str(dispute["dispute_id"])
        if dispute_id in self.disputes:
            raise gl.vm.UserError("[EXPECTED] Dispute already exists")
        self.disputes[dispute_id] = json.dumps(dispute, sort_keys=True)
        self._append({
            "event_id": str(dispute["dispute_event_id"]),
            "event_type": "DISPUTE_OPENED",
            "agent_id": str(dispute["agent_id"]),
            "platform_id": str(dispute["platform_id"]),
            "job_id": str(dispute["job_id"]),
            "dispute_id": dispute_id,
            "counterparty_id": str(dispute.get("claimant", "requester")),
            "category": str(dispute.get("category", "research")),
            "provenance": "platform_reported",
            "verification_status": "pending",
            "evidence_uri": str(dispute.get("evidence_uri", "")),
            "evidence_hash": str(dispute.get("evidence_hash", "")),
            "references": dispute.get("references", []),
            "metadata": {"reason": str(dispute.get("reason", ""))},
        })

        def evaluate() -> str:
            prompt = (
                "Evaluate this disputed AI research job. Inspect all supplied web evidence. "
                "Return only JSON with verdict (satisfied, partially_satisfied, failed, fraudulent, or inconclusive), "
                "confidence_bps (0-10000), and reasoning_summary.\n\n" + dispute_payload
            )
            raw = gl.nondet.exec_prompt(prompt, response_format="json")
            if isinstance(raw, str):
                parsed = json.loads(raw.replace("```json", "").replace("```", ""))
            else:
                parsed = raw
            verdict = str(parsed.get("verdict", "inconclusive")).lower()
            if verdict not in ["satisfied", "partially_satisfied", "failed", "fraudulent", "inconclusive"]:
                verdict = "inconclusive"
            return json.dumps({
                "verdict": verdict,
                "confidence_bps": max(0, min(10000, int(parsed.get("confidence_bps", 0)))),
                "reasoning_summary": str(parsed.get("reasoning_summary", ""))[:1200],
            }, sort_keys=True)

        judgment = json.loads(gl.eq_principle.prompt_comparative(
            evaluate,
            principle=(
                "The verdict must match exactly. Confidence may differ by at most 1500 basis points. "
                "Reasoning may differ in wording but must identify materially the same task failures, "
                "citation problems, fabrication, or lack of evidence."
            ),
        ))
        judgment["dispute_id"] = dispute_id
        judgment["agent_id"] = str(dispute["agent_id"])
        judgment["platform_id"] = str(dispute["platform_id"])
        judgment["job_id"] = str(dispute["job_id"])
        judgment["status"] = "provisional"
        judgment["appeal_state"] = "open"
        judgment["provisional_event_id"] = str(dispute["provisional_event_id"])
        self.judgments[dispute_id] = json.dumps(judgment, sort_keys=True)
        self._append({
            "event_id": str(dispute["provisional_event_id"]),
            "event_type": "JUDGMENT_PROVISIONAL",
            "agent_id": judgment["agent_id"],
            "platform_id": judgment["platform_id"],
            "job_id": judgment["job_id"],
            "dispute_id": dispute_id,
            "category": str(dispute.get("category", "research")),
            "provenance": "genlayer_provisional",
            "verification_status": "provisional",
            "evidence_uri": str(dispute.get("evidence_uri", "")),
            "evidence_hash": str(dispute.get("evidence_hash", "")),
            "references": [str(dispute["dispute_event_id"])],
            "metadata": judgment,
        })

    @gl.public.write
    def finalize_judgment(self, dispute_id: str, event_id: str, supersedes_event_id: str) -> None:
        if dispute_id not in self.judgments:
            raise gl.vm.UserError("[EXPECTED] Unknown judgment")
        judgment = json.loads(self.judgments[dispute_id])
        if str(judgment["status"]) != "provisional":
            raise gl.vm.UserError("[EXPECTED] Judgment is not provisional")
        judgment["status"] = "finalized"
        judgment["appeal_state"] = "closed"
        judgment["superseded_event_reference"] = supersedes_event_id
        self.judgments[dispute_id] = json.dumps(judgment, sort_keys=True)
        self._append({
            "event_id": event_id,
            "event_type": "JUDGMENT_FINALIZED",
            "agent_id": judgment["agent_id"],
            "platform_id": judgment["platform_id"],
            "job_id": judgment["job_id"],
            "dispute_id": dispute_id,
            "category": "research",
            "provenance": "genlayer_verified",
            "verification_status": "finalized",
            "references": [supersedes_event_id],
            "metadata": judgment,
        })

    @gl.public.write
    def record_appeal_resolution(self, appeal_json: str) -> None:
        appeal = self._object(appeal_json)
        dispute_id = str(appeal.get("dispute_id", ""))
        if dispute_id not in self.judgments:
            raise gl.vm.UserError("[EXPECTED] Unknown judgment")
        judgment = json.loads(self.judgments[dispute_id])
        if str(judgment.get("status", "")) not in ["provisional", "appealed"]:
            raise gl.vm.UserError("[EXPECTED] Judgment is not appealable")

        original_verdict = str(appeal.get("original_verdict", "inconclusive"))
        final_verdict = str(judgment.get("verdict", "inconclusive"))
        provisional_event_id = str(appeal["provisional_event_id"])
        appeal_event_id = str(appeal["appeal_event_id"])
        resolved_event_id = str(appeal["resolved_event_id"])
        outcome_event_id = str(appeal["outcome_event_id"])
        superseded_event_id = str(appeal["superseded_event_id"])
        final_event_id = str(appeal["final_event_id"])
        outcome_type = "JUDGMENT_UPHELD" if final_verdict == original_verdict else "JUDGMENT_OVERTURNED"
        appeal_metadata = {
            "original_verdict": original_verdict,
            "final_verdict": final_verdict,
            "reason": str(appeal.get("reason", "")),
            "bond_amount": str(appeal.get("bond_amount", "")),
            "protocol_transaction_hash": str(appeal.get("protocol_transaction_hash", "")),
            "protocol_status": str(appeal.get("protocol_status", "FINALIZED")),
            "protocol_round": int(appeal.get("protocol_round", 1)),
        }
        common = {
            "agent_id": str(judgment["agent_id"]),
            "platform_id": str(judgment["platform_id"]),
            "job_id": str(judgment["job_id"]),
            "dispute_id": dispute_id,
            "category": "research",
            "evidence_uri": str(appeal.get("evidence_uri", "")),
            "evidence_hash": str(appeal.get("evidence_hash", "")),
        }
        self._append({
            **common,
            "event_id": appeal_event_id,
            "event_type": "APPEAL_SUBMITTED",
            "provenance": "challenged",
            "verification_status": "appealed",
            "references": [provisional_event_id],
            "metadata": appeal_metadata,
        })
        self._append({
            **common,
            "event_id": resolved_event_id,
            "event_type": "APPEAL_RESOLVED",
            "provenance": "genlayer_verified",
            "verification_status": "finalized",
            "references": [provisional_event_id, appeal_event_id],
            "metadata": appeal_metadata,
        })
        self._append({
            **common,
            "event_id": outcome_event_id,
            "event_type": outcome_type,
            "provenance": "genlayer_verified",
            "verification_status": "finalized",
            "references": [provisional_event_id, appeal_event_id, resolved_event_id],
            "metadata": appeal_metadata,
        })
        self._append({
            **common,
            "event_id": superseded_event_id,
            "event_type": "EVENT_SUPERSEDED",
            "provenance": "superseded",
            "verification_status": "superseded",
            "references": [provisional_event_id],
            "metadata": {"superseded_by": outcome_event_id, **appeal_metadata},
        })
        judgment["status"] = "finalized"
        judgment["appeal_state"] = "resolved"
        judgment["appeal_outcome"] = "upheld" if outcome_type == "JUDGMENT_UPHELD" else "overturned"
        judgment["superseded_event_reference"] = provisional_event_id
        judgment["protocol_transaction_hash"] = appeal_metadata["protocol_transaction_hash"]
        judgment["protocol_round"] = appeal_metadata["protocol_round"]
        self.judgments[dispute_id] = json.dumps(judgment, sort_keys=True)
        self._append({
            **common,
            "event_id": final_event_id,
            "event_type": "JUDGMENT_FINALIZED",
            "provenance": "genlayer_verified",
            "verification_status": "finalized",
            "references": [provisional_event_id, appeal_event_id, resolved_event_id, outcome_event_id],
            "metadata": judgment,
        })

    @gl.public.write
    def append_verified_event(self, event_json: str) -> None:
        event = self._object(event_json)
        event["provenance"] = "genlayer_verified"
        event["verification_status"] = "finalized"
        self._append(event)

    @gl.public.write
    def evaluate_responsibility(self, case_json: str) -> None:
        case = self._object(case_json)
        case_id = str(case["responsibility_case_id"])
        if case_id in self.responsibility_cases:
            raise gl.vm.UserError("[EXPECTED] Responsibility case already exists")
        case_payload = json.dumps(case, sort_keys=True)

        self._append({
            "event_id": str(case["dispute_event_id"]),
            "event_type": "RESPONSIBILITY_DISPUTED",
            "agent_id": str(case["principal_agent_id"]),
            "platform_id": str(case["platform_id"]),
            "job_id": str(case["job_id"]),
            "dispute_id": case_id,
            "counterparty_id": str(case["worker_agent_id"]),
            "category": str(case.get("category", "research")),
            "provenance": "platform_reported",
            "verification_status": "pending",
            "evidence_uri": str(case.get("evidence_uri", "")),
            "evidence_hash": str(case.get("evidence_hash", "")),
            "metadata": {"delegation_id": str(case["delegation_id"]), "reason": str(case.get("reason", ""))},
        })

        def evaluate() -> str:
            prompt = (
                "Attribute responsibility for this delegated AI-agent failure. Inspect the signed authority scope, "
                "subdelegation permission, disclosure requirement, prior warnings, review duty, output, and evidence. "
                "Do not split liability automatically. Return only JSON with outcome (worker_primary, delegator_primary, "
                "shared_responsibility, unauthorized_subdelegation, tool_failure, no_fault, or inconclusive), "
                "delegator_responsibility_bps, worker_responsibility_bps, impact_kind, confidence_bps, and reasoning_summary. "
                "For accountable outcomes the two responsibility values must total 10000. For tool_failure, no_fault, or "
                "inconclusive both must be zero.\n\n" + case_payload
            )
            raw = gl.nondet.exec_prompt(prompt, response_format="json")
            parsed = json.loads(raw.replace("```json", "").replace("```", "")) if isinstance(raw, str) else raw
            outcome = str(parsed.get("outcome", "inconclusive")).lower()
            allowed = ["worker_primary", "delegator_primary", "shared_responsibility", "unauthorized_subdelegation", "tool_failure", "no_fault", "inconclusive"]
            if outcome not in allowed:
                outcome = "inconclusive"
            delegator_bps = max(0, min(10000, int(parsed.get("delegator_responsibility_bps", 0))))
            worker_bps = max(0, min(10000, int(parsed.get("worker_responsibility_bps", 0))))
            if outcome in ["tool_failure", "no_fault", "inconclusive"]:
                delegator_bps = 0
                worker_bps = 0
            elif delegator_bps + worker_bps != 10000:
                delegator_bps = 5000
                worker_bps = 5000
            if outcome == "worker_primary" and worker_bps <= delegator_bps:
                delegator_bps, worker_bps = 2000, 8000
            if outcome == "delegator_primary" and delegator_bps <= worker_bps:
                delegator_bps, worker_bps = 8000, 2000
            return json.dumps({
                "outcome": outcome,
                "delegator_responsibility_bps": delegator_bps,
                "worker_responsibility_bps": worker_bps,
                "impact_kind": str(parsed.get("impact_kind", "delivery_failure"))[:80],
                "confidence_bps": max(0, min(10000, int(parsed.get("confidence_bps", 0)))),
                "reasoning_summary": str(parsed.get("reasoning_summary", ""))[:1200],
            }, sort_keys=True)

        judgment = json.loads(gl.eq_principle.prompt_comparative(
            evaluate,
            principle=(
                "The outcome must match exactly. Delegator and worker responsibility allocations may each differ by at "
                "most 1000 basis points and must obey the outcome constraints. Reasoning must identify materially the "
                "same authority, disclosure, review, subdelegation, or tool-failure facts."
            ),
        ))
        judgment.update({
            "responsibility_case_id": case_id,
            "delegation_id": str(case["delegation_id"]),
            "principal_agent_id": str(case["principal_agent_id"]),
            "worker_agent_id": str(case["worker_agent_id"]),
            "platform_id": str(case["platform_id"]),
            "job_id": str(case["job_id"]),
            "status": "provisional",
            "appeal_state": "open",
        })
        self.responsibility_cases[case_id] = json.dumps(judgment, sort_keys=True)
        for role in ["principal", "worker"]:
            agent_id = judgment["principal_agent_id"] if role == "principal" else judgment["worker_agent_id"]
            bps = judgment["delegator_responsibility_bps"] if role == "principal" else judgment["worker_responsibility_bps"]
            metadata = {**judgment, "role": "delegator" if role == "principal" else "worker", "responsibility_bps": bps}
            self._append({
                "event_id": str(case[role + "_provisional_event_id"]),
                "event_type": "RESPONSIBILITY_JUDGMENT_PROVISIONAL",
                "agent_id": agent_id,
                "platform_id": judgment["platform_id"],
                "job_id": judgment["job_id"],
                "dispute_id": case_id,
                "counterparty_id": judgment["worker_agent_id"] if role == "principal" else judgment["principal_agent_id"],
                "category": str(case.get("category", "research")),
                "provenance": "genlayer_provisional",
                "verification_status": "provisional",
                "evidence_uri": str(case.get("evidence_uri", "")),
                "evidence_hash": str(case.get("evidence_hash", "")),
                "references": [str(case["dispute_event_id"])],
                "metadata": metadata,
            })

    @gl.public.write
    def finalize_responsibility(self, resolution_json: str) -> None:
        resolution = self._object(resolution_json)
        case_id = str(resolution["responsibility_case_id"])
        if case_id not in self.responsibility_cases:
            raise gl.vm.UserError("[EXPECTED] Unknown responsibility case")
        judgment = json.loads(self.responsibility_cases[case_id])
        if str(judgment.get("status", "")) not in ["provisional", "appealed"]:
            raise gl.vm.UserError("[EXPECTED] Responsibility judgment is not finalizable")
        appealed = bool(resolution.get("appealed", False))
        references = [str(resolution["principal_provisional_event_id"]), str(resolution["worker_provisional_event_id"])]
        if appealed:
            appeal_event_id = str(resolution["appeal_event_id"])
            self._append({
                "event_id": appeal_event_id,
                "event_type": "RESPONSIBILITY_APPEALED",
                "agent_id": judgment["principal_agent_id"],
                "platform_id": judgment["platform_id"],
                "job_id": judgment["job_id"],
                "dispute_id": case_id,
                "counterparty_id": judgment["worker_agent_id"],
                "category": "research",
                "provenance": "challenged",
                "verification_status": "appealed",
                "references": references,
                "evidence_uri": str(resolution.get("evidence_uri", "")),
                "evidence_hash": str(resolution.get("evidence_hash", "")),
                "metadata": {**judgment, "reason": str(resolution.get("appeal_reason", ""))},
            })
            references.append(appeal_event_id)
        judgment["status"] = "finalized"
        judgment["appeal_state"] = "resolved" if appealed else "closed"
        judgment["protocol_transaction_hash"] = str(resolution.get("protocol_transaction_hash", ""))
        judgment["protocol_round"] = int(resolution.get("protocol_round", 0))
        self.responsibility_cases[case_id] = json.dumps(judgment, sort_keys=True)
        for role in ["principal", "worker"]:
            agent_id = judgment["principal_agent_id"] if role == "principal" else judgment["worker_agent_id"]
            bps = judgment["delegator_responsibility_bps"] if role == "principal" else judgment["worker_responsibility_bps"]
            role_name = "delegator" if role == "principal" else "worker"
            metadata = {**judgment, "role": role_name, "responsibility_bps": bps}
            final_id = str(resolution[role + "_final_event_id"])
            self._append({
                "event_id": final_id,
                "event_type": "RESPONSIBILITY_JUDGMENT_FINALIZED",
                "agent_id": agent_id,
                "platform_id": judgment["platform_id"],
                "job_id": judgment["job_id"],
                "dispute_id": case_id,
                "counterparty_id": judgment["worker_agent_id"] if role == "principal" else judgment["principal_agent_id"],
                "category": "research",
                "provenance": "genlayer_verified",
                "verification_status": "finalized",
                "references": references,
                "metadata": metadata,
            })
            self._append({
                "event_id": str(resolution[role + "_liability_event_id"]),
                "event_type": "LIABILITY_APPORTIONED",
                "agent_id": agent_id,
                "platform_id": judgment["platform_id"],
                "job_id": judgment["job_id"],
                "dispute_id": case_id,
                "counterparty_id": judgment["worker_agent_id"] if role == "principal" else judgment["principal_agent_id"],
                "category": "research",
                "provenance": "genlayer_verified",
                "verification_status": "finalized",
                "references": [final_id],
                "metadata": metadata,
            })

    @gl.public.view
    def get_responsibility_case(self, case_id: str) -> str:
        if case_id not in self.responsibility_cases:
            return ""
        return self.responsibility_cases[case_id]

    @gl.public.view
    def get_event(self, event_id: str) -> str:
        if event_id not in self.events:
            return ""
        return self.events[event_id]

    @gl.public.view
    def get_event_count(self) -> int:
        if "event_count" not in self.ledger_metadata:
            return 0
        return int(self.ledger_metadata["event_count"])

    @gl.public.view
    def get_agent_events(self, agent_id: str, cursor: int, limit: int) -> str:
        matches = []
        event_count = self.get_event_count()
        for index in range(event_count):
            event_id = self.event_order[str(index)]
            event = json.loads(self.events[event_id])
            if str(event["agent_id"]) == agent_id:
                matches.append(event)
        page = matches[cursor:cursor + min(limit, 100)]
        return json.dumps({"events": page, "next_cursor": cursor + len(page)}, sort_keys=True)

    @gl.public.view
    def get_events_after(self, last_event_id: str, limit: int) -> str:
        start = 0
        event_count = self.get_event_count()
        if last_event_id != "" and last_event_id != "__START__":
            for index in range(event_count):
                if self.event_order[str(index)] == last_event_id:
                    start = index + 1
                    break
        result = []
        end = min(event_count, start + min(limit, 100))
        for index in range(start, end):
            result.append(json.loads(self.events[self.event_order[str(index)]]))
        return json.dumps({"events": result}, sort_keys=True)

    @gl.public.view
    def get_dispute(self, dispute_id: str) -> str:
        if dispute_id not in self.disputes:
            return ""
        return self.disputes[dispute_id]

    @gl.public.view
    def get_judgment(self, dispute_id: str) -> str:
        if dispute_id not in self.judgments:
            return ""
        return self.judgments[dispute_id]

    def _append(self, event) -> None:
        event_id = str(event["event_id"])
        if event_id in self.events:
            raise gl.vm.UserError("[EXPECTED] Event already exists")
        if "references" not in event:
            event["references"] = []
        if "metadata" not in event:
            event["metadata"] = {}
        if "counterparty_id" not in event:
            event["counterparty_id"] = ""
        if "evidence_uri" not in event:
            event["evidence_uri"] = ""
        if "evidence_hash" not in event:
            event["evidence_hash"] = ""
        if "block_number" not in event:
            event["block_number"] = 0
        if "occurred_at" not in event:
            event["occurred_at"] = str(gl.message_raw["datetime"])
        elif str(event["occurred_at"]) == "":
            event["occurred_at"] = str(gl.message_raw["datetime"])
        self.events[event_id] = json.dumps(event, sort_keys=True)
        event_count = self.get_event_count()
        self.event_order[str(event_count)] = event_id
        self.ledger_metadata["event_count"] = str(event_count + 1)

    def _object(self, value):
        if isinstance(value, str):
            return json.loads(value)
        return value
