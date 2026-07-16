import hashlib
import hmac
import json
import secrets
import threading
import time
from datetime import datetime

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from .config import settings
from .database import Base, SessionLocal, engine, get_db
from .genlayer import GenLayerClient
from .indexer import GenLayerEventIndexer
from .identity import binding_message, normalize_identity, registration_message, verify_identity_signature
from .ledger import append_event, event_dict, identity_projection_dict, projection_dict, rebuild_all_identity_projections, rebuild_all_projections, rebuild_identity_projection, rebuild_platform_credibility, rebuild_projection
from .models import Agent, AgentIdentityProjection, AgentReputationProjection, Delegation, Deliverable, DemoRun, Dispute, Job, Judgment, Platform, PlatformCredibilityProjection, ReputationEvent, new_id
from .schemas import (
    AgentIdentityRegister, AgentRegister, AppealSubmit, AttestationConfirm, AttestationCreate, DeliverableSubmit,
    DelegatedOutputSubmit, DelegationAccept, DelegationCreate, DisputeOpen, EventChallenge,
    IdentityBindingChallenge, IdentityBindingConfirm, IdentityBindingPropose, JobCreate, PlatformIdentityVerify,
    PlatformRegister, ResponsibilityAppealSubmit, ResponsibilityDisputeOpen, TrustEvaluateRequest,
)

Base.metadata.create_all(bind=engine)


def ensure_dev_columns() -> None:
    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as conn:
        existing = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(judgments)").fetchall()}
        for name, ddl in {
            "contract_address": "ALTER TABLE judgments ADD COLUMN contract_address VARCHAR(80) DEFAULT ''",
            "tx_hash": "ALTER TABLE judgments ADD COLUMN tx_hash VARCHAR(120) DEFAULT ''",
            "verify_url": "ALTER TABLE judgments ADD COLUMN verify_url TEXT DEFAULT ''",
        }.items():
            if name not in existing:
                conn.exec_driver_sql(ddl)
        platform_columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(platforms)").fetchall()}
        if "api_key_hash" not in platform_columns:
            conn.exec_driver_sql("ALTER TABLE platforms ADD COLUMN api_key_hash VARCHAR(160) DEFAULT ''")


ensure_dev_columns()

app = FastAPI(title="Agent Reputation Registry API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

genlayer = GenLayerClient()
indexer = GenLayerEventIndexer(genlayer)
ADMIN_AUTH = {"type": "admin", "platform_id": None}


@app.exception_handler(RuntimeError)
def runtime_error_handler(request, exc: RuntimeError):
    import re

    detail = clean_runtime_error(str(exc))
    return JSONResponse(status_code=502, content={"detail": detail})


def clean_runtime_error(raw: str) -> str:
    import re

    tx_match = re.search(r"0x[a-fA-F0-9]{64}", raw)
    if "fetch failed" in raw or "UnknownRpcError" in raw:
        if tx_match:
            return (
                "GenLayer transaction was submitted, but RPC readback timed out. "
                f"Tx: {tx_match.group(0)}"
            )
        return "GenLayer RPC timed out during readback. Wait a moment and retry."
    detail = re.sub(r"private_key:\s*'[^']+'", "private_key: '<redacted>'", raw)
    detail = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", detail)
    detail = re.sub(r"Enter password to decrypt keystore:\s*\S*", "", detail)
    detail = re.sub(r"\*{2,}", "[hidden]", detail)
    detail = re.sub(r"\s+", " ", detail)
    return detail.strip()[-1000:]


def admin_key() -> str:
    return settings.admin_api_key or settings.api_key


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def generate_api_key() -> str:
    return f"rpl_test_{secrets.token_urlsafe(32)}"


def authenticate_key(x_api_key: str | None, db: Session) -> dict:
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing x-api-key")
    configured_admin_key = admin_key()
    if configured_admin_key and hmac.compare_digest(x_api_key, configured_admin_key):
        return {"type": "admin", "platform_id": None}
    key_hash = hash_api_key(x_api_key)
    platform = db.scalars(select(Platform).where(Platform.api_key_hash == key_hash, Platform.active.is_(True))).first()
    if platform:
        return {"type": "platform", "platform_id": platform.id}
    raise HTTPException(status_code=401, detail="Invalid or missing x-api-key")


def get_auth(x_api_key: str | None = Header(default=None), db: Session = Depends(get_db)) -> dict:
    return authenticate_key(x_api_key, db)


def require_key(auth: dict = Depends(get_auth)) -> None:
    return None


def require_admin_key(x_api_key: str | None = Header(default=None)) -> None:
    configured_admin_key = admin_key()
    if not configured_admin_key or not x_api_key or not hmac.compare_digest(x_api_key, configured_admin_key):
        raise HTTPException(status_code=401, detail="Admin API key required")


def authorize_platform(auth: dict, platform_id: str) -> None:
    if auth.get("type") == "admin":
        return
    if auth.get("platform_id") != platform_id:
        raise HTTPException(status_code=403, detail="API key is not authorized for this platform")


def acquire_ledger_write_lock(db: Session) -> None:
    if db.bind and db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": 724_726_592})


def read_identity_projection(db: Session, agent_id: str) -> AgentIdentityProjection:
    projection = db.scalars(select(AgentIdentityProjection).where(
        AgentIdentityProjection.agent_id == agent_id,
        AgentIdentityProjection.projection_version == "v1",
    )).first()
    return projection or rebuild_identity_projection(db, agent_id)


def read_reputation_projection(
    db: Session, agent_id: str, projection: str = "research_trust_v6"
) -> AgentReputationProjection:
    projection_name, projection_version = projection.rsplit("_", 1)
    stored = db.scalars(select(AgentReputationProjection).where(
        AgentReputationProjection.agent_id == agent_id,
        AgentReputationProjection.projection_name == projection_name,
        AgentReputationProjection.projection_version == projection_version,
    )).first()
    return stored or rebuild_projection(db, agent_id, projection)


@app.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    if settings.genlayer_mode != "live" and not settings.allow_test_mocks:
        raise HTTPException(status_code=503, detail="Public runtime requires live GenLayer mode")
    return {
        "ok": True,
        "genlayer_mode": settings.genlayer_mode,
        "source_of_truth": "genlayer_contract",
        "contract_address": settings.genlayer_contract_address,
        "counts": {
            "platforms": db.scalar(select(func.count()).select_from(Platform)),
            "agents": db.scalar(select(func.count()).select_from(Agent)),
            "jobs": db.scalar(select(func.count()).select_from(Job)),
        },
    }


@app.get("/auth/check")
def auth_check(x_api_key: str | None = Header(default=None), db: Session = Depends(get_db)) -> dict:
    auth = authenticate_key(x_api_key, db)
    return {"ok": True, **auth}


@app.post("/demo/reset", dependencies=[Depends(require_key)])
def reset_demo(db: Session = Depends(get_db)) -> dict:
    return reset_demo_data(db)


@app.post("/demo/seed", dependencies=[Depends(require_key)])
def seed_demo(db: Session = Depends(get_db)) -> dict:
    reset = reset_demo_data(db)
    suffix = str(int(time.time()))
    platform_id = f"researchagents_io_{suffix}"
    partner_platform_id = f"partner_market_{suffix}"
    agent_id = f"deepresearchbot_{suffix}"
    good_job_id = f"research_good_{suffix}"
    fraud_job_id = f"research_fraud_{suffix}"

    events = []
    register_platform(
        PlatformRegister(
            platform_id=platform_id,
            platform_name="ResearchAgents.io",
            webhook_url="https://researchagents.example/webhooks/replayer",
        ),
        db,
    )
    events.append("ResearchAgents.io registers as an agent platform.")
    register_platform(
        PlatformRegister(
            platform_id=partner_platform_id,
            platform_name="EnterpriseAgentMarket",
            webhook_url="https://enterprise.example/webhooks/replayer",
        ),
        db,
    )
    events.append("EnterpriseAgentMarket is ready to query portable reputation.")
    register_agent(
        AgentRegister(
            agent_id=agent_id,
            platform_id=platform_id,
            agent_name="DeepResearchBot",
            owner_wallet="researchagents_owner_wallet",
            capabilities=["research", "citations", "market-analysis"],
            metadata_uri="https://researchagents.example/agents/deepresearchbot.json",
        ),
        db,
        ADMIN_AUTH,
    )
    events.append("DeepResearchBot registers with research and citation capabilities.")

    create_job(
        JobCreate(
            job_id=good_job_id,
            platform_id=platform_id,
            requester_id="buyer_series_a",
            provider_agent_id=agent_id,
            task_spec="Research five AI infrastructure companies with real sources.",
            category="research",
            payment_amount=100,
            currency="USDC",
        ),
        db,
        ADMIN_AUTH,
    )
    submit_deliverable(
        good_job_id,
        DeliverableSubmit(
            deliverable_id=f"deliv_{good_job_id}",
            deliverable_uri="https://example.com/good-research",
            summary="Completed the research task with credible sources.",
            evidence_urls=["https://example.com/source-good"],
        ),
        db,
        ADMIN_AUTH,
    )
    accepted = accept_job(good_job_id, db, ADMIN_AUTH)
    events.append("Good research job is accepted, so reputation rises.")

    create_job(
        JobCreate(
            job_id=fraud_job_id,
            platform_id=platform_id,
            requester_id="buyer_fintech",
            provider_agent_id=agent_id,
            task_spec="Find top 20 Series A fintech startups in Brazil with citations.",
            category="research",
            payment_amount=250,
            currency="USDC",
        ),
        db,
        ADMIN_AUTH,
    )
    submit_deliverable(
        fraud_job_id,
        DeliverableSubmit(
            deliverable_id=f"deliv_{fraud_job_id}",
            deliverable_uri="https://example.com/fraud-research",
            summary="Claims example.com proves 20 real Brazilian fintech companies and their Series A funding rounds.",
            evidence_urls=["https://www.iana.org/help/example-domains"],
        ),
        db,
        ADMIN_AUTH,
    )
    open_dispute(
        fraud_job_id,
        DisputeOpen(
            dispute_id=f"disp_{fraud_job_id}",
            claimant="requester",
            reason="The agent lied: several companies are not Series A and two citations are fabricated.",
            evidence_uri="https://www.iana.org/help/example-domains",
            bond_amount=10,
        ),
        db,
        ADMIN_AUTH,
    )
    events.append("Buyer disputes the bad deliverable for fabricated citations.")
    evaluated = evaluate_job(fraud_job_id, db, ADMIN_AUTH)
    events.append("GenLayer verifies fraud and the aggressive demo policy collapses reputation.")
    profile = public_profile(agent_id, db)
    partner_agents = platform_agents(platform_id, db)

    return {
        "reset": reset,
        "story": {
            "platform_id": platform_id,
            "partner_platform_id": partner_platform_id,
            "agent_id": agent_id,
            "good_job_id": good_job_id,
            "fraud_job_id": fraud_job_id,
            "events": events,
        },
        "accepted": accepted,
        "evaluated": evaluated,
        "profile": profile,
        "partner_agents": partner_agents,
        "demo_line": "Any agent platform can integrate this API and outsource trust, disputes, and portable reputation to GenLayer.",
    }


def execute_demo_run(run_id: str) -> None:
    with SessionLocal() as db:
        run = db.get(DemoRun, run_id)
        if not run:
            return
        run.status = "running"
        db.commit()
        try:
            result = seed_demo(db)
            run = db.get(DemoRun, run_id)
            run.status = "completed"
            run.result = result
            run.error = ""
            db.commit()
        except Exception as exc:
            db.rollback()
            run = db.get(DemoRun, run_id)
            if run:
                run.status = "failed"
                run.error = clean_runtime_error(str(exc)) or exc.__class__.__name__
                db.commit()


@app.post("/demo/runs", dependencies=[Depends(require_key)])
def start_demo_run(db: Session = Depends(get_db)) -> dict:
    run_id = new_id("demo_run")
    db.add(DemoRun(id=run_id, status="pending"))
    db.commit()
    threading.Thread(target=execute_demo_run, args=(run_id,), daemon=True).start()
    return {"run_id": run_id, "status": "pending"}


@app.get("/demo/runs/{run_id}", dependencies=[Depends(require_key)])
def get_demo_run(run_id: str, db: Session = Depends(get_db)) -> dict:
    run = db.get(DemoRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Unknown demo run")
    return {"run_id": run.id, "status": run.status, "result": run.result or None, "error": run.error or None}


@app.get("/platforms/{platform_id}/agents")
def platform_agents(platform_id: str, db: Session = Depends(get_db)) -> dict:
    platform = db.get(Platform, platform_id)
    if not platform:
        raise HTTPException(status_code=404, detail="Unknown platform")
    agents = db.scalars(select(Agent).where(Agent.platform_id == platform_id).order_by(Agent.created_at.desc())).all()
    return {
        "platform": platform_to_dict(platform),
        "agents": [
            agent_to_dict(agent) | {"reputation": projection_dict(read_reputation_projection(db, agent.id))}
            for agent in agents
        ],
    }


@app.get("/platforms/{platform_id}/credibility")
def platform_credibility(platform_id: str, db: Session = Depends(get_db)) -> dict:
    if not db.get(Platform, platform_id):
        raise HTTPException(status_code=404, detail="Unknown platform")
    projection = rebuild_platform_credibility(db, platform_id)
    db.commit()
    return platform_credibility_dict(projection)


@app.post("/platforms/{platform_id}/verify-identity", dependencies=[Depends(require_admin_key)])
def verify_platform_identity(platform_id: str, payload: PlatformIdentityVerify, db: Session = Depends(get_db)) -> dict:
    acquire_ledger_write_lock(db)
    platform = db.get(Platform, platform_id)
    agent = db.get(Agent, payload.agent_id)
    if not platform or not agent or agent.platform_id != platform_id:
        raise HTTPException(status_code=404, detail="Platform agent not found")
    event_id = new_id("rep_evt_platform_identity")
    metadata = {"identity_type": "marketplace", "platform_name": platform.name}
    contract_payload = {
        "event_id": event_id, "event_type": "PLATFORM_IDENTITY_VERIFIED",
        "agent_id": agent.id, "platform_id": platform_id, "category": "platform_identity",
        "evidence_uri": payload.evidence_uri, "evidence_hash": payload.evidence_hash,
        "references": [], "metadata": metadata,
    }
    tx = write_contract_json("append_platform_event", contract_payload, event_id)
    event = append_event(
        db, event_id=event_id, event_type="PLATFORM_IDENTITY_VERIFIED", agent_id=agent.id,
        platform_id=platform_id, category="platform_identity", provenance="platform_reported",
        verification_status="finalized", evidence_uri=payload.evidence_uri, evidence_hash=payload.evidence_hash,
        contract_address=genlayer.contract_address, transaction_hash=tx.get("tx_id") or None,
        metadata={**metadata, "contract_readback_verified": True},
    )
    projection = rebuild_platform_credibility(db, platform_id)
    db.commit()
    return {"event": event_dict(db, event), "credibility": platform_credibility_dict(projection), "tx": tx}


@app.post("/platforms/register", dependencies=[Depends(require_admin_key)])
def register_platform(payload: PlatformRegister, db: Session = Depends(get_db)) -> dict:
    platform_id = payload.platform_id or new_id("platform")
    if db.get(Platform, platform_id):
        raise HTTPException(status_code=409, detail="Platform already exists")
    tx = {"mode": "local", "method": "register_platform", "tx_id": ""}
    api_key = generate_api_key()
    platform = Platform(
        id=platform_id,
        name=payload.platform_name,
        owner_wallet=payload.owner_wallet,
        webhook_url=payload.webhook_url,
        api_key_hash=hash_api_key(api_key),
    )
    db.add(platform)
    db.commit()
    db.refresh(platform)
    return {
        "platform": platform_to_dict(platform),
        "api_key": api_key,
        "api_key_warning": "Store this key now. RepLayer only stores its hash and cannot show it again.",
        "tx": tx,
    }


@app.post("/platforms/{platform_id}/api-key", dependencies=[Depends(require_admin_key)])
def rotate_platform_api_key(platform_id: str, db: Session = Depends(get_db)) -> dict:
    platform = db.get(Platform, platform_id)
    if not platform:
        raise HTTPException(status_code=404, detail="Unknown platform")
    api_key = generate_api_key()
    platform.api_key_hash = hash_api_key(api_key)
    db.commit()
    return {
        "platform": platform_to_dict(platform),
        "api_key": api_key,
        "api_key_warning": "Store this key now. Existing platform keys for this platform are revoked.",
    }


@app.post("/agents/register")
def register_agent(payload: AgentRegister, db: Session = Depends(get_db), auth: dict = Depends(get_auth)) -> dict:
    acquire_ledger_write_lock(db)
    authorize_platform(auth, payload.platform_id)
    if not db.get(Platform, payload.platform_id):
        raise HTTPException(status_code=404, detail="Unknown platform")
    agent_id = payload.agent_id or new_id("agent")
    if db.get(Agent, agent_id):
        raise HTTPException(status_code=409, detail="Agent already exists")
    tx = write_platform_event("AGENT_REGISTERED", agent_id, payload.platform_id, metadata={
        "owner_wallet": payload.owner_wallet, "name": payload.agent_name,
        "capabilities": payload.capabilities, "metadata_uri": payload.metadata_uri,
    })
    agent = db.get(Agent, agent_id)
    if not agent:
        agent = Agent(id=agent_id, platform_id=payload.platform_id, name=payload.agent_name)
        db.add(agent)
    agent.owner_wallet = payload.owner_wallet
    agent.name = payload.agent_name
    agent.capabilities = payload.capabilities
    agent.metadata_uri = payload.metadata_uri
    append_event(db, event_id=contract_event_id("agent_registered", agent_id), event_type="AGENT_REGISTERED", agent_id=agent_id, platform_id=payload.platform_id,
                 provenance="platform_reported", verification_status="finalized", category="research",
                 transaction_hash=tx.get("tx_id") or None, contract_address=tx.get("contract_address") or None,
                 metadata={"contract_readback_verified": True})
    rebuild_projection(db, agent_id)
    db.commit()
    return {"agent": agent_to_dict(agent), "tx": tx}


@app.post("/jobs")
def create_job(payload: JobCreate, db: Session = Depends(get_db), auth: dict = Depends(get_auth)) -> dict:
    acquire_ledger_write_lock(db)
    authorize_platform(auth, payload.platform_id)
    if not db.get(Platform, payload.platform_id):
        raise HTTPException(status_code=404, detail="Unknown platform")
    if not db.get(Agent, payload.provider_agent_id):
        raise HTTPException(status_code=404, detail="Unknown agent")
    job_id = payload.job_id or new_id("job")
    if db.get(Job, job_id):
        raise HTTPException(status_code=409, detail="Job already exists")
    tx = write_platform_event("JOB_CREATED", payload.provider_agent_id, payload.platform_id,
                              job_id=job_id, category=payload.category,
                              counterparty_id=payload.requester_id,
                              metadata={"task_spec": payload.task_spec, "payment_amount": payload.payment_amount,
                                        "currency": payload.currency})
    job = db.get(Job, job_id)
    if not job:
        job = Job(
            id=job_id,
            platform_id=payload.platform_id,
            requester_id=payload.requester_id,
            provider_agent_id=payload.provider_agent_id,
            task_spec=payload.task_spec,
        )
        db.add(job)
    job.category = payload.category
    job.payment_amount = payload.payment_amount
    job.currency = payload.currency
    append_event(db, event_id=contract_event_id("job_created", job.id), event_type="JOB_CREATED", agent_id=job.provider_agent_id, platform_id=job.platform_id,
                 job_id=job.id, counterparty_id=job.requester_id, category=job.category,
                 provenance="platform_reported", verification_status="finalized",
                 transaction_hash=tx.get("tx_id") or None, contract_address=tx.get("contract_address") or None,
                 metadata={"contract_readback_verified": True})
    db.commit()
    db.refresh(job)
    return {"job": job_to_dict(job), "tx": tx}


@app.post("/jobs/{job_id}/deliverable")
def submit_deliverable(
    job_id: str,
    payload: DeliverableSubmit,
    db: Session = Depends(get_db),
    auth: dict = Depends(get_auth),
) -> dict:
    acquire_ledger_write_lock(db)
    job = require_job(db, job_id)
    authorize_platform(auth, job.platform_id)
    if job.status != "created":
        raise HTTPException(status_code=409, detail="Job is not accepting deliverables")
    deliverable_id = payload.deliverable_id or new_id("deliv")
    tx = write_platform_event("DELIVERABLE_SUBMITTED", job.provider_agent_id, job.platform_id,
                              job_id=job.id, category=job.category, evidence_uri=payload.deliverable_uri,
                              metadata={"deliverable_id": deliverable_id, "summary": payload.summary,
                                        "evidence_urls": payload.evidence_urls})
    deliverable = db.scalars(select(Deliverable).where(Deliverable.job_id == job_id)).first()
    if not deliverable:
        deliverable = Deliverable(id=deliverable_id, job_id=job_id, deliverable_uri=payload.deliverable_uri)
        db.add(deliverable)
    deliverable.deliverable_uri = payload.deliverable_uri
    deliverable.summary = payload.summary
    deliverable.evidence_urls = payload.evidence_urls
    job.status = "submitted"
    append_event(db, event_id=contract_event_id("deliverable_submitted", job.id), event_type="DELIVERABLE_SUBMITTED", agent_id=job.provider_agent_id,
                 platform_id=job.platform_id, job_id=job.id, category=job.category,
                 provenance="platform_reported", verification_status="finalized",
                 evidence_uri=payload.deliverable_uri, transaction_hash=tx.get("tx_id") or None,
                 contract_address=tx.get("contract_address") or None,
                 metadata={"contract_readback_verified": True})
    db.commit()
    db.refresh(deliverable)
    return {"deliverable": deliverable_to_dict(deliverable), "tx": tx}


@app.post("/jobs/{job_id}/accept")
def accept_job(job_id: str, db: Session = Depends(get_db), auth: dict = Depends(get_auth)) -> dict:
    acquire_ledger_write_lock(db)
    job = require_job(db, job_id)
    authorize_platform(auth, job.platform_id)
    if job.status != "submitted":
        raise HTTPException(status_code=409, detail="Job is not submitted")
    tx = write_platform_event("JOB_ACCEPTED", job.provider_agent_id, job.platform_id,
                              job_id=job.id, category=job.category, counterparty_id=job.requester_id)
    job.status = "accepted"
    append_event(db, event_id=contract_event_id("job_accepted", job.id), event_type="JOB_ACCEPTED", agent_id=job.provider_agent_id, platform_id=job.platform_id,
                 job_id=job.id, counterparty_id=job.requester_id, category=job.category,
                 provenance="counterparty_confirmed", verification_status="finalized",
                 transaction_hash=tx.get("tx_id") or None, contract_address=tx.get("contract_address") or None,
                 metadata={"contract_readback_verified": True})
    projection = rebuild_projection(db, job.provider_agent_id)
    db.commit()
    return {"job": job_to_dict(job), "reputation": projection_dict(projection), "tx": tx}


@app.post("/jobs/{job_id}/dispute", response_model=None)
def open_dispute(job_id: str, payload: DisputeOpen, db: Session = Depends(get_db), auth: dict = Depends(get_auth)):
    acquire_ledger_write_lock(db)
    job = require_job(db, job_id)
    deliverable = db.scalars(select(Deliverable).where(Deliverable.job_id == job_id)).first()
    authorize_platform(auth, job.platform_id)
    if job.status != "submitted":
        raise HTTPException(status_code=409, detail="Only submitted jobs can be disputed")
    dispute_id = payload.dispute_id or new_id("disp")
    dispute_event_id = contract_event_id("dispute_opened", dispute_id)
    provisional_event_id = contract_event_id("provisional", dispute_id)
    tx = genlayer.write("evaluate_dispute", [json.dumps({
        "dispute_id": dispute_id, "job_id": job_id, "agent_id": job.provider_agent_id,
        "platform_id": job.platform_id, "claimant": payload.claimant, "reason": payload.reason,
        "evidence_uri": payload.evidence_uri, "evidence_hash": "", "category": job.category,
        "task_spec": job.task_spec,
        "deliverable_uri": deliverable.deliverable_uri if deliverable else "",
        "deliverable_summary": deliverable.summary if deliverable else "",
        "evidence_urls": deliverable.evidence_urls if deliverable else [],
        "dispute_event_id": dispute_event_id, "provisional_event_id": provisional_event_id, "references": [],
    }, sort_keys=True)])
    dispute = db.get(Dispute, dispute_id)
    if not dispute:
        dispute = Dispute(id=dispute_id, job_id=job_id, reason=payload.reason)
        db.add(dispute)
    dispute.claimant = payload.claimant
    dispute.reason = payload.reason
    dispute.evidence_uri = payload.evidence_uri
    dispute.bond_amount = payload.bond_amount
    job.status = "disputed"
    append_event(
        db, event_id=dispute_event_id, event_type="DISPUTE_OPENED",
        agent_id=job.provider_agent_id, platform_id=job.platform_id, job_id=job.id,
        dispute_id=dispute_id, counterparty_id=payload.claimant, category=job.category,
        provenance="platform_reported", verification_status="pending",
        evidence_uri=payload.evidence_uri, transaction_hash=tx.get("tx_id") or None,
        metadata={"reason": payload.reason, "contract_readback_verified": False},
    )
    provisional = genlayer.call_json("get_event", [provisional_event_id])
    if not (isinstance(provisional, dict) and provisional.get("metadata")):
        rebuild_projection(db, job.provider_agent_id, "research_trust_v6")
        db.commit()
        db.refresh(dispute)
        return JSONResponse(status_code=202, content={
            "dispute": dispute_to_dict(dispute), "tx": tx, "judgment_status": "pending",
        })
    opened = db.scalars(select(ReputationEvent).where(ReputationEvent.event_id == dispute_event_id)).first()
    opened.contract_address = genlayer.contract_address
    opened.event_metadata = {**opened.event_metadata, "contract_readback_verified": True}
    append_event(
        db, event_id=provisional_event_id, event_type="JUDGMENT_PROVISIONAL",
        agent_id=job.provider_agent_id, platform_id=job.platform_id, job_id=job.id,
        dispute_id=dispute_id, counterparty_id=payload.claimant, category=job.category,
        provenance="genlayer_provisional", verification_status="provisional",
        evidence_uri=payload.evidence_uri, contract_address=genlayer.contract_address,
        transaction_hash=tx.get("tx_id") or None,
        references=provisional.get("references", []),
        metadata={**provisional["metadata"], "contract_readback_verified": True},
    )
    rebuild_projection(db, job.provider_agent_id, "research_trust_v6")
    db.commit()
    db.refresh(dispute)
    return {"dispute": dispute_to_dict(dispute), "tx": tx}


@app.post("/jobs/{job_id}/appeal")
def appeal_job(job_id: str, payload: AppealSubmit, db: Session = Depends(get_db), auth: dict = Depends(get_auth)) -> dict:
    acquire_ledger_write_lock(db)
    job = require_job(db, job_id)
    authorize_platform(auth, job.platform_id)
    dispute = db.scalars(select(Dispute).where(Dispute.job_id == job_id)).first()
    if not dispute:
        raise HTTPException(status_code=409, detail="Job has no appealable dispute")
    provisional_event_id = contract_event_id("provisional", dispute.id)
    provisional = db.scalars(select(ReputationEvent).where(ReputationEvent.event_id == provisional_event_id)).first()
    if not provisional:
        opened = db.scalars(select(ReputationEvent).where(
            ReputationEvent.event_id == contract_event_id("dispute_opened", dispute.id)
        )).first()
        contract_provisional = genlayer.call_json("get_event", [provisional_event_id])
        if opened and opened.transaction_hash and isinstance(contract_provisional, dict) and contract_provisional.get("metadata"):
            provisional = append_event(
                db, event_id=provisional_event_id, event_type="JUDGMENT_PROVISIONAL",
                agent_id=job.provider_agent_id, platform_id=job.platform_id, job_id=job.id,
                dispute_id=dispute.id, counterparty_id=dispute.claimant, category=job.category,
                provenance="genlayer_provisional", verification_status="provisional",
                evidence_uri=dispute.evidence_uri, contract_address=genlayer.contract_address,
                transaction_hash=opened.transaction_hash,
                references=contract_provisional.get("references", []),
                metadata={**contract_provisional["metadata"], "contract_readback_verified": True},
            )
            opened.contract_address = genlayer.contract_address
            opened.event_metadata = {**opened.event_metadata, "contract_readback_verified": True}
    if not provisional or not provisional.transaction_hash:
        raise HTTPException(status_code=409, detail="Provisional GenLayer judgment has not been indexed")
    appeal_event_id = contract_event_id("appeal", dispute.id)
    if db.scalars(select(ReputationEvent).where(ReputationEvent.event_id == appeal_event_id)).first():
        raise HTTPException(status_code=409, detail="An appeal has already been submitted")
    provisional_reputation = projection_dict(rebuild_projection(db, job.provider_agent_id, "research_trust_v6"))
    try:
        protocol = genlayer.appeal_transaction(provisional.transaction_hash, payload.bond_amount)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=clean_runtime_error(str(exc))) from exc
    event = append_event(
        db, event_id=appeal_event_id, event_type="APPEAL_SUBMITTED",
        agent_id=job.provider_agent_id, platform_id=job.platform_id, job_id=job.id,
        dispute_id=dispute.id, counterparty_id=payload.appellant_id, category=job.category,
        provenance="challenged", verification_status="appealed",
        evidence_uri=payload.evidence_uri, evidence_hash=payload.evidence_hash,
        transaction_hash=protocol.get("appeal_submission_hash") or provisional.transaction_hash,
        references=[provisional_event_id],
        metadata={
            "original_verdict": str(provisional.event_metadata.get("verdict", "inconclusive")),
            "reason": payload.reason, "bond_amount": payload.bond_amount,
            "protocol_transaction_hash": provisional.transaction_hash,
            "protocol_status": protocol.get("status", "UNKNOWN"),
            "protocol_round": int(protocol.get("round", 1)),
        },
    )
    dispute.status = "appealed"
    job.status = "appeal_pending"
    appealed_reputation = projection_dict(rebuild_projection(db, job.provider_agent_id, "research_trust_v6"))
    db.commit()
    return {"appeal": event_dict(db, event), "protocol": protocol,
            "provisional_reputation": provisional_reputation,
            "appealed_reputation": appealed_reputation}


@app.post("/jobs/{job_id}/appeal/resolve")
def resolve_job_appeal(job_id: str, db: Session = Depends(get_db), auth: dict = Depends(get_auth)) -> dict:
    acquire_ledger_write_lock(db)
    job = require_job(db, job_id)
    authorize_platform(auth, job.platform_id)
    dispute = db.scalars(select(Dispute).where(Dispute.job_id == job_id)).first()
    if not dispute:
        raise HTTPException(status_code=409, detail="Job has no appealed dispute")
    provisional_event_id = contract_event_id("provisional", dispute.id)
    appeal_event_id = contract_event_id("appeal", dispute.id)
    provisional = db.scalars(select(ReputationEvent).where(ReputationEvent.event_id == provisional_event_id)).first()
    appeal = db.scalars(select(ReputationEvent).where(ReputationEvent.event_id == appeal_event_id)).first()
    if not provisional or not appeal:
        raise HTTPException(status_code=409, detail="Appeal has not been submitted")
    existing_final = db.scalars(select(ReputationEvent).where(
        ReputationEvent.event_id == contract_event_id("appeal_final", dispute.id)
    )).first()
    if existing_final:
        raise HTTPException(status_code=409, detail="Appeal has already been resolved")
    protocol_tx = str(appeal.event_metadata.get("protocol_transaction_hash") or provisional.transaction_hash or "")
    protocol = genlayer.transaction_status(protocol_tx)
    if protocol["status"] == "READY_TO_FINALIZE":
        protocol = genlayer.finalize_transaction(protocol_tx)
    if protocol["status"] != "FINALIZED":
        raise HTTPException(status_code=409, detail=f"GenLayer appeal is not final: {protocol['status']}")
    current = genlayer.call_json("get_judgment", [dispute.id])
    if not isinstance(current, dict) or not current.get("verdict"):
        raise RuntimeError("Final GenLayer judgment could not be read from contract state")
    resolved_event_id = contract_event_id("appeal_resolved", dispute.id)
    outcome_event_id = contract_event_id("appeal_outcome", dispute.id)
    superseded_event_id = contract_event_id("appeal_superseded", dispute.id)
    final_event_id = contract_event_id("appeal_final", dispute.id)
    resolution_payload = {
        "dispute_id": dispute.id, "provisional_event_id": provisional_event_id,
        "appeal_event_id": appeal_event_id, "resolved_event_id": resolved_event_id,
        "outcome_event_id": outcome_event_id, "superseded_event_id": superseded_event_id,
        "final_event_id": final_event_id,
        "original_verdict": str(appeal.event_metadata.get("original_verdict", "inconclusive")),
        "reason": str(appeal.event_metadata.get("reason", "")),
        "bond_amount": str(appeal.event_metadata.get("bond_amount", "")),
        "evidence_uri": appeal.evidence_uri or "", "evidence_hash": appeal.evidence_hash or "",
        "protocol_transaction_hash": protocol_tx, "protocol_status": protocol["status"],
        "protocol_round": int(protocol.get("round", 1)),
    }
    ledger_tx = genlayer.write("record_appeal_resolution", [json.dumps(resolution_payload, sort_keys=True)])
    indexer.sync_once(db)
    final_event = db.scalars(select(ReputationEvent).where(ReputationEvent.event_id == final_event_id)).first()
    if not final_event:
        raise RuntimeError(f"Final appeal judgment is pending. Tx: {ledger_tx.get('tx_id', '')}")
    final_event.transaction_hash = protocol_tx
    final_event.contract_address = genlayer.contract_address
    final_event.event_metadata = {
        **final_event.event_metadata, "contract_readback_verified": True,
        "ledger_record_transaction_hash": ledger_tx.get("tx_id") or "",
    }
    verdict = str(final_event.event_metadata.get("verdict") or current["verdict"])
    judgment = db.scalars(select(Judgment).where(Judgment.job_id == job_id)).first()
    if not judgment:
        judgment = Judgment(id=new_id("judgment"), job_id=job_id, dispute_id=dispute.id, verdict=verdict)
        db.add(judgment)
    judgment.verdict = verdict
    judgment.confidence_bps = int(final_event.event_metadata.get("confidence_bps") or 0)
    judgment.reasoning_summary = str(final_event.event_metadata.get("reasoning_summary") or "")
    judgment.source = "genlayer"
    judgment.contract_address = genlayer.contract_address
    judgment.tx_hash = protocol_tx
    judgment.verify_url = genlayer.verify_url(protocol_tx)
    dispute.status = "resolved"
    job.status = f"judged_{verdict}"
    projection = rebuild_projection(db, job.provider_agent_id, "research_trust_v6")
    db.commit()
    outcome = db.scalars(select(ReputationEvent).where(ReputationEvent.event_id == outcome_event_id)).first()
    return {"judgment": judgment_to_dict(judgment), "outcome": event_dict(db, outcome),
            "event": event_dict(db, final_event), "reputation": projection_dict(projection),
            "protocol": protocol, "ledger_tx": ledger_tx}


@app.post("/jobs/{job_id}/evaluate")
def evaluate_job(job_id: str, db: Session = Depends(get_db), auth: dict = Depends(get_auth)) -> dict:
    acquire_ledger_write_lock(db)
    job = require_job(db, job_id)
    authorize_platform(auth, job.platform_id)
    dispute = db.scalars(select(Dispute).where(Dispute.job_id == job_id)).first()
    deliverable = db.scalars(select(Deliverable).where(Deliverable.job_id == job_id)).first()
    if not dispute or not deliverable:
        raise HTTPException(status_code=409, detail="Job needs a deliverable and open dispute")
    if db.scalars(select(Judgment).where(Judgment.job_id == job_id)).first():
        raise HTTPException(status_code=409, detail="Job already evaluated")
    if db.scalars(select(ReputationEvent).where(
        ReputationEvent.event_type == "APPEAL_SUBMITTED", ReputationEvent.dispute_id == dispute.id
    )).first():
        raise HTTPException(status_code=409, detail="Appealed judgments must use the appeal resolution endpoint")

    genlayer.require_live()
    provisional_event_id = contract_event_id("provisional", dispute.id)
    provisional = None
    for _ in range(settings.genlayer_read_attempts):
        provisional = genlayer.call_json("get_event", [provisional_event_id])
        if isinstance(provisional, dict) and provisional.get("metadata"):
            break
        time.sleep(settings.genlayer_read_interval_seconds)
    if not (isinstance(provisional, dict) and provisional.get("metadata")):
        raise RuntimeError(f"GenLayer provisional judgment is still pending for job {job_id}")
    provisional_row = db.scalars(select(ReputationEvent).where(
        ReputationEvent.event_id == provisional_event_id
    )).first()
    if not provisional_row or not provisional_row.transaction_hash:
        raise HTTPException(status_code=409, detail="Provisional judgment transaction provenance is missing")
    protocol = genlayer.transaction_status(provisional_row.transaction_hash)
    if protocol["status"] == "READY_TO_FINALIZE":
        protocol = genlayer.finalize_transaction(provisional_row.transaction_hash)
    if protocol["status"] != "FINALIZED":
        raise HTTPException(status_code=409, detail=f"GenLayer judgment is not final: {protocol['status']}")
    final_event_id = contract_event_id("final", dispute.id)
    resolve_tx = genlayer.write("finalize_judgment", [dispute.id, final_event_id, provisional_event_id])
    if not resolve_tx.get("tx_id"):
        raise RuntimeError("GenLayer did not return a finalization transaction hash")
    final_event = None
    for _ in range(settings.genlayer_read_attempts):
        final_event = genlayer.call_json("get_event", [final_event_id])
        if isinstance(final_event, dict) and final_event.get("metadata"):
            break
        time.sleep(settings.genlayer_read_interval_seconds)
    if not (isinstance(final_event, dict) and final_event.get("metadata")):
        raise RuntimeError(f"GenLayer final judgment is pending. Tx: {resolve_tx['tx_id']}")
    raw = final_event["metadata"]
    result = {
        "verdict": raw["verdict"],
        "confidence_bps": int(raw.get("confidence_bps", 0)),
        "reasoning_summary": raw.get("reasoning_summary", ""),
        "score_deltas": raw.get("score_deltas") or {},
    }
    judgment = db.scalars(select(Judgment).where(Judgment.job_id == job_id)).first()
    if not judgment:
        judgment = Judgment(id=new_id("judgment"), job_id=job_id, dispute_id=dispute.id, verdict=result["verdict"])
        db.add(judgment)
    judgment.verdict = result["verdict"]
    judgment.confidence_bps = result["confidence_bps"]
    judgment.reasoning_summary = result["reasoning_summary"]
    judgment.score_deltas = result["score_deltas"]
    judgment.source = "genlayer"
    judgment.contract_address = genlayer.contract_address
    judgment.tx_hash = provisional_row.transaction_hash
    judgment.verify_url = genlayer.verify_url(provisional_row.transaction_hash)
    dispute.status = "resolved"
    job.status = f"judged_{result['verdict']}"
    judgment_event = append_event(
        db, event_id=final_event_id, event_type="JUDGMENT_FINALIZED", agent_id=job.provider_agent_id,
        platform_id=job.platform_id, job_id=job.id, dispute_id=dispute.id,
        counterparty_id=dispute.claimant, category=job.category,
        provenance="genlayer_verified", verification_status="finalized",
        evidence_uri=dispute.evidence_uri, contract_address=genlayer.contract_address,
        transaction_hash=provisional_row.transaction_hash,
        references=[provisional_event_id],
        metadata={"verdict": result["verdict"], "confidence_bps": result["confidence_bps"],
                  "reasoning_summary": result["reasoning_summary"], "contract_readback_verified": True,
                  "protocol_status": protocol["status"], "protocol_round": protocol.get("round", 0),
                  "ledger_record_transaction_hash": resolve_tx["tx_id"]},
    )
    projection = rebuild_projection(db, job.provider_agent_id)
    db.commit()
    return {"judgment": judgment_to_dict(judgment), "reputation": projection_dict(projection),
            "event": event_dict(db, judgment_event)}


@app.post("/delegations")
def create_delegation(payload: DelegationCreate, db: Session = Depends(get_db), auth: dict = Depends(get_auth)) -> dict:
    acquire_ledger_write_lock(db)
    authorize_platform(auth, payload.platform_id)
    principal = db.get(Agent, payload.principal_agent_id)
    worker = db.get(Agent, payload.worker_agent_id)
    job = require_job(db, payload.job_id)
    if not principal or not worker:
        raise HTTPException(status_code=404, detail="Principal or worker agent not found")
    if principal.id == worker.id:
        raise HTTPException(status_code=409, detail="An agent cannot delegate work to itself")
    if job.platform_id != payload.platform_id or job.provider_agent_id != principal.id:
        raise HTTPException(status_code=409, detail="Delegation principal must be the job provider")
    parent = db.get(Delegation, payload.parent_delegation_id) if payload.parent_delegation_id else None
    if payload.parent_delegation_id and not parent:
        raise HTTPException(status_code=404, detail="Parent delegation not found")
    if parent and (not parent.allow_subdelegation or parent.worker_agent_id != principal.id):
        raise HTTPException(status_code=409, detail="Parent delegation does not authorize this subdelegation")
    delegation_id = payload.delegation_id or new_id("delegation")
    if db.get(Delegation, delegation_id):
        raise HTTPException(status_code=409, detail="Delegation already exists")
    delegation = Delegation(
        id=delegation_id, principal_agent_id=principal.id, worker_agent_id=worker.id,
        platform_id=payload.platform_id, job_id=job.id, parent_delegation_id=payload.parent_delegation_id,
        authority_scope=payload.authority_scope, permitted_tools=payload.permitted_tools,
        permitted_actions=payload.permitted_actions, spending_limit=payload.spending_limit,
        currency=payload.currency, allow_subdelegation=payload.allow_subdelegation,
        disclosure_required=payload.disclosure_required, principal_signature=payload.principal_signature,
        evidence_uri=payload.evidence_uri, evidence_hash=payload.evidence_hash,
    )
    db.add(delegation)
    db.flush()
    shared = {
        "principal_agent_id": principal.id, "worker_agent_id": worker.id,
        "authority_scope": payload.authority_scope, "permitted_tools": payload.permitted_tools,
        "permitted_actions": payload.permitted_actions, "allow_subdelegation": payload.allow_subdelegation,
        "disclosure_required": payload.disclosure_required, "principal_signature": payload.principal_signature,
        "identity_bindings": [principal.owner_wallet, worker.owner_wallet],
    }
    created_id = contract_event_id("delegation_created", delegation.id)
    created, created_tx = append_delegation_event(
        db, delegation, "DELEGATION_CREATED", event_id=created_id, actor_agent_id=principal.id,
        counterparty_id=worker.id, evidence_uri=payload.evidence_uri, evidence_hash=payload.evidence_hash,
        references=[], metadata=shared,
    )
    scope_id = contract_event_id("authority_scope_granted", delegation.id)
    scope, _ = append_delegation_event(
        db, delegation, "AUTHORITY_SCOPE_GRANTED", event_id=scope_id, actor_agent_id=principal.id,
        counterparty_id=worker.id, evidence_uri=payload.evidence_uri, evidence_hash=payload.evidence_hash,
        references=[created_id], metadata=shared,
    )
    spending_id = contract_event_id("spending_limit_set", delegation.id)
    spending, _ = append_delegation_event(
        db, delegation, "SPENDING_LIMIT_SET", event_id=spending_id, actor_agent_id=principal.id,
        counterparty_id=worker.id, evidence_uri=payload.evidence_uri, evidence_hash=payload.evidence_hash,
        references=[scope_id], metadata={**shared, "spending_limit": payload.spending_limit, "currency": payload.currency},
    )
    events = [created, scope, spending]
    if parent:
        subdelegated, _ = append_delegation_event(
            db, delegation, "WORK_SUBDELEGATED",
            event_id=contract_event_id("work_subdelegated", delegation.id), actor_agent_id=principal.id,
            counterparty_id=worker.id, evidence_uri=payload.evidence_uri, evidence_hash=payload.evidence_hash,
            references=[contract_event_id("delegation_accepted", parent.id), created_id],
            metadata={**shared, "parent_delegation_id": parent.id},
        )
        events.append(subdelegated)
    db.commit()
    return {"delegation": delegation_to_dict(delegation), "events": [event_dict(db, event) for event in events], "tx": created_tx}


@app.post("/delegations/{delegation_id}/accept")
def accept_delegation(delegation_id: str, payload: DelegationAccept, db: Session = Depends(get_db), auth: dict = Depends(get_auth)) -> dict:
    acquire_ledger_write_lock(db)
    delegation = db.get(Delegation, delegation_id)
    if not delegation:
        raise HTTPException(status_code=404, detail="Delegation not found")
    authorize_platform(auth, delegation.platform_id)
    if delegation.status != "created":
        raise HTTPException(status_code=409, detail="Delegation is not awaiting acceptance")
    event, tx = append_delegation_event(
        db, delegation, "DELEGATION_ACCEPTED", event_id=contract_event_id("delegation_accepted", delegation.id),
        actor_agent_id=delegation.worker_agent_id, counterparty_id=delegation.principal_agent_id,
        evidence_uri=payload.evidence_uri or delegation.evidence_uri,
        evidence_hash=payload.evidence_hash or delegation.evidence_hash,
        references=[contract_event_id("delegation_created", delegation.id)],
        metadata={"worker_signature": payload.worker_signature},
    )
    delegation.worker_signature = payload.worker_signature
    delegation.status = "accepted"
    delegation.accepted_at = datetime.utcnow()
    db.commit()
    return {"delegation": delegation_to_dict(delegation), "event": event_dict(db, event), "tx": tx}


@app.post("/delegations/{delegation_id}/output")
def submit_delegated_output(delegation_id: str, payload: DelegatedOutputSubmit, db: Session = Depends(get_db), auth: dict = Depends(get_auth)) -> dict:
    acquire_ledger_write_lock(db)
    delegation = db.get(Delegation, delegation_id)
    if not delegation:
        raise HTTPException(status_code=404, detail="Delegation not found")
    authorize_platform(auth, delegation.platform_id)
    if delegation.status != "accepted":
        raise HTTPException(status_code=409, detail="Delegation must be accepted before output submission")
    event_id = contract_event_id("delegated_output_submitted", delegation.id)
    event, tx = append_delegation_event(
        db, delegation, "DELEGATED_OUTPUT_SUBMITTED", event_id=event_id,
        actor_agent_id=delegation.worker_agent_id, counterparty_id=delegation.principal_agent_id,
        evidence_uri=payload.output_uri, evidence_hash=payload.evidence_hash,
        references=[contract_event_id("delegation_accepted", delegation.id)],
        metadata={"output_uri": payload.output_uri, "summary": payload.summary, "evidence_urls": payload.evidence_urls},
    )
    delegation.status = "output_submitted"
    db.commit()
    return {"delegation": delegation_to_dict(delegation), "event": event_dict(db, event), "tx": tx}


@app.get("/delegations/{delegation_id}")
def get_delegation(delegation_id: str, db: Session = Depends(get_db)) -> dict:
    delegation = db.get(Delegation, delegation_id)
    if not delegation:
        raise HTTPException(status_code=404, detail="Delegation not found")
    events = db.scalars(select(ReputationEvent).where(
        ReputationEvent.job_id == delegation.job_id
    ).order_by(ReputationEvent.occurred_at, ReputationEvent.event_id)).all()
    events = [event for event in events if event.event_metadata.get("delegation_id") == delegation.id]
    return {"delegation": delegation_to_dict(delegation), "events": [event_dict(db, event) for event in events]}


@app.post("/delegations/{delegation_id}/responsibility-dispute", response_model=None)
def dispute_delegated_responsibility(delegation_id: str, payload: ResponsibilityDisputeOpen, db: Session = Depends(get_db), auth: dict = Depends(get_auth)):
    acquire_ledger_write_lock(db)
    delegation = db.get(Delegation, delegation_id)
    if not delegation:
        raise HTTPException(status_code=404, detail="Delegation not found")
    authorize_platform(auth, delegation.platform_id)
    if delegation.status != "output_submitted":
        raise HTTPException(status_code=409, detail="Delegated output must be submitted before responsibility is disputed")
    case_id = new_id("responsibility")
    ids = responsibility_event_ids(case_id)
    output = db.scalars(select(ReputationEvent).where(
        ReputationEvent.event_id == contract_event_id("delegated_output_submitted", delegation.id)
    )).first()
    job = require_job(db, delegation.job_id)
    db.add(Dispute(
        id=case_id,
        job_id=delegation.job_id,
        claimant=payload.claimant_id,
        reason=payload.reason,
        evidence_uri=payload.evidence_uri,
        status="responsibility_open",
    ))
    db.flush()
    contract_payload = {
        "responsibility_case_id": case_id, "delegation_id": delegation.id,
        "principal_agent_id": delegation.principal_agent_id, "worker_agent_id": delegation.worker_agent_id,
        "platform_id": delegation.platform_id, "job_id": delegation.job_id, "category": job.category,
        "authority_scope": delegation.authority_scope, "permitted_tools": delegation.permitted_tools,
        "permitted_actions": delegation.permitted_actions, "spending_limit": float(delegation.spending_limit or 0),
        "currency": delegation.currency, "allow_subdelegation": delegation.allow_subdelegation,
        "disclosure_required": delegation.disclosure_required,
        "principal_signature": delegation.principal_signature, "worker_signature": delegation.worker_signature,
        "task_spec": job.task_spec, "delegated_output": output.event_metadata if output else {},
        "claimant_id": payload.claimant_id, "reason": payload.reason,
        "evidence_uri": payload.evidence_uri, "evidence_hash": payload.evidence_hash,
        "dispute_event_id": ids["dispute"], "principal_provisional_event_id": ids["principal_provisional"],
        "worker_provisional_event_id": ids["worker_provisional"],
    }
    tx = genlayer.write("evaluate_responsibility", [json.dumps(contract_payload, sort_keys=True)])
    opened = append_event(
        db, event_id=ids["dispute"], event_type="RESPONSIBILITY_DISPUTED",
        agent_id=delegation.principal_agent_id, platform_id=delegation.platform_id,
        job_id=delegation.job_id, dispute_id=case_id, counterparty_id=delegation.worker_agent_id,
        category=job.category, provenance="platform_reported", verification_status="pending",
        evidence_uri=payload.evidence_uri, evidence_hash=payload.evidence_hash,
        transaction_hash=tx.get("tx_id") or None,
        metadata={"delegation_id": delegation.id, "reason": payload.reason,
                  "event_ids": ids, "contract_readback_verified": False},
    )
    provisional_events = []
    for role in ["principal", "worker"]:
        event_id = ids[role + "_provisional"]
        contract_event = genlayer.call_json("get_event", [event_id])
        if not isinstance(contract_event, dict) or not contract_event.get("metadata"):
            continue
        provisional_events.append(append_event(
            db, event_id=event_id, event_type="RESPONSIBILITY_JUDGMENT_PROVISIONAL",
            agent_id=contract_event["agent_id"], platform_id=delegation.platform_id,
            job_id=delegation.job_id, dispute_id=case_id, counterparty_id=contract_event.get("counterparty_id"),
            category=job.category, provenance="genlayer_provisional", verification_status="provisional",
            evidence_uri=payload.evidence_uri, evidence_hash=payload.evidence_hash,
            references=contract_event.get("references", []), contract_address=genlayer.contract_address,
            transaction_hash=tx.get("tx_id") or None,
            metadata={**contract_event["metadata"], "contract_readback_verified": True},
        ))
    if len(provisional_events) == 2:
        opened.contract_address = genlayer.contract_address
        opened.event_metadata = {**opened.event_metadata, "contract_readback_verified": True}
    delegation.status = "responsibility_disputed"
    principal_projection = rebuild_projection(db, delegation.principal_agent_id, "research_trust_v6")
    worker_projection = rebuild_projection(db, delegation.worker_agent_id, "research_trust_v6")
    db.commit()
    response = {"responsibility_case_id": case_id, "event": event_dict(db, opened), "tx": tx,
                "provisional_events": [event_dict(db, event) for event in provisional_events],
                "principal_reputation": projection_dict(principal_projection),
                "worker_reputation": projection_dict(worker_projection)}
    return response if len(provisional_events) == 2 else JSONResponse(status_code=202, content=response)


@app.post("/delegations/{delegation_id}/responsibility/finalize")
def finalize_delegated_responsibility(delegation_id: str, db: Session = Depends(get_db), auth: dict = Depends(get_auth)) -> dict:
    delegation = db.get(Delegation, delegation_id)
    if not delegation:
        raise HTTPException(status_code=404, detail="Delegation not found")
    authorize_platform(auth, delegation.platform_id)
    return resolve_responsibility_case(db, delegation, appealed=False)


@app.post("/delegations/{delegation_id}/responsibility/appeal")
def appeal_delegated_responsibility(delegation_id: str, payload: ResponsibilityAppealSubmit, db: Session = Depends(get_db), auth: dict = Depends(get_auth)) -> dict:
    acquire_ledger_write_lock(db)
    delegation = db.get(Delegation, delegation_id)
    if not delegation:
        raise HTTPException(status_code=404, detail="Delegation not found")
    authorize_platform(auth, delegation.platform_id)
    opened = responsibility_open_event(db, delegation)
    if not opened or not opened.transaction_hash:
        raise HTTPException(status_code=409, detail="Responsibility judgment has not been submitted")
    ids = opened.event_metadata["event_ids"]
    if db.scalars(select(ReputationEvent).where(ReputationEvent.event_id == ids["appeal"])).first():
        raise HTTPException(status_code=409, detail="Responsibility judgment has already been appealed")
    try:
        protocol = genlayer.appeal_transaction(opened.transaction_hash, payload.bond_amount)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=clean_runtime_error(str(exc))) from exc
    event = append_event(
        db, event_id=ids["appeal"], event_type="RESPONSIBILITY_APPEALED",
        agent_id=delegation.principal_agent_id, platform_id=delegation.platform_id,
        job_id=delegation.job_id, dispute_id=opened.dispute_id, counterparty_id=delegation.worker_agent_id,
        category="research", provenance="challenged", verification_status="appealed",
        evidence_uri=payload.evidence_uri, evidence_hash=payload.evidence_hash,
        references=[ids["principal_provisional"], ids["worker_provisional"]],
        transaction_hash=protocol.get("appeal_submission_hash") or opened.transaction_hash,
        metadata={"delegation_id": delegation.id, "responsibility_case_id": opened.dispute_id,
                  "reason": payload.reason, "appellant_id": payload.appellant_id,
                  "bond_amount": payload.bond_amount, "protocol_transaction_hash": opened.transaction_hash,
                  "protocol_round": int(protocol.get("round", 1))},
    )
    delegation.status = "responsibility_appealed"
    principal = rebuild_projection(db, delegation.principal_agent_id, "research_trust_v6")
    worker = rebuild_projection(db, delegation.worker_agent_id, "research_trust_v6")
    db.commit()
    return {"appeal": event_dict(db, event), "protocol": protocol,
            "principal_reputation": projection_dict(principal), "worker_reputation": projection_dict(worker)}


@app.post("/delegations/{delegation_id}/responsibility/appeal/resolve")
def resolve_delegated_responsibility_appeal(delegation_id: str, db: Session = Depends(get_db), auth: dict = Depends(get_auth)) -> dict:
    delegation = db.get(Delegation, delegation_id)
    if not delegation:
        raise HTTPException(status_code=404, detail="Delegation not found")
    authorize_platform(auth, delegation.platform_id)
    return resolve_responsibility_case(db, delegation, appealed=True)


def registered_identity_event(db: Session, agent_id: str, identity: str) -> ReputationEvent | None:
    normalized = normalize_identity(identity)
    events = db.scalars(select(ReputationEvent).where(
        ReputationEvent.event_type == "AGENT_IDENTITY_REGISTERED"
    )).all()
    return next((event for event in events if event.agent_id == agent_id and event.event_metadata.get("identity") == normalized), None)


@app.post("/agents/{agent_id}/identities")
def register_agent_identity(agent_id: str, payload: AgentIdentityRegister, db: Session = Depends(get_db), auth: dict = Depends(get_auth)) -> dict:
    acquire_ledger_write_lock(db)
    agent = db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Unknown agent")
    authorize_platform(auth, agent.platform_id)
    try:
        identity = normalize_identity(payload.identity)
        message = registration_message(agent_id, identity, payload.nonce)
        verify_identity_signature(identity, message, payload.signature)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    existing_events = db.scalars(select(ReputationEvent).where(
        ReputationEvent.event_type == "AGENT_IDENTITY_REGISTERED"
    )).all()
    owner = next((event for event in existing_events if event.event_metadata.get("identity") == identity), None)
    if owner and owner.agent_id != agent_id:
        raise HTTPException(status_code=409, detail="Identity is already registered to another agent")
    if owner:
        projection = rebuild_identity_projection(db, agent_id)
        db.commit()
        return {"event": event_dict(db, owner), "identity": identity_projection_dict(projection), "idempotent_replay": True}
    event_id = new_id("rep_evt_agent_identity")
    metadata = {
        "identity": identity,
        "controller": identity,
        "nonce": payload.nonce,
        "signature_hash": hashlib.sha256(payload.signature.encode("utf-8")).hexdigest(),
        "proof_message_hash": hashlib.sha256(message.encode("utf-8")).hexdigest(),
    }
    contract_payload = {
        "event_id": event_id, "event_type": "AGENT_IDENTITY_REGISTERED",
        "agent_id": agent_id, "platform_id": agent.platform_id, "category": "agent_identity",
        "evidence_uri": payload.evidence_uri, "evidence_hash": payload.evidence_hash,
        "references": [], "metadata": metadata,
    }
    tx = write_contract_json("append_platform_event", contract_payload, event_id)
    event = append_event(
        db, event_id=event_id, event_type="AGENT_IDENTITY_REGISTERED", agent_id=agent_id,
        platform_id=agent.platform_id, category="agent_identity", provenance="platform_reported",
        verification_status="finalized", evidence_uri=payload.evidence_uri,
        evidence_hash=payload.evidence_hash, contract_address=genlayer.contract_address,
        transaction_hash=tx.get("tx_id") or None,
        metadata={**metadata, "contract_readback_verified": True},
    )
    projection = rebuild_identity_projection(db, agent_id)
    reputation = rebuild_projection(db, agent_id, "research_trust_v6")
    db.commit()
    return {"event": event_dict(db, event), "identity": identity_projection_dict(projection),
            "reputation": projection_dict(reputation), "tx": tx}


@app.post("/identity-bindings")
def propose_identity_binding(payload: IdentityBindingPropose, db: Session = Depends(get_db), auth: dict = Depends(get_auth)) -> dict:
    acquire_ledger_write_lock(db)
    source = db.get(Agent, payload.source_agent_id)
    target = db.get(Agent, payload.target_agent_id)
    if not source or not target:
        raise HTTPException(status_code=404, detail="Source or target agent not found")
    if source.id == target.id:
        raise HTTPException(status_code=400, detail="Cannot link an agent to itself")
    authorize_platform(auth, source.platform_id)
    try:
        source_identity = normalize_identity(payload.source_identity)
        target_identity = normalize_identity(payload.target_identity)
        message = binding_message(source.id, target.id, payload.nonce)
        verify_identity_signature(source_identity, message, payload.source_signature)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not registered_identity_event(db, source.id, source_identity):
        raise HTTPException(status_code=400, detail="Source identity is not registered to the source agent")
    if not registered_identity_event(db, target.id, target_identity):
        raise HTTPException(status_code=400, detail="Target identity is not registered to the target agent")
    source_projection = rebuild_identity_projection(db, source.id)
    if target.id in source_projection.linked_agents:
        raise HTTPException(status_code=409, detail="Agents are already linked")
    event_id = new_id("rep_evt_identity_binding")
    metadata = {
        "source_agent_id": source.id, "target_agent_id": target.id,
        "source_identity": source_identity, "target_identity": target_identity,
        "source_controller": source_identity, "nonce": payload.nonce,
        "source_signature_hash": hashlib.sha256(payload.source_signature.encode("utf-8")).hexdigest(),
        "proof_message_hash": hashlib.sha256(message.encode("utf-8")).hexdigest(),
    }
    contract_payload = {
        "event_id": event_id, "event_type": "IDENTITY_BINDING_PROPOSED",
        "agent_id": source.id, "platform_id": source.platform_id, "counterparty_id": target.id,
        "category": "agent_identity", "evidence_uri": payload.evidence_uri,
        "evidence_hash": payload.evidence_hash, "references": [], "metadata": metadata,
    }
    tx = write_contract_json("append_platform_event", contract_payload, event_id)
    event = append_event(
        db, event_id=event_id, event_type="IDENTITY_BINDING_PROPOSED", agent_id=source.id,
        platform_id=source.platform_id, counterparty_id=target.id, category="agent_identity",
        provenance="platform_reported", verification_status="pending",
        evidence_uri=payload.evidence_uri, evidence_hash=payload.evidence_hash,
        contract_address=genlayer.contract_address, transaction_hash=tx.get("tx_id") or None,
        metadata={**metadata, "contract_readback_verified": True},
    )
    db.commit()
    return {"proposal": event_dict(db, event), "signing_message": message, "tx": tx}


@app.post("/identity-bindings/{proposal_event_id}/confirm")
def confirm_identity_binding(proposal_event_id: str, payload: IdentityBindingConfirm, db: Session = Depends(get_db), auth: dict = Depends(get_auth)) -> dict:
    acquire_ledger_write_lock(db)
    proposal = db.scalars(select(ReputationEvent).where(
        ReputationEvent.event_id == proposal_event_id,
        ReputationEvent.event_type == "IDENTITY_BINDING_PROPOSED",
    )).first()
    if not proposal:
        raise HTTPException(status_code=404, detail="Unknown identity binding proposal")
    metadata = proposal.event_metadata
    target = db.get(Agent, str(metadata.get("target_agent_id") or ""))
    source = db.get(Agent, str(metadata.get("source_agent_id") or proposal.agent_id))
    if not source or not target:
        raise HTTPException(status_code=404, detail="Binding agents no longer exist")
    authorize_platform(auth, target.platform_id)
    message = binding_message(source.id, target.id, str(metadata.get("nonce") or ""))
    try:
        target_identity = str(metadata.get("target_identity") or "")
        verify_identity_signature(target_identity, message, payload.target_signature)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    confirmation_id = new_id("rep_evt_controller_confirmed")
    link_id = new_id("rep_evt_identity_linked")
    contract_payload = {
        "proposal_event_id": proposal_event_id, "confirmation_event_id": confirmation_id,
        "link_event_id": link_id, "platform_id": target.platform_id,
        "evidence_uri": payload.evidence_uri, "evidence_hash": payload.evidence_hash,
        "metadata": {"target_controller": target_identity,
                     "target_signature_hash": hashlib.sha256(payload.target_signature.encode("utf-8")).hexdigest()},
    }
    tx = write_contract_json("confirm_identity_binding", contract_payload, link_id)
    indexer.sync_once(db)
    for created_id in (confirmation_id, link_id):
        created = db.scalars(select(ReputationEvent).where(ReputationEvent.event_id == created_id)).first()
        if created:
            created.transaction_hash = tx.get("tx_id") or created.transaction_hash
            created.contract_address = genlayer.contract_address
            created.event_metadata = {**created.event_metadata, "contract_readback_verified": True}
    link = db.scalars(select(ReputationEvent).where(ReputationEvent.event_id == link_id)).first()
    if not link:
        raise RuntimeError("GenLayer identity link was not indexed")
    rebuild_all_identity_projections(db)
    source_identity = rebuild_identity_projection(db, source.id)
    source_reputation = rebuild_projection(db, source.id, "research_trust_v6")
    rebuild_projection(db, target.id, "research_trust_v6")
    db.commit()
    return {"link": event_dict(db, link), "identity": identity_projection_dict(source_identity),
            "reputation": projection_dict(source_reputation), "tx": tx}


@app.post("/identity-bindings/{proposal_event_id}/challenge")
def challenge_identity_binding(proposal_event_id: str, payload: IdentityBindingChallenge, db: Session = Depends(get_db), auth: dict = Depends(get_auth)) -> dict:
    acquire_ledger_write_lock(db)
    proposal = db.scalars(select(ReputationEvent).where(
        ReputationEvent.event_id == proposal_event_id,
        ReputationEvent.event_type == "IDENTITY_BINDING_PROPOSED",
    )).first()
    challenger = db.get(Agent, payload.challenger_agent_id)
    if not proposal or not challenger:
        raise HTTPException(status_code=404, detail="Binding proposal or challenger not found")
    authorize_platform(auth, challenger.platform_id)
    challenge_id = new_id("rep_evt_identity_challenge")
    judgment_id = new_id("rep_evt_identity_judgment")
    resolution_id = new_id("rep_evt_identity_resolution")
    contract_payload = {
        "event_id": challenge_id, "proposal_event_id": proposal_event_id,
        "agent_id": proposal.agent_id, "platform_id": proposal.platform_id,
        "counterparty_id": payload.challenger_agent_id, "category": "agent_identity",
        "evidence_uri": payload.evidence_uri, "evidence_hash": payload.evidence_hash,
        "metadata": {"reason": payload.reason, "judgment_event_id": judgment_id,
                     "resolution_event_id": resolution_id},
    }
    tx = write_contract_json("challenge_identity_binding", contract_payload, judgment_id)
    indexer.sync_once(db)
    for created_id in (challenge_id, judgment_id, resolution_id):
        created = db.scalars(select(ReputationEvent).where(ReputationEvent.event_id == created_id)).first()
        if created:
            created.transaction_hash = tx.get("tx_id") or created.transaction_hash
            created.contract_address = genlayer.contract_address
            created.event_metadata = {**created.event_metadata, "contract_readback_verified": True}
    judgment = db.scalars(select(ReputationEvent).where(ReputationEvent.event_id == judgment_id)).first()
    resolution = db.scalars(select(ReputationEvent).where(ReputationEvent.event_id == resolution_id)).first()
    if not judgment or not resolution:
        raise RuntimeError("GenLayer identity judgment was not indexed")
    rebuild_all_identity_projections(db)
    source_identity = rebuild_identity_projection(db, proposal.agent_id)
    db.commit()
    return {"judgment": event_dict(db, judgment), "resolution": event_dict(db, resolution),
            "identity": identity_projection_dict(source_identity), "tx": tx}


@app.get("/agents/{agent_id}/identity")
def get_agent_identity(agent_id: str, db: Session = Depends(get_db)) -> dict:
    if not db.get(Agent, agent_id):
        raise HTTPException(status_code=404, detail="Unknown agent")
    projection = read_identity_projection(db, agent_id)
    db.commit()
    return identity_projection_dict(projection)


@app.get("/identities/resolve")
def resolve_identity(identity: str, db: Session = Depends(get_db)) -> dict:
    try:
        normalized = normalize_identity(identity)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    projection = db.scalars(select(AgentIdentityProjection).where(
        AgentIdentityProjection.projection_version == "v1"
    )).all()
    matched = next((row for row in projection if normalized in (row.aliases or [])), None)
    if not matched:
        raise HTTPException(status_code=404, detail="Unknown identity")
    reputation = read_reputation_projection(db, matched.agent_id)
    db.commit()
    return {"identity": identity_projection_dict(matched), "reputation": projection_dict(reputation),
            "passport_url": f"/agents/{matched.canonical_agent_id}/profile"}


@app.post("/attestations")
def create_attestation(payload: AttestationCreate, db: Session = Depends(get_db), auth: dict = Depends(get_auth)) -> dict:
    acquire_ledger_write_lock(db)
    authorize_platform(auth, payload.platform_id)
    if payload.type != "jobs_completed":
        raise HTTPException(status_code=400, detail="V2.1 supports jobs_completed attestations")
    if not payload.evidence_uri or not payload.evidence_hash:
        raise HTTPException(status_code=400, detail="Attestations require evidence_uri and evidence_hash")
    agent = db.get(Agent, payload.agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Unknown agent")
    if not db.get(Platform, payload.platform_id):
        raise HTTPException(status_code=404, detail="Unknown platform")
    event_id = new_id("rep_evt_attestation")
    credibility = rebuild_platform_credibility(db, payload.platform_id)
    metadata = {
        "type": payload.type, "value": payload.value,
        "period_start": payload.period_start, "period_end": payload.period_end,
        "issuer_credibility_bps": credibility.credibility_score * 100,
        "credibility_projection_version": "platform_credibility_v1",
    }
    contract_payload = {
        "event_id": event_id, "event_type": "REPUTATION_ATTESTED",
        "agent_id": payload.agent_id, "platform_id": payload.platform_id,
        "category": payload.category, "evidence_uri": payload.evidence_uri,
        "evidence_hash": payload.evidence_hash, "references": [], "metadata": metadata,
    }
    tx = write_contract_json("append_platform_event", contract_payload, event_id)
    event = append_event(
        db, event_id=event_id, event_type="REPUTATION_ATTESTED", agent_id=payload.agent_id,
        platform_id=payload.platform_id, category=payload.category, provenance="platform_reported",
        verification_status="uncontested", evidence_uri=payload.evidence_uri,
        evidence_hash=payload.evidence_hash, contract_address=genlayer.contract_address,
        transaction_hash=tx.get("tx_id") or None, metadata={**metadata, "contract_readback_verified": True},
    )
    projection = rebuild_projection(db, payload.agent_id, "research_trust_v3")
    db.commit()
    return {"event": event_dict(db, event), "reputation": projection_dict(projection), "tx": tx}


@app.post("/attestations/{event_id}/confirm")
def confirm_attestation(event_id: str, payload: AttestationConfirm, db: Session = Depends(get_db), auth: dict = Depends(get_auth)) -> dict:
    acquire_ledger_write_lock(db)
    authorize_platform(auth, payload.platform_id)
    original = db.scalars(select(ReputationEvent).where(ReputationEvent.event_id == event_id)).first()
    if not original or original.event_type != "REPUTATION_ATTESTED":
        raise HTTPException(status_code=404, detail="Unknown attestation")
    if payload.value > int(original.event_metadata.get("value") or 0):
        raise HTTPException(status_code=400, detail="Confirmation cannot exceed the reported value")
    confirmation_id = new_id("rep_evt_confirmation")
    credibility = rebuild_platform_credibility(db, payload.platform_id)
    metadata = {
        "type": original.event_metadata.get("type"), "value": payload.value,
        "attestation_event_id": event_id,
        "issuer_credibility_bps": credibility.credibility_score * 100,
        "credibility_projection_version": "platform_credibility_v1",
    }
    contract_payload = {
        "event_id": confirmation_id, "agent_id": original.agent_id, "platform_id": payload.platform_id,
        "counterparty_id": payload.counterparty_id, "category": original.category or "research",
        "evidence_uri": payload.evidence_uri, "evidence_hash": payload.evidence_hash,
        "attestation_event_id": event_id, "metadata": metadata,
    }
    tx = write_contract_json("confirm_attestation", contract_payload, confirmation_id)
    event = append_event(
        db, event_id=confirmation_id, event_type="COUNTERPARTY_CONFIRMED", agent_id=original.agent_id,
        platform_id=payload.platform_id, counterparty_id=payload.counterparty_id,
        category=original.category, provenance="counterparty_confirmed", verification_status="finalized",
        evidence_uri=payload.evidence_uri, evidence_hash=payload.evidence_hash, references=[event_id],
        contract_address=genlayer.contract_address, transaction_hash=tx.get("tx_id") or None,
        metadata={**metadata, "contract_readback_verified": True},
    )
    projection = rebuild_projection(db, original.agent_id, "research_trust_v3")
    db.commit()
    return {"event": event_dict(db, event), "reputation": projection_dict(projection), "tx": tx}


@app.post("/events/{event_id}/challenge")
def challenge_attestation(event_id: str, payload: EventChallenge, db: Session = Depends(get_db), auth: dict = Depends(get_auth)) -> dict:
    acquire_ledger_write_lock(db)
    original = db.scalars(select(ReputationEvent).where(ReputationEvent.event_id == event_id)).first()
    if not original or original.event_type != "REPUTATION_ATTESTED":
        raise HTTPException(status_code=404, detail="Unknown attestation")
    challenge_id = new_id("rep_evt_challenge")
    judgment_id = new_id("rep_evt_attestation_judgment")
    superseded_id = new_id("rep_evt_superseded")
    replacement_id = new_id("rep_evt_attestation_corrected")
    contract_payload = {
        "event_id": challenge_id, "attestation_event_id": event_id,
        "agent_id": original.agent_id, "platform_id": original.platform_id,
        "category": original.category or "research", "evidence_uri": payload.evidence_uri,
        "evidence_hash": payload.evidence_hash, "counterparty_id": payload.challenger_id,
        "metadata": {"reason": payload.reason, "judgment_event_id": judgment_id,
                     "superseded_event_id": superseded_id, "replacement_event_id": replacement_id},
    }
    tx = write_contract_json("challenge_attestation", contract_payload, judgment_id)
    indexer.sync_once(db)
    judgment = db.scalars(select(ReputationEvent).where(ReputationEvent.event_id == judgment_id)).first()
    if not judgment:
        raise RuntimeError("GenLayer attestation judgment was not indexed")
    for created_event_id in (challenge_id, judgment_id, superseded_id, replacement_id):
        created_event = db.scalars(select(ReputationEvent).where(ReputationEvent.event_id == created_event_id)).first()
        if created_event:
            created_event.transaction_hash = tx.get("tx_id") or created_event.transaction_hash
            created_event.contract_address = genlayer.contract_address
            created_event.event_metadata = {**created_event.event_metadata, "contract_readback_verified": True}
    projection = rebuild_projection(db, original.agent_id, "research_trust_v3")
    issuer_credibility = rebuild_platform_credibility(db, original.platform_id)
    db.commit()
    return {"judgment": event_dict(db, judgment), "reputation": projection_dict(projection),
            "issuer_credibility": platform_credibility_dict(issuer_credibility), "tx": tx}


@app.get("/agents/{agent_id}/reputation")
def get_reputation(agent_id: str, projection: str = "research_trust_v6", db: Session = Depends(get_db)) -> dict:
    if not db.get(Agent, agent_id):
        raise HTTPException(status_code=404, detail="Unknown agent")
    if projection not in {"research_trust_v1", "research_trust_v2", "research_trust_v3", "research_trust_v4", "research_trust_v5", "research_trust_v6"}:
        raise HTTPException(status_code=400, detail="Unsupported projection")
    result = read_reputation_projection(db, agent_id, projection)
    db.commit()
    return projection_dict(result)


@app.get("/agents/{agent_id}/history")
def get_history(agent_id: str, db: Session = Depends(get_db)) -> dict:
    if not db.get(Agent, agent_id):
        raise HTTPException(status_code=404, detail="Unknown agent")
    identity = read_identity_projection(db, agent_id)
    member_ids = identity.linked_agents or [agent_id]
    jobs = db.scalars(select(Job).where(Job.provider_agent_id.in_(member_ids)).order_by(Job.created_at.desc())).all()
    ledger_events = db.scalars(select(ReputationEvent).where(
        ReputationEvent.agent_id.in_(member_ids)
    ).order_by(ReputationEvent.occurred_at.desc())).all()
    return {
        "agent_id": identity.canonical_agent_id,
        "requested_agent_id": agent_id,
        "identity": identity_projection_dict(identity),
        "jobs": [job_to_dict(job) for job in jobs],
        "disputes": [dispute_to_dict(d) for d in db.scalars(select(Dispute).join(Job).where(Job.provider_agent_id.in_(member_ids))).all()],
        "judgments": [judgment_to_dict(j) for j in db.scalars(select(Judgment).join(Job).where(Job.provider_agent_id.in_(member_ids))).all()],
        "reputation_snapshots": [],
        "events": [event_dict(db, event) for event in ledger_events],
        "timeline": [ledger_timeline_event(db, event) for event in ledger_events],
    }


@app.get("/agents/{agent_id}/profile")
def public_profile(agent_id: str, db: Session = Depends(get_db)) -> dict:
    agent = db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Unknown agent")
    history = get_history(agent_id, db)
    identity = read_identity_projection(db, agent_id)
    canonical_agent = db.get(Agent, identity.canonical_agent_id) or agent
    projection = read_reputation_projection(db, agent_id)
    db.commit()
    return {"agent": agent_to_dict(canonical_agent), "requested_alias": agent_to_dict(agent),
            "identity": identity_projection_dict(identity), "reputation": projection_dict(projection), **history}


@app.get("/agents/{agent_id}/events")
def get_agent_events(agent_id: str, limit: int = 100, db: Session = Depends(get_db)) -> dict:
    if not db.get(Agent, agent_id):
        raise HTTPException(status_code=404, detail="Unknown agent")
    identity = read_identity_projection(db, agent_id)
    events = db.scalars(select(ReputationEvent).where(
        ReputationEvent.agent_id.in_(identity.linked_agents or [agent_id])
    ).order_by(ReputationEvent.occurred_at.desc()).limit(min(limit, 500))).all()
    return {"agent_id": identity.canonical_agent_id, "requested_agent_id": agent_id,
            "identity": identity_projection_dict(identity), "events": [event_dict(db, event) for event in events]}


@app.get("/events/{event_id}")
def get_event(event_id: str, db: Session = Depends(get_db)) -> dict:
    event = db.scalars(select(ReputationEvent).where(ReputationEvent.event_id == event_id)).first()
    if not event:
        raise HTTPException(status_code=404, detail="Unknown reputation event")
    return event_dict(db, event)


@app.get("/health/indexer")
def indexer_health(db: Session = Depends(get_db)) -> dict:
    return indexer.health(db)


@app.get("/admin/genlayer/transactions/{tx_id}", dependencies=[Depends(require_admin_key)])
def genlayer_transaction_diagnostics(tx_id: str) -> dict:
    try:
        return genlayer.receipt_diagnostics(tx_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/admin/indexer/sync", dependencies=[Depends(require_admin_key)])
def sync_indexer(db: Session = Depends(get_db)) -> dict:
    return indexer.sync_once(db)


@app.post("/admin/projections/rebuild", dependencies=[Depends(require_admin_key)])
def rebuild_projections(db: Session = Depends(get_db)) -> dict:
    projections = rebuild_all_projections(db)
    db.commit()
    identity_count = db.scalar(select(func.count()).select_from(AgentIdentityProjection)) or 0
    return {"rebuilt": len(projections) + identity_count,
            "projections": ["research_trust_v1", "research_trust_v2", "research_trust_v3",
                            "research_trust_v4", "research_trust_v5", "research_trust_v6", "platform_credibility_v1", "agent_identity_v1"]}


@app.post("/trust/evaluate", dependencies=[Depends(require_key)])
def evaluate_trust(payload: TrustEvaluateRequest, db: Session = Depends(get_db)) -> dict:
    agent = db.get(Agent, payload.agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Unknown agent")

    reputation = rebuild_projection(db, payload.agent_id, "research_trust_v6")
    judgments = db.scalars(select(Judgment).join(Job).where(Job.provider_agent_id == payload.agent_id)).all()
    fraud_judgments = [judgment for judgment in judgments if judgment.verdict == "fraudulent"]
    fraud_incidents = reputation.fraud_incidents
    risk_score = reputation.risk_score

    reasons = []
    if fraud_incidents:
        reasons.append("Fraudulent judgment recorded on GenLayer")
    if reputation.status == "flagged":
        reasons.append("Flagged status")
    if reputation.trust_score < 70:
        reasons.append("Trust score below common marketplace threshold")
    if risk_score > 70:
        reasons.append("High computed risk score")
    if payload.job_value >= 10000:
        reasons.append("High-value job requires stricter marketplace policy")

    if fraud_incidents or reputation.status == "flagged" or risk_score >= 70:
        recommendation = "high_risk"
        confidence = 0.94
    elif reputation.trust_score < 70 or reputation.disputes:
        recommendation = "manual_review"
        confidence = 0.82
    else:
        recommendation = "low_risk"
        confidence = 0.88

    policy = payload.policy
    policy_reasons = []
    eligible = True
    if policy:
        if reputation.trust_score < policy.min_trust_score:
            eligible = False
            policy_reasons.append(f"Trust score below policy minimum of {policy.min_trust_score}")
        if risk_score > policy.max_risk_score:
            eligible = False
            policy_reasons.append(f"Risk score above policy maximum of {policy.max_risk_score}")
        if fraud_incidents > policy.max_fraud_incidents:
            eligible = False
            policy_reasons.append("Fraud incident count exceeds policy")
        if reputation.status == "flagged" and not policy.allow_flagged:
            eligible = False
            policy_reasons.append("Policy does not allow flagged agents")

    latest_fraud = fraud_judgments[-1] if fraud_judgments else None
    policy_outcome = "eligible" if eligible else "ineligible"
    if policy:
        append_event(
            db, event_type="POLICY_EVALUATED", agent_id=payload.agent_id,
            platform_id=agent.platform_id, category=payload.job_type,
            provenance="platform_reported", verification_status="finalized",
            metadata={"outcome": policy_outcome, "reasons": policy_reasons, "policy": policy.model_dump()},
        )
        db.commit()
    return {
        "agent_id": payload.agent_id,
        "job_type": payload.job_type,
        "job_value": payload.job_value,
        "trust_score": reputation.trust_score,
        "risk_score": risk_score,
        "fraud_incidents": fraud_incidents,
        "status": reputation.status,
        "recommendation": recommendation,
        "confidence": confidence,
        "reasons": reasons or ["No material risk signals found"],
        "latest_judgment": judgment_to_dict(latest_fraud) if latest_fraud else None,
        "policy_result": {
            "evaluated": policy is not None,
            "eligible": eligible if policy else None,
            "outcome": policy_outcome,
            "reasons": policy_reasons,
            "policy": policy.model_dump() if policy else None,
        },
        "timeline": build_reputation_timeline(
            db,
            payload.agent_id,
            policy_event={
                "platform": "Requesting marketplace",
                "title": f"Policy check: {policy_outcome}",
                "detail": policy_reasons[0] if policy_reasons else "Agent satisfies this marketplace policy.",
                "severity": "danger" if not eligible else "success",
            }
            if policy
            else None,
        ),
    }


def require_job(db: Session, job_id: str) -> Job:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Unknown job")
    return job


def ledger_timeline_event(db: Session, event: ReputationEvent) -> dict:
    data = event_dict(db, event)
    titles = {
        "AGENT_REGISTERED": "Agent registered",
        "JOB_CREATED": "Job created",
        "DELIVERABLE_SUBMITTED": "Deliverable submitted",
        "JOB_ACCEPTED": "Job accepted",
        "DISPUTE_OPENED": "Dispute opened",
        "JUDGMENT_PROVISIONAL": "GenLayer judgment provisional",
        "APPEAL_SUBMITTED": "GenLayer protocol appeal submitted",
        "APPEAL_RESOLVED": "GenLayer appeal resolved",
        "JUDGMENT_UPHELD": "Judgment upheld",
        "JUDGMENT_OVERTURNED": "Judgment overturned",
        "JUDGMENT_FINALIZED": "GenLayer judgment finalized",
        "EVENT_SUPERSEDED": "Prior judgment superseded",
        "FRAUD_CONFIRMED": "Fraud confirmed",
        "POLICY_EVALUATED": "Marketplace policy evaluated",
    }
    verdict = str(event.event_metadata.get("verdict", ""))
    danger = event.event_type in {"FRAUD_CONFIRMED", "EVENT_CHALLENGED"} or verdict == "fraudulent"
    return {
        "id": event.event_id,
        "type": event.event_type.lower(),
        "date": event.occurred_at.strftime("%b %d"),
        "timestamp": event.occurred_at.isoformat(),
        "marker": "!" if danger else "✓",
        "title": titles.get(event.event_type, event.event_type.replace("_", " ").title()),
        "detail": event.event_metadata.get("reasoning_summary") or event.event_metadata.get("reason") or verdict,
        "severity": "danger" if danger else "warning" if event.verification_status in {"pending", "provisional", "appealed"} else "success",
        "verify_url": genlayer.verify_url(event.transaction_hash) if event.transaction_hash else "",
        "provenance": event.provenance,
        "verification_status": event.verification_status,
        "evidence": {"reputation_event": data},
    }


def build_reputation_timeline(db: Session, agent_id: str, policy_event: dict | None = None) -> list[dict]:
    jobs = db.scalars(select(Job).where(Job.provider_agent_id == agent_id)).all()
    job_ids = [job.id for job in jobs]
    deliverables = db.scalars(select(Deliverable).where(Deliverable.job_id.in_(job_ids))).all() if job_ids else []
    disputes = db.scalars(select(Dispute).where(Dispute.job_id.in_(job_ids))).all() if job_ids else []
    judgments = db.scalars(select(Judgment).where(Judgment.job_id.in_(job_ids))).all() if job_ids else []
    deliverables_by_job = {deliverable.job_id: deliverable for deliverable in deliverables}
    disputes_by_job = {dispute.job_id: dispute for dispute in disputes}
    judgments_by_job = {judgment.job_id: judgment for judgment in judgments}

    events = []
    for job in jobs:
        events.append(
            timeline_event(
                job.created_at,
                "✓" if job.status in {"accepted"} else "•",
                "Job created",
                job.task_spec,
                "neutral",
                "job_created",
                evidence_for(job, deliverables_by_job.get(job.id), disputes_by_job.get(job.id), judgments_by_job.get(job.id)),
            )
        )
        if job.status == "accepted":
            events.append(
                timeline_event(
                    job.updated_at,
                    "✓",
                    "Job accepted",
                    job.task_spec,
                    "success",
                    "job_accepted",
                    evidence_for(job, deliverables_by_job.get(job.id), disputes_by_job.get(job.id), judgments_by_job.get(job.id)),
                )
            )

    for deliverable in deliverables:
        job = next((item for item in jobs if item.id == deliverable.job_id), None)
        events.append(
            timeline_event(
                deliverable.submitted_at,
                "✓",
                "Deliverable submitted",
                deliverable.summary or deliverable.deliverable_uri,
                "success",
                "deliverable_submitted",
                evidence_for(job, deliverable, disputes_by_job.get(deliverable.job_id), judgments_by_job.get(deliverable.job_id)),
            )
        )

    for dispute in disputes:
        job = next((item for item in jobs if item.id == dispute.job_id), None)
        events.append(
            timeline_event(
                dispute.opened_at,
                "⚠",
                "Dispute opened",
                dispute.reason,
                "warning",
                "dispute_opened",
                evidence_for(job, deliverables_by_job.get(dispute.job_id), dispute, judgments_by_job.get(dispute.job_id)),
            )
        )

    for judgment in judgments:
        job = next((item for item in jobs if item.id == judgment.job_id), None)
        is_fraud = judgment.verdict == "fraudulent"
        events.append(
            timeline_event(
                judgment.created_at,
                "🚨" if is_fraud else "✓",
                "Fraudulent judgment recorded on GenLayer" if is_fraud else f"Judgment recorded: {judgment.verdict}",
                judgment.reasoning_summary,
                "danger" if is_fraud else "success",
                "genlayer_judgment",
                evidence_for(job, deliverables_by_job.get(judgment.job_id), disputes_by_job.get(judgment.job_id), judgment),
                judgment.verify_url,
            )
        )

    if policy_event:
        events.append(
            timeline_event(
                None,
                "⚖",
                f"{policy_event['platform']} {policy_event['title']}",
                policy_event["detail"],
                policy_event["severity"],
                "policy_check",
                {
                    "policy": {
                        "platform": policy_event["platform"],
                        "result": policy_event["title"].replace("Policy check: ", ""),
                        "reason": policy_event["detail"],
                    }
                },
            )
        )

    events.sort(key=lambda event: event["sort_key"])
    for event in events:
        event.pop("sort_key", None)
    return events


def timeline_event(
    occurred_at,
    marker: str,
    title: str,
    detail: str,
    severity: str,
    event_type: str,
    evidence: dict | None = None,
    verify_url: str = "",
) -> dict:
    timestamp = occurred_at.isoformat() if occurred_at else ""
    return {
        "id": f"{event_type}_{timestamp or 'now'}_{title.lower().replace(' ', '_')}",
        "type": event_type,
        "date": occurred_at.strftime("%b %d") if occurred_at else "Now",
        "timestamp": timestamp,
        "marker": marker,
        "title": title,
        "detail": detail,
        "severity": severity,
        "verify_url": verify_url,
        "evidence": evidence or {},
        "sort_key": timestamp or "9999-12-31T23:59:59",
    }


def evidence_for(
    job: Job | None = None,
    deliverable: Deliverable | None = None,
    dispute: Dispute | None = None,
    judgment: Judgment | None = None,
) -> dict:
    evidence = {}
    if job:
        evidence["job"] = job_to_dict(job)
    if deliverable:
        evidence["deliverable"] = deliverable_to_dict(deliverable)
    if dispute:
        evidence["dispute"] = dispute_to_dict(dispute)
    if judgment:
        evidence["judgment"] = judgment_to_dict(judgment)
    return evidence


def reset_demo_data(db: Session) -> dict:
    # V2 reputation events are append-only. A demo reset starts a fresh namespaced
    # run and clears client state without deleting ledger-backed history.
    return {"deleted": {}, "ledger_preserved": True}


def json_list(values: list[str]) -> str:
    return json.dumps(values)


def contract_event_id(kind: str, value: str) -> str:
    digest = hashlib.sha256(f"{kind}:{value}".encode("utf-8")).hexdigest()[:24]
    return f"rep_evt_{kind}_{digest}"


def write_platform_event(
    event_type: str,
    agent_id: str,
    platform_id: str,
    *,
    job_id: str = "",
    category: str = "research",
    counterparty_id: str = "",
    evidence_uri: str = "",
    metadata: dict | None = None,
) -> dict:
    event_id = contract_event_id(event_type.lower(), job_id or agent_id)
    payload = {
        "event_id": event_id, "event_type": event_type, "agent_id": agent_id,
        "platform_id": platform_id, "job_id": job_id, "dispute_id": "",
        "counterparty_id": counterparty_id, "category": category,
        "evidence_uri": evidence_uri, "evidence_hash": "", "references": [],
        "metadata": metadata or {},
    }
    existing = genlayer.call_json("get_event", [event_id])
    if isinstance(existing, dict) and existing.get("event_id") == event_id:
        return {
            "mode": "live", "method": "append_platform_event", "tx_id": "",
            "contract_address": genlayer.contract_address, "verify_url": "",
            "contract_event": existing, "idempotent_replay": True,
        }
    tx = genlayer.write("append_platform_event", [json.dumps(payload, sort_keys=True)])
    for _ in range(settings.genlayer_read_attempts):
        contract_event = genlayer.call_json("get_event", [event_id])
        if isinstance(contract_event, dict) and contract_event.get("event_id") == event_id:
            tx["contract_event"] = contract_event
            return tx
        time.sleep(settings.genlayer_read_interval_seconds)
    raise RuntimeError(
        f"GenLayer accepted transaction {tx.get('tx_id', '')}, but event {event_id} was not readable from contract state. "
        f"Execution: {tx.get('execution_result', 'unknown')}. Contract error: {tx.get('contract_error') or 'none reported'}"
    )


def write_contract_json(method: str, payload: dict, expected_event_id: str) -> dict:
    existing = genlayer.call_json("get_event", [expected_event_id])
    if isinstance(existing, dict) and existing.get("event_id") == expected_event_id:
        return {"mode": "live", "method": method, "tx_id": "", "contract_address": genlayer.contract_address,
                "contract_event": existing, "idempotent_replay": True}
    tx = genlayer.write(method, [json.dumps(payload, sort_keys=True)])
    for _ in range(settings.genlayer_read_attempts):
        contract_event = genlayer.call_json("get_event", [expected_event_id])
        if isinstance(contract_event, dict) and contract_event.get("event_id") == expected_event_id:
            tx["contract_event"] = contract_event
            return tx
        time.sleep(settings.genlayer_read_interval_seconds)
    raise RuntimeError(f"GenLayer transaction {tx.get('tx_id', '')} did not expose event {expected_event_id}")


def delegation_to_dict(delegation: Delegation) -> dict:
    return {
        "delegation_id": delegation.id,
        "principal_agent_id": delegation.principal_agent_id,
        "worker_agent_id": delegation.worker_agent_id,
        "platform_id": delegation.platform_id,
        "job_id": delegation.job_id,
        "parent_delegation_id": delegation.parent_delegation_id,
        "authority_scope": delegation.authority_scope,
        "permitted_tools": delegation.permitted_tools,
        "permitted_actions": delegation.permitted_actions,
        "spending_limit": float(delegation.spending_limit or 0),
        "currency": delegation.currency,
        "allow_subdelegation": delegation.allow_subdelegation,
        "disclosure_required": delegation.disclosure_required,
        "evidence_uri": delegation.evidence_uri,
        "evidence_hash": delegation.evidence_hash,
        "status": delegation.status,
        "created_at": delegation.created_at.isoformat(),
        "accepted_at": delegation.accepted_at.isoformat() if delegation.accepted_at else None,
    }


def append_delegation_event(
    db: Session,
    delegation: Delegation,
    event_type: str,
    *,
    event_id: str,
    actor_agent_id: str,
    counterparty_id: str,
    evidence_uri: str,
    evidence_hash: str,
    references: list[str],
    metadata: dict,
) -> tuple[ReputationEvent, dict]:
    payload = {
        "event_id": event_id, "event_type": event_type, "agent_id": actor_agent_id,
        "platform_id": delegation.platform_id, "job_id": delegation.job_id,
        "dispute_id": "", "counterparty_id": counterparty_id, "category": "research",
        "evidence_uri": evidence_uri, "evidence_hash": evidence_hash,
        "references": references, "metadata": {"delegation_id": delegation.id, **metadata},
    }
    tx = write_contract_json("append_platform_event", payload, event_id)
    event = append_event(
        db, event_id=event_id, event_type=event_type, agent_id=actor_agent_id,
        platform_id=delegation.platform_id, job_id=delegation.job_id,
        counterparty_id=counterparty_id, category="research", provenance="platform_reported",
        verification_status="finalized", evidence_uri=evidence_uri, evidence_hash=evidence_hash,
        references=references, contract_address=genlayer.contract_address,
        transaction_hash=tx.get("tx_id") or None,
        metadata={"delegation_id": delegation.id, **metadata, "contract_readback_verified": True},
    )
    return event, tx


def responsibility_event_ids(case_id: str) -> dict[str, str]:
    return {
        "dispute": contract_event_id("responsibility_disputed", case_id),
        "principal_provisional": contract_event_id("responsibility_principal_provisional", case_id),
        "worker_provisional": contract_event_id("responsibility_worker_provisional", case_id),
        "appeal": contract_event_id("responsibility_appealed", case_id),
        "principal_final": contract_event_id("responsibility_principal_final", case_id),
        "worker_final": contract_event_id("responsibility_worker_final", case_id),
        "principal_liability": contract_event_id("liability_principal", case_id),
        "worker_liability": contract_event_id("liability_worker", case_id),
    }


def responsibility_open_event(db: Session, delegation: Delegation) -> ReputationEvent | None:
    events = db.scalars(select(ReputationEvent).where(
        ReputationEvent.job_id == delegation.job_id,
        ReputationEvent.event_type == "RESPONSIBILITY_DISPUTED",
    ).order_by(ReputationEvent.occurred_at.desc())).all()
    return next((event for event in events if event.event_metadata.get("delegation_id") == delegation.id), None)


def resolve_responsibility_case(db: Session, delegation: Delegation, *, appealed: bool) -> dict:
    acquire_ledger_write_lock(db)
    opened = responsibility_open_event(db, delegation)
    if not opened or not opened.transaction_hash or not opened.dispute_id:
        raise HTTPException(status_code=409, detail="Responsibility judgment has not been submitted")
    ids = opened.event_metadata.get("event_ids") or responsibility_event_ids(opened.dispute_id)
    existing = db.scalars(select(ReputationEvent).where(
        ReputationEvent.event_id == ids["principal_liability"]
    )).first()
    if existing:
        raise HTTPException(status_code=409, detail="Responsibility judgment is already finalized")
    appeal = db.scalars(select(ReputationEvent).where(ReputationEvent.event_id == ids["appeal"])).first()
    if appealed and not appeal:
        raise HTTPException(status_code=409, detail="Responsibility appeal has not been submitted")
    if not appealed and appeal:
        raise HTTPException(status_code=409, detail="Appealed responsibility must use the appeal resolution endpoint")
    protocol = genlayer.transaction_status(opened.transaction_hash)
    if protocol["status"] == "READY_TO_FINALIZE":
        protocol = genlayer.finalize_transaction(opened.transaction_hash)
    if protocol["status"] != "FINALIZED":
        raise HTTPException(status_code=409, detail=f"GenLayer responsibility judgment is not final: {protocol['status']}")
    current = genlayer.call_json("get_responsibility_case", [opened.dispute_id])
    if not isinstance(current, dict) or not current.get("outcome"):
        raise RuntimeError("Final GenLayer responsibility judgment could not be read from contract state")
    payload = {
        "responsibility_case_id": opened.dispute_id,
        "principal_provisional_event_id": ids["principal_provisional"],
        "worker_provisional_event_id": ids["worker_provisional"],
        "appealed": appealed, "appeal_event_id": ids["appeal"],
        "appeal_reason": str((appeal.event_metadata if appeal else {}).get("reason", "")),
        "evidence_uri": appeal.evidence_uri if appeal else opened.evidence_uri or "",
        "evidence_hash": appeal.evidence_hash if appeal else opened.evidence_hash or "",
        "protocol_transaction_hash": opened.transaction_hash,
        "protocol_round": int(protocol.get("round", 0)),
        "principal_final_event_id": ids["principal_final"],
        "worker_final_event_id": ids["worker_final"],
        "principal_liability_event_id": ids["principal_liability"],
        "worker_liability_event_id": ids["worker_liability"],
    }
    ledger_tx = write_contract_json("finalize_responsibility", payload, ids["principal_liability"])
    indexer.sync_once(db)
    final_events = {}
    for key in ["principal_final", "worker_final", "principal_liability", "worker_liability"]:
        event = db.scalars(select(ReputationEvent).where(ReputationEvent.event_id == ids[key])).first()
        if not event:
            raise RuntimeError(f"Final responsibility event {ids[key]} was not indexed")
        event.transaction_hash = opened.transaction_hash
        event.contract_address = genlayer.contract_address
        event.event_metadata = {
            **event.event_metadata, "contract_readback_verified": True,
            "ledger_record_transaction_hash": ledger_tx.get("tx_id") or "",
        }
        final_events[key] = event
    delegation.status = "responsibility_finalized"
    principal = rebuild_projection(db, delegation.principal_agent_id, "research_trust_v6")
    worker = rebuild_projection(db, delegation.worker_agent_id, "research_trust_v6")
    db.commit()
    return {
        "responsibility_case_id": opened.dispute_id,
        "outcome": current.get("outcome"),
        "delegator_responsibility_bps": int(current.get("delegator_responsibility_bps", 0)),
        "worker_responsibility_bps": int(current.get("worker_responsibility_bps", 0)),
        "events": {key: event_dict(db, event) for key, event in final_events.items()},
        "principal_reputation": projection_dict(principal),
        "worker_reputation": projection_dict(worker),
        "protocol": protocol, "ledger_tx": ledger_tx,
    }


def platform_to_dict(platform: Platform) -> dict:
    return {"id": platform.id, "name": platform.name, "owner_wallet": platform.owner_wallet, "webhook_url": platform.webhook_url}


def platform_credibility_dict(projection: PlatformCredibilityProjection) -> dict:
    return {
        "platform_id": projection.platform_id,
        "projection": f"platform_credibility_{projection.projection_version}",
        "credibility_score": projection.credibility_score,
        "credibility_bps": projection.credibility_score * 100,
        "status": projection.status,
        "attestations_issued": projection.attestations_issued,
        "confirmations_received": projection.confirmations_received,
        "challenges": projection.challenges,
        "overturns": projection.overturns,
        "verified_identity": projection.verified_identity,
        "last_event_id": projection.last_event_id,
        "calculated_at": projection.calculated_at.isoformat(),
        "details": projection.details,
    }


def agent_to_dict(agent: Agent) -> dict:
    return {
        "id": agent.id,
        "platform_id": agent.platform_id,
        "owner_wallet": agent.owner_wallet,
        "name": agent.name,
        "capabilities": agent.capabilities,
        "metadata_uri": agent.metadata_uri,
        "status": agent.status,
    }


def job_to_dict(job: Job) -> dict:
    return {
        "id": job.id,
        "platform_id": job.platform_id,
        "requester_id": job.requester_id,
        "provider_agent_id": job.provider_agent_id,
        "task_spec": job.task_spec,
        "category": job.category,
        "payment_amount": float(job.payment_amount),
        "currency": job.currency,
        "status": job.status,
    }


def deliverable_to_dict(deliverable: Deliverable) -> dict:
    return {
        "id": deliverable.id,
        "job_id": deliverable.job_id,
        "deliverable_uri": deliverable.deliverable_uri,
        "summary": deliverable.summary,
        "evidence_urls": deliverable.evidence_urls,
    }


def dispute_to_dict(dispute: Dispute) -> dict:
    return {
        "id": dispute.id,
        "job_id": dispute.job_id,
        "claimant": dispute.claimant,
        "reason": dispute.reason,
        "evidence_uri": dispute.evidence_uri,
        "bond_amount": float(dispute.bond_amount),
        "status": dispute.status,
    }


def judgment_to_dict(judgment: Judgment) -> dict:
    verify_url = genlayer.verify_url(judgment.tx_hash) if judgment.tx_hash else judgment.verify_url
    return {
        "id": judgment.id,
        "job_id": judgment.job_id,
        "dispute_id": judgment.dispute_id,
        "verdict": judgment.verdict,
        "confidence_bps": judgment.confidence_bps,
        "reasoning_summary": judgment.reasoning_summary,
        "score_deltas": judgment.score_deltas,
        "source": judgment.source,
        "contract_address": judgment.contract_address,
        "tx_hash": judgment.tx_hash,
        "verify_url": verify_url,
        "timestamp": judgment.created_at.isoformat() if judgment.created_at else "",
    }
