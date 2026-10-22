# OmniIQ — Unified AI, Data Analytics & Machine Learning Platform

> An open-source-first intelligence workspace for data preparation, analytics, machine learning experiments, document intelligence, and workflow automation.

**Project type:** MCA Final-Year Major Project + Long-Term Portfolio Product
**Architecture:** Modular monolith + asynchronous workers
**Primary languages:** Python, TypeScript, SQL
**License:** To be decided after reviewing dependencies and model licenses.

This file is the source of truth for scope. Implementation progress is tracked in
[`docs/implementation-status.md`](docs/implementation-status.md).

---

## 1. Overview

OmniIQ is a full-stack platform that brings data analytics, machine learning, AI-powered document understanding, and repeatable data workflows into a single application. Users can upload datasets, inspect data quality, perform analysis, build interactive dashboards, train machine learning models, query documents using retrieval-augmented generation (RAG), and generate reports.

## 2. Problem Statement

Data analysis and AI experimentation often require switching between multiple tools for file preparation, visualization, model training, document search, and reporting. OmniIQ provides a unified, project-based workspace that makes these tasks reproducible, easier to understand, and accessible through a consistent web interface.

## 3. Objectives

- Build a responsive full-stack web application.
- Provide secure authentication and project-level access control.
- Support dataset upload, profiling, cleaning, and versioning.
- Provide interactive analytics and visualization.
- Train and evaluate classification, regression, and clustering models.
- Track experiments and manage model artifacts.
- Support document question answering with source references.
- Execute long-running tasks through background workers.
- Generate downloadable reports.
- Maintain automated tests, documentation, and reproducible deployments.

## 4. Core Modules

**Data Studio** — CSV/Excel ingestion; schema inference and type validation; missing-value and duplicate detection; descriptive statistics and quality reports; explicit cleaning transformations; dataset versioning and export.

**Analytics Studio** — SQL/Pandas analytics; descriptive statistics and correlations; KPI calculations and interactive charts; date and column filters; dashboard configuration and report export.

**ML Lab** — classification, regression, clustering; train/test splitting and preprocessing pipelines; evaluation and experiment comparison; parameter/metric tracking; versioned model artifacts; validated prediction endpoints.

**Document AI** — PDF, DOCX, text ingestion; parsing and chunking; embeddings and vector retrieval; retrieval-augmented Q&A; source references and page citations; local-model integration where supported.

**Workflow Studio** — repeatable data-processing workflows; cleaning, analysis, inference, and report steps; background execution; run history and error reporting.

**AI Copilot and Reports** — natural-language document questions; grounded summaries; structured AI outputs; downloadable reports; graceful fallback when an optional model provider is unavailable.

**Developer Hub** — API documentation; API key management; job and execution history; health and logs; usage and audit information.

## 5. Technology Stack

- **Frontend:** React, TypeScript, Vite, Tailwind CSS, shadcn/ui, React Router, TanStack Query, React Hook Form + Zod, Recharts and Plotly, Vitest.
- **Backend:** Python, FastAPI, Pydantic, SQLAlchemy 2.x, Alembic, PostgreSQL, Pytest.
- **Data/ML:** Pandas, NumPy, PyArrow, Scikit-learn, optional XGBoost, MLflow.
- **Document AI:** PyMuPDF, python-docx, Sentence Transformers, FAISS (optional pgvector), optional local LLM runtime.
- **Infrastructure:** Redis, Celery, Docker, Docker Compose, GitHub Actions.

Prefer free and open-source dependencies. Check model licenses, system requirements, and commercial-use conditions before deployment.

## 6. Architecture

Modular monolith with separate background workers. The frontend talks to FastAPI through versioned REST endpoints. The backend validates requests, applies authorization, invokes service-layer logic, and persists metadata in PostgreSQL. Large datasets, documents, reports, and model artifacts live in private file/object storage; PostgreSQL holds metadata and storage references. Long-running ingestion, training, indexing, and report generation run as background jobs.

- Request flow: Browser → React → FastAPI → Authorization → Service layer → PostgreSQL / private storage.
- Background flow: API request → Job record → Redis/Celery queue → Worker → Result or error → Job status endpoint.

## 7. Data Model

Core entities: `users`, `organizations`, `organization_members`, `projects`, `audit_logs`, `api_keys`, `datasets`, `dataset_versions`, `data_jobs`, `dashboards`, `reports`, `ml_experiments`, `ml_runs`, `model_versions`, `predictions`, `documents`, `document_chunks`, `conversations`, `messages`, `workflow_definitions`, `workflow_runs`, `workflow_tasks`.

Use UUID primary keys, foreign keys, indexes, timestamps, unique constraints, and Alembic migrations. Enforce organization and project boundaries in the backend. Do not store large binary files in relational tables.

## 8. API Convention

All endpoints use the `/api/v1` prefix. Groups: `/auth`, `/organizations`, `/projects`, `/projects/{id}/datasets`, `/datasets/{id}/profile`, `/datasets/{id}/cleaning-jobs`, `/datasets/{id}/query`, `/projects/{id}/dashboards`, `/projects/{id}/experiments`, `/experiments/{id}/runs`, `/models/{id}/predict`, `/projects/{id}/documents`, `/projects/{id}/chat`, `/projects/{id}/workflows`, `/workflows/{id}/runs`, `/projects/{id}/reports`, `/health/live`, `/health/ready`.

Every endpoint has validated request/response schemas, correct status codes, structured errors, and access control. Long-running operations return a job identifier and are tracked asynchronously (HTTP 202; states: queued, running, succeeded, failed, cancelled).

## 9. Machine Learning Pipeline

1. Select a dataset version. 2. Validate target and feature columns. 3. Split the data appropriately. 4. Build preprocessing pipelines. 5. Train candidate models. 6. Evaluate with task-appropriate metrics. 7. Compare runs. 8. Save the fitted pipeline and artifact metadata. 9. Register a model version. 10. Serve validated predictions.

Classification: precision, recall, F1, ROC-AUC where appropriate. Regression: MAE, RMSE, R². Prevent data leakage, preserve training configuration, and ensure inference uses the same feature schema as training.

## 10. Document AI / RAG Pipeline

1. Validate and upload. 2. Extract text and page metadata. 3. Chunk. 4. Embed. 5. Store chunks and vector references. 6. Retrieve for a question. 7. Apply document/project authorization. 8. Generate a grounded answer. 9. Return source references and page citations.

Handle irrelevant retrieval honestly, never fabricate citations, treat document contents as untrusted input. AI must not bypass authorization or execute arbitrary database queries.

## 11. Security Requirements

Secure password hashing; expiring tokens/sessions; organization/project authorization; server-side role enforcement (owner, admin, member, viewer); private document and dataset storage; upload size/type/resource limits; secrets via environment variables; safe DB access through SQLAlchemy; rate limiting for sensitive endpoints; audit logging; safe error messages; data retention and deletion policies; trusted model artifact loading; resource limits for workers and ML jobs.

## 12. Testing Strategy

Backend: auth and authorization, org/project isolation, migrations and constraints, dataset ingestion, analytics calculations, ML preprocessing/evaluation, retrieval and citations, job state transitions, upload restrictions. Frontend: forms, protected routes, upload/profiling, dashboards, experiment results, document Q&A, loading/empty/error states. Integration: clean-environment start, migrations, demo project, dataset → analytics, train → evaluate, document → grounded retrieval, unauthorized access denied.

## 13. Roadmap

1. Foundation — auth skeleton, DB migrations, frontend layout, Docker, CI.
2. Identity and Data Studio — authentication, authorization, upload, profiling, cleaning, versioning, job lifecycle.
3. Analytics Studio — aggregations, charts, filters, dashboards, reports.
4. ML Lab — classification, regression, clustering, tracking, evaluation, inference.
5. Document AI — parsing, embeddings, retrieval, source-grounded RAG, evaluation.
6. Workflow Studio — background processing, workflow execution, retries, run history.
7. Production Hardening — security review, performance tests, monitoring, backups, deployment docs.

Each phase ends with runnable software; the next phase starts only when the current phase's tests pass and setup instructions work.

## 14. Success Criteria

A new developer can run it from the docs; authentication and project-level authorization work; dataset upload and profiling work end to end; analytics results come from real data; at least one ML train + inference workflow passes tests; document Q&A returns relevant source references; background job failures are visible and recoverable; tests and migrations run in a clean environment; no secrets or private documents are committed.

**Do not claim unimplemented features, fabricated metrics, or unverified deployment results.**

## 15. Future Enhancements

Visual workflow editor; more ML algorithms; drift monitoring; scheduled reports and workflows; more vector databases; usage quotas and billing; collaboration and sharing; additional data connectors; production-grade model serving.

---

*One Workspace. Data to Decisions.*
