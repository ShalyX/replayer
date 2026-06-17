import hashlib
import hmac
import secrets
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
from .schemas import AgentRegister, DeliverableSubmit, DisputeOpen, JobCreate, PlatformRegister, TrustEvaluateRequest
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
            summary="Submitted a confident report, but several cited companies and sources are fabricated.",
            evidence_urls=["https://example.com/source-bad"],
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
            evidence_uri="https://example.com/dispute.txt",
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


@app.post("/platforms/register", dependencies=[Depends(require_admin_key)])
def register_platform(payload: PlatformRegister, db: Session = Depends(get_db)) -> dict:
    platform_id = payload.platform_id or new_id("platform")
    if db.get(Platform, platform_id):
        raise HTTPException(status_code=409, detail="Platform already exists")
    tx = genlayer.write("register_platform", [platform_id, payload.platform_name, payload.webhook_url])
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
    authorize_platform(auth, payload.platform_id)
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


@app.post("/jobs")
def create_job(payload: JobCreate, db: Session = Depends(get_db), auth: dict = Depends(get_auth)) -> dict:
    authorize_platform(auth, payload.platform_id)
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


@app.post("/jobs/{job_id}/deliverable")
def submit_deliverable(
    job_id: str,
    payload: DeliverableSubmit,
    db: Session = Depends(get_db),
    auth: dict = Depends(get_auth),
) -> dict:
    job = require_job(db, job_id)
    authorize_platform(auth, job.platform_id)
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


@app.post("/jobs/{job_id}/accept")
def accept_job(job_id: str, db: Session = Depends(get_db), auth: dict = Depends(get_auth)) -> dict:
    job = require_job(db, job_id)
    authorize_platform(auth, job.platform_id)
    if job.status != "submitted":
        raise HTTPException(status_code=409, detail="Job is not submitted")
    tx = genlayer.write("accept_job", [job_id])
    job.status = "accepted"
    snapshot = score_acceptance(db, job)
    db.commit()
    return {"job": job_to_dict(job), "reputation": snapshot_dict(snapshot), "tx": tx}


@app.post("/jobs/{job_id}/dispute")
def open_dispute(job_id: str, payload: DisputeOpen, db: Session = Depends(get_db), auth: dict = Depends(get_auth)) -> dict:
    job = require_job(db, job_id)
    authorize_platform(auth, job.platform_id)
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


@app.post("/jobs/{job_id}/evaluate")
def evaluate_job(job_id: str, db: Session = Depends(get_db), auth: dict = Depends(get_auth)) -> dict:
    job = require_job(db, job_id)
    authorize_platform(auth, job.platform_id)
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
        read_error = None
        try:
            resolve_tx = genlayer.write("resolve_dispute", [job_id])
        except RuntimeError as exc:
            resolve_error = exc
        raw = None
        for _ in range(settings.genlayer_read_attempts):
            try:
                raw = genlayer.call_json("get_judgment", [job_id])
            except RuntimeError as exc:
                read_error = exc
                break
            if isinstance(raw, dict) and raw.get("verdict"):
                break
            time.sleep(settings.genlayer_read_interval_seconds)
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
            if resolve_tx.get("tx_id"):
                source = "genlayer"
                result["reasoning_summary"] = (
                    "GenLayer transaction was submitted, but RPC readback timed out. "
                    "The demo used deterministic scoring while preserving the onchain transaction link."
                )
            elif read_error:
                result["reasoning_summary"] = (
                    "GenLayer RPC readback timed out before the judgment could be fetched. "
                    "The demo used deterministic scoring so the marketplace policy flow can continue."
                )
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
        "timeline": build_reputation_timeline(db, agent_id),
    }


@app.get("/agents/{agent_id}/profile")
def public_profile(agent_id: str, db: Session = Depends(get_db)) -> dict:
    agent = db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Unknown agent")
    history = get_history(agent_id, db)
    return {"agent": agent_to_dict(agent), "reputation": snapshot_dict(current_snapshot(db, agent_id)), **history}


@app.post("/trust/evaluate", dependencies=[Depends(require_key)])
def evaluate_trust(payload: TrustEvaluateRequest, db: Session = Depends(get_db)) -> dict:
    agent = db.get(Agent, payload.agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Unknown agent")

    reputation = current_snapshot(db, payload.agent_id)
    reputation_data = snapshot_dict(reputation)
    judgments = db.scalars(select(Judgment).join(Job).where(Job.provider_agent_id == payload.agent_id)).all()
    fraud_judgments = [judgment for judgment in judgments if judgment.verdict == "fraudulent"]
    fraud_incidents = len(fraud_judgments)
    risk_score = min(
        100,
        reputation.fraud_risk * 8
        + reputation.valid_dispute_count * 15
        + fraud_incidents * 45
        + (20 if reputation.status == "flagged" else 0),
    )

    reasons = []
    if fraud_incidents:
        reasons.append("Fraudulent judgment recorded on GenLayer")
    if reputation.status == "flagged":
        reasons.append("Flagged status")
    if reputation.overall < 70:
        reasons.append("Trust score below common marketplace threshold")
    if risk_score > 70:
        reasons.append("High computed risk score")
    if payload.job_value >= 10000:
        reasons.append("High-value job requires stricter marketplace policy")

    if fraud_incidents or reputation.status == "flagged" or risk_score >= 70:
        recommendation = "high_risk"
        confidence = 0.94
    elif reputation.overall < 70 or reputation.valid_dispute_count:
        recommendation = "manual_review"
        confidence = 0.82
    else:
        recommendation = "low_risk"
        confidence = 0.88

    policy = payload.policy
    policy_reasons = []
    eligible = True
    if policy:
        if reputation.overall < policy.min_trust_score:
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
    return {
        "agent_id": payload.agent_id,
        "job_type": payload.job_type,
        "job_value": payload.job_value,
        "trust_score": reputation.overall,
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
                "platform": "EnterpriseAgents.io",
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
