from jira import JIRA
from config import JIRA_URL, JIRA_TOKEN
from threading import Lock
from requests.exceptions import RequestException

# -----------------------------
# Global state (lazy init)
# -----------------------------
_jira_client = None
_lock = Lock()


def get_client():
    """
    Lazy initialization for Jira client.
    Prevents crash on import time and supports thread-safe init.
    """

    global _jira_client

    if _jira_client is None:
        with _lock:
            if _jira_client is None:
                _jira_client = JIRA(
                    server=JIRA_URL,
                    token_auth=JIRA_TOKEN,
                    timeout=5
                )

    return _jira_client


# -----------------------------
# Health check
# -----------------------------
def jira_health_check() -> bool:
    """
    Lightweight check to verify Jira connectivity + auth.
    """
    try:
        client = get_client()
        client.myself()   # lightweight API call
        return True

    except Exception:
        return False


# -----------------------------
# Add comment
# -----------------------------
def add_comment(issue_key: str, comment: str):
    try:
        client = get_client()
        client.add_comment(issue_key, comment)

    except RequestException as e:
        raise Exception(f"Failed to add comment: {str(e)}")


# -----------------------------
# Transition issue
# -----------------------------
def transition_issue(issue_key: str, transition_name: str):
    client = get_client()

    issue = client.issue(issue_key)
    transitions = client.transitions(issue)

    transition_id = None

    for t in transitions:
        if t.get("name") == transition_name:
            transition_id = t.get("id")
            break

    if not transition_id:
        raise Exception(f"Transition '{transition_name}' not found")

    try:
        client.transition_issue(issue, transition_id)

    except RequestException as e:
        raise Exception(f"Failed to transition issue: {str(e)}")