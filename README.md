# Devin GitHub Issues CLI

A command-line tool that integrates the [Devin API](https://docs.devin.ai/api-reference/overview) with GitHub Issues to automate issue triaging, scoping, and execution.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green.svg)](https://fastapi.tiangolo.com/)

## What Does This Do?

This CLI tool connects Devin AI with your GitHub repositories to:

1. **List and Filter Issues** - View issues from any GitHub repository with smart filtering
2. **Scope Issues** - Devin analyzes issues and provides:
   - Implementation plans (step-by-step)
   - Confidence scores (0-100%)
   - Risk assessments (low/medium/high)
   - Effort estimates (in hours)
3. **Execute Issues** - Devin automatically:
   - Creates feature branches
   - Implements the fix
   - Runs tests
   - Opens Pull Requests
4. **Track Sessions** - View history and status of all Devin sessions

## Key Features

- **CLI Interface** - Color-coded output, tables, and progress indicators
- **Smart Defaults** - Non-blocking execution prevents terminal hangs
- **Session Tracking** - SQLite database stores all sessions and results
- **Confidence Scoring** - Color-coded confidence levels (high, medium, low)

## Architecture

<img width="2274" height="740" alt="image" src="https://github.com/user-attachments/assets/b2b57336-6d89-4275-8c27-03bb5894f0ba" />



## Installation

### Prerequisites

- Python 3.11 or higher
- pip or conda
- GitHub Personal Access Token ([create one here](https://github.com/settings/tokens))
- Devin API Key (from your Cognition dashboard)

### Step 1: Clone or Download

```bash
cd devin-issues-cli-integration
```

### Step 2: Create Virtual Environment

**Using conda (recommended):**
```bash
conda create -n devin-cli python=3.11 -y
conda activate devin-cli
```

**Or using venv:**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Configure API Keys

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your credentials
nano .env  # or use your favorite editor
```

**Update these values in `.env`:**
```bash
GITHUB_TOKEN=ghp_your_actual_github_token_here
DEVIN_API_KEY=your_actual_devin_api_key_here
```

**Getting your API keys:**
- **GitHub Token**: https://github.com/settings/tokens
  - Required scopes: `repo` (for private repos) or `public_repo` (for public repos only)
- **Devin API Key**: From your Cognition/Devin dashboard

### Step 5: Initialize Database

```bash
python -m app.database
```

You should see:
```
✅ Database connection successful!
✅ Database tables created!
```

### Step 6: Test Configuration

```bash
python -m app.config
```

You should see your configuration loaded successfully (with API keys hidden).

## Usage

### Starting the API Server

**Terminal 1 - Start the backend:**
```bash
conda activate devin-cli
uvicorn app.api.main:app --reload
```

The API will start on `http://localhost:8000`


### Using the CLI

**Terminal 2 - Run CLI commands:**

> **Tip:** You can use the `python devin-issues` script as a convenient entry point instead of `python -m cli.main`. For example: `python devin-issues list python/cpython` instead of `python -m cli.main list python/cpython`.

---

## Command Reference

> **Note:** All examples below use `python -m cli.main`, but you can also use the `devin-issues` convenience script (e.g., `python devin-issues list python/cpython`).

### `list` - List GitHub Issues

View and filter issues from any GitHub repository.

```bash
python -m cli.main list <owner>/<repo> [OPTIONS]
```

**Options:**
- `--label, -l TEXT` - Filter by label (e.g., "bug", "enhancement")
- `--state, -s TEXT` - Filter by state ("open", "closed", "all") [default: open]
- `--per-page, -n INT` - Number of issues to show (max 100) [default: 30]

**Examples:**
```bash
# List open bugs from Python's CPython
python -m cli.main list python/cpython --label type-bug

# List all issues (open and closed)
python -m cli.main list facebook/react --state all

# Show only 5 issues
python -m cli.main list myorg/myrepo -n 5

# Or use the convenience script:
python devin-issues list python/cpython --label type-bug
```

**Output:**
- Summary panel with issue count
- Formatted table with:
  - Issue number
  - Title with status emoji (🔴 open, ✅ closed)
  - Color-coded labels
  - Comment count
  - Human-readable update time ("2h ago")

Example: `python devin-issues list python/cpython --label type-bug -n 5`

<img width="1640" height="1108" alt="image" src="https://github.com/user-attachments/assets/ed022096-481e-4545-b0dc-64d3e915a9d6" />

---

### `scope` - Scope an Issue with Devin AI

Analyze an issue and get an implementation plan with confidence score.

```bash
python -m cli.main scope <owner>/<repo> <issue_number> [OPTIONS]
```

**Options:**
- `--wait / --no-wait` - Wait for Devin to complete (default: wait)

**Examples:**
```bash
# Scope an issue and wait for results
python -m cli.main scope python/cpython 12345

# Start scoping without waiting (check status later)
python -m cli.main scope myorg/myrepo 42 --no-wait
```

**What You Get:**
- Implementation summary
- Step-by-step plan (3-7 steps)
- **Confidence score** (0-100%, color-coded)
- Risk level (LOW/MEDIUM/HIGH)
- Estimated effort (in hours)
- Link to Devin session

**Confidence Scoring:**
- 🟢 **80%+** - High confidence (safe to execute)
- 🟡 **60-79%** - Medium confidence (review carefully)
- 🔴 **<60%** - Low confidence (manual review recommended)

Example: Scoping `issue #142424` from `python/cpython`, a bug identified in the example screenshotted issue listings

`python devin-issues scope python/cpython 142424`

<img width="1846" height="1186" alt="image" src="https://github.com/user-attachments/assets/33b08246-85ce-4b84-9a11-908667be2703" />


---

### `execute` - Execute an Issue with Devin AI

Let Devin implement the fix and create a Pull Request automatically. If the issue was scoped prior, implementation steps from the scope are used.

```bash
python -m cli.main execute <owner>/<repo> <issue_number> [OPTIONS]
```

**Options:**
- `--wait / --no-wait` - Wait for completion (default: no-wait, **recommended**)

**Examples:**
```bash
# Execute an issue (returns immediately, triggers Devin asynchronously)
python -m cli.main execute myorg/myrepo 42

# Execute and wait for completion (10-30+ minutes depending on issue complexity)
python -m cli.main execute myorg/myrepo 42 --wait
```

**What Devin Does:**
1. Clones your repository (if needed)
2. Creates a feature branch
3. Implements the fix following best practices
4. Runs tests
5. Opens a Pull Request with detailed description

**Returns:**
- Session ID and URL to track progress
- PR URL (when complete)
- Branch name
- Test results (passed/failed counts)

**Recommendation**: Use `--no-wait` (default) to avoid terminal hanging. Check progress via the session URL or `status` command.

Example: Executing a [fraction class issue](https://github.com/rlnguyen/test-repo/issues) from a test repository.

`python devin-issues execute rlnguyen/test-repo 11`

<img width="1542" height="648" alt="image" src="https://github.com/user-attachments/assets/3ade893a-845f-4110-90a1-4ec922a03a57" />

See the Devin-produced PR [here!](https://github.com/rlnguyen/test-repo/pull/20)

---

### `status` - View Session History

Check the status of Devin sessions and view history.

```bash
# List all recent sessions
python -m cli.main status [OPTIONS]

# Check specific session
python -m cli.main status <session_id>
```

**Options:**
- `--repo, -r TEXT` - Filter by repository (owner/repo)
- `--issue, -i INT` - Filter by issue number (requires --repo)
- `--phase, -p TEXT` - Filter by phase ("scope" or "exec")
- `--limit, -l INT` - Maximum sessions to show [default: 20]

**Examples:**
```bash
# View all recent sessions
python -m cli.main status

# View specific session details
python -m cli.main status devin-abc123def456...

# Filter by repository
python -m cli.main status --repo python/cpython

# Filter by issue
python -m cli.main status --repo myorg/myrepo -i 42

# Show only scoping sessions
python -m cli.main status --phase scope

# Show only execution sessions
python -m cli.main status --phase exec

# Show last 50 sessions
python -m cli.main status --limit 50
```

**Output:**
- Table with all sessions showing:
  - Session ID
  - Repository
  - Issue number
  - Phase (scope/exec)
  - Status
  - Confidence score (for scoping sessions)
  - Creation time

Example: Showing a scoping session from a public repository, and an issue execution from a personal repository.

`python devin-issues status`

<img width="1988" height="406" alt="image" src="https://github.com/user-attachments/assets/f59b6546-34b7-4401-990e-8521b7b29e6c" />


---

### `version` - Show Version Information

```bash
python -m cli.main version
```

Shows CLI version and orchestrator URL.

---

## Complete Workflow Example

Here's a typical workflow for automating an issue:

```bash
# 1. Find an interesting issue
python devin-issues list user/user-repo --label type-bug -n 10

# Pick issue #12345 from the list

# 2. Scope the issue first
python devin-issues scope user/user-repo 12345

# Output shows:
# - Confidence: 🟢 85%
# - Risk: LOW
# - Estimated Effort: 3.5 hours
# - Implementation plan with 5 steps

# 3. If confidence is high, execute it (using scoped summary as aid if issue was scoped prior)
python devin-issues execute user/user-repo 12345

# Output shows:
# - Session URL to track Devin's progress
# - Devin will create a PR in 10-30 minutes

# 4. Check status later
python devin-issues status --repo user/user-repo

# Or check specific session:
python devin-issues status devin-abc123...
```


## Database

The tool automatically tracks all operations in `devin_cli.db` (SQLite):

**Tables:**
- `issues` - GitHub issues with confidence scores and execution results
- `devin_sessions` - All Devin sessions (scope + exec) with metadata
- `events` - Audit log of all operations

**View database:**
```bash
sqlite3 devin_cli.db

# In SQLite shell, some example commands:
.tables
SELECT * FROM issues;
SELECT * FROM devin_sessions ORDER BY created_at DESC LIMIT 10;
SELECT * FROM events ORDER BY created_at DESC LIMIT 20;
.quit
```

## Configuration

All configuration is in the `.env` file:

```bash
# GitHub API
GITHUB_TOKEN=ghp_your_token_here

# Devin API
DEVIN_API_KEY=your_key_here
DEVIN_API_URL=https://api.devin.ai/v1

# Backend Settings
ORCHESTRATOR_HOST=0.0.0.0
ORCHESTRATOR_PORT=8000

# Database
DATABASE_URL=sqlite:///./devin_cli.db

# Polling Configuration
DEVIN_POLL_INTERVAL=15        # Seconds between polls
DEVIN_POLL_TIMEOUT=1800       # Max wait time (30 minutes)
```


## High-level Overview of Data-Flow

```
1. You run a CLI command (e.g., scope python/cpython 12345)
   ↓
2. CLI sends HTTP request to FastAPI backend
   ↓
3. Backend fetches issue from GitHub API
   ↓
4. Backend creates Devin session with structured prompt
   ↓
5. Backend polls Devin API for completion
   ↓
6. Backend parses structured output (confidence, plan, etc.)
   ↓
7. Backend saves results to SQLite database
   ↓
8. Backend returns results to CLI
   ↓
9. CLI displays user-friendly, formatted output
```

### Structured Output

The tool uses Devin's structured output feature with simplified schemas:

**Scoping Output:**
```json
{
  "summary": "Add error handling to parser module",
  "plan": [
    "Identify error-prone code sections",
    "Add try-catch blocks",
    "Write unit tests",
    "Update error messages"
  ],
  "risk_level": "low",
  "estimated_effort": 2.5,
  "confidence": 0.85
}
```

**Execution Output:**
```json
{
  "status": "done",
  "branch": "fix-issue-12345-parser-errors",
  "pr_url": "https://github.com/owner/repo/pull/456",
  "tests_passed": 15,
  "tests_failed": 0
}
```


## Use Cases

### 1. Automated Bug Triage
```bash
# List all open bugs
python devin-issues list myorg/myrepo --label bug --state open

# Scope each one to get confidence scores
# Execute high-confidence ones automatically
```

### 2. Good First Issues for Contributors
```bash
# Find beginner-friendly issues
python devin-issues list myorg/myrepo --label "good first issue"

# Scope to verify they're actually beginner-friendly
# High-confidence simple issues are great for new contributors
```

### 3. Backlog Grooming
```bash
# Review old issues
python devin-issues list myorg/myrepo --state all

# Scope uncertain issues to understand effort
# Close or update based on confidence scores
```


### Clearing the Database

```bash
rm devin_cli.db
python -m app.database  # Recreate tables
```

### Author: Ryan Nguyen

---

