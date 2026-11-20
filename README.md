# Crash Fix AI

An AI agent (built with [Google ADK](https://google.github.io/adk-docs/) and Gemini) that automatically fixes production Android crashes:

1. Fetches recent fatal crashes from **Firebase Crashlytics** (exported to **BigQuery**).
2. Locates and reads the offending source file in the target Android repo.
3. Writes a minimal fix.
4. Commits to a new branch, pushes, and opens a **GitHub Pull Request** (via a GitHub App).

## Project structure

```
crash-fix-ai/
├── .env                      # Environment configuration (do not commit)
├── secrets/                  # GitHub App private key (do not commit)
└── crash_agent/
    ├── agent.py              # root_agent definition (model, instructions, tools)
    ├── tools/
    │   ├── crashlytics_tools.py  # get_crash_reports (BigQuery)
    │   ├── code_tools.py         # find/read/write source files in target repo
    │   └── github_tools.py       # branch, commit, push, open PR
    └── repositories/
        └── Crash-Fix-AI/     # Clone of the target Android repo (default)
```

## Prerequisites

- Python 3.10+
- A Google Cloud project with Firebase Crashlytics -> BigQuery export enabled
- A Gemini API key (Google AI Studio) or Vertex AI access
- A GitHub App installed on the target Android repository
- `git` installed locally

## Setup

### 1. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install google-adk google-cloud-bigquery PyGithub PyJWT cryptography requests
```

### 2. Clone the target Android repo

The agent edits code in `crash_agent/repositories/Crash-Fix-AI` by default. Clone your Android app there, with `origin` pointing at GitHub:

```bash
git clone https://github.com/<owner>/<repo>.git crash_agent/repositories/Crash-Fix-AI
```

To use another location, set `TARGET_REPO_DIR`.

### 3. Firebase Crashlytics -> BigQuery integration

1. In the Firebase console go to **Project settings -> Integrations -> BigQuery** and enable Crashlytics export.
2. Wait for the dataset (`firebase_crashlytics`) and table (e.g. `com_example_crash_fix_ai_ANDROID`) to be created.
3. Create a Google Cloud **service account** with the roles:
   - `BigQuery Job User` (project level)
   - `BigQuery Data Viewer` (on the `firebase_crashlytics` dataset)
4. Create a JSON key for it, store it locally (outside git) and point `GOOGLE_APPLICATION_CREDENTIALS` at it.
5. If your table name differs from the default, set `CRASHLYTICS_TABLE` as `<project>.<dataset>.<table>`.

### 4. Gemini model integration

The agent uses the model configured in `crash_agent/agent.py`.

- **Google AI Studio:** set `GOOGLE_API_KEY` and leave `GOOGLE_GENAI_USE_ENTERPRISE`/`GOOGLE_GENAI_USE_VERTEXAI` as `FALSE`.
- **Vertex AI:** set the flag to `TRUE`, and also set `GOOGLE_CLOUD_PROJECT` and `GOOGLE_CLOUD_LOCATION`; credentials come from `GOOGLE_APPLICATION_CREDENTIALS`.

### 5. GitHub App integration (push + PR)

1. GitHub -> **Settings -> Developer settings -> GitHub Apps -> New GitHub App**.
2. Repository permissions: **Contents: Read & write**, **Pull requests: Read & write**, **Metadata: Read**.
3. Generate a **private key** (`.pem`) and save it to `secrets/github-private-key.pem`.
4. Note the **App ID**.
5. **Install** the app on the target repository.
6. Optionally note the **Installation ID** (otherwise it is looked up automatically from `GITHUB_REPO`).

Fallback: set `GITHUB_TOKEN` to a personal access token with `repo` scope instead of the App variables.

### 6. Configure `.env`

Create `.env` in the project root (and in `crash_agent/` if running `adk` from there):

```env
GOOGLE_GENAI_USE_ENTERPRISE=FALSE
GOOGLE_API_KEY=<gemini-api-key>
GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/service-account.json
GCP_PROJECT_ID=<gcp-project-id>

# GitHub App auth
GITHUB_REPO=<owner>/<repo>
GITHUB_APP_ID=<app-id>
GITHUB_APP_PRIVATE_KEY_PATH=secrets/github-private-key.pem
# GITHUB_APP_INSTALLATION_ID=<installation-id>
# GITHUB_TOKEN=<personal-access-token>

# Optional
# CRASHLYTICS_TABLE=<project>.<dataset>.<table>
# TARGET_REPO_DIR=/path/to/android/repo
```

| Variable | Required | Purpose |
|---|---|---|
| `GOOGLE_API_KEY` | Yes (AI Studio) | Gemini access |
| `GOOGLE_GENAI_USE_ENTERPRISE` | Yes | Selects Vertex/enterprise vs API key mode |
| `GOOGLE_APPLICATION_CREDENTIALS` | Yes | Service account JSON for BigQuery |
| `GCP_PROJECT_ID` | Yes | Project used to run BigQuery jobs |
| `GITHUB_REPO` | Recommended | `owner/repo`; otherwise derived from `origin` remote |
| `GITHUB_APP_ID` | Yes* | GitHub App ID |
| `GITHUB_APP_PRIVATE_KEY_PATH` | Yes* | Path to App private key |
| `GITHUB_APP_INSTALLATION_ID` | No | Skips installation lookup |
| `GITHUB_TOKEN` | Yes* | Fallback if App vars are unset |
| `CRASHLYTICS_TABLE` | No | Override BigQuery table |
| `TARGET_REPO_DIR` | No | Override target repo path |

\* Either the GitHub App variables or `GITHUB_TOKEN`.

## Running

From the project root:

```bash
source .venv/bin/activate
adk web      # browser UI; select "crash_agent"
# or
adk run crash_agent
```

Then prompt, e.g.: `Fix the latest crash`, or `Fix issue <issue_id>`.

## Agent tools

| Tool | Description |
|---|---|
| `get_crash_reports(limit)` | Queries BigQuery for the latest distinct fatal issues (blame frame, developer frames, exceptions) |
| `find_source_file(file_name)` | Finds files by name in the target repo |
| `read_source_file(path)` | Reads a file with line numbers |
| `write_source_file(path, content)` | Overwrites `.kt/.java/.kts/.xml` files; returns a git diff |
| `create_fix_pull_request(...)` | Creates branch, commits `app/src` changes, pushes, opens PR, returns URL |

## Safety notes

- File edits are restricted to the target repo and to `.kt`, `.java`, `.kts`, `.xml`; `build`, `.git`, `.gradle`, `.idea` are blocked.
- Only changes under `app/src` are committed.
- Commits are authored as `Crash Fix AI`; the PR base is the repo's currently checked-out branch, and the agent returns to it afterward.
- Never commit `.env`, service-account JSON, or `.pem` files. Add them to `.gitignore` and rotate any that were exposed.

## Troubleshooting

- **`Set GITHUB_APP_ID + GITHUB_APP_PRIVATE_KEY_PATH (or GITHUB_TOKEN)`**: GitHub credentials missing in `.env`.
- **404 on installation lookup**: the App isn't installed on `GITHUB_REPO`.
- **BigQuery 403 / table not found**: check service account roles, `GCP_PROJECT_ID`, and `CRASHLYTICS_TABLE`.
- **"No changes to commit"**: the agent made no edits under `app/src`.
