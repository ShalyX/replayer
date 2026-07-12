from __future__ import annotations

import re
import time
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .genlayer import GenLayerClient
from .ledger import append_event, rebuild_all_projections
from .models import (
    Agent,
    Deliverable,
    Dispute,
    IndexerCheckpoint,
    Job,
    Judgment,
    Platform,
    ReputationEvent,
    new_id,
)


class GenLayerEventIndexer:
    def __init__(self, client: GenLayerClient | None = None) -> None:
        self.client = client or GenLayerClient()

    def checkpoint(self, db: Session) -> IndexerCheckpoint:
        checkpoint = db.get(IndexerCheckpoint, self.client.contract_address)
        if not checkpoint:
            checkpoint = IndexerCheckpoint(
                contract_address=self.client.contract_address,
                last_processed_block=settings.genlayer_start_block,
            )
            db.add(checkpoint)
            db.flush()
        return checkpoint

    @staticmethod
    def _proof_transaction(event_id: str) -> str | None:
        transaction_hash = settings.genlayer_proof_transaction_hash
        if (
            event_id == settings.genlayer_proof_event_id
            and re.fullmatch(r"0x[a-fA-F0-9]{64}", transaction_hash)
        ):
            return transaction_hash
        return None

    def _materialize_read_models(self, db: Session, item: dict, occurred_at: datetime) -> None:
        """Rebuild mutable API read models from the ordered contract event stream."""
        event_type = str(item["event_type"])
        agent_id = str(item["agent_id"])
        platform_id = str(item["platform_id"])
        job_id = str(item.get("job_id") or "")
        dispute_id = str(item.get("dispute_id") or "")
        metadata = item.get("metadata") or {}

        if not db.get(Platform, platform_id):
            db.add(Platform(id=platform_id, name=platform_id, created_at=occurred_at))
            db.flush()

        agent = db.get(Agent, agent_id)
        if not agent:
            agent = Agent(
                id=agent_id,
                platform_id=platform_id,
                owner_wallet=str(metadata.get("owner_wallet") or ""),
                name=str(metadata.get("name") or agent_id),
                capabilities=metadata.get("capabilities") or [],
                metadata_uri=str(metadata.get("metadata_uri") or ""),
                created_at=occurred_at,
            )
            db.add(agent)
            db.flush()

        job = db.get(Job, job_id) if job_id else None
        if job_id and not job:
            job = Job(
                id=job_id,
                requester_id=str(item.get("counterparty_id") or metadata.get("claimant") or "unknown"),
                provider_agent_id=agent_id,
                platform_id=platform_id,
                task_spec=str(metadata.get("task_spec") or "Recovered from GenLayer event ledger"),
                category=str(item.get("category") or "research"),
                payment_amount=metadata.get("payment_amount") or 0,
                currency=str(metadata.get("currency") or "USDC"),
                created_at=occurred_at,
                updated_at=occurred_at,
            )
            db.add(job)
            db.flush()

        if job and event_type == "DELIVERABLE_SUBMITTED":
            if not db.scalars(select(Deliverable).where(Deliverable.job_id == job.id)).first():
                db.add(Deliverable(
                    id=str(metadata.get("deliverable_id") or new_id("deliv")),
                    job_id=job.id,
                    deliverable_uri=str(item.get("evidence_uri") or "ledger://recovered"),
                    summary=str(metadata.get("summary") or "Recovered from GenLayer event ledger"),
                    evidence_urls=metadata.get("evidence_urls") or [],
                    submitted_at=occurred_at,
                ))
            job.status = "submitted"
        elif job and event_type in {"JOB_ACCEPTED", "JOB_COMPLETED"}:
            job.status = "accepted"

        dispute = db.get(Dispute, dispute_id) if dispute_id else None
        if job and dispute_id and not dispute:
            dispute = Dispute(
                id=dispute_id,
                job_id=job.id,
                claimant=str(item.get("counterparty_id") or metadata.get("claimant") or "requester"),
                reason=str(metadata.get("reasoning_summary") or metadata.get("reason") or "Recovered GenLayer dispute"),
                evidence_uri=str(item.get("evidence_uri") or ""),
                status="open",
                opened_at=occurred_at,
            )
            db.add(dispute)
            db.flush()
            job.status = "disputed"

        if job and dispute and event_type == "JUDGMENT_FINALIZED":
            verdict = str(metadata.get("verdict") or "inconclusive")
            existing_judgment = db.scalars(select(Judgment).where(Judgment.job_id == job.id)).first()
            if not existing_judgment:
                db.add(Judgment(
                    id=new_id("judgment"),
                    job_id=job.id,
                    dispute_id=dispute.id,
                    verdict=verdict,
                    confidence_bps=int(metadata.get("confidence_bps") or 0),
                    reasoning_summary=str(metadata.get("reasoning_summary") or ""),
                    score_deltas=metadata.get("score_deltas") or {},
                    source="genlayer",
                    contract_address=self.client.contract_address,
                    tx_hash=str(item.get("transaction_hash") or ""),
                    verify_url=self.client.verify_url(str(item.get("transaction_hash") or "")) if item.get("transaction_hash") else "",
                    created_at=occurred_at,
                ))
            dispute.status = "resolved"
            job.status = f"judged_{verdict}"

        db.flush()

    def _restore_release_provenance(self, db: Session) -> None:
        event_id = settings.genlayer_proof_event_id
        transaction_hash = self._proof_transaction(event_id)
        if not event_id or not transaction_hash:
            return
        event = db.scalars(select(ReputationEvent).where(ReputationEvent.event_id == event_id)).first()
        if not event:
            return
        if not event.transaction_hash:
            contract_event = self.client.call_json("get_event", [event_id])
            if not isinstance(contract_event, dict) or str(contract_event.get("event_id")) != event_id:
                raise RuntimeError(f"Release proof event {event_id} was not readable from contract state")
            event.transaction_hash = transaction_hash
            event.contract_address = self.client.contract_address
            event.event_metadata = {**event.event_metadata, "contract_readback_verified": True}
        if event.job_id:
            judgment = db.scalars(select(Judgment).where(Judgment.job_id == event.job_id)).first()
            if judgment:
                judgment.tx_hash = transaction_hash
                judgment.verify_url = self.client.verify_url(transaction_hash)

    def sync_once(self, db: Session) -> dict:
        if not self.client.enabled():
            raise RuntimeError("Public runtime requires GENLAYER_MODE=live; indexer refused mock mode")
        checkpoint = self.checkpoint(db)
        # An explicit sentinel survives Windows/CLI argument parsing; the contract treats an unknown cursor as genesis.
        raw = self.client.call_json("get_events_after", [checkpoint.last_processed_event_id or "__START__", "100"])
        if raw in (None, ""):
            raise RuntimeError("GenLayer event read returned no data; checkpoint was not advanced")
        payload = raw if isinstance(raw, dict) else {"events": raw}
        events = payload.get("events", [])
        if isinstance(events, str):
            import json
            events = json.loads(events)
        indexed = 0
        for item in events:
            event_id = str(item["event_id"])
            occurred_at = datetime.fromisoformat(item["occurred_at"]) if item.get("occurred_at") else datetime.utcnow()
            existing = db.scalars(select(ReputationEvent).where(ReputationEvent.event_id == event_id)).first()
            transaction_hash = (
                item.get("transaction_hash")
                or (existing.transaction_hash if existing else None)
                or self._proof_transaction(event_id)
            )
            if not transaction_hash and item.get("dispute_id"):
                source_event = db.scalars(
                    select(ReputationEvent)
                    .where(
                        ReputationEvent.dispute_id == str(item["dispute_id"]),
                        ReputationEvent.transaction_hash.is_not(None),
                    )
                    .order_by(ReputationEvent.occurred_at)
                ).first()
                transaction_hash = source_event.transaction_hash if source_event else None
            if existing:
                existing.contract_address = self.client.contract_address
                existing.transaction_hash = transaction_hash
                existing.block_number = item.get("block_number") or existing.block_number
                existing.event_metadata = {**existing.event_metadata, "contract_readback_verified": True}
                if existing.event_type == "JUDGMENT_FINALIZED" and transaction_hash and existing.job_id:
                    judgment = db.scalars(select(Judgment).where(Judgment.job_id == existing.job_id)).first()
                    if judgment:
                        judgment.tx_hash = transaction_hash
                        judgment.verify_url = self.client.verify_url(transaction_hash)
                checkpoint.last_processed_event_id = event_id
                checkpoint.last_processed_block = max(checkpoint.last_processed_block, int(item.get("block_number") or 0))
                continue
            self._materialize_read_models(db, item, occurred_at)
            append_event(
                db,
                event_id=event_id,
                event_type=str(item["event_type"]),
                agent_id=str(item["agent_id"]),
                platform_id=str(item["platform_id"]),
                job_id=item.get("job_id") or None,
                dispute_id=item.get("dispute_id") or None,
                counterparty_id=item.get("counterparty_id") or None,
                category=item.get("category") or None,
                provenance=str(item["provenance"]),
                verification_status=str(item["verification_status"]),
                evidence_uri=item.get("evidence_uri") or None,
                evidence_hash=item.get("evidence_hash") or None,
                references=item.get("references", []),
                contract_address=self.client.contract_address,
                transaction_hash=transaction_hash,
                block_number=item.get("block_number"),
                occurred_at=occurred_at,
                metadata={**item.get("metadata", {}), "contract_readback_verified": True},
            )
            checkpoint.last_processed_event_id = event_id
            checkpoint.last_processed_block = max(checkpoint.last_processed_block, int(item.get("block_number") or 0))
            indexed += 1
        self._restore_release_provenance(db)
        rebuild_all_projections(db)
        checkpoint.last_sync_at = datetime.utcnow()
        checkpoint.updated_at = datetime.utcnow()
        db.commit()
        return {"indexed": indexed, **self.health(db)}

    def health(self, db: Session) -> dict:
        checkpoint = self.checkpoint(db)
        return {
            "status": "healthy" if checkpoint.last_sync_at else "starting",
            "contract_address": self.client.contract_address,
            "last_processed_block": checkpoint.last_processed_block,
            "last_processed_event_id": checkpoint.last_processed_event_id,
            "last_sync_at": checkpoint.last_sync_at.isoformat() if checkpoint.last_sync_at else None,
            "lag": 0,
        }

    def run_forever(self, session_factory) -> None:
        while True:
            with session_factory() as db:
                try:
                    self.sync_once(db)
                except Exception:
                    db.rollback()
            time.sleep(settings.genlayer_indexer_poll_interval)
