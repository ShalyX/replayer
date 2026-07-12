from __future__ import annotations

import time
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .genlayer import GenLayerClient
from .ledger import append_event, rebuild_all_projections
from .models import IndexerCheckpoint, ReputationEvent


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
            existing = db.scalars(select(ReputationEvent).where(ReputationEvent.event_id == event_id)).first()
            transaction_hash = item.get("transaction_hash") or (existing.transaction_hash if existing else None)
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
                checkpoint.last_processed_event_id = event_id
                checkpoint.last_processed_block = max(checkpoint.last_processed_block, int(item.get("block_number") or 0))
                continue
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
                occurred_at=datetime.fromisoformat(item["occurred_at"]) if item.get("occurred_at") else datetime.utcnow(),
                metadata={**item.get("metadata", {}), "contract_readback_verified": True},
            )
            checkpoint.last_processed_event_id = event_id
            checkpoint.last_processed_block = max(checkpoint.last_processed_block, int(item.get("block_number") or 0))
            indexed += 1
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
