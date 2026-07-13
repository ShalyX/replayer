# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

import json
from genlayer import *


class ReputationEventLedger(gl.Contract):
    events: TreeMap[str, str]
    event_order: TreeMap[str, str]
    ledger_metadata: TreeMap[str, str]
    disputes: TreeMap[str, str]
    judgments: TreeMap[str, str]

    def __init__(self):
        pass

    @gl.public.write
    def append_platform_event(self, event_json: str) -> None:
        event = self._object(event_json)
        allowed = ["AGENT_REGISTERED", "JOB_CREATED", "DELIVERABLE_SUBMITTED", "JOB_ACCEPTED", "JOB_COMPLETED", "EVENT_ATTESTED", "REPUTATION_ATTESTED", "PLATFORM_IDENTITY_VERIFIED"]
        if str(event.get("event_type", "")) not in allowed:
            raise gl.vm.UserError("[EXPECTED] Unsupported platform event")
        event["provenance"] = "platform_reported"
        event["verification_status"] = "uncontested" if event["event_type"] == "REPUTATION_ATTESTED" else "finalized"
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
            "references": dispute.get("references", []),
            "metadata": judgment,
        })

    @gl.public.write
    def finalize_judgment(self, dispute_id: str, event_id: str, supersedes_event_id: str) -> None:
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
    def append_verified_event(self, event_json: str) -> None:
        event = self._object(event_json)
        event["provenance"] = "genlayer_verified"
        event["verification_status"] = "finalized"
        self._append(event)

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
            event["occurred_at"] = ""
        self.events[event_id] = json.dumps(event, sort_keys=True)
        event_count = self.get_event_count()
        self.event_order[str(event_count)] = event_id
        self.ledger_metadata["event_count"] = str(event_count + 1)

    def _object(self, value):
        if isinstance(value, str):
            return json.loads(value)
        return value
