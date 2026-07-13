import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, select

from app.database import Base, SessionLocal, engine
from app.ledger import projection_dict, rebuild_all_projections
from app.models import AgentReputationProjection, PlatformCredibilityProjection


def normalized(db):
    rows = db.scalars(select(AgentReputationProjection).order_by(
        AgentReputationProjection.agent_id,
        AgentReputationProjection.projection_name,
        AgentReputationProjection.projection_version,
    )).all()
    agents = [{key: value for key, value in projection_dict(row).items() if key != "calculated_at"} for row in rows]
    platforms = db.scalars(select(PlatformCredibilityProjection).order_by(
        PlatformCredibilityProjection.platform_id, PlatformCredibilityProjection.projection_version
    )).all()
    return {
        "agents": agents,
        "platforms": [{
            "platform_id": row.platform_id, "version": row.projection_version,
            "score": row.credibility_score, "status": row.status,
            "attestations": row.attestations_issued, "confirmations": row.confirmations_received,
            "challenges": row.challenges, "overturns": row.overturns,
            "verified_identity": row.verified_identity, "details": row.details,
        } for row in platforms],
    }


Base.metadata.create_all(engine)
with SessionLocal() as db:
    rebuild_all_projections(db)
    db.commit()
    before = normalized(db)
    db.execute(delete(AgentReputationProjection))
    db.execute(delete(PlatformCredibilityProjection))
    db.commit()
    rebuild_all_projections(db)
    db.commit()
    after = normalized(db)
    if before != after:
        raise SystemExit("Projection replay mismatch\n" + json.dumps({"before": before, "after": after}, indent=2))
    print(f"Ledger rebuild deterministic for {len(after['agents'])} agent and {len(after['platforms'])} platform projections")
