# Coached — Milestone Canvas

> Voice-based AI coaching platform powered by VAPI + Claude with long-term memory.
> Production URL: `https://expertly-coached.vercel.app`

---

## Legend

| Status | Meaning |
|--------|---------|
| DONE | Task fully completed and deployed |
| IN PROGRESS | Actively being worked on |
| PLANNED | Scoped but not yet started |

---

## Milestone 1: Core Platform Foundation
**Status: DONE**
**Commits:** `6b89797`, `883fafb`, `62ac27f`

### Task 1.1 — Project Scaffolding & FastAPI Backend
**Status:** DONE

**What was involved:**
- Initialized a Python FastAPI project with async support
- Created the modular project structure: `app/config.py`, `app/database.py`, `app/dependencies.py`, `app/models/`, `app/routers/`, `app/services/`
- Set up Pydantic Settings for environment-based configuration (`MONGODB_URI`, `ANTHROPIC_API_KEY`, `CLAUDE_MODEL`, etc.)
- Added `requirements.txt` with core dependencies: `fastapi`, `uvicorn`, `motor` (async MongoDB), `pydantic`, `anthropic`, `python-dotenv`
- Created `.env.example` as a configuration template
- Implemented `/health` endpoint for uptime monitoring

### Task 1.2 — MongoDB Database Layer
**Status:** DONE

**What was involved:**
- Integrated MongoDB via the `motor` async driver in `app/database.py`
- Designed two collections:
  - **`agentMemoryRecords`** — stores transcripts, summaries, and identity data per caller/topic with fields: `agentId`, `personKey`, `topicId`, `sequence`, `text`, `recordKind`, `conversationId`, `createdAt`, `updatedAt`
  - **`conversationSessions`** — maps each conversation to a topic/caller with fields: `conversationId`, `agentId`, `personKey`, `topicId`, `topicName`, `mode`, `coachingTemplateCode`, `createdAt`
- Created compound indexes for efficient queries:
  - `(agentId, personKeyType, personKey, topicId, recordKind)` on memory records
  - `(agentId, personKeyType, personKey)` on memory records
  - Unique index on `conversationId` for sessions
- Indexes auto-create on app startup

### Task 1.3 — VAPI Tool Call Integration
**Status:** DONE

**What was involved:**
- Built `POST /vapi/tools` endpoint in `app/routers/vapi_tools.py` to handle real-time tool calls from VAPI during live phone conversations
- Implemented **`lookupPersonAndTopics`** tool: retrieves caller's stored name and list of existing coaching topics (with last summary snippet and timestamp) based on phone number and assistant ID
- Implemented **`startTopicSession`** tool: loads or creates a topic, returns concatenated summary history as `summarySoFar`, creates a `conversationSession` record for tracking
- Phone number normalization to E.164 format (handles 10-digit, 11-digit, and international formats)
- Tool call arguments extracted from VAPI context (assistantId, callerPhone) rather than tool arguments, matching VAPI's actual payload structure

### Task 1.4 — Webhook & Transcript Processing
**Status:** DONE

**What was involved:**
- Built `POST /vapi/webhooks` endpoint in `app/routers/vapi_webhooks.py` to handle VAPI's end-of-call reports
- On call completion: saves raw transcript to MongoDB as a `transcript` record
- Triggers Claude-based summary generation from past summaries + new transcript (via `app/services/summary_service.py`)
- Saves the generated summary as a new `summary` record with incrementing sequence numbers
- Implemented graceful fallback: if summary generation fails, transcript is still saved; if conversation session lookup fails, transcript saved to `_unmatched` topic
- Background task processing so webhook responds immediately while summary generates async

### Task 1.5 — Authentication & Security
**Status:** DONE

**What was involved:**
- Implemented HMAC-based secret validation for VAPI endpoints (`X-Vapi-Secret` header) in `app/dependencies.py`
- Implemented API key authentication for admin endpoints (`X-Admin-Key` header)
- Dev mode: when secrets are empty/unset, validation is skipped (for local development)
- Built `POST /admin/set-person-name` endpoint for managing caller display names with admin auth

### Task 1.6 — Long-Term Memory & Summary Consolidation
**Status:** DONE

**What was involved:**
- Designed the rolling summary window system in `app/services/summary_service.py` and `app/services/memory_service.py`
- After each call, Claude generates a summary from: all past summaries for the topic + the new transcript
- When summary count exceeds `SUMMARY_CAP` (default: 5), oldest summaries are consolidated into one via a separate Claude call
- Consolidation algorithm: merge oldest `(total - (cap-1))` summaries into 1, keep `(cap-1)` most recent, re-sequence all to contiguous numbers
- Fallback: if consolidation fails, the most recent summary is preserved as-is
- This design keeps token usage bounded while preserving long-term context across unlimited sessions

---

## Milestone 2: Coaching Assistants & Prompts
**Status: DONE**
**Commits:** `26f0b4f`, `bc8bf9c`, `f1f3487`, `3bed5f1`

### Task 2.1 — Five Specialized Coaching Prompts
**Status:** DONE

**What was involved:**
- Created detailed system prompts (~165-173 lines each) for five coaching specializations, stored as `prompt_*.txt` files:
  1. **Accountability Partner** (`prompt_accountability_partner.txt`) — general goals, projects, habits; flexible brainstorming + accountability balance
  2. **Student Success Coach** (`prompt_student_success.txt`) — academics, exams, assignments, study planning; age-appropriate language
  3. **Personal Performance Coach** (`prompt_personal_performance.txt`) — clarity, focus, execution optimization; mental model building
  4. **Founder Execution Coach** (`prompt_founder_execution.txt`) — shipping products, business priorities, startup execution; bias toward action
  5. **Weight Loss & Health Habits Coach** (`prompt_health_weight_loss.txt`) — food, movement, sleep habits; behavior change focus
- Each prompt configured in VAPI with a unique Assistant ID and template code

### Task 2.2 — Shared Conversational Rules
**Status:** DONE

**What was involved:**
- Established consistent rules across all five coaching prompts:
  - **Brevity:** 1-3 short sentences per response (optimized for phone, not text)
  - **Single question per turn:** no stacking multiple questions
  - **Natural speech:** no markdown, bullet points, or lists
  - **Tone calibration:** avoid over-enthusiasm, stay warm but grounded
  - **Clarification protocol:** ask follow-up on unclear input instead of guessing
  - **Emotional boundaries:** recognize when to refer to mental health professionals
  - **Graceful call ending:** natural wrap-up with actionable takeaway

### Task 2.3 — Onboarding & First-Call Experience
**Status:** DONE

**What was involved:**
- Added first-call onboarding flows within each coaching prompt
- New callers get oriented on how the coaching works and what to expect
- Returning callers are greeted by name with a recap of their last topic
- Topic selection flow handles: picking existing topic, starting new topic, or clarifying when intent is ambiguous

### Task 2.4 — Iterative Prompt Refinement
**Status:** DONE (3 refinement passes)

**What was involved:**
- **Pass 1** (`bc8bf9c`): Initial prompt updates — tightened tone, improved question quality, better handling of vague responses
- **Pass 2** (`f1f3487`): Scenario-specific improvements — better handling of callers who go off-topic, callers who are frustrated, callers who want to switch topics mid-call
- **Pass 3** (`3bed5f1`): Onboarding, pacing, and edge cases — improved first-time caller onboarding, better pacing for callers who talk fast/slow, handling of silence/dropped audio, caller confusion recovery

---

## Milestone 3: Testing & Simulation
**Status: DONE**
**Commit:** `26f0b4f`

### Task 3.1 — Automated Conversation Tests
**Status:** DONE

**What was involved:**
- Created `test_conversation.py` with 3 scripted end-to-end conversation scenarios using Claude with mock tool responses (no backend required):
  1. **Returning caller picks existing topic** — validates tool call structure, topic recognition, summary usage
  2. **New caller starts fresh** — validates onboarding flow, new topic creation
  3. **Returning caller starts new topic** — validates topic branching, correct tool arguments
- Tests validate: correct tool invocation, argument structure, conversational tone, coaching protocol adherence

### Task 3.2 — All-Assistant Stress Test Suite
**Status:** DONE

**What was involved:**
- Created `test_all_assistants.py` — comprehensive test runner that exercises all 5 coaching assistants
- Runs targeted scenarios per specialization (e.g., academic stress for Student Coach, shipping deadlines for Founder Coach)
- Tests edge cases and protocol compliance per assistant
- CLI flags: `--assistant` to filter by coach, `--verbose` for detailed output
- Validates domain-specific response quality alongside shared rules

### Task 3.3 — Interactive Conversation Simulator
**Status:** DONE

**What was involved:**
- Created `simulate.py` — real-time interactive conversation simulator
- **Mock mode:** uses hardcoded scenarios with no backend required; supports `--scenario new` and `--scenario returning`
- **Live mode (`--live`):** calls the real production backend for end-to-end testing
- Interactive commands: `/quit`, `/reset`, `/prompt`, `/transcript`
- Displays Claude's responses and tool calls in real time for debugging

---

## Milestone 4: Deployment & Infrastructure
**Status: DONE**
**Commits:** `6cd1e08`, `b741c53`, `4c75546`

### Task 4.1 — Vercel Deployment (Primary)
**Status:** DONE

**What was involved:**
- Created `vercel.json` configuration for deploying the FastAPI app on Vercel
- Deployed to Vercel with production URL: `https://expertly-coached.vercel.app`
- Configured all environment variables in Vercel dashboard
- VAPI dashboard configured with webhook and tool server URLs pointing to Vercel

### Task 4.2 — Railway Deployment (Legacy)
**Status:** DONE

**What was involved:**
- Created `Procfile` with startup command: `web: uvicorn main:app --host 0.0.0.0 --port $PORT`
- Previously deployed to Railway; migrated to Vercel as the primary platform

### Task 4.3 — Documentation
**Status:** DONE

**What was involved:**
- Created comprehensive `README.md` covering:
  - Architecture diagram (Caller → VAPI → Backend → MongoDB/Claude)
  - All 5 coaching assistants with VAPI Assistant IDs and template codes
  - Full API endpoint documentation with request/response examples
  - Call lifecycle walkthrough (7-step flow)
  - Memory system explanation (rolling summary window)
  - Database schema and indexes
  - Environment variable reference
  - Local development setup instructions
  - Testing guide (automated tests, simulator, manual API testing)
  - Deployment instructions for Vercel and Railway
  - Project directory structure

---

## Milestone 5: Future Enhancements
**Status: PLANNED**

### Task 5.1 — Analytics & Coaching Dashboard
**Status:** PLANNED
- Caller engagement metrics, session frequency, topic progression
- Admin dashboard for reviewing coaching quality

### Task 5.2 — Caller Feedback Collection
**Status:** PLANNED
- Post-call rating system
- Feedback integration into prompt tuning

### Task 5.3 — Prompt A/B Testing Framework
**Status:** PLANNED
- Run multiple prompt variants per assistant
- Measure effectiveness by caller retention and feedback

### Task 5.4 — Scheduling & Reminders
**Status:** PLANNED
- Callers can schedule follow-up calls
- SMS/push reminders for accountability check-ins

### Task 5.5 — Multi-Language Support
**Status:** PLANNED
- Expand coaching beyond English
- Language detection and routing

### Task 5.6 — External Calendar Integration
**Status:** PLANNED
- Sync goals and deadlines with Google Calendar / Apple Calendar
- Proactive accountability nudges based on upcoming events

---

## Summary

| Milestone | Tasks | Status |
|-----------|-------|--------|
| 1. Core Platform Foundation | 6 tasks | DONE |
| 2. Coaching Assistants & Prompts | 4 tasks | DONE |
| 3. Testing & Simulation | 3 tasks | DONE |
| 4. Deployment & Infrastructure | 3 tasks | DONE |
| 5. Future Enhancements | 6 tasks | PLANNED |

**Total completed tasks:** 16/22
**Project phase:** MVP shipped and deployed to production, iterating on coaching quality
