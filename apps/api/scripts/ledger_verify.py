from sqlalchemy import select
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import Base, SessionLocal, engine
from app.ledger import PROVENANCE, VERIFICATION_STATUSES
from app.models import ReputationEvent, ReputationEventReference
from app.genlayer import GenLayerClient

Base.metadata.create_all(engine)
errors = []
client = GenLayerClient()
quarantined = 0
authoritative = 0
with SessionLocal() as db:
    events = db.scalars(select(ReputationEvent)).all()
    ids = {event.event_id for event in events}
    for event in events:
        if event.contract_address and event.event_metadata.get("contract_readback_verified") is not True:
            quarantined += 1
            continue
        authoritative += 1
        if event.provenance not in PROVENANCE:
            errors.append(f"{event.event_id}: invalid provenance")
        if event.verification_status not in VERIFICATION_STATUSES:
            errors.append(f"{event.event_id}: invalid verification status")
        if event.provenance.startswith("genlayer") and (not event.contract_address or not event.transaction_hash):
            errors.append(f"{event.event_id}: GenLayer provenance missing contract/transaction")
        if event.contract_address:
            try:
                contract_event = client.call_json("get_event", [event.event_id])
            except RuntimeError as exc:
                errors.append(f"{event.event_id}: contract read failed: {exc}")
                continue
            if not isinstance(contract_event, dict):
                errors.append(f"{event.event_id}: transaction recorded locally but event is absent from contract")
            elif contract_event.get("event_type") != event.event_type or contract_event.get("agent_id") != event.agent_id:
                errors.append(f"{event.event_id}: local event does not match contract state")
    for reference in db.scalars(select(ReputationEventReference)).all():
        if reference.event_id not in ids or reference.referenced_event_id not in ids:
            errors.append(f"broken reference: {reference.event_id} -> {reference.referenced_event_id}")
if errors:
    raise SystemExit("\n".join(errors))
print(f"Ledger verified: {authoritative} authoritative append-only events; {quarantined} quarantined legacy rows")
