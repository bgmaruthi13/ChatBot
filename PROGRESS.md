# PROGRESS — PDF ChatBot

Tracks build status against `BACKLOG.md`. Check off a story only once its
acceptance criteria are demonstrably true (server runs, pipeline
completes, UI reflects it) — not merely when code is written. Work top to
bottom; each epic depends on prior epics.

## Epic 0 — Project Foundation
- [x] 0.1 Django project + app skeleton
- [x] 0.2 requirements.txt + `.env` settings
- [x] 0.3 Base template / Azure Portal shell
- [x] 0.4 `.gitignore`

## Epic 1 — Document Upload
- [x] 1.1 Document model + migration
- [x] 1.2 Upload view/form + validation
- [x] 1.3 Document list view (resource-list style)
- [x] 1.4 Document detail + delete

## Epic 2 — Text Extraction
- [x] 2.1 `extract_text()` (pypdf)
- [x] 2.2 ~~OCR fallback~~ — **dropped 2026-07-17** (user decision): needs Tesseract+Poppler system binaries, `winget` install failed on UAC elevation this environment can't approve. See BACKLOG.md 2.2. Code/deps removed; digital-text PDFs only.
- [x] 2.3 Wired into pipeline w/ failure handling

## Epic 3 — Chunking
- [x] 3.1 Chunk model + migration
- [x] 3.2 `chunk_text()` service
- [x] 3.3 Persisted + ordered chunks verified

## Epic 4 — Embedding
- [x] 4.1 Local embedding service (sentence-transformers)
- [x] 4.2 Batch-embed chunks, mark `embedded=True`

## Epic 5 — Vector Storage
- [x] 5.1 Chroma client wrapper (add/query/delete)
- [x] 5.2 Wired into pipeline, `status='ready'`
- [x] 5.3 Delete cascade removes vectors

## Epic 6 — Pipeline Orchestration
- [x] 6.1 `process_document()` orchestrator + failure handling (already unified while building Epics 2-5; reconfirmed against a fresh corrupted-file case)
- [x] 6.2 Non-blocking trigger on upload
- [x] 6.3 Auto-refreshing status UI (vanilla JS polling, not htmx — see note below)

## Epic 7 — Retrieval & Chat (no LLM required)
- [x] 7.1 ChatSession/ChatMessage models
- [x] 7.2 `retrieve()` service
- [x] 7.3 `LLMProvider` ABC + `ExtractiveProvider` default
- [x] 7.4 Chat view (ask/answer round-trip)
- [x] 7.5 Chat UI (blade-styled)

## Epic 8 — Azure Portal Theming
- [x] 8.1 Design tokens (`theme.css`) — built in 0.3, verified exact match to spec (all colors/font confirmed)
- [x] 8.2 Top command bar — built in 0.3; no user/context area content since app has no auth system
- [x] 8.3 Left nav — built in 0.3/1.3; added collapse toggle this pass (`nav-toggle.js`, localStorage-persisted), verified 220px↔48px in-browser
- [x] 8.4 Document list as resource-list table — built in 1.3
- [x] 8.5 Chat panel as slide-in blade — built in 7.5; added header close (×) control this pass to match "title + close" spec

## Epic 9 — Pluggable LLM Providers (inactive by default)
- [x] 9.1 Provider registry/factory + fallback
- [x] 9.2 Claude adapter
- [x] 9.3 OpenAI adapter
- [x] 9.4 Ollama adapter

## Epic 10 — Hardening & Deployment Readiness
- [x] 10.1 Input validation hardening
- [x] 10.2 Automated tests (services layer)
- [x] 10.3 README
- [x] 10.4 Dockerfile / docker-compose (optional) — written to standard patterns, YAML validated; not build/run-tested since Docker isn't available in this environment

---
**Next up:** None — all epics complete (2026-07-17).

**Final verification pass:** `manage.py check` clean, all 11 automated
tests pass, and a completely fresh upload→ready→chat round trip via
the real HTTP UI succeeded (document processed to `ready` with 3
chunks, question answered with citations for all 3 pages). Docker
build itself is unverified (no Docker in this environment) but the
Dockerfile/compose files follow standard patterns and the YAML is
syntax-validated.
