import time

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from .config import settings
from .database import Base, engine, get_db
from .genlayer import GenLayerClient
from .models import Agent, Deliverable, Dispute, Job, Judgment, Platform, ReputationSnapshot, new_id
from .schemas import AgentRegister, DeliverableSubmit, DisputeOpen, JobCreate, PlatformRegister
from .scoring import apply_deltas, current_snapshot, mock_judgment, score_acceptance, snapshot_dict, verdict_deltas

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


ensure_dev_columns()

app = FastAPI(title="Agent Reputation Registry API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

genlayer = GenLayerClient()


@app.exception_handler(RuntimeError)
def runtime_error_handler(request, exc: RuntimeError):
    import re

    detail = re.sub(r"private_key:\s*'[^']+'", "private_key: '<redacted>'", str(exc))
    return JSONResponse(status_code=502, content={"detail": detail[-4000:]})


def require_key(x_api_key: str | None = Header(default=None)) -> None:
    if settings.api_key and x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing x-api-key")


@app.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    return {
        "ok": True,
        "genlayer_mode": settings.genlayer_mode,
        "contract_address": settings.genlayer_contract_address,
        "counts": {
            "platforms": db.scalar(select(func.count()).select_from(Platform)),
            "agents": db.scalar(select(func.count()).select_from(Agent)),
            "jobs": db.scalar(select(func.count()).select_from(Job)),
        },
    }


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
    )
    accepted = accept_job(good_job_id, db)
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
    )
    submit_deliverable(
        fraud_job_id,
        DeliverableSubmit(
            deliverable_id=f"deliv_{fraud_job_id}",
            deliverable_uri="https://example.com/fraud-research",
            summary="Submitted a confident report, but several cited companies and sources are fabricated.",
            evidence_urls=["https://example.com/source-bad"],
        ),
        db,
    )
    open_dispute(
        fraud_job_id,
        DisputeOpen(
            dispute_id=f"disp_{fraud_job_id}",
            claimant="requester",
            reason="The agent lied: several companies are not Series A and two citations are fabricated.",
            evidence_uri="https://example.com/dispute.txt",
            bond_amount=10,
        ),
        db,
    )
    events.append("Buyer disputes the bad deliverable for fabricated citations.")
    evaluated = evaluate_job(fraud_job_id, db)
    events.append("GenLayer judges the dispute fraudulent and reputation collapses.")
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


@app.get("/platforms/{platform_id}/agents")
def platform_agents(platform_id: str, db: Session = Depends(get_db)) -> dict:
    platform = db.get(Platform, platform_id)
    if not platform:
        raise HTTPException(status_code=404, detail="Unknown platform")
    agents = db.scalars(select(Agent).where(Agent.platform_id == platform_id).order_by(Agent.created_at.desc())).all()
    return {
        "platform": platform_to_dict(platform),
        "agents": [
            agent_to_dict(agent) | {"reputation": snapshot_dict(current_snapshot(db, agent.id))}
            for agent in agents
        ],
    }


@app.post("/platforms/register", dependencies=[Depends(require_key)])
def register_platform(payload: PlatformRegister, db: Session = Depends(get_db)) -> dict:
    platform_id = payload.platform_id or new_id("platform")
    if db.get(Platform, platform_id):
        raise HTTPException(status_code=409, detail="Platform already exists")
    tx = genlayer.write("register_platform", [platform_id, payload.platform_name, payload.webhook_url])
    platform = Platform(
        id=platform_id,
        name=payload.platform_name,
        owner_wallet=payload.owner_wallet,
        webhook_url=payload.webhook_url,
    )
    db.add(platform)
    db.commit()
    db.refresh(platform)
    return {"platform": platform_to_dict(platform), "tx": tx}


@app.post("/agents/register", dependencies=[Depends(require_key)])
def register_agent(payload: AgentRegister, db: Session = Depends(get_db)) -> dict:
    if not db.get(Platform, payload.platform_id):
        raise HTTPException(status_code=404, detail="Unknown platform")
    agent_id = payload.agent_id or new_id("agent")
    if db.get(Agent, agent_id):
        raise HTTPException(status_code=409, detail="Agent already exists")
    tx = genlayer.write(
        "register_agent",
        [
            agent_id,
            payload.platform_id,
            payload.owner_wallet,
            payload.agent_name,
            ",".join(payload.capabilities),
            payload.metadata_uri,
        ],
    )
    agent = Agent(
        id=agent_id,
        platform_id=payload.platform_id,
        owner_wallet=payload.owner_wallet,
        name=payload.agent_name,
        capabilities=payload.capabilities,
        metadata_uri=payload.metadata_uri,
    )
    db.add(agent)
    db.commit()
    current_snapshot(db, agent_id)
    return {"agent": agent_to_dict(agent), "tx": tx}


@app.post("/jobs", dependencies=[Depends(require_key)])
def create_job(payload: JobCreate, db: Session = Depends(get_db)) -> dict:
    if not db.get(Platform, payload.platform_id):
        raise HTTPException(status_code=404, detail="Unknown platform")
    if not db.get(Agent, payload.provider_agent_id):
        raise HTTPException(status_code=404, detail="Unknown agent")
    job_id = payload.job_id or new_id("job")
    if db.get(Job, job_id):
        raise HTTPException(status_code=409, detail="Job already exists")
    tx = genlayer.write(
        "create_job",
        [
            job_id,
            payload.platform_id,
            payload.requester_id,
            payload.provider_agent_id,
            payload.task_spec,
            payload.category,
            str(payload.payment_amount),
            payload.currency,
        ],
    )
    job = Job(
        id=job_id,
        platform_id=payload.platform_id,
        requester_id=payload.requester_id,
        provider_agent_id=payload.provider_agent_id,
        task_spec=payload.task_spec,
        category=payload.category,
        payment_amount=payload.payment_amount,
        currency=payload.currency,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return {"job": job_to_dict(job), "tx": tx}


@app.post("/jobs/{job_id}/deliverable", dependencies=[Depends(require_key)])
def submit_deliverable(job_id: str, payload: DeliverableSubmit, db: Session = Depends(get_db)) -> dict:
    job = require_job(db, job_id)
    if job.status != "created":
        raise HTTPException(status_code=409, detail="Job is not accepting deliverables")
    deliverable_id = payload.deliverable_id or new_id("deliv")
    tx = genlayer.write(
        "submit_deliverable",
        [deliverable_id, job_id, payload.deliverable_uri, payload.summary, json_list(payload.evidence_urls)],
    )
    deliverable = Deliverable(
        id=deliverable_id,
        job_id=job_id,
        deliverable_uri=payload.deliverable_uri,
        summary=payload.summary,
        evidence_urls=payload.evidence_urls,
    )
    job.status = "submitted"
    db.add(deliverable)
    db.commit()
    db.refresh(deliverable)
    return {"deliverable": deliverable_to_dict(deliverable), "tx": tx}


@app.post("/jobs/{job_id}/accept", dependencies=[Depends(require_key)])
def accept_job(job_id: str, db: Session = Depends(get_db)) -> dict:
    job = require_job(db, job_id)
    if job.status != "submitted":
        raise HTTPException(status_code=409, detail="Job is not submitted")
    tx = genlayer.write("accept_job", [job_id])
    job.status = "accepted"
    snapshot = score_acceptance(db, job)
    db.commit()
    return {"job": job_to_dict(job), "reputation": snapshot_dict(snapshot), "tx": tx}


@app.post("/jobs/{job_id}/dispute", dependencies=[Depends(require_key)])
def open_dispute(job_id: str, payload: DisputeOpen, db: Session = Depends(get_db)) -> dict:
    job = require_job(db, job_id)
    if job.status != "submitted":
        raise HTTPException(status_code=409, detail="Only submitted jobs can be disputed")
    dispute_id = payload.dispute_id or new_id("disp")
    tx = genlayer.write(
        "open_dispute",
        [dispute_id, job_id, payload.claimant, payload.reason, payload.evidence_uri, str(payload.bond_amount)],
    )
    dispute = Dispute(
        id=dispute_id,
        job_id=job_id,
        claimant=payload.claimant,
        reason=payload.reason,
        evidence_uri=payload.evidence_uri,
        bond_amount=payload.bond_amount,
    )
    job.status = "disputed"
    db.add(dispute)
    apply_deltas(db, job.provider_agent_id, job.id, "dispute_opened", {"dispute_count": 1})
    db.commit()
    db.refresh(dispute)
    return {"dispute": dispute_to_dict(dispute), "tx": tx}


@app.post("/jobs/{job_id}/evaluate", dependencies=[Depends(require_key)])
def evaluate_job(job_id: str, db: Session = Depends(get_db)) -> dict:
    job = require_job(db, job_id)
    dispute = db.scalars(select(Dispute).where(Dispute.job_id == job_id)).first()
    deliverable = db.scalars(select(Deliverable).where(Deliverable.job_id == job_id)).first()
    if not dispute or not deliverable:
        raise HTTPException(status_code=409, detail="Job needs a deliverable and open dispute")
    if db.scalars(select(Judgment).where(Judgment.job_id == job_id)).first():
        raise HTTPException(status_code=409, detail="Job already evaluated")

    source = "mock"
    resolve_tx = {"tx_id": "", "mode": "mock"}
    if genlayer.enabled():
        resolve_error = None
        try:
            resolve_tx = genlayer.write("resolve_dispute", [job_id])
        except RuntimeError as exc:
            resolve_error = exc
        raw = None
        for _ in range(6):
            raw = genlayer.call_json("get_judgment", [job_id])
            if isinstance(raw, dict) and raw.get("verdict"):
                break
            time.sleep(5)
        if not (isinstance(raw, dict) and raw.get("verdict")) and resolve_error:
            if "Job is not disputed" not in str(resolve_error) and "Job already evaluated" not in str(resolve_error):
                raise resolve_error
        if isinstance(raw, dict) and raw.get("verdict"):
            result = {
                "verdict": raw["verdict"],
                "confidence_bps": int(raw.get("confidence_bps", 0)),
                "reasoning_summary": raw.get("reasoning_summary", ""),
                "score_deltas": raw.get("score_deltas") or verdict_deltas(raw["verdict"]),
            }
            source = "genlayer"
        else:
            result = mock_judgment(dispute.reason, deliverable.summary)
    else:
        result = mock_judgment(dispute.reason, deliverable.summary)

    result["score_deltas"]["genlayer_verified_jobs"] = 1 if source == "genlayer" else 0
    judgment = Judgment(
        id=new_id("judgment"),
        job_id=job_id,
        dispute_id=dispute.id,
        verdict=result["verdict"],
        confidence_bps=result["confidence_bps"],
        reasoning_summary=result["reasoning_summary"],
        score_deltas=result["score_deltas"],
        source=source,
        contract_address=genlayer.contract_address if source == "genlayer" else "",
        tx_hash=resolve_tx.get("tx_id", "") if source == "genlayer" else "",
        verify_url=genlayer.verify_url(resolve_tx.get("tx_id", "")) if source == "genlayer" else "",
    )
    dispute.status = "resolved"
    job.status = f"judged_{result['verdict']}"
    db.add(judgment)
    snapshot = apply_deltas(db, job.provider_agent_id, job.id, f"judgment_{result['verdict']}", result["score_deltas"])
    db.commit()
    return {"judgment": judgment_to_dict(judgment), "reputation": snapshot_dict(snapshot)}


@app.get("/agents/{agent_id}/reputation")
def get_reputation(agent_id: str, db: Session = Depends(get_db)) -> dict:
    if not db.get(Agent, agent_id):
        raise HTTPException(status_code=404, detail="Unknown agent")
    return snapshot_dict(current_snapshot(db, agent_id))


@app.get("/agents/{agent_id}/history")
def get_history(agent_id: str, db: Session = Depends(get_db)) -> dict:
    if not db.get(Agent, agent_id):
        raise HTTPException(status_code=404, detail="Unknown agent")
    jobs = db.scalars(select(Job).where(Job.provider_agent_id == agent_id).order_by(Job.created_at.desc())).all()
    snapshots = db.scalars(
        select(ReputationSnapshot)
        .where(ReputationSnapshot.agent_id == agent_id)
        .order_by(ReputationSnapshot.created_at.desc())
    ).all()
    return {
        "agent_id": agent_id,
        "jobs": [job_to_dict(job) for job in jobs],
        "disputes": [dispute_to_dict(d) for d in db.scalars(select(Dispute).join(Job).where(Job.provider_agent_id == agent_id)).all()],
        "judgments": [judgment_to_dict(j) for j in db.scalars(select(Judgment).join(Job).where(Job.provider_agent_id == agent_id)).all()],
        "reputation_snapshots": [snapshot_dict(snapshot) | {"reason": snapshot.reason} for snapshot in snapshots],
    }


@app.get("/agents/{agent_id}/profile")
def public_profile(agent_id: str, db: Session = Depends(get_db)) -> dict:
    agent = db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Unknown agent")
    history = get_history(agent_id, db)
    return {"agent": agent_to_dict(agent), "reputation": snapshot_dict(current_snapshot(db, agent_id)), **history}


def require_job(db: Session, job_id: str) -> Job:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Unknown job")
    return job


def reset_demo_data(db: Session) -> dict:
    demo_platforms = ("researchagents_io_%", "partner_market_%", "platform_demo_%")
    demo_agents = ("deepresearchbot_%", "agent_research_%")
    demo_jobs = ("research_good_%", "research_fraud_%", "job_good_%", "job_bad_%")
    demo_deliverables = ("deliv_research_good_%", "deliv_research_fraud_%", "deliv_job_good_%", "deliv_job_bad_%")
    demo_disputes = ("disp_research_fraud_%", "disp_job_bad_%")

    def like_any(column, patterns: tuple[str, ...]):
        return or_(*(column.like(pattern) for pattern in patterns))

    counts = {}
    for label, model, condition in [
        ("judgments", Judgment, like_any(Judgment.job_id, demo_jobs)),
        ("disputes", Dispute, like_any(Dispute.id, demo_disputes)),
        ("deliverables", Deliverable, like_any(Deliverable.id, demo_deliverables)),
        ("reputation_snapshots", ReputationSnapshot, like_any(ReputationSnapshot.agent_id, demo_agents)),
        ("jobs", Job, like_any(Job.id, demo_jobs)),
        ("agents", Agent, like_any(Agent.id, demo_agents)),
        ("platforms", Platform, like_any(Platform.id, demo_platforms)),
    ]:
        result = db.execute(delete(model).where(condition))
        counts[label] = result.rowcount or 0
    db.commit()
    return {"deleted": counts}


def json_list(values: list[str]) -> str:
    import json

    return json.dumps(values)


def platform_to_dict(platform: Platform) -> dict:
    return {"id": platform.id, "name": platform.name, "owner_wallet": platform.owner_wallet, "webhook_url": platform.webhook_url}


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
