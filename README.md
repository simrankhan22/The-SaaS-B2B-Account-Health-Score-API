# SaaS Account Health Score API

A portfolio MVP for estimating B2B SaaS account churn risk over the next 90 days. It builds monthly point-in-time snapshots, compares logistic regression with a small random forest, and serves scores through FastAPI.

## Target and available signals

The target is an account's `churned_at` date falling within 90 days after a monthly snapshot. A blank churn date means the account is active through the dataset observation end (January 31, 2026). Rows without a full 90-day outcome window are excluded.

The selected public dataset has dated B2B account churn, but no product usage event history. To avoid using post-snapshot information, the model uses only signup-time attributes plus account tenure:

| Signal | Model field | Meaning |
| --- | --- | --- |
| Tenure | `tenure_days` | Days since signup at the snapshot date |
| Subscription value proxy | `plan` | Plan selected at signup |
| Account size | `seats_at_signup` | Seats at signup |
| Account context | `region`, `industry`, `channel` | Signup-time descriptors |

The source's `mrr_usd` and `seats_now` describe the last observation, not each historical snapshot, so they are excluded. The original Recency/Frequency/Monetary design cannot be learned from this dataset: there are no dated logins or usage counts. The API contract reflects the available data. A later version can add usage RFM when a suitable dated usage dataset is available.

## Dataset

Download: [Datanemics SaaS subscriptions](https://datanemics.com/datasets/saas-subscriptions/). It contains 2,500 synthetic B2B subscription accounts with signup dates and dated churn outcomes. The publisher marks it public domain under CC0 1.0. The project copy is `data/saas_subscriptions.csv`.

## Training and evaluation

Snapshots are monthly from January 2023 through October 2025. The temporal evaluation starts July 2025; training snapshots are purged when their 90-day label window reaches the evaluation period. Evaluation rows therefore represent later months than training rows, while accounts can appear in both periods as they would in a live account portfolio.

Current run: 23,622 snapshots; 2,832 positives (12.0%) overall. The holdout contains 5,280 snapshots with a 9.5% churn rate.

| Model | ROC AUC | Average precision | Brier score | Precision at 16% | Recall at 16% |
| --- | ---: | ---: | ---: | ---: | ---: |
| Logistic regression | 0.730 | 0.205 | 0.081 | 0.225 | 0.494 |
| Random forest | 0.724 | 0.211 | 0.190 | 0.101 | 0.996 |

Logistic regression is the API model: it has similar ranking performance and materially better probability calibration on this split. The current risk bands (<12% Low, 12–16% Medium, >=16% High) are provisional demo thresholds, not an operational policy. Repeated monthly rows from the same account are not statistically independent, so the holdout metrics should be read as an MVP check rather than a formal confidence estimate. Synthetic data also may not represent a production customer base.

## Setup

Requires Python 3.12 or compatible.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Train and write the model artifacts and evaluation reports:

```powershell
python -m src.saas_health.train
```

Run the API:

```powershell
$env:OPENAI_API_KEY = "your-api-key"
$env:OPENAI_MODEL = "gpt-4o-mini"
uvicorn src.saas_health.api:app --reload
```

Install the updated dependencies with `python -m pip install -r requirements.txt` before starting. Set `OPENAI_API_KEY` in the backend process environment; never put it in frontend files or commit it. `OPENAI_MODEL` is optional and defaults to `gpt-4o-mini`.

Open the website at <http://127.0.0.1:8000/>. The dashboard is served by FastAPI on the same origin and calls `/health`, `/predict`, `/explain`, and `/batch-scoring`; no separate frontend server or CORS setup is needed. Interactive API docs: <http://127.0.0.1:8000/docs>.

The website includes a single-account form, an on-demand OpenAI explanation and suggested CS action, a CSV upload workflow with job polling, a downloadable input template, and exportable scored results. AI explanations are optional and only run when requested; the churn probability continues to come from the trained model. The explanation request sends the score and signup attributes to OpenAI, without the account ID. CSV columns: `account_id,tenure_days,plan,seats_at_signup,region,industry,channel`.

## Single-account scoring

`POST /predict`

```json
{
  "account_id": "acct-001",
  "tenure_days": 420,
  "plan": "team",
  "seats_at_signup": 24,
  "region": "EMEA",
  "industry": "software",
  "channel": "partner"
}
```

The response includes `churn_probability_90d`, `risk_tier`, and `prediction_horizon_days`.

## Batch scoring

`POST /batch-scoring` accepts a JSON array (or `{"accounts": [...]}`), CSV as `text/csv`, or a multipart upload with field name `file`. It returns a `job_id`; poll `GET /batch-scoring/{job_id}` for status and results. The MVP accepts up to 10,000 accounts per job.

CSV headers:

```text
account_id,tenure_days,plan,seats_at_signup,region,industry,channel
```

The MVP uses FastAPI background tasks and an in-memory job store. Jobs and results disappear if the process restarts; use a persistent queue and result store before production use.
