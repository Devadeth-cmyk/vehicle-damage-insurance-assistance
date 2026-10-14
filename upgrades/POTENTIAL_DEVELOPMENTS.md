# AutoInsight Potential Developments

## Purpose

This document describes potential improvements for taking AutoInsight from a local prototype to a secure, reliable, supportable insurance-claim platform. It is a planning document, not a statement that the listed capabilities already exist or have been verified.

AutoInsight currently combines customer and service-center portals, a FastAPI backend, SQLAlchemy persistence, vehicle-damage computer vision, claim-package generation, and a policy-question assistant based on retrieval-augmented generation (RAG). Development should preserve that workflow while improving privacy, security, data integrity, operational reliability, and the quality of human review.

## Product goals

1. Customers can submit and track claims without seeing another customer's information.
2. Service-center staff can access only claims assigned to their organization and can record accountable review decisions.
3. Uploaded identity, vehicle, policy, and damage files remain private and are handled safely.
4. AI results are traceable, appropriately qualified, and reviewed by a person before they affect a claim decision.
5. Claim records and generated insurer packages remain complete, consistent, and recoverable.
6. Developers can deploy, monitor, update, and restore the service using repeatable processes.

## Priority guide

- **P0 — Release blocker:** Resolve before exposing the system to real users or real claim documents.
- **P1 — Near-term:** Required for a controlled pilot and dependable operations.
- **P2 — Expansion:** Valuable after core security and operational controls are established.
- **P3 — Longer-term:** Strategic capabilities that depend on reliable production data and governance.

## P0 — Security and privacy foundations

### 1. Private claim documents and evidence

**Current concern:** Claim storage and upload directories are mounted as static web paths, and claim package download endpoints need authorization checks. Claim IDs must not be treated as secrets.

**Potential development:**

- Remove public static serving of claim evidence and generated packages.
- Create an authenticated download endpoint that checks the caller's role, claim ownership or assignment, and organization membership before returning a file.
- Store uploads outside the web root. For larger deployments, use private object storage with short-lived, narrowly scoped download links.
- Use generated storage identifiers; keep the original filename as display metadata only.
- Define retention and deletion rules for identity documents, policy PDFs, accident photos, and generated packages.
- Audit document views, downloads, replacements, and deletions.

**Acceptance goals:** Unauthenticated requests cannot retrieve files; a customer cannot retrieve another customer's files; a service-center user cannot retrieve a claim outside its permitted scope; authorized users can still open the files they need.

### 2. Service-center account provisioning and tenant isolation

**Current concern:** Public registration can select a service-center role. Service-center claim listing currently spans the global claim table, which is unsafe if multiple service centers use the system.

**Potential development:**

- Replace self-selected privileged registration with invitation codes, administrator approval, or organization-domain onboarding.
- Add service-center organization records and membership relationships.
- Add claim assignment or routing rules that identify which organization may process each claim.
- Apply tenant filters to every service-center list, detail, update, download, and package endpoint.
- Separate administrator privileges from service-center staff privileges and define a least-privilege permission matrix.
- Add audit events for assignments, status changes, technician reviews, estimates, and package generation.

**Acceptance goals:** New users cannot grant themselves privileged access; users in one organization cannot enumerate or modify another organization's claims; all privileged actions identify the acting account and timestamp.

### 3. Production configuration and secrets

**Current concern:** Development defaults include debug mode, a placeholder JWT signing secret, local CORS origins, and SQLite.

**Potential development:**

- Fail startup in production when required secrets or production configuration are missing or weak.
- Separate development, test, staging, and production settings.
- Load secrets from the deployment platform's secret manager; never commit secrets or place them in frontend build variables.
- Configure CORS for exact deployed frontend origins, with only required methods and headers.
- Use HTTPS, secure proxy settings, and trusted-host validation in production.
- Disable interactive API documentation in public production deployments unless access is restricted.

**Acceptance goals:** A production launch cannot use the development JWT key or debug settings by accident; only approved web origins can call credentialed APIs.

### 4. Authentication and session controls

**Potential development:**

- Increase password requirements and enforce bcrypt's maximum supported input length explicitly instead of silently truncating passwords.
- Add login and registration rate limits, abuse monitoring, and account lockout or progressive delays.
- Add verified email, password reset, and account recovery flows.
- Define token expiration, refresh, logout/revocation, and account-deactivation behavior.
- Review browser token storage and XSS exposure; document the chosen session model and threat assumptions.
- Add administrative controls for disabling accounts and removing compromised sessions.

**Acceptance goals:** Common credential attacks are throttled; users can recover accounts safely; an administrator can disable access without waiting for a long-lived token to expire.

### 5. Authorization correctness and claim lifecycle integrity

**Current concern:** Package generation changes claim status before access authorization and before package generation succeeds. Status updates accept any status enum without validating the workflow transition.

**Potential development:**

- Check authorization before any database or filesystem mutation.
- Define a state-transition table, such as submitted → intake → assessment → technician review → estimate → package → insurer review.
- Reject invalid or out-of-order transitions with clear errors.
- Commit claim status only when the corresponding action succeeds; use transactions for related database changes.
- Make package generation idempotent and record a generation/version history rather than leaving ambiguous old artifacts.
- Ensure failed generation leaves the previous valid package and claim state intact.

**Acceptance goals:** Unauthorized calls never change claim data; invalid transitions are rejected; retries do not create inconsistent duplicate package state.

## P1 — Reliable data, files, and application operations

### 6. Upload validation and resilient storage

**Potential development:**

- Enforce per-file and per-request size limits while streaming; do not read large uploads wholly into memory.
- Validate actual file signatures and decodability in addition to declared MIME type and filename extension.
- Use random server-generated names, collision-resistant paths, and safe file permissions.
- Add image dimension and PDF page limits to reduce decompression and resource-exhaustion risks.
- Scan uploaded files for malware where required by the deployment environment.
- Write file data to temporary storage, validate it, then atomically move it and persist metadata; clean up orphaned files on errors.
- Record upload category, uploader, size, checksum, detected type, and timestamps.

**Acceptance goals:** Oversized, malformed, unsupported, or interrupted uploads fail safely and do not leave misleading database records or orphaned files.

### 7. Database migrations and data lifecycle

**Current concern:** Tables and columns are currently created or altered during application import/startup. This is difficult to review and risky during deployment.

**Potential development:**

- Move schema evolution into reviewed Alembic migrations and run migrations as a deployment step.
- Adopt PostgreSQL for production, with connection pooling and tested backup/restore procedures.
- Add database constraints and indexes for ownership, organization scope, claim status, and frequently queried fields.
- Define retention, archival, export, and deletion workflows for personal data and claims.
- Use transactions and explicit rollback behavior for multi-record workflows.
- Document safe local reset commands separately from production backup and deletion procedures.

**Acceptance goals:** Fresh environments and upgrades reach the same schema; migration failures do not partially deploy; a backup can be restored and validated in a documented exercise.

### 8. API consistency and error handling

**Potential development:**

- Use consistent request/response schemas, pagination, sorting, and error formats across API endpoints.
- Avoid returning internal exception details to clients; log tracebacks privately with a request identifier.
- Add request IDs and structured logs to connect frontend errors, API events, and worker jobs.
- Add API versioning and documented compatibility rules.
- Validate state transitions and business rules in service-layer functions rather than duplicating them in endpoints.
- Remove obsolete endpoints and duplicate/old service implementations after confirming they are not imported or used.

**Acceptance goals:** Clients receive stable, useful errors without stack traces or secrets; support staff can correlate an error to server logs using a request ID.

### 9. Background jobs and workload controls

**Potential development:**

- Move long-running computer-vision inference and claim-package generation to a job queue.
- Persist job state, progress, retries, failure reasons, and artifact links.
- Add worker concurrency and GPU/memory limits appropriate to the installed models.
- Make assessment and package jobs idempotent and safe to retry.
- Add queue monitoring and a dead-letter or manual-retry process.
- Apply timeouts and resource limits to image processing, PDF parsing, and external LLM calls.

**Acceptance goals:** Slow model work does not block API workers; users can see whether work is queued, running, complete, or failed; transient errors can be retried safely.

### 10. Health checks and observability

**Potential development:**

- Separate liveness from readiness checks.
- Report readiness of the database, required model weights, RAG index, and external LLM configuration without leaking secrets.
- Add error monitoring, latency/error metrics, inference duration, upload volume, queue depth, and LLM request metrics.
- Add alerts for repeated failures, storage pressure, database availability, and elevated response time.
- Establish log retention and redaction rules; avoid logging passwords, tokens, policy contents, or sensitive personal details.

**Acceptance goals:** Operators can tell whether the service is ready and identify the failing dependency; alerts fire before users report sustained outages.

## P1 — AI assessment and policy assistant quality

### 11. Computer-vision quality, traceability, and human review

**Potential development:**

- Record model name, version, weights checksum, preprocessing settings, thresholds, runtime, and inference timestamp with every assessment.
- Measure performance on representative, labeled data, including different vehicle makes, lighting, weather, camera angles, and damage types.
- Track false positives/negatives and confidence calibration; make low-confidence and out-of-distribution cases explicit.
- Keep technician findings distinct from model output and preserve who changed each finding and why.
- Require human approval for decisions that affect claim outcomes or insurer-facing estimates.
- Create a process for model updates, validation, rollback, and comparison against the currently deployed model.
- Review whether severity and repair-cost outputs are sufficiently supported before presenting them as more than indicative estimates.

**Acceptance goals:** Every result can be traced to a model version and evidence set; users can distinguish AI suggestions from verified technician findings; model changes pass a documented evaluation before release.

### 12. RAG retrieval and answer grounding

**Current concern:** The repository contains placeholder RAG classes as well as the actual policy pipeline; the chatbot's dependency-error text still references a separate RAG requirements file that has been removed.

**Potential development:**

- Consolidate on one supported RAG implementation and update stale setup messages to refer to `backend/requirements.txt`.
- Validate that each policy source is approved, current, correctly attributed, and associated with the correct insurer and effective dates.
- Add retrieval evaluation datasets for the pre-packed questions and difficult edge cases; measure recall, source relevance, and answer correctness.
- Return clear “not found in supplied policy” answers when evidence is insufficient; avoid implying legal or claim-settlement authority.
- Test insurer filtering, conflicting policy clauses, outdated documents, prompt injection inside retrieved documents, and malicious user inputs.
- Record document version, page, chunk, retrieval score, model, and prompt version for support and audit, while applying privacy controls.
- Set rate limits, timeouts, token budgets, cost tracking, and fallback behavior for Groq outages.
- Add policy-document ingestion validation, duplicate detection, index versioning, and a safe re-index/rollback workflow.

**Acceptance goals:** Answers cite source documents and pages; the assistant declines unsupported claims; evaluation scores and known failure cases are documented for each release.

### 13. Insurer-ready claim-package validation

**Potential development:**

- Define a versioned insurer package schema and required-field checklist.
- Validate that customer, vehicle, accident, policy, evidence, assessment, technician review, and repair-estimate data are consistent before generation.
- Provide explicit missing-information and exception lists instead of silently filling defaults.
- Include evidence manifests with safe filenames, file hashes, timestamps, and category labels.
- Validate generated PDFs and ZIP archives, including expected contents, readability, and consistent claim identifiers.
- Add package version history and a reproducible record of the inputs used to generate each version.
- Have a domain expert confirm actual insurer requirements before claiming the package is ready for submission.

**Acceptance goals:** Invalid or incomplete packages are clearly marked; every generated package can be reproduced from recorded inputs; generated artifacts pass automated structure checks and human review.

## P2 — Product maturity and usability

### 14. Notifications and customer communication

- Add email or SMS notifications for claim submission, missing information, assessment completion, package preparation, and status changes.
- Let customers manage contact preferences and notification consent.
- Store delivery status and avoid sending sensitive claim details in message bodies.
- Provide in-app notification history and clear next steps for customers.

### 15. Service-center workflow tools

- Add assignment queues, workload visibility, technician roles, due dates, and escalation rules.
- Add searchable, paginated claim lists with filters by status, insurer, date, and assigned technician.
- Add internal notes distinct from customer-visible notes.
- Add configurable repair-estimate labor rates and parts catalogs with audit history.
- Add organization profile settings and a reviewable process for correcting submitted claim information.

### 16. Accessibility, responsive design, and localization

- Audit keyboard navigation, focus visibility, form labels, screen-reader announcements, contrast, and responsive layouts.
- Test customer and service-center workflows on mobile widths and low-bandwidth connections.
- Localize dates, currency, time zones, and supported languages consistently.
- Ensure color is never the only indicator of claim status, severity, or error state.

### 17. Search, reporting, and exports

- Add role- and tenant-scoped reporting for claim throughput, processing time, assessment outcomes, and package completeness.
- Build export workflows with authorization, audit logging, and data minimization.
- Define consistent reporting metrics so dashboards do not derive conflicting counts from different status subsets.

## P2 — Engineering quality and delivery

### 18. Automated test strategy

- Add unit tests for authorization helpers, status transitions, upload validation, package validation, and RAG query handling.
- Add integration tests for customer ownership, service-center tenant isolation, package download permissions, and file privacy.
- Add frontend tests for login separation, claim creation, document display, error states, and accessibility-critical interactions.
- Add end-to-end tests for a complete claim lifecycle using synthetic data and non-production files.
- Add load tests for concurrent uploads, model inference, claim queues, and RAG responses.
- Keep test data synthetic and ensure production data cannot be copied into CI.

### 19. CI/CD and dependency management

- Pin and lock backend and frontend dependencies for the supported runtime and operating systems.
- Add CI checks for linting, formatting, static typing, unit/integration tests, frontend production builds, and dependency vulnerability scanning.
- Build deployment artifacts in CI and promote the same artifact through staging to production.
- Use database migration checks and deployment smoke tests.
- Create a software bill of materials and a process for security updates.

### 20. Deployment and scaling

- Create documented production deployment configuration, container images, and a local orchestration setup for development.
- Put the frontend behind a secure web server/CDN and the API behind a TLS-terminating reverse proxy.
- Use managed PostgreSQL, private object storage, and a queue/worker system where appropriate.
- Keep model assets and vector indexes versioned and mounted or downloaded through controlled deployment steps.
- Define staging and production environments with separate data, secrets, domains, and LLM keys.
- Add deployment rollback and maintenance procedures.

## P3 — Longer-term opportunities

### 21. Integrations

- Evaluate approved insurer submission APIs and partner integrations.
- Add vehicle or policy verification integrations only after legal, licensing, consent, and data-protection review.
- Integrate with repair-shop inventory and estimating systems when data contracts are available.
- Add webhook delivery with signatures, retries, replay protection, and event logs.

### 22. Model and policy governance

- Establish model cards, evaluation reports, data provenance, approval gates, and version retirement plans.
- Monitor model performance drift and changes in incoming evidence quality.
- Keep policy ingestion and answer generation aligned with policy effective dates and insurer-specific terms.
- Create an incident process for incorrect AI suggestions or outdated policy answers.

### 23. Privacy and compliance program

- Map personal and sensitive data collected by each workflow and document the purpose and retention period.
- Conduct a privacy and security threat assessment before handling production documents.
- Define access reviews, incident response, breach notification responsibilities, and data-subject request handling based on applicable law.
- Have qualified legal and insurance-domain reviewers assess jurisdiction-specific requirements before launch.

## Suggested delivery phases

### Phase 0 — Secure prototype for internal use

- Remove public access to private claim files and require authorization for downloads.
- Require secure production configuration and prevent unapproved service-center registration.
- Fix authorization-before-mutation and validate claim lifecycle transitions.
- Add basic upload size/content validation and audit logging for privileged workflow actions.

### Phase 1 — Controlled pilot

- Add organization-level claim assignment and tenant isolation.
- Move schema evolution to Alembic and use a production database with backup/restore drills.
- Add background workers, operational monitoring, error reporting, and retry-safe jobs.
- Establish computer-vision evaluation and RAG answer-quality evaluation using synthetic or approved data.
- Add a package completeness checklist and domain-expert review.

### Phase 2 — Production launch

- Complete security review, access-control tests, load tests, and deployment rollback exercises.
- Set up managed storage, TLS, secret management, CI/CD, alerting, and support procedures.
- Define retention/deletion rules and publish clear user-facing AI and privacy disclosures.
- Confirm insurer package requirements and operational responsibilities with relevant domain experts.

### Phase 3 — Scale and integrations

- Add partner integrations, advanced reporting, multi-region or high-availability architecture, and model governance improvements based on actual pilot evidence.

## Release checklist

Use this as a go/no-go checklist for a production release:

- [ ] Production secrets are required and are not present in source control or client bundles.
- [ ] Public browsing of uploads, evidence, and generated packages is disabled.
- [ ] File downloads enforce customer ownership or service-center organization assignment.
- [ ] Privileged registration requires approval or invitation.
- [ ] Service-center APIs enforce organization-level isolation.
- [ ] Authorization is checked before every mutation, file operation, or package generation.
- [ ] Claim lifecycle transitions are validated and audited.
- [ ] Upload size, content, processing, and storage limits are enforced.
- [ ] Database migrations, backup, restore, and rollback procedures are documented and exercised.
- [ ] Tests cover cross-user access, role boundaries, file access, and failure paths.
- [ ] AI results are versioned, qualified, evaluated, and subject to human review.
- [ ] RAG answers are grounded in current insurer-specific sources and can decline unsupported questions.
- [ ] Monitoring, alerting, structured logs, and incident response are operational.
- [ ] Privacy, retention, and deletion practices have been reviewed for the launch jurisdiction.
- [ ] Insurer-facing package contents have been reviewed by an insurance-domain expert.

## How to use this roadmap

Treat the P0 items as release blockers for real customer information. For each item selected for implementation, create a trackable issue with an owner, acceptance criteria, migration impact, security considerations, and test plan. Revisit priorities after a controlled pilot using measured user feedback, system reliability, AI evaluation results, and applicable regulatory or insurer requirements.

