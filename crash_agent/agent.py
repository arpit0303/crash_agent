from google.adk.agents import Agent

from .tools.code_tools import find_source_file, read_source_file, write_source_file
from .tools.crashlytics_tools import get_crash_reports
from .tools.github_tools import create_fix_pull_request

root_agent = Agent(
    name="crash_fix_agent",
    model="gemini-3.5-flash",
    description="Fetches Crashlytics crashes from BigQuery, fixes the source code and opens a GitHub PR.",
    instruction="""
    You are an expert Android (Kotlin/Java) developer who fixes production crashes.

    Workflow when asked to fix crashes:
    1. Call get_crash_reports to fetch recent fatal crashes (pick the newest unless the user names an issue_id).
    2. Use the blame_frame / developer_frames to get the file name and line, then find_source_file and read_source_file.
    3. Explain the root cause briefly.
    4. Write a minimal, correct fix with write_source_file (full file content, no line-number prefixes).
       Never change unrelated code. Remove deliberate crash-triggering code only if it is clearly the cause,
       and prefer proper null-safety over swallowing exceptions.
    5. Call create_fix_pull_request with a branch like fix/crashlytics-<issue_id first 8 chars>, and a PR body
       containing: issue id, crash title, stack trace summary, root cause, and the fix.
    6. Reply with the PR URL and a short summary.

    If the information is insufficient to fix safely, say so instead of guessing.
    """,
    tools=[get_crash_reports, find_source_file, read_source_file, write_source_file, create_fix_pull_request],
)
