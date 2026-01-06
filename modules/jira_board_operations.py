from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

import requests
from requests.auth import HTTPBasicAuth
import streamlit as st
from jira import JIRA

from modules.config import (
    JIRA_URL,
    JIRA_API_URL,
    JIRA_API_URL_V3,
    TEMPLATE_WF_BOARD_ID,
    DEFAULT_BOARD_GROUPS,
    JIRA_ADMIN_ROLE_ID,
)

# -----------------------------
# Constants
# -----------------------------

HEADERS: Dict[str, str] = {
    "Accept": "application/json",
    "Content-Type": "application/json",
}

DEFAULT_TIMEOUT = 30


# -----------------------------
# Credentials / Clients (LAZY)
# -----------------------------

def _get_creds() -> Tuple[str, str]:
    """
    Get Jira credentials from Streamlit session_state at runtime.
    MUST NOT be called at import time by top-level code.
    """
    email = (st.session_state.get("api_username") or "").strip()
    token = (st.session_state.get("api_password") or "").strip()

    if not email or not token:
        raise RuntimeError(
            "Missing Jira credentials in session_state (api_username/api_password). "
            "Please log in again."
        )
    return email, token


def _get_auth() -> HTTPBasicAuth:
    email, token = _get_creds()
    return HTTPBasicAuth(email, token)


def _get_jira_client() -> JIRA:
    email, token = _get_creds()
    return JIRA(server=JIRA_URL, basic_auth=(email, token))


def _safe_json(resp: requests.Response) -> Optional[dict]:
    ct = (resp.headers.get("content-type") or "").lower()
    if "application/json" not in ct:
        return None
    try:
        return resp.json()
    except Exception:
        return None


# -----------------------------
# Helpers
# -----------------------------

def jira_preflight() -> Dict[str, Any]:
    """
    Quick auth validation: GET /rest/api/3/myself
    Returns structured result for logging.
    """
    url = f"{JIRA_API_URL_V3}/myself"
    try:
        resp = requests.get(
            url,
            headers={"Accept": "application/json"},
            auth=_get_auth(),
            timeout=DEFAULT_TIMEOUT,
        )
        return {
            "ok": resp.status_code == 200,
            "status": resp.status_code,
            "url": url,
            "response_text": resp.text[:2000],
            "response_json": _safe_json(resp),
        }
    except requests.RequestException as e:
        return {
            "ok": False,
            "status": None,
            "url": url,
            "error": str(e),
        }


# -----------------------------
# Project checks / lookup
# -----------------------------

def check_project_name_exists(project_name: str) -> None:
    """
    Raises ValueError if a project with this name already exists.
    """
    url = f"{JIRA_API_URL_V3}/project/search"

    response = requests.get(
        url,
        headers=HEADERS,
        auth=_get_auth(),
        timeout=DEFAULT_TIMEOUT,
    )

    if response.status_code == 200:
        projects = (response.json() or {}).get("values", [])
        for project in projects:
            if (project.get("name") or "").lower() == project_name.lower():
                raise ValueError(
                    f"Error: Jira Board with the name '{project_name}' already exists. "
                    f"Try another Board Name"
                )
        st.success(f"Jira Board '{project_name}' is available.", icon="✅")
        return

    st.error(f"Failed to fetch projects: {response.status_code} - {response.text}")


def get_id_for_jira_board(jira_board_key: str) -> str:
    url = f"{JIRA_API_URL}/project/{jira_board_key}"

    response = requests.get(
        url,
        headers=HEADERS,
        auth=_get_auth(),
        timeout=DEFAULT_TIMEOUT,
    )

    data = _safe_json(response)
    if not data or "id" not in data:
        raise RuntimeError(f"Could not fetch project id for {jira_board_key}: {response.status_code} - {response.text}")

    st.write(data["id"])
    return data["id"]


# -----------------------------
# Workflow / scheme assignment
# -----------------------------

def get_project_workflow_scheme() -> None:
    url = f"{JIRA_API_URL}/workflowscheme/project"
    params = {"projectId": TEMPLATE_WF_BOARD_ID}

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            params=params,
            auth=_get_auth(),
            timeout=DEFAULT_TIMEOUT,
        )
        data = _safe_json(response)
        st.write(json.dumps(data if data is not None else {"raw": response.text[:2000]}, sort_keys=True, indent=4))
    except Exception as e:
        st.error(f"Error occurred: {str(e)}")


def assign_project_workflow_scheme(jira_board_Id: str) -> None:
    url = f"{JIRA_API_URL_V3}/workflowscheme/project"
    payload = {"projectId": jira_board_Id, "workflowSchemeId": "10145"}  # MB: Project Management Workflow v2

    try:
        response = requests.put(
            url,
            json=payload,
            headers=HEADERS,
            auth=_get_auth(),
            timeout=DEFAULT_TIMEOUT,
        )
        if response.status_code in (200, 204):
            st.write(f"✅ Workflowscheme assigned to Jira Board {jira_board_Id}")
        else:
            st.error(f"Failed to assign workflowscheme: {response.status_code} - {response.text}")
    except Exception as e:
        st.error(f"Error occurred: {str(e)}")


def assign_issue_type_scheme(jira_board_Id: str) -> None:
    url = f"{JIRA_API_URL_V3}/issuetypescheme/project"
    payload = {
        "issueTypeSchemeId": "10466",  # MB: Project Management Issue Type Scheme
        "projectId": jira_board_Id,
    }

    try:
        response = requests.put(
            url,
            json=payload,
            headers=HEADERS,
            auth=_get_auth(),
            timeout=DEFAULT_TIMEOUT,
        )
        if response.status_code in (200, 204):
            st.write(f"✅ Issue Type Scheme assigned to Jira Board {jira_board_Id}")
        else:
            st.error(f"Failed to assign Issue Type Scheme: {response.status_code} - {response.text}")
    except Exception as e:
        st.error(f"Error occurred: {str(e)}")


def assign_issue_type_screen_scheme(jira_board_Id: str) -> None:
    url = f"{JIRA_API_URL_V3}/issuetypescreenscheme/project"
    payload = {
        "issueTypeScreenSchemeId": "10137",  # MB: Project Management Issue Type Screen Scheme
        "projectId": jira_board_Id,
    }

    try:
        response = requests.put(
            url,
            json=payload,
            headers=HEADERS,
            auth=_get_auth(),
            timeout=DEFAULT_TIMEOUT,
        )
        if response.status_code in (200, 204):
            st.write(f"✅ Issue Type Screen Scheme assigned to Jira Board {jira_board_Id}")
        else:
            st.error(f"Failed to assign Issue Type Screen Scheme: {response.status_code} - {response.text}")
    except Exception as e:
        st.error(f"Error occurred: {str(e)}")


def assign_permission_scheme(jira_board_Id: str) -> None:
    url = f"{JIRA_API_URL_V3}/project/{jira_board_Id}/permissionscheme"
    payload = {"id": "10087"}  # Permission scheme ID

    try:
        response = requests.put(
            url,
            json=payload,
            headers=HEADERS,
            auth=_get_auth(),
            timeout=DEFAULT_TIMEOUT,
        )
        if response.status_code in (200, 204):
            st.write(f"✅ Permission Scheme assigned to Jira Project {jira_board_Id}")
        else:
            st.error(f"Failed to assign Permission Scheme: {response.status_code} - {response.text}")
    except Exception as e:
        st.error(f"Error occurred: {str(e)}")


# -----------------------------
# Roles / users / groups
# -----------------------------

def assign_group_to_role(projectIdOrKey: str, group_name: str, role: str) -> None:
    url = f"{JIRA_API_URL}/project/{projectIdOrKey}/role/{role}"
    data = {"group": [group_name]}

    try:
        st.write(f"Assigning group '{group_name}' to role {role}")
        response = requests.post(
            url,
            headers=HEADERS,
            auth=_get_auth(),
            data=json.dumps(data),
            timeout=DEFAULT_TIMEOUT,
        )
        if response.status_code in (200, 201):
            st.write(f"✅ Group '{group_name}' assigned to role {role}")
        else:
            st.write(f"❌ Failed to assign group '{group_name}' to role {role}: {response.status_code} - {response.text}")
    except requests.exceptions.RequestException as e:
        st.write(f"Error while assigning group '{group_name}' to role {role}: {e}")


def assign_groups_to_role(projectIdOrKey: str, group_names: List[str], role: str) -> None:
    url = f"{JIRA_API_URL}/project/{projectIdOrKey}/role/{role}"
    data = {"group": group_names}

    try:
        st.write(f"Assigning groups {group_names} to role {role}")
        response = requests.post(
            url,
            headers=HEADERS,
            auth=_get_auth(),
            data=json.dumps(data),
            timeout=DEFAULT_TIMEOUT,
        )
        if response.status_code in (200, 201):
            st.write(f"✅ Groups {group_names} assigned to role {role}")
        else:
            st.write(f"❌ Failed to assign groups {group_names} to role {role}: {response.status_code} - {response.text}")
    except requests.exceptions.RequestException as e:
        st.write(f"Error while assigning groups {group_names} to role {role}: {e}")


def assign_users_to_role_of_jira_board(
    projectIdOrKey: str,
    user_list: List[str],
    jira_roles: List[int],
    user_groups: List[str],
) -> None:
    default_groups = DEFAULT_BOARD_GROUPS
    default_jira_roles = [JIRA_ADMIN_ROLE_ID]

    # Assign default user groups to project (COE/admin group)
    for role in default_jira_roles:
        assign_groups_to_role(projectIdOrKey, default_groups, str(role))

    # Assign external user groups to requested roles
    if user_groups:
        for role in jira_roles:
            assign_groups_to_role(projectIdOrKey, user_groups, str(role))

    # Assign internal users to default roles
    for role in default_jira_roles:
        url = f"{JIRA_API_URL}/project/{projectIdOrKey}/role/{role}"
        data = {"user": user_list}

        try:
            response = requests.post(
                url,
                headers=HEADERS,
                auth=_get_auth(),
                data=json.dumps(data),
                timeout=DEFAULT_TIMEOUT,
            )

            if response.status_code in (200, 201):
                st.write(f"✅ User(s) successfully assigned to role {role}")
            else:
                st.write(f"❌ Failed to assign user(s) to role {role}: {response.status_code} - {response.text}")
                return
        except requests.exceptions.RequestException as e:
            st.write(f"Error while assigning user(s) to role {role}: {e}")
            return


def get_all_groups(group_alias: Optional[str] = None) -> List[str]:
    """
    Fetch all groups and return list of group names.
    If group_alias == "partner", only return groups starting with "ext-".
    """
    url = f"{JIRA_API_URL}/groups/picker"
    try:
        params = {"maxResults": 250}
        response = requests.get(
            url,
            headers=HEADERS,
            params=params,
            auth=_get_auth(),
            timeout=DEFAULT_TIMEOUT,
        )
        response.raise_for_status()

        groups = (response.json() or {}).get("groups", [])
        group_names = [g.get("name") for g in groups if g.get("name")]

        if group_alias == "partner":
            group_names = [name for name in group_names if name.startswith("ext-")]

        return group_names
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching groups: {e}")
        return []


def get_assignable_users(project_keys: str) -> List[dict]:
    """
    Get assignable users from Jira API.
    Note: Jira expects comma-separated project keys in 'projectKeys' param for multiProjectSearch.
    """
    url = f"{JIRA_API_URL}/user/assignable/multiProjectSearch"
    params = {"projectKeys": project_keys, "maxResults": 150}

    response = requests.get(
        url,
        headers=HEADERS,
        params=params,
        auth=_get_auth(),
        timeout=DEFAULT_TIMEOUT,
    )

    if response.status_code == 200:
        data = response.json()
        st.write(data)
        return data
    st.error(f"Failed to retrieve users: {response.status_code} - {response.text}")
    return []


def get_all_role_ids() -> List[dict]:
    """
    Helper function to get all role ids for a sample project (currently hardcoded).
    """
    projectIdOrKey = "FNK"
    url = f"{JIRA_API_URL}/project/{projectIdOrKey}/role"

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            auth=_get_auth(),
            timeout=DEFAULT_TIMEOUT,
        )
        response.raise_for_status()
        roles = response.json()
        st.write(roles)
        return roles
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching roles: {e}")
        return []


# -----------------------------
# Project creation
# -----------------------------

def create_jira_board(
    key: str,
    name: str,
    project_type: str,
    project_template: str,
    lead_account_id: str,
) -> Dict[str, Any]:
    """
    Create a Jira project (called 'Board' in your app).
    Returns structured result:
      ok, status, id, key, url, sent_headers, sent_payload, response_text, response_json
    """
    url = f"{JIRA_API_URL}/project"
    payload = {
        "key": key,
        "name": name,
        "projectTypeKey": project_type,
        "projectTemplateKey": project_template,
        "leadAccountId": lead_account_id,
    }

    # Preflight
    pre = jira_preflight()
    if not pre.get("ok"):
        # Provide helpful hint for 401
        hint = None
        if pre.get("status") == 401:
            hint = "401 on /myself usually means wrong email/token or empty session_state values."
        return {
            "ok": False,
            "status": pre.get("status"),
            "error": "Preflight failed: not authenticated",
            "hint": hint,
            "url": pre.get("url"),
            "response_text": (pre.get("response_text") or "")[:2000],
            "preflight": pre,
        }

    try:
        resp = requests.post(
            url,
            json=payload,
            headers=HEADERS,
            auth=_get_auth(),
            timeout=DEFAULT_TIMEOUT,
        )
    except requests.RequestException as e:
        return {"ok": False, "status": None, "error": str(e), "url": url}

    result: Dict[str, Any] = {
        "ok": resp.status_code == 201,
        "status": resp.status_code,
        "url": url,
        "response_text": resp.text[:2000],
        "sent_payload": payload,
    }

    # sanitize sent headers for debug
    sent_headers = dict(resp.request.headers)
    if "Authorization" in sent_headers:
        sent_headers["Authorization"] = "****"
    result["sent_headers"] = sent_headers

    data = _safe_json(resp)
    if data is not None:
        result["response_json"] = data

    if result["ok"]:
        result["id"] = (data or {}).get("id")
        result["key"] = (data or {}).get("key")
        if result.get("key"):
            result["project_url"] = f"https://hypatos.atlassian.net/jira/core/projects/{result['key']}/board"

    return result
