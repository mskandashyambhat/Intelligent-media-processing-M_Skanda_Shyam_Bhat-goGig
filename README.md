# Intelligent Media Processing Pipeline

A backend system that accepts vehicle field photos, processes them asynchronously, and returns structured quality and authenticity analysis.

Built for the Backend + AI Engineering take-home assignment.

### Hosted on: <a href="https://intelligent-media-processing-mskandashyambhat-production.up.railway.app/docs" target="_blank" rel="noopener noreferrer">Intelligent Media Processing </a>
---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Processing Flow](#processing-flow)
- [Queue Strategy](#queue-strategy)
- [Image Analysis Checks](#image-analysis-checks)
- [API Reference](#api-reference)
- [Assumptions](#assumptions)
- [Running Locally](#running-locally)
- [Testing](#testing)
- [Trade-offs](#trade-offs)
- [AI Usage Disclosure](#ai-usage-disclosure)

---

## Overview

Users upload vehicle images from the field. The API accepts the upload immediately and returns a processing ID. A background worker runs eight heuristic checks (blur, brightness, dimensions, duplicates, screenshot detection, photo-of-photo detection, OCR number plate validation, and tampering heuristics). Results are persisted in PostgreSQL and exposed via status and results endpoints.

**Tech stack**

| Layer | Choice | Reason |
|-------|--------|--------|
| API | FastAPI (Python 3.12) | Async-friendly, auto OpenAPI docs, strong typing |
| Queue | Celery + Redis | Mature task queue with retries and worker scaling |
| Database | PostgreSQL | Relational metadata + JSONB for flexible check results |
| Image analysis | OpenCV, Pillow, imagehash, Tesseract | Local heuristics without external API cost |
| Containerization | Docker Compose | One-command local setup |

---

## Architecture

```
                    +------------------+
                    |     Client       |
                    +--------+---------+
                             |
                             | POST /upload
                             v
                    +------------------+
                    |   FastAPI API    |
                    |   (port 8000)    |
                    +--------+---------+
                             |
              +--------------+---------------+
              |                              |
              v                              v
     +----------------+              +----------------+
     |   PostgreSQL   |              |     Redis      |
     |  (metadata +   |              |  (Celery       |
     |   results)     |              |   broker)      |
     +----------------+              +--------+-------+
                                              |
                                              | dequeue
                                              v
                                     +----------------+
                                     | Celery Worker  |
                                     | (analysis      |
                                     |  pipeline)     |
                                     +--------+-------+
                                              |
                                              v
                                     +----------------+
                                     | Local uploads/ |
                                     |   directory    |
                                     +----------------+
```

### Service responsibilities

- **API service** — Validates uploads, stores files locally, writes metadata with `pending` status, enqueues Celery task, serves status/results endpoints.
- **Worker service** — Picks jobs from Redis, transitions status to `processing`, runs the analysis pipeline, persists structured results, marks `completed` or `failed`.
- **PostgreSQL** — Stores image records, processing lifecycle timestamps, perceptual hashes (for duplicate detection), and JSONB analysis output.
- **Redis** — Message broker and result backend for Celery.

### Major design decisions

1. **Immediate 202 response on upload** — The client never blocks on analysis. This matches real field-upload patterns where connectivity may be poor.
2. **Heuristic analysis over ML APIs** — Keeps the system self-contained, debuggable, and free of per-image API cost. Each check returns explicit confidence and details so reviewers can inspect reasoning.
3. **JSONB for check results** — Avoids a wide normalized schema for eight evolving checks while keeping queryable metadata on the parent record.
4. **Perceptual hashing for duplicates** — Compared against completed uploads only, using Hamming distance on pHash. Simple and effective for near-identical re-uploads.
5. **Separate status and results endpoints** — Status is lightweight and poll-friendly; results are only available when processing completes.

---

## Processing Flow

```
Upload Request
     |
     v
[Validate file type & size]
     |
     v
[Save to uploads/ directory]
     |
     v
[Insert DB record: status=pending]
     |
     v
[Enqueue Celery task] ------> Return 202 + processing_id
     |
     (async)
     v
[Worker: status=processing]
     |
     v
[Run 8 analysis checks]
     |
     v
[Persist AnalysisResult JSONB]
     |
     v
[status=completed]  (or failed + failure_reason)
```

### Processing states

| State | Meaning |
|-------|---------|
| `pending` | Record created, task queued but not yet picked up |
| `processing` | Worker actively running checks |
| `completed` | All checks finished, results available |
| `failed` | Unrecoverable error after retries; see `failure_reason` on status endpoint |

---

## Queue Strategy

Celery with Redis as broker. Configuration highlights:

- **Dedicated queue**: `image_processing`
- **Late acknowledgment** (`task_acks_late=True`) — Task is only acknowledged after completion, so a crashed worker can redeliver the job.
- **Automatic retries** — Up to 3 retries with exponential backoff (5s base, max 60s) on transient failures (DB blip, file read error).
- **Prefetch multiplier of 1** — Each worker takes one task at a time, preventing a slow image analysis from blocking the queue unfairly.
- **Concurrency=2** — Reasonable default for CPU-bound OpenCV work on a laptop; tunable via worker command.

**Why Celery over in-memory queue?** In-memory works for demos but loses jobs on restart and cannot scale horizontally. Redis + Celery gives durable queuing with minimal operational overhead for local development.

---

## Image Analysis Checks

Eight checks are implemented (requirement: at least 4):

| Check | Method | Issue detected |
|-------|--------|----------------|
| Dimension validation | OpenCV shape read | Resolution too low for reliable review |
| Blur detection | Laplacian variance | Motion blur or out-of-focus capture |
| Brightness analysis | Mean grayscale intensity | Underexposed (low light) or overexposed |
| Duplicate detection | Perceptual hash (pHash) vs prior uploads | Same or near-identical image re-uploaded |
| Screenshot detection | Aspect ratio + border uniformity + EXIF software hints | Mobile screenshot instead of direct camera capture |
| Photo-of-photo detection | Large rectangular contours + glare ratio | Photo of a screen or printed photo |
| Number plate validation | Tesseract OCR + Indian plate regex | Missing or invalid Indian registration format |
| Tampering heuristic | Error Level Analysis (ELA-lite) | Possible editing via compression inconsistency |

Each check returns:

```json
{
  "name": "blur_detection",
  "passed": false,
  "severity": "warning",
  "confidence": 0.85,
  "message": "Image appears blurry",
  "details": { "laplacian_variance": 42.3, "threshold": 100.0 }
}
```

Thresholds are configurable via environment variables / `app/config.py` without code changes.

---

## API Reference

Base URL: `http://localhost:8000/api/v1`

Interactive docs: `http://localhost:8000/docs`

### POST /upload

Upload an image for async processing.

**Request**

```bash
curl -X POST http://localhost:8000/api/v1/upload \
  -F "file=@sample_images/valid_vehicle.jpg"
```

**Response (202 Accepted)**

```json
{
  "processing_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "status": "pending",
  "message": "Image uploaded successfully. Processing has been queued."
}
```

### GET /status/{processing_id}

Poll processing lifecycle.

**Response (200 OK)**

```json
{
  "processing_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "status": "completed",
  "original_filename": "valid_vehicle.jpg",
  "created_at": "2026-07-21T09:00:00Z",
  "updated_at": "2026-07-21T09:00:02Z",
  "started_at": "2026-07-21T09:00:01Z",
  "completed_at": "2026-07-21T09:00:02Z",
  "failure_reason": null
}
```

When failed:

```json
{
  "processing_id": "...",
  "status": "failed",
  "failure_reason": "Unable to read image at /app/uploads/....jpg",
  ...
}
```

### GET /results/{processing_id}

Fetch structured analysis (only when `status=completed`).

**Response (200 OK)**

```json
{
  "processing_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "status": "completed",
  "overall_confidence": 0.712,
  "issue_count": 1,
  "checks": [
    {
      "name": "blur_detection",
      "passed": true,
      "severity": "info",
      "confidence": 0.7,
      "message": "Image sharpness is acceptable",
      "details": { "laplacian_variance": 152.4, "threshold": 100.0 }
    }
  ],
  "summary": {
    "total_checks": 8,
    "issues_found": 1,
    "critical_issues": 0,
    "warnings": 1,
    "recommendation": "Review recommended; image has quality or authenticity concerns."
  }
}
```

**Error responses**

| Code | When |
|------|------|
| 404 | Unknown processing ID |
| 409 | Still pending/processing, or failed (message includes failure reason) |
| 400 | Invalid file type or empty upload |

### GET /health

```bash
curl http://localhost:8000/api/v1/health
```

```json
{ "status": "healthy", "service": "media-processing-pipeline" }
```

---

## Assumptions

1. **Single-tenant local deployment** — No authentication or multi-tenant isolation in this scope.
2. **Local filesystem storage** — Images stored under `uploads/`. Production would use S3/GCS with pre-signed URLs.
3. **Indian number plates** — Regex covers common formats (e.g. `KA01AB1234`, `DL3CAB1234`). OCR quality depends on plate visibility and image quality.
4. **Duplicate scope** — Duplicates are detected only against prior uploads in this database, not a global corpus.
5. **Heuristic confidence is not ground truth** — Confidence scores reflect heuristic certainty, not calibrated ML probability.
6. **Supported formats** — JPEG, PNG, WebP, HEIC/HEIF up to 10 MB (configurable).
7. **Tesseract installed** — Required for OCR; included in Docker image via `tesseract-ocr` package.

---

## Running Locally

### Option A: Docker Compose (recommended)

**Prerequisites:** Docker and Docker Compose

```bash
# Clone / enter project directory
cd Handshake

# Copy environment file
cp .env.example .env

# Start all services (API, worker, Postgres, Redis)
docker compose up --build
```

Services:

| Service | URL / Port |
|---------|------------|
| API | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |

Generate sample images:

```bash
docker compose exec api python scripts/seed_samples.py
```

Upload a sample:

```bash
curl -X POST http://localhost:8000/api/v1/upload \
  -F "file=@sample_images/valid_vehicle.jpg"
```

Run smoke test (with services up):

```bash
docker compose exec api python scripts/smoke_test.py
```

### Option B: Manual setup

**Prerequisites:** Python 3.12, PostgreSQL 16, Redis 7, Tesseract OCR

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit DATABASE_URL if needed

# Terminal 1: API
uvicorn app.main:app --reload --port 8000

# Terminal 2: Worker
celery -A app.services.queue.celery_app worker --loglevel=info

# Generate samples
python scripts/seed_samples.py
```

---

## Testing

```bash
# Unit tests (analysis heuristics)
pytest tests/ -v

# End-to-end smoke test (requires running stack)
python scripts/smoke_test.py
```

Tests cover plate validation, blur/brightness/dimension checks, and normalization helpers.

---

## Trade-offs

### Intentionally simplified

- **No authentication or rate limiting** — Focus on core pipeline; would add API keys or JWT in production.
- **Local disk storage** — Faster to ship; cloud storage would be first production change.
- **Heuristics instead of trained models** — Faster, explainable, no GPU; accuracy is limited on edge cases.
- **No admin dashboard** — API-only; Swagger UI suffices for demo and review.
- **No dead-letter queue UI** — Failed jobs surface via status API; DLQ would be added for ops visibility.

### Would improve with more time

1. **Object storage (S3)** with lifecycle policies for upload retention.
2. **Dedicated ML model** for blur/screenshot/tamper detection with calibrated confidence.
3. **Prometheus metrics** — Queue depth, processing latency histogram, check failure rates.
4. **Idempotency keys** on upload to handle client retries safely.
5. **Horizontal worker autoscaling** based on Redis queue length.
6. **Plate detection crop** before OCR (YOLO or OpenCV cascade) to improve OCR accuracy.
7. **Integration tests** with Testcontainers for Postgres and Redis.

### Scalability concerns

- **CPU-bound workers** — OpenCV analysis does not parallelize well within a single image; scale by adding worker replicas.
- **Duplicate check is O(n)** over completed records — Acceptable at low volume; would move perceptual hashes to Redis or a vector index at scale.
- **Local disk** — Becomes a bottleneck; object storage is required beyond a single node.
- **Postgres JSONB** — Fine for thousands of records; archival to cold storage for old analyses if volume grows.

### Failure handling concerns

- **Worker crash mid-processing** — Late ack + Celery retry handles most cases; status may briefly show `processing` until retry or timeout policy kicks in.
- **Poison messages** — After 3 retries, task fails permanently; `failure_reason` is stored. A DLQ would prevent silent loss in high-volume systems.
- **Disk full on upload** — Not handled explicitly; would return 507 and alert in production.
- **OCR dependency** — If Tesseract is missing, plate check may degrade; Docker image pins this dependency.

---

## AI Usage Disclosure

This project was built with AI assistance (Cursor / Claude). Below is an honest account of where AI helped, where it was wrong, and how outputs were validated.

### Where AI was used

| Area | AI contribution |
|------|-----------------|
| Project scaffolding | Initial directory layout, Docker Compose structure, FastAPI boilerplate |
| Analysis heuristics | Suggested Laplacian blur, pHash duplicates, ELA-lite tampering, screenshot aspect-ratio checks |
| README structure | Outline for architecture, trade-offs, and API examples per assignment requirements |
| Regex for Indian plates | Draft patterns for common state codes and formats |
| Celery configuration | Retry/backoff settings and queue routing |

### What AI helped with most

- **Speed** — Boilerplate for API, Celery, SQLAlchemy models, and Docker was generated quickly so effort could focus on pipeline design and README reasoning.
- **Heuristic catalog** — AI suggested a reasonable set of checks aligned with the assignment brief (blur, brightness, duplicate, OCR, screenshot, photo-of-photo).
- **Documentation** — Draft API examples and architecture diagrams were refined into the final README.

### Where AI output was wrong or needed correction

1. **Celery retry logic** — Initial suggestion mixed manual `self.retry()` with `task_autoretry_for`, which could cause double retries. Simplified to automatic retry only.
2. **FastAPI lifespan** — AI sometimes used deprecated `@app.on_event("startup")`; kept for simplicity but noted for future migration to lifespan context manager.
3. **Indian plate regex** — First draft was too permissive (accepted invalid lengths). Tightened after testing against known valid/invalid examples.
4. **Health check** — Generated code used incorrect SQLAlchemy import pattern; fixed to use `sqlalchemy.text()`.
5. **OpenCV on slim Docker** — Required explicit `libgl1` and `libglib2.0-0` packages; AI's first Dockerfile missed these runtime dependencies.

### How AI-generated code was validated

- **Ran Docker Compose** — Verified all four services start and communicate.
- **Unit tests** — `pytest` for plate validation, blur, brightness, and dimension checks against synthetic images.
- **Smoke test script** — End-to-end upload → poll status → fetch results against live API.
- **Manual curl requests** — Confirmed 202/200/409 response codes and JSON shape.
- **Code review** — Read through analysis pipeline to ensure heuristics match stated behavior and confidence scores are bounded [0, 1].

### Strategic vs blind usage

AI was used for **acceleration and exploration**, not as a substitute for decisions. Framework choices (FastAPI, Celery, PostgreSQL), queue semantics (late ack, prefetch=1), and the decision to prefer local heuristics over paid vision APIs were made deliberately and documented in trade-offs. Every AI-generated module was read, adjusted, and tested before inclusion.

---

## Project Structure

```
Handshake/
├── app/
│   ├── main.py              # FastAPI application entry
│   ├── config.py            # Settings and thresholds
│   ├── api/routes.py        # Upload, status, results endpoints
│   ├── db/models.py         # SQLAlchemy models
│   ├── models/schemas.py    # Pydantic response schemas
│   ├── services/
│   │   ├── storage.py       # File validation and persistence
│   │   └── queue.py         # Celery app configuration
│   ├── workers/tasks.py     # Background processing task
│   └── analysis/pipeline.py # Image analysis checks
├── tests/test_analysis.py
├── scripts/
│   ├── seed_samples.py      # Generate test images
│   └── smoke_test.py        # E2E API test
├── sample_images/           # Generated test images
├── uploads/                 # Stored uploads (gitignored)
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── README.md
```

---


## License

Submitted as part of a take-home engineering assignment.

## Author
#### M Skanda Shyam Bhat
#### skandashyam102@gmail.com
#### https://www.linkedin.com/in/mskandashyambhat/
