import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import Base, SessionLocal, engine
from app.indexer import GenLayerEventIndexer


parser = argparse.ArgumentParser()
parser.add_argument("--once", action="store_true")
args = parser.parse_args()
indexer = GenLayerEventIndexer()
Base.metadata.create_all(engine)
if args.once:
    with SessionLocal() as db:
        print(indexer.sync_once(db))
else:
    indexer.run_forever(SessionLocal)
