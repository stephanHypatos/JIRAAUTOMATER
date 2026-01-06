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
# Custom Exceptions
# -----------------------------

class JiraAuthenticationError(Exception):
    """Raised when Jira authentication fails"""
    pass


class JiraProjectCreationError(Exception):
    """Raised when project creation fails"""
    pass


class JiraAPIError(Exception):
    """Raised for general Jira API errors"""
    pass


# -----------------------------
# Credentials / Clients (LAZY)
# -----------------------------

def _get_creds() -> Tuple[str, str]:
    """
    Get Jira credentials from Streamlit session_state at runtime.
    MUST NOT be called at import time by top-level code.
    
    Raises:
        JiraAuthenticationError: If credentials are missing or invalid
    """
    email = (st.session_state.get("api_username") or "").strip()
    token = (st.session_state.get("api_password") or "").strip()

    if not email or not token:
        raise JiraAuthenticationError(
            "Missing Jira credentials in session_state (api_username/api_password). "
            "Please log in again via the Authenticate page."
        )
    return email, token


def _get_auth() -> HTTPBasicAuth:
    """Get HTTPBasicAuth object with current credentials"""
    email, token = _get_creds()
    return HTTPBasicAuth(email, token)


def _get_jira_client() -> JIRA:
    """Get authenticated JIRA client"""
    email, token = _get_creds()
    return JIRA(server=JIRA_URL, basic_auth=(email, token))


def _safe_json(resp: requests.Response) -> Optional[dict]:
    """Safely parse JSON response, return None if not JSON"""
    ct = (resp.headers.get("content-type") or "").lower()
    if "application/json" not in ct:
        return None
    try:
        return resp.json()
    except Exception:
        return None


def _handle_response(
    response: requests.Response,
    success_codes: List[int] = None,
    error_message: str = "API request failed"
) -> dict:
    """
    Handle API response with proper error checking
    
    Args:
        response: The response object
        success_codes: List of acceptable status codes (default: [200])
        error_message: Custom error message prefix
        
    Returns:
        Parsed JSON response
        
    Raises:
        JiraAPIError: If response indicates an error
    """
    if success_codes is None:
        success_codes = [200]
    
    if response.status_code not in success_codes:
        error_detail = _safe_json(response)
        if error_detail:
            raise JiraAPIError(
                f"{error_message}: {response.status_code} - "
                f"{error_detail.get('errorMessages', error_detail)}"
            )
        else:
            raise JiraAPIError(
                f"{error_message}: {response.status_code} - {response.text[:500]}"
            )
    
    return _safe_json(response) or {}


# -----------------------------
# Helpers
# -----------------------------

def jira_preflight() -> Dict[str, Any]:
    """
    Quick auth validation: GET /rest/api/3/myself
    Returns structured result for logging.
    
    Raises:
        JiraAuthenticationError: If authentication fails
    """
    url = f"{JIRA_API_URL_V3}/myself"
    try:
        resp = requests.get(
            url,
            headers={"Accept": "application/json"},
            auth=_get_auth(),
            timeout=DEFAULT_TIMEOUT,
        )
        
        if resp.status_code == 401:
            raise JiraAuthenticationError(
                "Authentication failed (401). Please check your credentials on the Authenticate page."
            )
        
        if resp.status_code != 200:
            raise JiraAuthenticationError(
                f"Preflight check failed: {resp.status_code} - {resp.text[:500]}"
            )
        
        return {
            "ok": True,
            "status": resp.status_code,
            "user": _safe_json(resp),
        }
    except requests.RequestException as e:
        raise JiraAuthenticationError(f"Network error during authentication: {str(e)}")


# -----------------------------
# Project checks / lookup
# -----------------------------

def check_project_name_exists(project_name: str) -> None:
    """
    Raises ValueError if a project with this name already exists.
    
    Args:
        project_name: The project name to check
        
    Raises:
        ValueError: If project name already exists
        JiraAPIError: If API request fails
    """
    url = f"{JIRA_API_URL_V3}/project/search"

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            auth=_get_auth(),
            timeout=DEFAULT_TIMEOUT,
        )
        data = _handle_response(response, error_message="Failed to search projects")
        
        projects = data.get("values", [])
        for project in projects:
            if (project.get("name") or "").lower() == project_name.lower():
                raise ValueError(
                    f"Error: Jira Board with the name '{project_name}' already exists. "
                    f"Try another Board Name"
                )
        
        st.success(f"Jira Board '{project_name}' is available.", icon="✅")
        
    except JiraAPIError:
        raise
    except Exception as e:
        raise JiraAPIError(f"Error checking project name: {str(e)}")


def get_id_for_jira_board(jira_board_key: str) -> str:
    """
    Get project ID from project key
    
    Args:
        jira_board_key: The project key
        
    Returns:
        The project ID as string
        
    Raises:
        JiraAPIError: If request fails or ID not found
    """
    url = f"{JIRA_API_URL}/project/{jira_board_key}"

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            auth=_get_auth(),
            timeout=DEFAULT_TIMEOUT,
        )
        data = _handle_response(response, error_message=f"Failed to get project ID for {jira_board_key}")
        
        project_id = data.get("id")
        if not project_id:
            raise JiraAPIError(f"No ID found in response for project {jira_board_key}")
        
        return str(project_id)
        
    except Exception as e:
        raise JiraAPIError(f"Error fetching project ID: {str(e)}")


# -----------------------------
# Workflow / scheme assignment
# -----------------------------

def get_project_workflow_scheme() -> None:
    """Debug helper to view workflow scheme of template project"""
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


def assign_project_workflow_scheme(jira_board_id: str) -> None:
    """
    Assign workflow scheme to project
    
    Args:
        jira_board_id: The project ID
        
    Raises:
        JiraAPIError: If assignment fails
    """
    url = f"{JIRA_API_URL_V3}/workflowscheme/project"
    payload = {"projectId": jira_board_id, "workflowSchemeId": "10145"}

    try:
        response = requests.put(
            url,
            json=payload,
            headers=HEADERS,
            auth=_get_auth(),
            timeout=DEFAULT_TIMEOUT,
        )
        _handle_response(
            response, 
            success_codes=[200, 204],
            error_message="Failed to assign workflow scheme"
        )
        st.write(f"✅ Workflow scheme assigned to Jira Board {jira_board_id}")
        
    except Exception as e:
        raise JiraAPIError(f"Error assigning workflow scheme: {str(e)}")


def assign_issue_type_scheme(jira_board_id: str) -> None:
    """
    Assign issue type scheme to project
    
    Args:
        jira_board_id: The project ID
        
    Raises:
        JiraAPIError: If assignment fails
    """
    url = f"{JIRA_API_URL_V3}/issuetypescheme/project"
    payload = {
        "issueTypeSchemeId": "10466",
        "projectId": jira_board_id,
    }

    try:
        response = requests.put(
            url,
            json=payload,
            headers=HEADERS,
            auth=_get_auth(),
            timeout=DEFAULT_TIMEOUT,
        )
        _handle_response(
            response,
            success_codes=[200, 204],
            error_message="Failed to assign issue type scheme"
        )
        st.write(f"✅ Issue Type Scheme assigned to Jira Board {jira_board_id}")
        
    except Exception as e:
        raise JiraAPIError(f"Error assigning issue type scheme: {str(e)}")


def assign_issue_type_screen_scheme(jira_board_id: str) -> None:
    """
    Assign issue type screen scheme to project
    
    Args:
        jira_board_id: The project ID
        
    Raises:
        JiraAPIError: If assignment fails
    """
    url = f"{JIRA_API_URL_V3}/issuetypescreenscheme/project"
    payload = {
        "issueTypeScreenSchemeId": "10137",
        "projectId": jira_board_id,
    }

    try:
        response = requests.put(
            url,
            json=payload,
            headers=HEADERS,
            auth=_get_auth(),
            timeout=DEFAULT_TIMEOUT,
        )
        _handle_response(
            response,
            success_codes=[200, 204],
            error_message="Failed to assign issue type screen scheme"
        )
        st.write(f"✅ Issue Type Screen Scheme assigned to Jira Board {jira_board_id}")
        
    except Exception as e:
        raise JiraAPIError(f"Error assigning issue type screen scheme: {str(e)}")


def assign_permission_scheme(jira_board_id: str) -> None:
    """
    Assign permission scheme to project
    
    Args:
        jira_board_id: The project ID
        
    Raises:
        JiraAPIError: If assignment fails
    """
    url = f"{JIRA_API_URL_V3}/project/{jira_board_id}/permissionscheme"
    payload = {"id": "10087"}

    try:
        response = requests.put(
            url,
            json=payload,
            headers=HEADERS,
            auth=_get_auth(),
            timeout=DEFAULT_TIMEOUT,
        )
        _handle_response(
            response,
            success_codes=[200, 204],
            error_message="Failed to assign permission scheme"
        )
        st.write(f"✅ Permission Scheme assigned to Jira Project {jira_board_id}")
        
    except Exception as e:
        raise JiraAPIError(f"Error assigning permission scheme: {str(e)}")


# -----------------------------
# Roles / users / groups
# -----------------------------

def assign_group_to_role(project_id_or_key: str, group_name: str, role: str) -> None:
    """
    Assign a single group to a project role
    
    Args:
        project_id_or_key: Project ID or key
        group_name: Name of the group to assign
        role: Role ID as string
        
    Raises:
        JiraAPIError: If assignment fails
    """
    url = f"{JIRA_API_URL}/project/{project_id_or_key}/role/{role}"
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
        _handle_response(
            response,
            success_codes=[200, 201],
            error_message=f"Failed to assign group '{group_name}' to role {role}"
        )
        st.write(f"✅ Group '{group_name}' assigned to role {role}")
        
    except Exception as e:
        st.error(f"Error while assigning group '{group_name}' to role {role}: {e}")
        raise


def assign_groups_to_role(project_id_or_key: str, group_names: List[str], role: str) -> None:
    """
    Assign multiple groups to a project role
    
    Args:
        project_id_or_key: Project ID or key
        group_names: List of group names to assign
        role: Role ID as string
        
    Raises:
        JiraAPIError: If assignment fails
    """
    url = f"{JIRA_API_URL}/project/{project_id_or_key}/role/{role}"
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
        _handle_response(
            response,
            success_codes=[200, 201],
            error_message=f"Failed to assign groups {group_names} to role {role}"
        )
        st.write(f"✅ Groups {group_names} assigned to role {role}")
        
    except Exception as e:
        st.error(f"Error while assigning groups {group_names} to role {role}: {e}")
        raise


def assign_users_to_role_of_jira_board(
    project_id_or_key: str,
    user_list: List[str],
    jira_roles: List[int],
    user_groups: List[str],
) -> None:
    """
    Assign users and groups to project roles
    
    Args:
        project_id_or_key: Project ID or key
        user_list: List of user account IDs
        jira_roles: List of role IDs for external users
        user_groups: List of external user group names
        
    Raises:
        JiraAPIError: If assignment fails
    """
    default_groups = DEFAULT_BOARD_GROUPS
    default_jira_roles = [JIRA_ADMIN_ROLE_ID]

    # Assign default user groups to project (COE/admin group)
    for role in default_jira_roles:
        assign_groups_to_role(project_id_or_key, default_groups, str(role))

    # Assign external user groups to requested roles
    if user_groups:
        for role in jira_roles:
            assign_groups_to_role(project_id_or_key, user_groups, str(role))

    # Assign internal users to default roles
    for role in default_jira_roles:
        url = f"{JIRA_API_URL}/project/{project_id_or_key}/role/{role}"
        data = {"user": user_list}

        try:
            response = requests.post(
                url,
                headers=HEADERS,
                auth=_get_auth(),
                data=json.dumps(data),
                timeout=DEFAULT_TIMEOUT,
            )
            _handle_response(
                response,
                success_codes=[200, 201],
                error_message=f"Failed to assign users to role {role}"
            )
            st.write(f"✅ User(s) successfully assigned to role {role}")
            
        except Exception as e:
            st.error(f"Error while assigning user(s) to role {role}: {e}")
            raise


def get_all_groups(group_alias: Optional[str] = None) -> List[str]:
    """
    Fetch all groups and return list of group names.
    
    Args:
        group_alias: If "partner", only return groups starting with "ext-"
        
    Returns:
        List of group names
        
    Raises:
        JiraAPIError: If request fails
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
        data = _handle_response(response, error_message="Failed to fetch groups")

        groups = data.get("groups", [])
        group_names = [g.get("name") for g in groups if g.get("name")]

        if group_alias == "partner":
            group_names = [name for name in group_names if name.startswith("ext-")]

        return group_names
        
    except Exception as e:
        st.error(f"Error fetching groups: {e}")
        raise JiraAPIError(f"Failed to fetch groups: {str(e)}")


def get_assignable_users(project_keys: str) -> List[dict]:
    """
    Get assignable users from Jira API.
    
    Args:
        project_keys: Comma-separated project keys
        
    Returns:
        List of user dictionaries with accountId and displayName
        
    Raises:
        JiraAPIError: If request fails
    """
    url = f"{JIRA_API_URL}/user/assignable/multiProjectSearch"
    params = {"projectKeys": project_keys, "maxResults": 150}

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            params=params,
            auth=_get_auth(),
            timeout=DEFAULT_TIMEOUT,
        )
        data = _handle_response(response, error_message="Failed to retrieve assignable users")
        return data if isinstance(data, list) else []
        
    except Exception as e:
        st.error(f"Failed to retrieve users: {e}")
        raise JiraAPIError(f"Failed to fetch assignable users: {str(e)}")


def get_all_role_ids() -> List[dict]:
    """
    Helper function to get all role ids for a sample project.
    
    Returns:
        List of role dictionaries
        
    Raises:
        JiraAPIError: If request fails
    """
    project_id_or_key = "FNK"
    url = f"{JIRA_API_URL}/project/{project_id_or_key}/role"

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            auth=_get_auth(),
            timeout=DEFAULT_TIMEOUT,
        )
        roles = _handle_response(response, error_message="Failed to fetch roles")
        st.write(roles)
        return roles if isinstance(roles, list) else []
        
    except Exception as e:
        st.error(f"Error fetching roles: {e}")
        raise JiraAPIError(f"Failed to fetch role IDs: {str(e)}")


# -----------------------------
# Project creation (FIXED)
# -----------------------------

def create_jira_board(
    key: str,
    name: str,
    project_type: str,
    project_template: str,
    lead_account_id: str,
) -> Dict[str, str]:
    """
    Create a Jira project (called 'Board' in your app).
    
    Args:
        key: Project key (3 letters)
        name: Project name
        project_type: Project type key (e.g., 'business')
        project_template: Template key
        lead_account_id: Account ID of project lead
        
    Returns:
        Dictionary with 'key' and 'id' of created project
        
    Raises:
        JiraAuthenticationError: If authentication fails
        JiraProjectCreationError: If project creation fails
    """
    # Validate credentials first
    try:
        preflight_result = jira_preflight()
        st.write(f"✅ Authentication successful for user: {preflight_result.get('user', {}).get('displayName', 'Unknown')}")
    except JiraAuthenticationError as e:
        st.error(f"❌ Authentication failed: {str(e)}")
        raise

    url = f"{JIRA_API_URL}/project"
    payload = {
        "key": key,
        "name": name,
        "projectTypeKey": project_type,
        "projectTemplateKey": project_template,
        "leadAccountId": lead_account_id,
    }

    try:
        st.write(f"Creating project with key: {key}, name: {name}")
        
        response = requests.post(
            url,
            json=payload,
            headers=HEADERS,
            auth=_get_auth(),
            timeout=DEFAULT_TIMEOUT,
        )
        
        # Check for success
        if response.status_code != 201:
            error_data = _safe_json(response)
            if error_data:
                error_msg = error_data.get('errorMessages', [])
                errors = error_data.get('errors', {})
                full_error = f"Status {response.status_code}: {error_msg} {errors}"
            else:
                full_error = f"Status {response.status_code}: {response.text[:500]}"
            
            raise JiraProjectCreationError(
                f"Failed to create Jira project: {full_error}"
            )
        
        # Parse successful response
        data = _safe_json(response)
        if not data:
            raise JiraProjectCreationError(
                f"Project creation returned non-JSON response: {response.text[:500]}"
            )
        
        project_key = data.get("key")
        project_id = data.get("id")
        
        if not project_key or not project_id:
            raise JiraProjectCreationError(
                f"Project creation response missing 'key' or 'id'. Response: {data}"
            )
        
        project_url = f"https://hypatos.atlassian.net/jira/core/projects/{project_key}/board"
        st.success(f"✅ Project created successfully: {project_key} (ID: {project_id})")
        st.write(f"Project URL: {project_url}")
        
        # Return simple dict with just key and id
        return {
            "key": project_key,
            "id": str(project_id),
        }
        
    except requests.RequestException as e:
        raise JiraProjectCreationError(f"Network error during project creation: {str(e)}")
    except JiraProjectCreationError:
        raise
    except Exception as e:
        raise JiraProjectCreationError(f"Unexpected error during project creation: {str(e)}")
