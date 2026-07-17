# BACKLOG — PDF ChatBot

Ordered epics/stories for a `/loop`-driven build. Work strictly in order —
each epic depends on the ones before it. Check off stories in `PROGRESS.md`
as they're completed, not just when code is written — a story is done when
its acceptance criteria are demonstrably true (page loads, pipeline runs,
etc.), matching this repo's build discipline.

Stack locked in for this build: Django 5.x + DRF, SQLite (dev), `pypdf` +
OCR fallback for extraction, `sentence-transformers` for embeddings
(local, no API key), ChromaDB (persistent, embedded) for vector storage,
a pluggable `LLMProvider` interface defaulting to an extractive
(no-LLM-required) answer mode, Django templates + htmx styled after the
**Azure Portal** design language (see Epic 8 for the token spec).

---

## Epic 0 — Project Foundation

Goal: a runnable Django skeleton with the app boundaries the rest of the
backlog builds into.

- **0.1** Initialize Django project (`config/`) + three apps: `documents`,
  `chat`, `vectorstore`. `manage.py runserver` serves an empty but working
  site.
  - AC: `python manage.py runserver` starts with no errors; hitting `/`
    returns a 200 (even if placeholder).
- **0.2** `requirements.txt` pinned (Django, djangorestframework, pypdf,
  pytesseract, pdf2image, sentence-transformers, chromadb,
  python-dotenv). `.env`-based settings for `SECRET_KEY`, `DEBUG`,
  `LLM_PROVIDER`, provider API keys (all optional/blank by default).
  - AC: fresh `venv` + `pip install -r requirements.txt` succeeds; app
    boots reading config from `.env`.
- **0.3** Base template (`templates/base.html`) with Azure Portal shell:
  top command bar, collapsible left nav, content area — no page-specific
  content yet, just the chrome (see Epic 8 tokens).
  - AC: base template renders with nav placeholders for "Documents" and
    "Chat"; visually reads as an Azure-Portal-style shell, not default
    Django styling.
- **0.4** `.gitignore` for `venv/`, `media/`, `chroma_data/`, `.env`,
  `db.sqlite3`, `__pycache__/`.
  - AC: `git status` after running the app shows none of the above as
    untracked.

## Epic 1 — Document Upload

Goal: a user can upload a PDF and see it listed.

- **1.1** `Document` model: `file`, `title`, `uploaded_at`, `status`
  (`pending`/`processing`/`ready`/`failed`), `page_count`, `error_message`.
  Migration applied.
- **1.2** Upload view/form: accepts a PDF, validates extension + size
  (e.g. max 50MB), saves to `media/documents/`, creates `Document` row
  with `status='pending'`.
  - AC: uploading a non-PDF is rejected with a clear error; uploading a
    valid PDF creates a row and redirects to the document list.
- **1.3** Document list view styled as an Azure Portal resource list
  (table with status badges/icons, upload timestamp, page count).
  - AC: uploaded documents appear in the list with correct status badge
    colors (pending=grey, processing=blue/spinner, ready=green,
    failed=red).
- **1.4** Document detail view + delete action (confirmation required
  before delete, per this project's action-safety norms).
  - AC: delete removes the `Document` row, its file, and (once Epic 5
    lands) its vectors — cascade is stubbed now, wired fully in 5.3.

## Epic 2 — Text Extraction

Goal: raw text is reliably pulled from any uploaded digital-text PDF.

- **2.1** `documents/services.py`: `extract_text(document) -> list[(page_number, text)]`
  using `pypdf` for digital PDFs.
  - AC: given a text-based PDF fixture, returns non-empty text per page
    in order.
- **2.2** ~~OCR fallback~~ — **dropped 2026-07-17.** Scanned/image-only
  PDF support via `pdf2image` + `pytesseract` needs Tesseract OCR and
  Poppler as system binaries; both `winget` installs failed in this
  environment with a UAC/elevation error (`0x800704c7`) that can't be
  approved from a non-interactive shell, and fetching an unofficial
  standalone binary from elsewhere was ruled out as an untrusted
  download. Decision: ship digital-text-PDF support only for now. The
  code (`_ocr_page`, `MIN_TEXT_LENGTH` threshold) and dependencies
  (`pytesseract`, `pdf2image`) were written, verified to fail at exactly
  the missing-binary point (not a code bug), then removed rather than
  left as untested dead code. Revisit if OCR support becomes a real
  requirement — install Tesseract + Poppler manually (interactively, so
  the UAC prompt can be approved) and reinstate.
- **2.3** Wire into pipeline: on upload, `status` moves
  `pending → processing`; extraction failures (corrupt file, password
  protection, scanned/image-only PDFs now unsupported per 2.2) set
  `status='failed'` + `error_message`, not a silent crash.
  - AC: a corrupted/password-protected PDF fixture ends in `status='failed'`
    with a human-readable error, not an unhandled exception.

## Epic 3 — Chunking

Goal: extracted text is split into retrieval-sized, overlapping chunks
with page provenance.

- **3.1** `Chunk` model: FK to `Document`, `text`, `page_number`,
  `chunk_index`, `embedded` (bool, default `False`). Migration applied.
- **3.2** `chunk_text(pages) -> list[Chunk-ready dicts]`: ~800-token
  windows, ~150-token overlap, chunk never crosses a silently-lost page
  boundary (each chunk records the page it started on).
  - AC: a multi-page fixture produces chunks whose concatenated text
    reconstructs the source (accounting for overlap); no chunk exceeds
    the configured max size.
- **3.3** Persist chunks for a processed document; verify order via
  `chunk_index`.
  - AC: `document.chunks.count()` matches expected chunk count for a
    known fixture.

## Epic 4 — Embedding

Goal: every chunk gets a local, no-API-key vector representation.

- **4.1** Embedding service wrapping `sentence-transformers`
  (`all-MiniLM-L6-v2`), model loaded once (module-level singleton, not
  per-call) — `embed(text: str) -> list[float]` and a batched
  `embed_many(texts: list[str]) -> list[list[float]]`.
  - AC: embedding the same string twice returns identical vectors;
    embedding 50 chunks via `embed_many` is meaningfully faster than 50
    sequential `embed` calls.
- **4.2** Batch-embed all chunks of a document; mark `Chunk.embedded=True`
  per chunk as it succeeds (so a partial failure doesn't silently look
  complete).
  - AC: after processing, every `Chunk` for a `ready` document has
    `embedded=True`.

## Epic 5 — Vector Storage

Goal: embeddings are queryable by similarity, scoped per document.

- **5.1** `vectorstore/client.py`: persistent Chroma client
  (`./chroma_data/`), wrapper functions `add_chunks(document_id, chunks,
  vectors)`, `query(vector, document_id=None, top_k=5)`,
  `delete_document(document_id)`.
  - AC: `add_chunks` then `query` on the same text's vector returns that
    chunk as the top result.
- **5.2** Wire into pipeline: after 4.2 embeds a document's chunks, push
  them to Chroma with metadata `{document_id, chunk_id, page_number}`;
  on success set `Document.status='ready'`.
  - AC: end-to-end, uploading a PDF results in `status='ready'` and a
    non-zero vector count in Chroma for that document.
- **5.3** Delete cascade: deleting a `Document` (1.4) also calls
  `delete_document(document_id)`.
  - AC: after deleting a document, querying Chroma for its old vectors
    returns nothing.

## Epic 6 — Pipeline Orchestration

Goal: Epics 2-5 are one reliable, observable operation, not four manual
steps.

- **6.1** `documents/services.py`: `process_document(document)`
  orchestrates extract → chunk → embed → store, updating `status` at
  each transition; any exception is caught, logged, and recorded as
  `status='failed'` + `error_message` (never an unhandled 500 on
  upload).
  - AC: intentionally breaking one stage (e.g. a garbage file) still
    leaves the app functional and the document visibly `failed`, not
    stuck `processing` forever.
- **6.2** Trigger `process_document` right after upload without blocking
  the HTTP response — a simple background thread is enough for now
  (no Celery/Redis yet; that's an explicit later upgrade, not required
  for this backlog).
  - AC: upload response returns immediately (sub-second); document
    status visibly progresses from `pending` to `ready`/`failed` on
    subsequent page loads/polls.
- **6.3** Processing status on the document list/detail view
  auto-refreshes (~~htmx polling~~ **implemented as vanilla JS polling
  instead, 2026-07-17**: htmx was never vendored into this project — CampusCore's
  htmx-vendoring convention doesn't automatically carry over to this
  separate app, and fetching htmx.min.js from a CDN would be a file
  download requiring explicit permission for a story that doesn't need
  it. A ~40-line vanilla `fetch()` poll against a small JSON status
  endpoint achieves the same UX with zero new dependencies) every few
  seconds until terminal status.
  - AC: watching the list view after upload shows the badge change
    without a manual page reload.

## Epic 7 — Retrieval & Chat (no LLM required)

Goal: a user can ask a question about a document and get a useful,
sourced answer — with zero external LLM API key configured.

- **7.1** `ChatSession` (FK to `Document`, `created_at`) and
  `ChatMessage` (FK to `ChatSession`, `role`, `content`,
  `source_chunks` JSON) models + migrations.
- **7.2** `chat/services.py`: `retrieve(query, document_id, top_k=5)` —
  embeds the query (reuses Epic 4's embedder) and calls
  `vectorstore.query`.
  - AC: querying with a phrase copied from a known fixture page returns
    that page's chunk in the top results.
- **7.3** `chat/llm/base.py`: `LLMProvider` ABC —
  `generate(question, chunks) -> str`. `chat/llm/extractive.py`:
  default provider, no API key needed, returns the top-ranked passages
  verbatim with page citations (e.g. "From page 4: ...") rather than a
  synthesized sentence — this is the real, functioning default, not a
  placeholder to delete later.
  - AC: with no provider configured, asking a question about an
    uploaded document returns a real answer built from retrieved text
    and page numbers, no errors, no "LLM not configured" dead end.
- **7.4** Chat view: create/continue a session scoped to one document,
  POST a question → retrieve → `LLMProvider.generate` → persist both
  messages → return the answer.
  - AC: a full ask/answer round-trip works via the UI end-to-end on a
    real uploaded PDF.
- **7.5** Chat UI: Azure-Portal-blade-styled panel (message bubbles,
  source/page citations shown per answer, input box pinned to bottom).
  - AC: visually consistent with Epic 8's token spec; citations are
    clickable/visible, not buried in raw JSON.

## Epic 8 — Azure Portal Theming

Goal: consistent visual language across every screen, matching Azure
Portal's design language (not a literal clone, but recognizably the same
family: Fluent-influenced, blue command bar, left nav, card/blade
layout).

- **8.1** Design tokens (CSS variables): primary `#0078D4`, primary-dark
  `#005A9E`, neutral background `#FAF9F8`, surface `#FFFFFF`, border
  `#EDEBE9`, text `#201F1E`, success `#107C10`, warning `#797673`/amber,
  error `#A4262C`; font stack `"Segoe UI", -apple-system, sans-serif`.
  Defined once in `static/css/theme.css`, imported by `base.html`.
- **8.2** Top command bar: app name/logo left, dark/light unaffected
  (light theme is the v1 target), user/context area right.
- **8.3** Left nav: collapsible, icon + label items (Documents, Chat),
  active-item highlight matching Azure Portal's left-border-accent
  pattern.
- **8.4** Document list as a "resource list" table (sortable header,
  status icon column, row hover state) instead of a plain Django
  scaffold table.
- **8.5** Chat panel as a slide-in blade (matches Azure Portal's
  panel/blade pattern: header with title + close, scrollable body,
  fixed-footer input).
  - AC for 8.1-8.5 collectively: a side-by-side glance at Documents and
    Chat screens reads as one coherent app, not mixed default-Django and
    themed pages.

## Epic 9 — Pluggable LLM Providers (inactive by default)

Goal: adding a real LLM later is a config change, not a rewrite.

- **9.1** `LLM_PROVIDER` env var + provider registry/factory in
  `chat/llm/__init__.py`; unset or unknown value falls back to
  `ExtractiveProvider` (7.3) with a visible (logged, not silent) notice.
- **9.2** `chat/llm/claude.py`: Anthropic adapter, active only when
  `ANTHROPIC_API_KEY` is set and `LLM_PROVIDER=claude`.
- **9.3** `chat/llm/openai.py`: OpenAI adapter, same activation pattern.
- **9.4** `chat/llm/ollama.py`: local Ollama adapter (no API key, calls
  `localhost:11434`), for a fully offline generative option.
  - AC for 9.1-9.4: with no env vars set, chat still works via 7.3's
    extractive provider; setting `LLM_PROVIDER` + a valid key switches
    to real generation with no other code changes.

## Epic 10 — Hardening & Deployment Readiness

Goal: the system survives real use, not just the happy path.

- **10.1** Input validation hardening: file size/type/page-count limits
  enforced server-side (not just UI), duplicate-upload handling,
  friendly error pages (no raw tracebacks in non-DEBUG mode).
- **10.2** Basic automated tests: extraction, chunking, embedding
  determinism, retrieval relevance (fixture-based), covering the
  services layer (not just views).
- **10.3** `README.md`: setup (venv, `.env`, `migrate`, `runserver`),
  architecture summary, how to enable a real LLM provider (points at
  Epic 9).
- **10.4** Optional Dockerfile/`docker-compose.yml` for reproducible
  local runs (not required to consider the project "done", but the
  logical last story).
