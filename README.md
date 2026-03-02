# Coached

Voice-based AI coaching platform powered by VAPI and Claude. Callers dial in, pick a topic, and get personalized coaching with long-term memory across sessions.

## Architecture

```
Caller --> VAPI (voice/transcription) --> This Backend (FastAPI)
                                              |
                                     MongoDB (memory)
                                     Claude API (summaries)
```

VAPI handles the phone call, speech-to-text, and text-to-speech. This backend provides:
- **Tool endpoints** that VAPI calls mid-conversation (person lookup, topic session start)
- **Webhook endpoint** that VAPI calls after a call ends (transcript storage, summary generation)
- **Admin endpoints** for managing caller data

## Coaching Assistants

Five coaching assistants are configured in VAPI, each with a unique system prompt and coaching style. All share the same backend infrastructure and tools.

| Coach | VAPI Assistant ID | Template Code | Best For |
|-------|-------------------|---------------|----------|
| Accountability Partner | `69411b1f-a971-462b-a11a-61cf3b5ab715` | `accountability-core` | General goals, projects, habits |
| Student Success Coach | `c1995689-523c-4de3-ae49-53ffb911be69` | `student-success` | Academics, exams, study habits |
| Personal Performance Coach | `54819721-5422-4a90-a4b9-47dc843016d0` | `personal-performance` | Clarity, focus, execution |
| Founder Execution Coach | `dc2284ca-a57a-4379-b981-bd65af9f9b22` | `founder-execution` | Shipping product, business priorities |
| Weight Loss & Health Habits Coach | `9c8b6724-7c77-46b2-86cf-6204e3dc630d` | `health-weight-loss` | Food, movement, sleep habits |

System prompts live in `prompt_*.txt` files in the project root.

## API Endpoints

### `GET /health`
Health check. No auth required.

**Response:** `{"status": "ok"}`

---

### `POST /vapi/tools`
Handles VAPI tool calls during a live conversation. Auth: `X-Vapi-Secret` header.

VAPI sends a request containing `message.type = "tool-calls"` with the assistant ID, caller phone, and a list of tool calls. The backend processes each tool and returns results.

#### Tool: `lookupPersonAndTopics`

Called at the start of every call. Returns the caller's name (if known) and their existing topics.

**Arguments (from VAPI context):**
- `assistantId` - VAPI assistant ID
- `callerPhone` - Caller's phone number

**Response:**
```json
{
  "success": true,
  "personName": "Alex",
  "topics": [
    {
      "topicId": "topic_a1b2c3d4e5f6",
      "topicName": "Launch my podcast",
      "lastSummarySnippet": "Committed to recording episode 1 by Friday...",
      "lastUpdatedAt": "2026-02-08T15:30:00Z"
    }
  ]
}
```

#### Tool: `startTopicSession`

Called after the caller picks a topic (or starts a new one). Returns the full conversation history for that topic.

**Arguments:**
- `assistantId`, `callerPhone` (from VAPI context)
- `topicId` (for existing topic) OR `newTopicName` (for new topic)
- `mode` - `"accountability"`, `"brainstorming"`, or `"mix"`
- `coachingTemplateCode` (optional)

**Response:**
```json
{
  "success": true,
  "topicId": "topic_a1b2c3d4e5f6",
  "topicName": "Launch my podcast",
  "conversationId": "conv_2026-02-10T14:30:00",
  "mode": "accountability",
  "summarySoFar": "--- Session 1 ---\n...\n--- Session 2 ---\n..."
}
```

---

### `POST /vapi/webhooks`
Handles VAPI end-of-call reports. Auth: `X-Vapi-Secret` header.

When a call ends, VAPI sends the full transcript. The backend:
1. Saves the raw transcript to MongoDB
2. Generates a summary using Claude (from past summaries + new transcript)
3. Saves the summary
4. Consolidates old summaries if count exceeds `SUMMARY_CAP`

**Response:** `{"status": "ok"}` (processing happens in background)

---

### `POST /admin/set-person-name`
Sets or updates a caller's display name. Auth: `X-Admin-Key` header.

**Request body:**
```json
{
  "agentId": "69411b1f-a971-462b-a11a-61cf3b5ab715",
  "personKey": "+18605551234",
  "personName": "Alex"
}
```

**Response:** `{"success": true, "recordId": "..."}`

## Call Lifecycle

1. **Caller dials in** - VAPI picks up, connects to the assigned assistant
2. **`lookupPersonAndTopics`** - Assistant calls backend to get caller name and topics
3. **Greeting** - Assistant greets by name, lists topics, asks what to focus on
4. **`startTopicSession`** - Assistant calls backend to load topic history
5. **Coaching conversation** - Assistant uses the topic summary as memory and coaches per its system prompt
6. **Call ends** - VAPI sends end-of-call report to `/vapi/webhooks`
7. **Backend processes** - Transcript saved, summary generated via Claude, old summaries consolidated

## Memory System

Each topic maintains a rolling window of session summaries:

- After each call, Claude generates a summary from the transcript
- Summaries are stored with incrementing sequence numbers per topic
- When summaries exceed `SUMMARY_CAP` (default 5), the oldest are consolidated into one via Claude
- On the next call, all summaries are concatenated and passed to the assistant as `summarySoFar`

This gives the assistant long-term memory without unbounded context growth.

## Database

MongoDB with two collections:

**`agentMemoryRecords`** - All coaching memory (transcripts, summaries, identity data)
- Indexed on `(agentId, personKeyType, personKey, topicId, recordKind)`
- Indexed on `(agentId, personKeyType, personKey)`

**`conversationSessions`** - Maps each conversation to its topic
- Unique index on `conversationId`

Indexes are created automatically on startup.

## Environment Variables

Copy `.env.example` to `.env` and fill in the values:

| Variable | Description |
|----------|-------------|
| `MONGODB_URI` | MongoDB connection string (e.g. MongoDB Atlas URI) |
| `MONGODB_DB_NAME` | Database name (default: `expertly`) |
| `ANTHROPIC_API_KEY` | Claude API key for summary generation |
| `CLAUDE_MODEL` | Claude model ID (e.g. `claude-sonnet-4-20250514`) |
| `VAPI_SERVER_SECRET` | Shared secret for VAPI webhook/tool auth |
| `ADMIN_API_KEY` | API key for admin endpoints |
| `SUMMARY_CAP` | Max summaries per topic before consolidation (default: `5`) |

## Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env with your values

# Run the server
uvicorn main:app --reload --port 8000
```

The server starts at `http://localhost:8000`. API docs at `http://localhost:8000/docs`.

For local VAPI testing, you'll need a public URL (e.g. ngrok) pointed at your local server, and set that as the server URL in VAPI.

## Testing

### Automated conversation tests

```bash
python test_conversation.py
```

Runs three scripted scenarios against Claude with mock tool responses (no backend needed). Tests validate tool call structure, conversation flow, and tone.

### Interactive simulator

```bash
# Mock mode (no backend required, uses hardcoded scenarios)
python simulate.py --scenario returning
python simulate.py --scenario new

# Live mode (calls real production backend)
python simulate.py --live
```

Type messages as the caller, see Claude's responses and tool calls in real time. Commands: `/quit`, `/reset`, `/prompt`, `/transcript`.

### Manual API testing

```bash
# Health check
curl http://localhost:8000/health

# Set a person's name
curl -X POST http://localhost:8000/admin/set-person-name \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: your-admin-key" \
  -d '{"agentId": "ASSISTANT_ID", "personKey": "+18605551234", "personName": "Alex"}'
```

## Deployment (Railway)

The app is deployed on Railway. The `Procfile` defines the start command:

```
web: uvicorn main:app --host 0.0.0.0 --port $PORT
```

### Steps to deploy

1. Push code to a GitHub repo connected to Railway (or use `railway up`)
2. Set all environment variables from `.env.example` in the Railway dashboard
3. Railway auto-detects Python, installs from `requirements.txt`, and runs the `Procfile`
4. Note the public URL Railway assigns (e.g. `https://your-app.up.railway.app`)
5. In the VAPI dashboard, set each assistant's server URL to:
   - Webhook URL: `https://your-app.up.railway.app/vapi/webhooks`
   - Tool server URL: `https://your-app.up.railway.app/vapi/tools` (configured per-tool in VAPI)
   - Server secret: must match `VAPI_SERVER_SECRET`

### Current production URL

`https://web-production-b0d30.up.railway.app`

## Project Structure

```
coached/
├── main.py                          # FastAPI app entrypoint
├── Procfile                         # Railway deployment
├── requirements.txt                 # Python dependencies
├── .env.example                     # Environment variable template
├── app/
│   ├── config.py                    # Pydantic settings
│   ├── database.py                  # MongoDB connection and indexes
│   ├── dependencies.py              # Auth middleware (VAPI secret, admin key)
│   ├── models/
│   │   └── memory.py                # Data models (records, sessions, responses)
│   ├── routers/
│   │   ├── vapi_tools.py            # Tool call handler (lookup, startSession)
│   │   └── vapi_webhooks.py         # End-of-call webhook handler
│   └── services/
│       ├── memory_service.py        # MongoDB CRUD operations
│       └── summary_service.py       # Claude-based summary generation
├── prompt_accountability_partner.txt # Coaching prompt
├── prompt_student_success.txt        # Coaching prompt
├── prompt_personal_performance.txt   # Coaching prompt
├── prompt_founder_execution.txt      # Coaching prompt
├── prompt_health_weight_loss.txt     # Coaching prompt
├── simulate.py                       # Interactive conversation simulator
└── test_conversation.py              # Automated conversation tests
```
