# modules/jira_clone_issue_operations.py
# Jira Cloud REST v3 implementation using JiraV3 only (no direct requests)

from __future__ import annotations

from datetime import datetime, timedelta
from collections import OrderedDict
from typing import Dict, List, Optional, Tuple, Union

import streamlit as st
from .jira_v3 import JiraV3  # expects (base_url, email, api_token)


# ------------------------------ Utilities ------------------------------

def _extract_issue_key(issue_like: Union[str, Dict, object]) -> Optional[str]:
    """
    Accepts a string key, an issue JSON dict, or an object with .key; returns the key string.
    """
    if isinstance(issue_like, str):
        return issue_like
    if isinstance(issue_like, dict):
        return issue_like.get("key")
    return getattr(issue_like, "key", None)


def _read_field(issue_json: Dict, fieldname: str):
    return issue_json.get("fields", {}).get(fieldname, None)


# ------------------------------ Public API ------------------------------

def update_project_name(client: JiraV3, project_issue_key: str, new_project_name: str) -> None:
    """
    Update issue summary (project issue's name).
    """
    if not new_project_name:
        return
    client.update_issue_fields(project_issue_key, {"summary": new_project_name})


def get_all_subtasks(client: JiraV3, issue: Union[str, Dict, object]) -> List[Dict]:
    """
    Return list of direct subtask issues (JSON dicts) ordered by created ASC.
    """
    key = _extract_issue_key(issue)
    if not key:
        raise ValueError("get_all_subtasks: invalid issue argument; expected key or JSON with 'key'.")
    return client.list_subtasks(key)


def compute_new_due_date(
    client: JiraV3,
    day_delta: Optional[int],
    issue: Union[str, Dict, object],
    fieldname: str,
) -> Optional[datetime.date]:
    """
    Compute a new date for 'duedate' or 'customfield_10015' (start date) by shifting the source value by day_delta.
    """
    if day_delta is None:
        st.error('You must provide a Project Start Date!')
        return None

    # Normalize to issue JSON
    if isinstance(issue, dict):
        issue_json = issue
    else:
        key = _extract_issue_key(issue)
        if not key:
            st.error("Cannot compute new date: invalid issue reference.")
            return None
        issue_json = client.get_issue(key, fields=[fieldname])

    date_str = _read_field(issue_json, fieldname)
    if not date_str:
        st.error('The Template Issue must have a start date and end date!')
        return None

    current_date = datetime.strptime(str(date_str)[:10], "%Y-%m-%d").date()
    return current_date + timedelta(days=day_delta)


def clone_issue_recursive_first_pass(
    client: JiraV3,
    issue: Union[str, Dict, object],
    target_project: str,
    parent: Optional[Union[str, Dict, object]] = None,
    cloned_issues: Optional[OrderedDict] = None,
    day_delta: int = 0,
    project_assignee: Optional[str] = None,  # accountId in GDPR strict mode
) -> Dict[str, str]:
    """
    Clone `issue` (and its subtasks) into `target_project` without links; store map {old_key: {"key": new_key}}.
    """
    if cloned_issues is None:
        cloned_issues = OrderedDict()

    # Normalize source
    src_key = _extract_issue_key(issue)
    if not src_key:
        raise ValueError("clone_issue_recursive_first_pass: cannot determine source issue key.")

    # avoid re-clone
    if src_key in cloned_issues:
        return cloned_issues[src_key]

    # Fetch source if needed
    if isinstance(issue, dict):
        src_issue = issue
        needed = {"summary", "description", "issuetype", "duedate", "customfield_10015", "created"}
        if not needed.issubset(set(src_issue.get("fields", {}).keys())):
            src_issue = client.get_issue(src_key, fields=list(needed))
    else:
        src_issue = client.get_issue(
            src_key,
            fields=["summary", "description", "issuetype", "duedate", "customfield_10015", "created"],
        )

    # Dates
    due_date_date = compute_new_due_date(client, day_delta, src_issue, "duedate")
    start_date_date = compute_new_due_date(client, day_delta, src_issue, "customfield_10015")
    due_date_str = due_date_date.strftime("%Y-%m-%d") if due_date_date else None
    start_date_str = start_date_date.strftime("%Y-%m-%d") if start_date_date else None

    # Build new fields
    issuetype_obj = _read_field(src_issue, "issuetype") or {}
    fields = {
        "project": {"key": target_project},
        "summary": _read_field(src_issue, "summary"),
        "description": _read_field(src_issue, "description"),
        "issuetype": {"name": issuetype_obj.get("name", "Task")},
    }
    if due_date_str:
        fields["duedate"] = due_date_str
    if start_date_str:
        fields["customfield_10015"] = start_date_str

    if parent:
        parent_key = _extract_issue_key(parent)
        if parent_key:
            fields["parent"] = {"key": parent_key}

    # Create the issue
    try:
        created = client.create_issue(fields)
        new_key = created["key"]
        if project_assignee:
            try:
                client.assign_issue(new_key, project_assignee)  # accountId only
            except Exception as e:
                st.warning(f"Assignee update failed for {new_key}: {e}")

        st.write(f"Created new issue: {new_key}")
    except Exception as e:
        st.error(f"Error creating issue: {str(e)}")
        return {}

    # record mapping
    cloned_issues[src_key] = {"key": new_key}

    # Clone children (ordered)
    for child in get_all_subtasks(client, src_key):
        clone_issue_recursive_first_pass(
            client,
            child,
            target_project,
            parent={"key": new_key},
            cloned_issues=cloned_issues,
            day_delta=day_delta,
            project_assignee=project_assignee,
        )

    return {"key": new_key}


def add_issue_links(client: JiraV3, cloned_issues: Dict[str, Dict[str, str]]) -> None:
    """
    Recreate issuelinks between cloned issues based on source links.
    """
    created_links: set[Tuple[str, str, str]] = set()  # (from_key, type_name, to_key)

    for original_key, cloned in cloned_issues.items():
        cloned_key = cloned.get("key")
        if not cloned_key:
            continue

        for link in client.get_issue_links(original_key):
            link_type = (link.get("type") or {}).get("name")
            if not link_type:
                continue

            outward = link.get("outwardIssue")
            inward = link.get("inwardIssue")

            # original -> outward
            if outward and outward.get("key") in cloned_issues:
                cloned_out = cloned_issues[outward["key"]]["key"]
                ident = (cloned_key, link_type, cloned_out)
                if ident not in created_links:
                    try:
                        client.create_issue_link(link_type, inward_key=cloned_key, outward_key=cloned_out)
                        st.write(f"Created link '{link_type}' between {cloned_key} → {cloned_out}")
                        created_links.add(ident)
                    except Exception as e:
                        st.error(f"Error linking {cloned_key} → {cloned_out}: {e}")

            # inward -> original
            if inward and inward.get("key") in cloned_issues:
                cloned_in = cloned_issues[inward["key"]]["key"]
                ident = (cloned_in, link_type, cloned_key)
                if ident not in created_links:
                    try:
                        client.create_issue_link(link_type, inward_key=cloned_in, outward_key=cloned_key)
                        st.write(f"Created link '{link_type}' between {cloned_in} → {cloned_key}")
                        created_links.add(ident)
                    except Exception as e:
                        st.error(f"Error linking {cloned_in} → {cloned_key}: {e}")


def get_linked_issues(client: JiraV3, issue: Union[str, Dict, object]) -> List[Tuple[str, Dict]]:
    """
    Return a list of tuples: (link_type_name, linked_issue_stub_dict) for both inward and outward links.
    """
    key = _extract_issue_key(issue)
    if not key:
        return []

    out: List[Tuple[str, Dict]] = []
    for link in client.get_issue_links(key):
        type_name = (link.get("type") or {}).get("name")
        if not type_name:
            continue
        if link.get("outwardIssue"):
            out.append((type_name, link["outwardIssue"]))
        if link.get("inwardIssue"):
            out.append((type_name, link["inwardIssue"]))
    return out


def get_time_delta(client: JiraV3, project_start_date, issue: Union[str, Dict, object]) -> Optional[int]:
    """
    Compute day delta between chosen project_start_date and the template's start date (customfield_10015).
    """
    if not project_start_date:
        st.error('You must provide a project Start Date! (YYYY-MM-DD)')
        return None

    key = _extract_issue_key(issue)
    if not key:
        st.error("Invalid issue provided to get_time_delta")
        return None

    data = client.get_issue(key, fields=["customfield_10015"])
    start_str = data.get("fields", {}).get("customfield_10015")
    if not start_str:
        st.error("Template issue must have a Start Date (customfield_10015).")
        return None

    original_start = datetime.strptime(str(start_str)[:10], "%Y-%m-%d").date()
    return (project_start_date - original_start).days
