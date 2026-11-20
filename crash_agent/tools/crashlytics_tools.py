import os
from google.cloud import bigquery

TABLE = os.getenv("CRASHLYTICS_TABLE", "zetwerk-a5d1d.firebase_crashlytics.com_example_crash_fix_ai_ANDROID")


def get_crash_reports(limit: int = 5) -> list[dict]:
    """Fetch the most recent distinct fatal crash issues from Firebase Crashlytics (BigQuery).

    Args:
        limit: Maximum number of distinct issues to return.

    Returns:
        A list of crashes, each with issue_id, title, subtitle, event_timestamp, the blamed
        frame (file, line, symbol) and the developer-owned stack frames of the root exception.
    """
    client = bigquery.Client(project=os.getenv("GCP_PROJECT_ID"))
    query = f"""
        SELECT * EXCEPT(rn) FROM (
          SELECT issue_id, issue_title, issue_subtitle, error_type, event_timestamp,
                 application.display_version AS app_version, blame_frame, exceptions,
                 ROW_NUMBER() OVER (PARTITION BY issue_id ORDER BY event_timestamp DESC) AS rn
          FROM `{TABLE}`
          WHERE is_fatal
        )
        WHERE rn = 1
        ORDER BY event_timestamp DESC
        LIMIT @limit
    """
    job = client.query(query, job_config=bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("limit", "INT64", limit)]))
    crashes = []
    for row in job.result():
        exceptions = [
            {
                "type": e["type"],
                "message": e["exception_message"],
                "caused_by": e["nested"],
                "developer_frames": [
                    {"file": f["file"], "line": f["line"], "symbol": f["symbol"]}
                    for f in e["frames"] if f["owner"] == "DEVELOPER"
                ],
            }
            for e in row["exceptions"]
        ]
        bf = row["blame_frame"]
        crashes.append({
            "issue_id": row["issue_id"],
            "title": row["issue_title"],
            "subtitle": row["issue_subtitle"],
            "error_type": row["error_type"],
            "event_timestamp": row["event_timestamp"].isoformat(),
            "app_version": row["app_version"],
            "blame_frame": {"file": bf["file"], "line": bf["line"], "symbol": bf["symbol"]} if bf else None,
            "exceptions": exceptions,
        })
    return crashes
