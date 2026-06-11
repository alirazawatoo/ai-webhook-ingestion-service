# AI Webhook Ingestion Service

A Django and Celery reference implementation for accepting vendor webhooks, preserving their raw payloads, and using an OpenAI-backed worker to normalize inconsistent events into shipment and invoice records.

The project demonstrates idempotent ingestion, asynchronous processing, replay controls, and timestamp-aware entity projections. It is a prototype architecture rather than a claim of guaranteed delivery.

## Event lifecycle

```text
Vendor webhook
      |
      v
POST /api/webhooks/ ---- compute idempotency key
      |                           |
      v                           v
RawWebhook in PostgreSQL    return existing record for duplicates
      |
      v after DB commit
Celery task in Redis
      |
      v
OpenAI normalization ---- validate canonical JSON
      |
      +----> NormalizedEvent
      |
      +----> EntityState when event_time is newer
```

## Implemented behavior

- Stores arbitrary JSON payloads before model processing
- Uses vendor event IDs when available and a canonical payload hash otherwise
- Enforces vendor-scoped idempotency with database constraints
- Returns `202 Accepted` without waiting for normalization
- Classifies shipment, invoice, and unclassified events
- Validates model output against a strict normalization schema
- Retries transient provider failures with bounded exponential backoff
- Tracks received, processing, normalized, failed, and dead-letter states
- Supports individual and bounded bulk replay
- Prevents older normalized events from replacing newer entity state
- Exposes OpenAPI documentation and structured logs

## Data model

| Model | Responsibility |
| --- | --- |
| `RawWebhook` | Original payload, vendor metadata, idempotency key, and processing state |
| `NormalizedEvent` | Canonical entity fields, confidence, model, and prompt version |
| `EntityState` | Latest timestamp-qualified state for an entity |

## API

### Ingest a webhook

```http
POST /api/webhooks/
Content-Type: application/json
X-Webhook-Vendor: example-carrier

{
  "event_id": "evt-1042",
  "shipment_id": "shipment-88",
  "status": "on the way"
}
```

```json
{
  "status": "accepted",
  "webhook_id": "f5b4f18b-703c-4bbd-9363-2cbb497fdb16"
}
```

### Replay an event

```http
POST /api/webhooks/{webhook_id}/replay/
Content-Type: application/json

{"force": false}
```

Other useful routes:

- `GET /api/health/`
- `GET /api/schema/`
- `GET /api/docs/`
- `GET /api/redoc/`

## Local setup

### Prerequisites

- Docker and Docker Compose
- An OpenAI API key for real normalization requests

```bash
git clone https://github.com/alirazawatoo/ai-webhook-ingestion-service.git
cd ai-webhook-ingestion-service
cp .env.example .env
docker compose up --build
```

The API defaults to `http://localhost:8000`; PostgreSQL and Redis are included in the Compose stack. Review every value in `.env` before using the service outside local development.

## Prompt and replay traceability

The normalization prompt lives in `apps/normalization/prompts.py`. Each normalized event records the model and prompt version so a result can be associated with the rules that produced it. Failed and dead-letter events remain queryable and can be replayed through the API, admin action, or bounded Celery task.

## Delivery semantics and failure boundaries

The implementation provides useful safeguards, but it is not an exactly-once pipeline:

- The database commit and Celery publication are separate operations. A broker failure after persistence can leave a `RECEIVED` row without a queued task.
- Duplicate ingestion returns the existing row and does not republish its task.
- A worker marks an event `PROCESSING` before calling the model. Process termination can strand that state until an operator forces replay.
- Normalized-event persistence and entity-state projection are separate repository operations rather than one demonstrated transaction.
- The ingestion and replay endpoints have no request authentication or vendor signature verification.

These constraints should be resolved with an outbox/reconciliation process, processing leases, transactional projection rules, and authenticated vendor-specific signatures before describing the service as durable production infrastructure.

## Test boundary

No assertion-bearing automated test suite is currently tracked. The repository includes sample payloads and a sender script, but those are demonstration aids rather than behavioral verification.

## Next improvements

1. Add a transactional outbox and a reconciler for undispatched records.
2. Add processing leases and recovery for abandoned worker tasks.
3. Cover duplicate delivery, broker failure, worker crash, malformed model output, and projection failure deterministically.
4. Authenticate replay operations and validate webhook signatures per vendor.
5. Add a low-confidence review queue before projecting uncertain events.
