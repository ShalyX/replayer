import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, select

from app.database import Base, SessionLocal, engine
from app.ledger import projection_dict, rebuild_all_projections
from app.models import AgentReputationProjection


def normalized(db):
    rows = db.scalars(select(AgentReputationProjection).order_by(
        AgentReputationProjection.agent_id,
        AgentReputationProjection.projection_name,
        AgentReputationProjection.projection_version,
    )).all()
    return [{key: value for key, value in projection_dict(row).items() if key != "calculated_at"} for row in rows]


Base.metadata.create_all(engine)
with SessionLocal() as db:
    rebuild_all_projections(db)
    db.commit()
    before = normalized(db)
    db.execute(delete(AgentReputationProjection))
    db.commit()
    rebuild_all_projections(db)
    db.commit()
    after = normalized(db)
    if before != after:
        raise SystemExit("Projection replay mismatch\n" + json.dumps({"before": before, "after": after}, indent=2))
    print(f"Ledger rebuild deterministic for {len(after)} agent projections")
