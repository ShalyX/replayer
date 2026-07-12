import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import Base, SessionLocal, engine
from app.ledger import projection_dict, rebuild_all_projections

Base.metadata.create_all(engine)
with SessionLocal() as db:
    projections = rebuild_all_projections(db)
    db.commit()
    for projection in projections:
        print(projection_dict(projection))
