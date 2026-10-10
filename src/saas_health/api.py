"""FastAPI inference and in-memory batch-scoring endpoints."""

from __future__ import annotations

import csv
import io
import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .model import load_bundle, risk_tier, score_features


app = FastAPI(
    title="SaaS Account Health Score API",
    description=(
        "A portfolio MVP that estimates the probability of an account-level "
        "subscription churn date within 90 days from dated account snapshots."
    ),
    version="0.1.0",
)

WEB_DIR = Path(__file__).resolve().parents[2] / "web"

MAX_BATCH_ROWS = 10_000
_bundle: dict[str, Any] | None = None
_jobs: dict[str, dict[str, Any]] = {}


class AccountFeatures(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: str = Field(min_length=1, max_length=128)
    tenure_days: int = Field(ge=0)
    plan: str = Field(min_length=1, max_length=64)
    seats_at_signup: int = Field(ge=1)
    region: str = Field(min_length=1, max_length=64)
    industry: str = Field(min_length=1, max_length=128)
    channel: str = Field(min_length=1, max_length=64)


def _get_bundle() -> dict[str, Any]:
    global _bundle
    if _bundle is None:
        try:
            _bundle = load_bundle()
        except FileNotFoundError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
    return _bundle


def _score_account(
    bundle: dict[str, Any], account: AccountFeatures
) -> dict[str, Any]:
    values = account.model_dump(exclude={"account_id"})
    probability = score_features(bundle, values)
    return {
        "account_id": account.account_id,
        "churn_probability_90d": round(probability, 6),
        "risk_tier": risk_tier(probability),
    }


def _run_job(job_id: str, accounts: list[AccountFeatures]) -> None:
    job = _jobs[job_id]
    job["status"] = "running"
    try:
        bundle = _get_bundle()
        job["results"] = [_score_account(bundle, account) for account in accounts]
        job["status"] = "completed"
    except Exception as exc:  # Persist a pollable failure for the MVP job store.
        job["status"] = "failed"
        job["error"] = str(exc)


def _parse_csv(content: bytes) -> list[dict[str, str]]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="CSV must be UTF-8 encoded.") from exc
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV must include a header row.")
    return list(reader)


async def _read_accounts(request: Request) -> list[AccountFeatures]:
    content_type = request.headers.get("content-type", "").lower()
    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        upload = form.get("file")
        if upload is None or not hasattr(upload, "read"):
            raise HTTPException(status_code=400, detail="Upload a CSV file in the 'file' field.")
        rows = _parse_csv(await upload.read())
    elif content_type.startswith("text/csv"):
        rows = _parse_csv(await request.body())
    elif content_type.startswith("application/json"):
        try:
            payload = await request.json()
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Request body is not valid JSON.") from exc
        if isinstance(payload, dict):
            rows = payload.get("accounts")
        else:
            rows = payload
        if not isinstance(rows, list):
            raise HTTPException(
                status_code=422,
                detail="JSON body must be an array of accounts or an object with an 'accounts' array.",
            )
    else:
        raise HTTPException(
            status_code=415,
            detail="Use application/json, text/csv, or multipart/form-data with a 'file' field.",
        )

    if not rows:
        raise HTTPException(status_code=422, detail="Provide at least one account row.")
    if len(rows) > MAX_BATCH_ROWS:
        raise HTTPException(
            status_code=413,
            detail=f"This MVP accepts at most {MAX_BATCH_ROWS:,} accounts per job.",
        )
    try:
        return [AccountFeatures.model_validate(row) for row in rows]
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "openai_explanations_enabled": bool(os.getenv("OPENAI_API_KEY")),
    }


@app.post("/predict")
def predict(account: AccountFeatures) -> dict[str, Any]:
    """Score one account with the model's 90-day churn probability."""
    bundle = _get_bundle()
    result = _score_account(bundle, account)
    result["prediction_horizon_days"] = bundle["prediction_horizon_days"]
    return result


@app.post("/explain")
def explain_account(account: AccountFeatures) -> dict[str, Any]:
    """Add a structured CS explanation without changing the model score."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="AI explanations are disabled. Set OPENAI_API_KEY in the backend environment.",
        )

    try:
        from openai import OpenAI

        bundle = _get_bundle()
        scored = _score_account(bundle, account)
        client = OpenAI(api_key=api_key)
        features = account.model_dump(exclude={"account_id"})
        response = client.responses.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            store=False,
            max_output_tokens=350,
            input=[
                {
                    "role": "system",
                    "content": (
                        "You help a B2B SaaS Customer Success team interpret a churn-risk score. "
                        "The numeric score comes from a separate statistical model and must not be changed. "
                        "Use only the supplied account attributes and score. Do not claim these attributes "
                        "caused the prediction or reveal the statistical model's reasoning. Do not invent "
                        "usage, sentiment, renewal, support, or revenue facts. Make the limitation explicit: "
                        "this dataset has no product usage history. Give one practical, respectful next action."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "churn_probability_90d": scored["churn_probability_90d"],
                            "risk_tier": scored["risk_tier"],
                            "account_attributes": features,
                        }
                    ),
                },
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "account_health_explanation",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "summary": {"type": "string"},
                            "context_signals": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "recommended_action": {"type": "string"},
                            "limitation": {"type": "string"},
                        },
                        "required": [
                            "summary",
                            "context_signals",
                            "recommended_action",
                            "limitation",
                        ],
                        "additionalProperties": False,
                    },
                }
            },
        )
        if not response.output_text:
            raise ValueError("The explanation response was empty.")
        explanation = json.loads(response.output_text)
        return {**scored, "explanation": explanation}
    except HTTPException:
        raise
    except Exception as exc:
        # Do not return provider exception text, which could expose request details.
        raise HTTPException(
            status_code=502,
            detail=f"AI explanation request failed ({type(exc).__name__}). Check backend configuration and try again.",
        ) from exc


@app.post("/batch-scoring", status_code=status.HTTP_202_ACCEPTED)
async def batch_scoring(
    request: Request, background_tasks: BackgroundTasks
) -> dict[str, str]:
    """Queue a JSON list or CSV file, then return a pollable job ID."""
    accounts = await _read_accounts(request)
    job_id = uuid4().hex
    _jobs[job_id] = {"job_id": job_id, "status": "queued", "row_count": len(accounts)}
    background_tasks.add_task(_run_job, job_id, accounts)
    return {
        "job_id": job_id,
        "status": "queued",
        "status_url": f"/batch-scoring/{job_id}",
    }


@app.get("/batch-scoring/{job_id}")
def batch_status(job_id: str) -> dict[str, Any]:
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Batch job not found.")
    return job


@app.get("/", include_in_schema=False)
def web_home() -> FileResponse:
    """Serve the web dashboard from the same origin as the scoring API."""
    return FileResponse(WEB_DIR / "index.html")


app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
