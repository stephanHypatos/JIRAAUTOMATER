from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple, Iterable
from collections import OrderedDict
import pandas as pd
import streamlit as st
import math
import requests
from datetime import datetime,timedelta
from pptx import Presentation
from pptx.util import Inches
from modules.config import JIRA_ACCOUNT_ISSUE_TYPE,JIRA_PROJECT_ISSUE_TYPE,JIRA_EPIC_ISSUE_TYPE, JIRA_TASK_ISSUE_TYPE, JIRA_SUBTASK_ISSUE_TYPE,JIRA_URL,EXCEL_FILE_PATH,EXCEL_FILE_PATH_BLUE_PRINT_PILOT,EXCEL_FILE_PATH_BLUE_PRINT_ROLLOUT,EXCEL_FILE_PATH_BLUE_PRINT_POC,EXCEL_FILE_PATH_BLUE_PRINT_TEST,EXCEL_FILE_PATH_BLUE_PRINT_ROLLOUT_WIL,JIRA_TEMPLATE_BOARD_KEY,EXCLUDED_BOARD_KEYS
from modules.utils import normalize_NaN, normalize_date, calculate_end_date
from .jira_v3 import JiraV3


class JiraOperations:
    def __init__(self, jira_instance: JiraV3):
        self.jira = jira_instance

    def get_all_projects(self) -> List[Dict[str, Any]]:
        """Get all projects from Jira"""
        return self.jira.project_search_all()

    def get_project_issues(self, project_key: str) -> List[Dict[str, Any]]:
        """Get all issues for a specific project"""
        jql = f'project = "{project_key}"'
        return self.jira.search_jql_all(jql, fields=["summary", "description", "issuetype", "priority"])

    def get_issue_details(self, issue_key: str) -> Dict[str, Any]:
        """Get details for a specific issue"""
        jql = f'issue = "{issue_key}"'
        results = self.jira.search_jql(jql, fields=["*all"])
        if results.get("issues"):
            return results["issues"][0]
        return {}

## generice Jira Auth Function that returns a new instance of JIRA
def authenticate(jira_url,jira_email,jira_api_token):
    
    jira = JIRA(jira_url,basic_auth=(jira_email, jira_api_token))
    return jira

# JIRA Credentials Handling

# Function to store credentials in session state
def save_credentials(username, password):
    if username and password:
        st.session_state['api_username'] = username
        st.session_state['api_password'] = password
        st.success("Credentials stored successfully!")
    else:
        st.warning('Provide Jira Credentials')


# JIRA Project relelated Functions

def get_project_keys(jira_url: str, username: str, password: str) -> List[str]:
    """
    Return a list of business (company-managed) project keys, excluding certain predefined keys.
    Adds a blank "" entry at the start for selectbox compatibility.
    Replaces python-jira .projects() with /rest/api/3/project/search.
    """
    client = JiraV3(jira_url, username, password)
    projects = client.project_search_all()

    excluded_keys = {
        "BXIMH","DFM","SE","ROP","OKR","FIPR","REQMAN","MBZ","T3S","SKK",
        "PMO","TESTC","DUR","PS","PE","TESTB","KATE","MDG","TESTA","UGI",
        "TESTD","TOH","MON","DBFM","CUSOPS"
    }

    # Filter for company-managed ("business") projects and exclude unwanted keys
    company_managed = [
        p["key"] for p in projects
        if p.get("projectTypeKey") == "business" and p.get("key") not in excluded_keys
    ]

    select_options = [""]
    select_options.extend(sorted(company_managed))  # optional sort for stable UI

    return select_options

def get_jira_issue_type_project_key_with_displayname(
    client: JiraV3,
    project_key: str,
    issue_type_name: str = "Project",
    limit: int = 50,
) -> List[Dict[str, str]]:
    """
    Return [{'key','summary'}] for issues of a given issuetype inside the given project.
    Uses /rest/api/3/search/jql (param name is 'jql').
    """
    jql = f'project = "{project_key}" AND issuetype = "{issue_type_name}" ORDER BY created DESC'
    data = client.search_jql(jql, fields=["summary"], max_results=limit)
    issues = data.get("issues", []) or []
    return [{"key": i["key"], "summary": i.get("fields", {}).get("summary", "")} for i in issues if i.get("key")]


def get_template_projects(client: JiraV3, key_prefix: str) -> List[Dict[str, str]]:
    """
    Fetches a list of Jira projects whose keys start with the specified prefix.

    #Args:
        client (JiraV3): An instance of the JiraV3 client used to interact with the Jira API.
        key_prefix (str): The prefix to filter project keys by (case-insensitive).

    Returns:
        List[Dict[str, str]]: A list of dictionaries, each containing the 'key' and 'name' of a matching project.
    
    Return [{'key','name'}] for projects whose key starts with key_prefix.
    """
    projects = client.project_search_all(query=key_prefix, limit=200)
    return [
        {"key": p["key"], "name": p["name"]}
        for p in projects
        if p.get("key","").upper().startswith(key_prefix.upper())
    ]

def project_has_issue_type(client: JiraV3, project_key: str, issue_type_name: str) -> bool:
    """
    Checks if a given Jira project contains at least one issue of a specified issue type.

    Args:
        client (JiraV3): An instance of the JiraV3 client used to interact with the Jira API.
        project_key (str): The key of the Jira project to search within.
        issue_type_name (str): The name of the issue type to check for.

    Returns:
        bool: True if the project contains at least one issue of the specified issue type, False otherwise.
    """
    jql = f'project = "{project_key}" AND issuetype = "{issue_type_name}"'
    data = client.search_jql(jql, fields=["issuetype"], max_results=1)
    return len(data.get("issues", [])) > 0

def update_parent_key(client: JiraV3, issue_key: str, new_parent_key: str) -> None:
    """
    Set/replace the parent of an issue using Jira Cloud REST v3.
    Works for issue types that support a parent (e.g., subtasks, issues under an Epic/Portfolio parent).
    Tries by key first; if Jira complains, falls back to using the parent's numeric id.
    """
    if not (issue_key and new_parent_key):
        st.error("update_parent_key: issue_key and new_parent_key are required.")
        return

    # 1) Try with the parent KEY (most tenants accept this)
    try:
        client.update_issue_fields(issue_key, {"parent": {"key": new_parent_key}})
        st.write(f"Parent key of issue {issue_key} updated to {new_parent_key}")
        return
    except Exception as e_key:
        # 2) Fallback: resolve parent's numeric ID and try with {"id": ...}
        try:
            parent_json = client.get_issue(new_parent_key, fields=["id"])
            parent_id = parent_json.get("id")
            if not parent_id:
                raise RuntimeError("Could not resolve parent id from key.")
            client.update_issue_fields(issue_key, {"parent": {"id": parent_id}})
            st.write(f"Parent of issue {issue_key} updated to {new_parent_key} (via id {parent_id}).")
            return
        except Exception as e_id:
            st.error(
                "Unable to update parent. "
                "This can also happen if the issue type cannot have a parent in your scheme "
                "(e.g., trying to parent a standard issue under another standard issue)."
            )
            # surface both errors for debugging
            st.exception(e_key)
            st.exception(e_id)

# Function to store jira project key in session state
def save_jira_project_key(project_key: str) -> None:
    st.session_state["jira_project_key"] = project_key

# Function to store jira project type in session state ( ROLLOUT, POC, PILOT)
def save_jira_project_type(projecttype): 
    st.session_state['jira_project_type'] = projecttype

# Function to store JQL in session state
def save_jql(jql):
    st.session_state['jira_query'] = jql

# Function to get Jira Project Key from session state   
def get_jira_project_key():
    return st.session_state['jira_project_key']



# Function to store the selected Account Parent Issue in session state
def save_jira_account_type_parent(parent):
    st.session_state['jira_issue_type_account'] = parent

# Function to store the selected Project Issue in session state
def save_jira_issue_type_project(project):
    st.session_state['jira_issue_type_project'] = project

# Function retunrns a GLOBAL FILEPATH to Blueprintfile
def get_blue_print_filepath(sessionStateProjectType):
    filepath=None
    if sessionStateProjectType == 'POC':
        filepath=EXCEL_FILE_PATH_BLUE_PRINT_POC
    if sessionStateProjectType == 'PILOT':
        filepath=EXCEL_FILE_PATH_BLUE_PRINT_PILOT
    if sessionStateProjectType == 'ROLLOUT':
        filepath=EXCEL_FILE_PATH_BLUE_PRINT_ROLLOUT
    if sessionStateProjectType == 'ROLLOUT_WIL':
        filepath=EXCEL_FILE_PATH_BLUE_PRINT_ROLLOUT_WIL
    if sessionStateProjectType == 'TEST':
        filepath=EXCEL_FILE_PATH_BLUE_PRINT_TEST
    
    return filepath



def get_jira_issue_type_account_key(base_url: str, email: str, token: str, issue_type_name: str = "Account", limit: int = 100) -> List[str]:
    """
    Return issue keys for the 'Account' issue type within the CURRENT target project
    (read from st.session_state['jira_project_key']), using /rest/api/3/search/jql.
    """
    client = JiraV3(base_url, email, token)

    project_key = st.session_state.get("jira_project_key")
    if not project_key:
        st.error("Target project key is not set. Please select a target board first.")
        return []

    jql = f'project = "{project_key}" AND issuetype = "{issue_type_name}" ORDER BY created DESC'
    data = client.search_jql(jql, fields=["summary"], max_results=limit)
    issues = data.get("issues", []) or []
    return [i["key"] for i in issues if i.get("key")]


def display_issue_summaries(issue_list: List[Dict]) -> Optional[str]:
    """
    Render a selectbox of issues and return the selected issue KEY.
    Accepts a list of dicts like {"key": "ABC-123", "summary": "Some title"}.
    Handles empty lists, missing fields, and duplicate summaries.
    """
    if not issue_list:
        st.warning("No 'Project' issues found for this board.")
        return None

    # Normalize and guard missing fields
    cleaned = [
        {
            "key": item.get("key") or "",
            "summary": (item.get("summary") or "").strip() or "(no summary)",
        }
        for item in issue_list
        if item and isinstance(item, dict)
    ]

    # Build stable choice objects so we don’t rely on summary equality
    choices = [
        {
            "key": it["key"],
            "label": f'{it["key"]} · {it["summary"]}',
        }
        for it in cleaned
        if it["key"]  # skip entries without a key
    ]

    if not choices:
        st.warning("No selectable issues available.")
        return None

    # Default to first item
    selected_obj = st.selectbox(
        "Select source Project issue:",
        choices,
        index=0,
        format_func=lambda o: o["label"],
    )

    return selected_obj["key"] if selected_obj else None


# get all child issues of a jira issue
def get_children_issues(jira, issue_key):
    issue = jira.issue(issue_key)
    # List to store children issues
    children_issues = []
    
    #Helper function to find issues linked to the given issue
    def get_linked_issues(issue_key):
        jql = f'"parent" = {issue_key}'
        return jira.search_issues(jql)

    linked_issues=get_linked_issues(issue_key)
    # Add linked issues to the list "children_issues"
    if linked_issues:
        for linked_issue in linked_issues:
            if linked_issue.fields.issuetype.name.lower() == 'epic':
                linked_issues_tasks=get_linked_issues(linked_issue)
                for linked_issues_task in linked_issues_tasks:
                    children_issues.append(linked_issues_task.key)
            children_issues.append(linked_issue.key)
        return children_issues
    return

def update_parent_issue_type_project(
    client: JiraV3,
    current_project_issue_key: str,
    new_project_issue_key: str,
) -> None:
    """
    Re-parent all issues that currently have `current_project_issue_key` as their parent,
    so they point to `new_project_issue_key` instead. Jira Cloud REST v3.
    """
    if not (current_project_issue_key and new_project_issue_key):
        st.error("update_parent_issue_type_project: both current and new project issue keys are required.")
        return

    # Bounded JQL (v3): use quotes around keys
    jql = f'parent = "{current_project_issue_key}" ORDER BY created ASC'
    try:
        # Use the built-in pager to get all children
        children: List[Dict] = client.search_jql_all(jql, fields=["key"])
    except Exception as e:
        st.error(f"Failed to search children with JQL '{jql}': {e}")
        return

    if not children:
        st.info(f"No children found under parent {current_project_issue_key}.")
        return

    # Try updating by parent key; if Jira complains, fall back to parent id
    parent_id = None
    try:
        client.update_issue_fields(children[0]["key"], {"parent": {"key": new_project_issue_key}})
        by_key_supported = True
    except Exception:
        by_key_supported = False
        try:
            p = client.get_issue(new_project_issue_key, fields=["id"])
            parent_id = p.get("id")
        except Exception as e:
            st.error(f"Cannot resolve new parent id for {new_project_issue_key}: {e}")
            return

    updated = 0
    for c in children:
        child_key = c.get("key")
        if not child_key:
            continue
        try:
            if by_key_supported:
                client.update_issue_fields(child_key, {"parent": {"key": new_project_issue_key}})
            else:
                client.update_issue_fields(child_key, {"parent": {"id": parent_id}})
            updated += 1
        except Exception as e:
            st.warning(f"Failed to re-parent {child_key}: {e}")

    st.success(f"Re-parented {updated} issue(s) to {new_project_issue_key}.")

def delete_newly_created_project(client: JiraV3, issue_key: str) -> None:
    """
    DELETE /rest/api/3/issue/{issueKey}?deleteSubtasks=true
    Removes the newly created project-issue (and its subtasks).
    """
    if not issue_key:
        st.warning("delete_newly_created_project: issue_key is required.")
        return

    url = f"{client.base_url}/rest/api/3/issue/{issue_key}"
    try:
        r = requests.delete(url, headers=client._auth_header, params={"deleteSubtasks": "true"}, timeout=client.timeout)
        if r.status_code in (200, 204):
            st.info(f"Issue {issue_key} deleted.")
        else:
            st.warning(f"Could not delete {issue_key}: {r.status_code} {r.text}")
    except Exception as e:
        st.warning(f"Could not delete newly created issue type project {issue_key}: {e}")


# get all child issues of a jira issue
def get_children_issues_ticket_template(jira, issue_key):
    issue = jira.issue(issue_key)
    # List to store children issues
    children_issues = []
    
    #Helper function to find issues linked to the given issue
    def get_linked_issues(issue_key):
        jql = f'"parent" = {issue_key}'
        return jira.search_issues(jql)
    linked_issues=get_linked_issues(issue_key)
    # Add linked issues to the list "children_issues"
    if linked_issues:
        for linked_issue in linked_issues:
            if linked_issue.fields.issuetype.name.lower() == 'epic':
                # children_issues.append(
                # {'key': linked_issue.key,
                # 'summary': linked_issue.fields.summary,
                # 'issuetype': linked_issue.fields.issuetype.name})
                linked_issues_tasks=get_linked_issues(linked_issue)
                for linked_issues_task in linked_issues_tasks:
                    children_issues.append(
                    {'key': linked_issues_task.key,
                    'summary': linked_issues_task.fields.summary,
                    'issuetype': linked_issues_task.fields.issuetype.name})
            # children_issues.append(
            #         {'key': linked_issues_task.key,
            #         'summary': linked_issues_task.fields.summary,
            #         'issuetype': linked_issues_task.fields.issuetype.name})
        return children_issues
    return []

             

def get_children_issues_for_timeline(jira, issue_key):
    issue = jira.issue(issue_key)
    # List to store children issues
    children_issues = []
    
    #Helper function to find issues linked to the given issue
    def get_linked_issues(issue_key):
        jql = f'"parent" = {issue_key}'
        return jira.search_issues(jql)

    linked_issues=get_linked_issues(issue_key)
    # Add linked issues to the list "children_issues"
    if linked_issues:
        for linked_issue in linked_issues:
            if linked_issue.fields.issuetype.name.lower() == 'epic':
                linked_issues_tasks=get_linked_issues(linked_issue)
                for linked_issues_task in linked_issues_tasks:
                    if linked_issues_task.fields.issuetype.name.lower() == 'task':
                        linked_issues_subtasks=get_linked_issues(linked_issues_task)
                        for linked_issues_subtask in linked_issues_subtasks:
                            children_issues.append(linked_issues_subtask.key)        
                    children_issues.append(linked_issues_task.key)
            children_issues.append(linked_issue.key)
        return children_issues
    return


def _option_value(val: Any) -> Optional[str]:
    """
    Normalize Jira option-like values to a plain string.
    Handles:
      - dicts with {"value": "..."}
      - python-jira style objects with .value
      - lists of either (joined by ", ")
      - plain strings / None
    """
    if val is None:
        return None
    if isinstance(val, list):
        parts = []
        for v in val:
            if isinstance(v, dict) and "value" in v:
                parts.append(str(v["value"]))
            elif hasattr(v, "value"):
                parts.append(str(v.value))
            else:
                parts.append(str(v))
        return ", ".join(parts) if parts else None
    if isinstance(val, dict) and "value" in val:
        return str(val["value"])
    if hasattr(val, "value"):
        return str(val.value)
    return str(val)


def create_report_dataframe(client: JiraV3, issuekey: str) -> pd.DataFrame:
    """
    Fetch all child issues for a given parent issue (issuekey) via Jira Cloud REST v3,
    and return a DataFrame with the fields used by the report.

    Columns: Id, Name, Due Date, Start Date, Status, Owner, Ext.Owner, Issue Type
    """
    # Collect children keys using the v3 helper
    jira_issues: List[str] = get_children_issues_for_report(client, issuekey)

    if not jira_issues:
        st.warning(f'The selected project: {issuekey} has no children issues. Choose another project.')
        return pd.DataFrame(columns=["Id", "Name", "Due Date", "Start Date", "Status", "Owner", "Ext.Owner", "Issue Type"])

    issue_data: List[Dict[str, Any]] = []

    # Fields we need in one call
    wanted_fields = [
        "summary",
        "issuetype",
        "duedate",
        "customfield_10015",   # Start Date
        "status",
        "assignee",
        "customfield_10127",   # Ext.Owner (adjust if different in your site)
    ]

    for key in jira_issues:
        try:
            issue = client.get_issue(key, fields=wanted_fields)
            f = issue.get("fields", {}) or {}

            name = f.get("summary")
            issuetype = (f.get("issuetype") or {}).get("name")
            duedate = f.get("duedate")
            start_date = f.get("customfield_10015")
            status = (f.get("status") or {}).get("name")
            assignee = f.get("assignee") or {}
            owner = assignee.get("displayName")
            ext_owner = _option_value(f.get("customfield_10127"))

            issue_data.append(
                {
                    "Id": key,
                    "Name": name,
                    "Due Date": duedate,
                    "Start Date": start_date,
                    "Status": status,
                    "Owner": owner,
                    "Ext.Owner": ext_owner,
                    "Issue Type": issuetype,
                }
            )
        except Exception as e:
            st.warning(f"Error fetching data for issue {key}: {e}")

    # Build DataFrame
    df = pd.DataFrame(issue_data, columns=["Id", "Name", "Due Date", "Start Date", "Status", "Owner", "Ext.Owner", "Issue Type"])

    # Normalize date columns (keep date only)
    if not df.empty:
        if "Due Date" in df.columns:
            df["Due Date"] = pd.to_datetime(df["Due Date"], errors="coerce").dt.date
        if "Start Date" in df.columns:
            df["Start Date"] = pd.to_datetime(df["Start Date"], errors="coerce").dt.date

    # Cache in session (if you rely on it elsewhere)
    st.session_state["df"] = df

    return df


def filter_dataframe(df, issue_type=None, statuses=None, days=None, owner_list=None,selected_rows=None):
    """
    Dynamically filters the DataFrame based on the provided conditions.

    Args:
    - df (DataFrame): The DataFrame to be filtered.
    - issue_type (list): List of issue types to filter by.
    - statuses (list): List of statuses to filter by.
    - days (int): Number of days from today to filter 'Due Date'.
    - owner_list (list): List of owners to filter by.
    - selected_rows list: List of ids a user has selected

    Returns:
    - filtered_df (DataFrame): The filtered DataFrame.
    """
    # Start with a filter that includes all rows
    filter_condition = pd.Series([True] * len(df))

    # Filter by issue type
    if issue_type:
        filter_condition &= df['Issue Type'].isin(issue_type)

    # Filter by statuses
    if statuses:
        filter_condition &= df['Status'].isin(statuses)

    # Filter by Due Date if 'days' is provided
    if days is not None and days > 0:
        today = datetime.now().date()
        date_from_today = today + timedelta(days=days)
        filter_condition &= (df['Due Date'].notna()) & (df['Due Date'] >= today) & (df['Due Date'] <= date_from_today)

    # Filter by owner list
    if owner_list:
        filter_condition &= df['Owner'].isin(owner_list)
    
    # Filter by Id selected by User
    if selected_rows:
        filter_condition &= df['Id'].isin(selected_rows)

    # Apply the filter to the DataFrame
    filtered_df = df[filter_condition]

    return filtered_df


def get_users_from_jira_project(client: JiraV3, project_key: str, max_results: int = 1000):
    """
    Return list of assignable users (accountId + displayName).
    """
    import requests
    url = f"{client.base_url}/rest/api/3/user/assignable/search"
    params = {"project": project_key, "maxResults": max_results}
    r = requests.get(url, headers=client._auth_header, params=params, timeout=client.timeout)
    r.raise_for_status()
    users = r.json() or []
    return [
        {
            "accountId": u.get("accountId"),
            "displayName": u.get("displayName"),
            "emailAddress": u.get("emailAddress", ""),
        }
        for u in users
        if u.get("accountId")
    ]



### fast fetching of all children issues of a given jira parent issue
def get_children_issues_for_report(client: JiraV3, issue_key: str) -> List[str]:
    """
    Fast fetching of all children issues for a given parent issue (Cloud v3).
    - Direct children: JQL parent = "<issue_key>"
    - If a child is an Epic, fetch its children: parent = "<epic_key>"
    - For standard issues (Task/Story/Bug/etc.), fetch subtasks: parent = "<issue_key>"
    Returns a flat list of keys (unique, order preserved).
    """
    if not issue_key:
        return []

    collected: "OrderedDict[str, None]" = OrderedDict()

    def _add_key(k: str):
        if k and k not in collected:
            collected[k] = None

    # 1) Direct children of the given parent
    jql_direct = f'parent = "{issue_key}" ORDER BY created ASC'
    direct_children: List[Dict] = client.search_jql_all(
        jql_direct,
        fields=["key", "issuetype", "subtasks"]
    )

    for child in direct_children:
        ckey = child.get("key")
        _add_key(ckey)

        itype = (child.get("fields", {}).get("issuetype") or {}).get("name", "").lower()

        # 2) If the child is an Epic, fetch all of its direct children (Cloud now uses parent=<EPIC>)
        if itype == "epic":
            jql_epic_children = f'parent = "{ckey}" ORDER BY created ASC'
            epic_children = client.search_jql_all(
                jql_epic_children,
                fields=["key", "issuetype", "subtasks"]
            )
            for ec in epic_children:
                eckey = ec.get("key")
                _add_key(eckey)

                # 3) For each epic child (usually Task/Story/Bug), fetch their subtasks
                jql_subtasks = f'parent = "{eckey}" ORDER BY created ASC'
                subtasks = client.search_jql_all(jql_subtasks, fields=["key"])
                for st in subtasks:
                    _add_key(st.get("key"))

        else:
            # 4) For non-epic children, pull their subtasks
            jql_subtasks = f'parent = "{ckey}" ORDER BY created ASC'
            subtasks = client.search_jql_all(jql_subtasks, fields=["key"])
            for st in subtasks:
                _add_key(st.get("key"))

    return list(collected.keys())

def delete_jira_issue(client: JiraV3, parent_issue_key: str) -> None:
    """
    Delete a Jira issue and all of its children (Cloud v3).
    Requires JiraV3.delete_issue(...).
    """
    if not parent_issue_key:
        return

    try:
        # 1) collect all children (epic children, tasks, subtasks)
        children: List[str] = get_children_issues_for_report(client, parent_issue_key) or []

        # 2) delete children first (reverse for safety)
        for key in reversed(children):
            try:
                client.delete_issue(key, delete_subtasks=True)
                st.write(f"Deleted child issue: {key}")
            except Exception as e:
                st.warning(f"Could not delete child issue {key}: {e}")

        # 3) delete the parent last
        try:
            client.delete_issue(parent_issue_key, delete_subtasks=True)
            st.write(f"Deleted parent issue: {parent_issue_key}")
        except Exception as e:
            st.warning(f"Could not delete parent issue {parent_issue_key}: {e}")

    except Exception as e:
        st.warning(f"Delete flow failed for {parent_issue_key}: {e}")

def create_jira_issue(summary, issue_type, start_date=None, due_date=None, parent_key=None, description_key=None):
    issue_dict = {
        'project': {'key': get_jira_project_key()},
        'summary': summary,
        'issuetype': {'name': issue_type}
    }
    
    if parent_key:
        issue_dict['parent'] = {'key': parent_key}

    if start_date:
        start_date_normalized = normalize_date(start_date)
        if start_date_normalized:
            issue_dict['customfield_10015'] = start_date_normalized

    if due_date:
        due_date_normalized = normalize_date(due_date)
        if due_date_normalized:
            issue_dict['duedate'] = due_date_normalized
    
    if description_key:
       issue_dict['description'] = description_key

    return issue_dict

def normalize_date(d: Optional[date]) -> Optional[str]:
    if not d:
        return None
    if isinstance(d, datetime):
        d = d.date()
    return d.strftime("%Y-%m-%d")

def create_jira_issue_ticket_template(
    board_key: str,
    summary: str,
    issue_type: str,
    start_date: Optional[date] = None,
    due_date: Optional[date] = None,
    parent_key: Optional[str] = None,
    description: Optional[str] = None,
) -> dict:
    """
    Build the v3 issue 'fields' payload for creating a ticket.
    Note: v3 expects 'project' to be an object: {'key': <PROJECT_KEY>}.
    Description can be a plain string; if you use ADF, pass the ADF dict instead.
    """
    fields: dict = {
        "project": {"key": board_key},       # v3 requires object with 'key'
        "summary": summary or "",
        "issuetype": {"name": issue_type},
        "description": description or "",    # keep as string unless you pass ADF
    }

    if parent_key:
        fields["parent"] = {"key": parent_key}

    start_date_normalized = normalize_date(start_date)
    if start_date_normalized:
        fields["customfield_10015"] = start_date_normalized

    due_date_normalized = normalize_date(due_date)
    if due_date_normalized:
        fields["duedate"] = due_date_normalized

    return fields

# Get the Jira Issue Key - ( search by using the summary)
def get_issue_key(jira, summary):
    # Find the issue key using the summary
    issues = jira.search_issues(f'project={get_jira_project_key()} AND summary~"{summary}"', maxResults=1)
    return issues[0].key if issues else None

# Add Links between Issues Blocking and Blocked
def add_issue_links(jira, excel_data):
    for index, row in excel_data.iterrows():
        issue_type = row['IssueType']
        link1_key = row.get('SummaryName')
        blocks = normalize_NaN(row.get('Blocks'))

        # Add issue links if link1 is provided
        if link1_key and blocks:
            link1_key_normalized = get_issue_key(jira, link1_key)
            if link1_key_normalized:
                # Split the blocks into a list of individual issue keys
                blocks_list = [block.strip() for block in blocks.split(',')]
                
                for block_key in blocks_list:
                    link2_key_normalized = get_issue_key(jira, block_key)
                    if link2_key_normalized:
                        jira.create_issue_link(
                            type="blocks",
                            inwardIssue=link1_key_normalized,
                            outwardIssue=link2_key_normalized
                        )
                    else:
                        st.write(f"Link2 issue '{block_key}' not found. Skipping link creation.")
            else:
                st.write(f"Link1 issue '{link1_key}' not found. Skipping link creation.")

def create_issues_from_excel(jira, excel_data,project_startdate):
    # Returns a List of Issues with start and enddates

    dates=compute_dates(excel_data, project_startdate)
    # Iterate through rows and create Jira issues and subtasks
    for index, row in excel_data.iterrows():
        summary = row['Summary']
        issue_type = row['IssueType']
        parent_key = row.get('Parent')
        start_date= None
        due_date= None
        # Get Start & End Dates 
        start_date = getIssueDate(dates,summary,date_type='start_date')#row.get('StartDate')
        due_date = getIssueDate(dates,summary,date_type='end_date')#row.get('StartDate')
        description = normalize_NaN(row.get('Description'))

        # Normalize the dates # can be deleted
        start_date_normalized = normalize_date(start_date) if start_date else None
        due_date_normalized = normalize_date(due_date) if due_date else None

        # Check if parent_key is NaN
        if isinstance(parent_key, float) and math.isnan(parent_key):
            parent_key = None  # Set to None if NaN

        ###### NEW START
        if issue_type == JIRA_ACCOUNT_ISSUE_TYPE:
            # Create only the Account issue
            if parent_key is not None:
                st.write("An Account can't have a parent. Skipping Account Issue creation.")
            else:
                
                issue_dict = create_jira_issue(summary, JIRA_ACCOUNT_ISSUE_TYPE, start_date, due_date, description_key=description)
                account_issue = jira.create_issue(fields=issue_dict)
                st.write(f"Created Jira Issue Type Account: {account_issue.key} - Summary: {account_issue.fields.summary}")    

        elif issue_type == JIRA_PROJECT_ISSUE_TYPE:
            # Check if the issue has a parent issue
            if parent_key is not None:
                # Find parent issue using summary
                parent_issue = jira.search_issues(f'project={get_jira_project_key()} AND summary~"{parent_key}"', maxResults=1)

                if parent_issue:
                    parent_key = parent_issue[0].key
                    issue_dict = create_jira_issue(summary, JIRA_PROJECT_ISSUE_TYPE, start_date, due_date, parent_key,description)
                    project_issue = jira.create_issue(fields=issue_dict)
                    st.write(f"Created Jira Issue Type Project: {project_issue.key} - Summary: {project_issue.fields.summary}, Linked to parent: {parent_key}")

                else:
                    st.write(f"Parent issue '{parent_key}' not found. Skipping task creation.")
            else:
                # Check if an Account Issue as parent was selected 
                if st.session_state['jira_issue_type_account'] and st.session_state['jira_issue_type_account'] != "No_Parent":
                    parent_key = st.session_state['jira_issue_type_account']
                    issue_dict = create_jira_issue(summary, JIRA_PROJECT_ISSUE_TYPE, start_date, due_date, parent_key,description)
                    project_issue = jira.create_issue(fields=issue_dict)
                    st.write(f"Created Jira Issue Type Project: {project_issue.key} - Summary: {project_issue.fields.summary}, Linked to parent: {parent_key}")
                else: 
                    # Create task on its own without adding an Issue Type "Account" to the Issue
                    issue_dict = create_jira_issue(summary, JIRA_PROJECT_ISSUE_TYPE, start_date, due_date, description_key=description)
                    project_issue = jira.create_issue(fields=issue_dict)
                    st.write(f"Created Jira Issue Type Project: {project_issue.key} - Summary: {project_issue.fields.summary}")

        elif issue_type == JIRA_EPIC_ISSUE_TYPE:
            # Check if the issue has a parent issue 
            if parent_key is not None:
                # Find parent issue using summary
                parent_issue = jira.search_issues(f'project={get_jira_project_key()} AND summary~"{parent_key}"', maxResults=1)

                if parent_issue:
                    parent_key = parent_issue[0].key
                    issue_dict = create_jira_issue(summary, JIRA_EPIC_ISSUE_TYPE, start_date_normalized, due_date_normalized, parent_key,description)
                    epic_issue = jira.create_issue(fields=issue_dict)
                    st.write(f"Created Jira Issue Type Epic: {epic_issue.key} - Summary: {epic_issue.fields.summary}, Linked to parent: {parent_key}")

                else:
                    st.write(f"Parent issue '{parent_key}' not found. Skipping task creation.")
            else:
                # Create task on its own
                issue_dict = create_jira_issue(summary, JIRA_EPIC_ISSUE_TYPE, start_date_normalized, due_date_normalized, description_key=description)
                epic_issue = jira.create_issue(fields=issue_dict)
                st.write(f"Created Jira Issue Type Epic: {epic_issue.key} - Summary: {epic_issue.fields.summary}")
        

        elif issue_type == JIRA_TASK_ISSUE_TYPE:
            # Check if the task has a parent issue
            if parent_key is not None:
                # Find parent issue using summary
                parent_issue = jira.search_issues(f'project={get_jira_project_key()} AND summary~"{parent_key}" AND issuetype = {JIRA_EPIC_ISSUE_TYPE}', maxResults=1)
                if parent_issue:
                    parent_key = parent_issue[0].key
                    issue_dict = create_jira_issue(summary, JIRA_TASK_ISSUE_TYPE, start_date_normalized, due_date_normalized, parent_key,description)
                    task_issue = jira.create_issue(fields=issue_dict)
                    st.write(f"Created Jira task: {task_issue.key} - Summary: {task_issue.fields.summary}, Linked to parent: {parent_key}")

                else:
                    st.write(f"Parent issue '{parent_key}' not found. Skipping task creation.")
            else:
                # Create task on its own
                issue_dict = create_jira_issue(summary, JIRA_TASK_ISSUE_TYPE, start_date_normalized, due_date_normalized, description_key=description)
                task_issue = jira.create_issue(fields=issue_dict)
                st.write(f"Created Jira task: {task_issue.key} - Summary: {task_issue.fields.summary}")
                
        elif issue_type == JIRA_SUBTASK_ISSUE_TYPE:
            # Check if the sub-task has a parent issue
            if parent_key is not None:
                # Find parent issue using summary
                parent_issue = jira.search_issues(f'project={get_jira_project_key()} AND summary~"{parent_key}" AND issuetype = {JIRA_TASK_ISSUE_TYPE}', maxResults=1)
                if parent_issue:
                    parent_key = parent_issue[0].key
                    issue_dict = create_jira_issue(summary, JIRA_SUBTASK_ISSUE_TYPE, start_date_normalized, due_date_normalized, parent_key, description)
                    subtask_issue = jira.create_issue(fields=issue_dict)
                    st.write(f"Created Jira subtask: {subtask_issue.key} - Summary: {subtask_issue.fields.summary}, Linked to parent: {parent_key}")
                else:
                    st.write(f"Parent issue '{parent_key}' not found. Skipping subtask creation.")
            else:
                st.write("A Sub-task must have a parent. Skipping subtask creation.")

    # Add issue links after all issues are created
    add_issue_links(jira, excel_data)

    # Update Jira Issue type Project if user provided project name
    if st.session_state['project_name_user']:
        issue=jira.issue(project_issue.key)
        issue.update(summary=st.session_state['project_name_user'])
    return

def update_issue_overview_sheet(excel_data, issue_data):
    # Create a DataFrame for the "IssueOverview" sheet with selected columns
    issue_overview_df = pd.DataFrame(issue_data, columns=['IssueKey', 'Summary', 'IssueType', 'ParentSummary', 'Status', 'StartDate', 'DueDate', 'Description', 'Assignee', 'ExternalAssignee','IssueLinks'])


    # Write updated data to the "IssueOverview" sheet
    with pd.ExcelWriter(EXCEL_FILE_PATH, engine='openpyxl') as writer:
        # Write "IssueOverview" with the specified columns
        issue_overview_df.to_excel(writer, index=False, sheet_name='IssueOverview')



def get_issues_from_jira(jira):
    # Query issues from Jira
    issues = jira.search_issues(f'project={get_jira_project_key()}', maxResults=None)
    
    # Extract relevant information for the "IssueOverview" sheet
    issue_data = []
    
    for issue in issues:
        # Extract information about parent issue if exists
        parent_summary = issue.fields.parent.fields.summary if hasattr(issue.fields, 'parent') and issue.fields.parent else None
        
        # Extract information about issue links
        issue_links = []
        for link in issue.fields.issuelinks:
            if hasattr(link, 'inwardIssue') and hasattr(link.inwardIssue.fields, 'summary'):
                issue_links.append({
                    'LinkType': link.type.inward,
                    'LinkedIssueSummary': link.inwardIssue.fields.summary
                    #'LinkedIssueKey': link.inwardIssue.key
                })
            elif hasattr(link, 'outwardIssue') and hasattr(link.outwardIssue.fields, 'summary'):
                issue_links.append({
                    'LinkType': link.type.outward,
                    'LinkedIssueSummary': link.outwardIssue.fields.summary
                    #'LinkedIssueKey': link.outwardIssue.key

                })
        
        assignee = issue.fields.assignee if issue.fields.assignee else None
        
        issue_info = {
            'Summary': issue.fields.summary,
            'IssueKey': issue.key,
            'ParentSummary': parent_summary,
            'IssueType': issue.fields.issuetype.name,
            'Status': issue.fields.status.name,
            'StartDate': issue.fields.customfield_10015,
            'DueDate': issue.fields.duedate,
            'Description': issue.fields.description,
            'Assignee': issue.fields.assignee,
            'ExternalAssignee': issue.fields.customfield_10127,
            'IssueLinks': issue_links
        }
        
        issue_info.update(issue_links)
        issue_data.append(issue_info)

    return issue_data


# Function to update Jira issues with status, start date, and due date comparison
def update_jira_issues(jira, excel_data):
    for index, row in excel_data.iterrows():
        issue_key = row['IssueKey']
        new_status = row.get('Status')
        issue_key_checked = normalize_NaN(issue_key)
        
        if issue_key_checked and new_status:
            try:
                existing_issue = jira.issue(issue_key)
                # Check if status, start date, or due date is different
                if (
                    new_status != existing_issue.fields.status.name
                    or normalize_date(row['StartDate']) != existing_issue.fields.customfield_10015
                    or normalize_date(row['DueDate']) != existing_issue.fields.duedate
                    #or row['Description'] != existing_issue.fields.description
                    # customfield_10127 is Other in Jira and used to assign an external User as an Owner of an Issue
                    or (existing_issue.fields.customfield_10127 and row['ExternalAssignee'] != existing_issue.fields.customfield_10127)
                ):
                    # Transition the issue to the new status
                    transition_issue(jira, issue_key, new_status)
                    
                    # Update issue details
                    if existing_issue.fields.customfield_10127:
                        existing_issue.update(
                            summary=row['Summary'],
                            #description=row['Description'],
                            customfield_10015=normalize_date(row['StartDate']),
                            duedate=normalize_date(row['DueDate']),
                            customfield_10127=row['ExternalAssignee']
                        )
                    else:
                        existing_issue.update(
                            summary=row['Summary'],
                            #description=row['Description'],
                            customfield_10015=normalize_date(row['StartDate']),
                            duedate=normalize_date(row['DueDate']),
                        )

                    st.write(f"Updated Jira issue: {issue_key} - Summary: {row['Summary']}")
            except Exception as e:
                st.write(f"Error updating issue {issue_key} in Jira: {e}")

        else:
            parent_key=row['ParentSummary']
            if parent_key is not None:
                # Find parent issue using summary
                parent_issue = jira.search_issues(f'project={get_jira_project_key()} AND summary~"{parent_key}"', maxResults=1)

                if parent_issue:
                    parent_key_id = parent_issue[0].key

                #TO DO IMPLEMENT HANDLING FOR EPICs

                else:
                    st.write(f"Parent issue '{parent_key}' not found. Tasks can only be created if ParentName is provided. Skipping task creation.")

            # Mandatory Input Values
            issue_dict = create_jira_issue(
                summary=row['Summary'],
                issue_type=row['IssueType'],
                parent_key=parent_key_id
            )
            # Optional Input Values 
            if normalize_NaN(row['StartDate']):
                start_date_normalized = normalize_date(row['StartDate'])
                issue_dict['customfield_10015'] = start_date_normalized

            if normalize_NaN(row['DueDate']):
                due_date_normalized = normalize_date(row['DueDate'])
                issue_dict['duedate'] = due_date_normalized
    
            if normalize_NaN(row['Description']):
                issue_dict['description'] = row['Description']
            
            if normalize_NaN(row['ExternalAssignee']) and existing_issue.fields.customfield_10127:
                issue_dict['customfield_10127'] = row['ExternalAssignee']

            new_issue = jira.create_issue(fields=issue_dict)
            st.write(f"Created Jira issue: {new_issue.key} - Summary: {new_issue.fields.summary}")
        

# Function to transition Jira issue to a new status
def transition_issue(jira, issue_key, new_status):
    # Get the transition ID based on the destination status
    transition_id = get_transition_id(jira, issue_key, new_status)
    
    if transition_id:
        # Perform the transition
        jira.transition_issue(issue_key, transition_id)
        st.write(f"Issue {issue_key} transitioned to status: {new_status}")
    else:
        st.write(f"Transition to status {new_status} failed. Transition from current status to {new_status} not allowed.")

# Function to get the transition ID for a specific status
def get_transition_id(jira, issue_key, target_status):
    transitions = jira.transitions(issue_key)
    for transition in transitions:
        
        if transition['to']['name'] == target_status:
            return transition['id']
    return None
    
def has_cf(jira):
    # UPDATE the function as follows: use JQL to check if a specific project has a customfield

    try:
        # Get all custom fields from Jira
        #fields = jira.search_issues(f'project={JIRA_PROJECT} AND "Other" is not EMPTY', maxResults=1)
        fields = jira.search_issues(f'project={get_jira_project_key()} AND cf[10127] is not EMPTY', maxResults=1)
        if fields: 
            st.write(f'CustomField is available in {get_jira_project_key()}')
            return True
        st.write(f'CustomField is not available in {get_jira_project_key()}')
        return False

    except Exception as e:
        st.write(f"Error retrieving custom fields: {e}")
        return False

# Function that computes start and enddates of subtasks and epics based on start and enddate of Issue Type Task
def compute_dates(excel_data, project_startdate):
    task_info = []
    # First Iteration: compute start and enddates for Tasks
    for index, row in excel_data.iterrows():
        
        summary = row['Summary']
        issue_type = row['IssueType']
        duration = row.get('Duration', 0)
        blocks = normalize_NaN(row.get('Blocks'))

        if issue_type =='Account':
            start_date = project_startdate
            end_date = project_startdate
            task_info.append({
                    'summary': summary,
                    'parent': 'NoParent',
                    'start_date': project_startdate,
                    'end_date': end_date
                })
        
        #    if issue_type =='Project':
        #        start_date = project_startdate
        #        end_date = project_startdate
        #        task_info.append({
        #                'summary': summary,
        #                'parent': row['Parent'],
        #                'start_date': project_startdate,
        #                'end_date': end_date
        #            })

        if issue_type == 'Task':
            # Check if there's already a task with the same summary in task_info
            existing_task = next((task for task in task_info if task['summary'] == summary), None)

            if existing_task:
                # Task with the same summary already exists, use existing start date
                start_date = existing_task['start_date']
                # Compute end date based on duration
                end_date = calculate_end_date(start_date, duration)
                 # Update existing task in task_info with computed end date
                existing_task['end_date'] = end_date
                
                # also check if task has a value in Blocks
                summary = existing_task['summary']
                blocks = excel_data.loc[excel_data['Summary'] == summary, 'Blocks'].iloc[0]
                dependendy_blocks = normalize_NaN(blocks)

                if dependendy_blocks:
                    for block_summary in dependendy_blocks.split(','):
                        task_info.append({
                                'summary': block_summary.strip(),
                                'start_date': end_date  # Use end date as start date
                                
                        })
            else:
                # Create a new task in task_info
                task_info.append({
                    'summary': summary,
                    'parent': row['Parent'],
                    'start_date': project_startdate,
                    'end_date': calculate_end_date(project_startdate, duration)
                })
                
                if blocks:

                    for block_summary in blocks.split(','):
                        task_info.append({
                                'summary': block_summary.strip(),
                                'start_date': calculate_end_date(project_startdate, duration)  # Use end date as start date
                        })

    # Second Iteration: Look up correct parent for tasks with 'Blocks'
    for task in task_info:
        if 'parent' not in task:
            # This task has no parent information, look it up in excel_data
            summary = task['summary']
            parent_from_excel = excel_data.loc[excel_data['Summary'] == summary, 'Parent'].iloc[0]
            task['parent'] = normalize_NaN(parent_from_excel)
            

    # Third Iteration: compute start and enddates for Sub-tasks
    for index, row in excel_data.iterrows():
        summary = row['Summary']
        issue_type = row['IssueType']
        parent = row['Parent']

        if issue_type == 'Sub-task':
            # Check for the parent Task of the current Sub-task in task_info
            existing_task = next((task for task in task_info if task['summary'] == parent), None)

            if existing_task:
                # Create a new task in task_info
                task_info.append({
                    'summary': summary,
                    'parent': row['Parent'],
                    'start_date': existing_task['start_date'],
                    'end_date': existing_task['end_date']
                })
    
    # Fourth Iteration: compute start and enddates for Epics
    for index, row in excel_data.iterrows():
        summary = row['Summary']
        issue_type = row['IssueType']
        parent = row['Parent']
        
        if issue_type == 'Epic':
            epic_start_date = min(task['start_date'] for task in task_info if task['parent'] == summary)
            epic_end_date = max(task['end_date'] for task in task_info if task['parent'] == summary)
            
            # Update epic information in task_info
            epic_task = next((task for task in task_info if task['summary'] == summary), None)

            if epic_task:
                epic_task['start_date'] = epic_start_date
                epic_task['end_date'] = epic_end_date
            else:
                # If epic not found in task_info (should not happen), create a new entry
                task_info.append({
                    'summary': summary,
                    'parent': parent,
                    'start_date': epic_start_date,
                    'end_date': epic_end_date,
                })
    
    # Fifth Iteration: compute start and enddates for Issue Type "Project"
    for index, row in excel_data.iterrows():
        summary = row['Summary']
        issue_type = row['IssueType']
        parent = row['Parent']
        
        if issue_type == 'Project':
            start_date = project_startdate
            # iterate through all tasks in the temp dict task_info - look for those that have Pilot or Rollout as parent - get the max endate
            project_end_date = max(task['end_date'] for task in task_info if task['parent'] == summary)
            end_date = project_end_date
            task_info.append({
                    'summary': summary,
                    'parent': 'NoParent',
                    'start_date': project_startdate,
                    'end_date': end_date
                })
            
    return task_info

def getIssueDate(dates,summary,date_type='start_date'):
    issue_date = None
    datesDF=pd.DataFrame(dates)
    for index, row in datesDF.iterrows():
        taskInfoSummary = row['summary']
        if taskInfoSummary == summary:
            issue_date=row[date_type]
            
        
    # Convert Timestamp to datetime
    issue_date_datetime = issue_date.to_pydatetime()
    # Format datetime as string
    issue_date_string = issue_date_datetime.strftime('%Y-%m-%d')
    return issue_date_string


# Generate a JQL string based on the selected project, issue type, and status etc
def generate_jql(project, issue_type, status,parent,owner,days,custom_jql):
    jql_parts = []
    if project:
        jql_parts.append(f'project = "{project}"')
    else:
        st.write('Please select a project key!')
        return
    if issue_type:
        joined_issue_type = '","'.join(issue_type)
        jql_parts.append(f'issuetype in ( "{joined_issue_type}")')

    if status:
        string_status = '","'.join(status)
        jql_parts.append(f'status in ("{string_status}")')


    if parent:
        if ',' in parent:
            # assume more then one issue was input
            parents = parent.split(",")
            # Initialize an empty string to hold the final result
            result_string = "parent in ("
            # Iterate over each element in the list
            for i, element in enumerate(parents):
                # Add "projectkey-" prefix to each element and a comma , if it's not the last element
                if i < len(parents) - 1:
                    result_string += f'"{project}-{element}",'
                else:
                    # If it's the last element don't add the )
                    result_string += f'"{project}-{element}")'
            jql_parts.append(f'{result_string}')
        else:
        # only one issue
            jql_parts.append(f'parent = "{project}-{parent}"')
    if owner:
        if owner == "Customer":
            jql_parts.append(f'cf[10127] is not EMPTY')
        else:
            pass
    if days:
        jql_parts.append(f'due >= startOfDay() AND due <= endOfDay("+{days}d")')
    if custom_jql:
        jql_parts.append(f'{custom_jql}')

    return " AND ".join(jql_parts)

def get_company_managed_projects_df(
    jira_url: str,
    username: str,
    password: str,
    excluded_keys: Optional[Iterable[str]] = None,
) -> pd.DataFrame:
    """
    Return a DataFrame with columns ['Key','Name'] for all *company-managed* Jira projects
    visible to the user, excluding EXCLUDED_BOARD_KEYS.
    Uses Jira Cloud REST v3 /project/search via JiraV3 (no python-jira).
    """
    client = JiraV3(jira_url, username, password)

    projects: List[Dict] = client.project_search_all()  # paginated under the hood
    excluded = set(excluded_keys or EXCLUDED_BOARD_KEYS)

    data = [
        {"Key": p["key"], "Name": p.get("name", "")}
        for p in projects
        if p.get("projectTypeKey") == "business" and p.get("key") and p["key"] not in excluded
    ]

    return pd.DataFrame(data, columns=["Key", "Name"])


# Function to retrieve all issues of a project that are relevant for updating the powerpoint timeline (gantt)
def get_all_jira_issues_of_project(jira, parent_issue_key):
    issue_data = []

    # Change the names according to your needs - those are the issue summaries (names)
    workshop_summaries_pilot= [
    'Perform Technical Workshop', 
    'Perform Assessment Workshop', 
    'Perform Functional Workshop', 
    'User Training', 
    'Project Management', 
    'Assessment', 
    'Design', 
    'Machine Learning', 
    'Application Implementation', 
    'Integration Implementation', 
    'Testing', 
    'Delivery'
    ]
    
    def get_issue_details(issue):
        return {
            'summary': issue.fields.summary,
            'customfield_10015': getattr(issue.fields, 'customfield_10015', None),
            'duedate': issue.fields.duedate
        }

    if parent_issue_key:
        child_issues = get_children_issues_for_timeline(jira, parent_issue_key)
        if child_issues:
            for issue_key in child_issues:
                issue = jira.issue(issue_key)
                summary = issue.fields.summary
                if summary in workshop_summaries_pilot:
                    issue_data.append(get_issue_details(issue))
    else:
        return
   
    return issue_data


def get_due_date_by_summary(issue_data, summary):
    try:
        for issue in issue_data:
            if issue.get('summary') == summary:
                duedate = issue.get('duedate')
                if duedate:
                    return datetime.strptime(duedate, '%Y-%m-%d')
        return None
    except (ValueError, KeyError, TypeError) as e:
        print(f"Error: {e}")
        return None

def get_start_date_by_summary(issue_data, summary):
    try:
        for issue in issue_data:
            if issue.get('summary') == summary:
                startdate = issue.get('customfield_10015')
                if startdate:
                    return datetime.strptime(startdate, '%Y-%m-%d')
        return None
    except (ValueError, KeyError, TypeError) as e:
        print(f"Error: {e}")
        return None

