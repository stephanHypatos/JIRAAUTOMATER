from __future__ import annotations

import time
import traceback
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

import streamlit as st
from jira import JIRA

from modules.config import (
    JIRA_DEV_ROLE_ID,
    JIRA_ADMIN_ROLE_ID,
    LEAD_USER_MAPPING,
    TEMPLATE_MAPPING,
    ASSIGNABLE_USER_GROUP,
    ADMINS,
    JIRA_URL,
    JIRA_EXTERNAL_USER_ROLE_ID,
    JIRA_URL_CONFLUENCE,
)
from modules.jira_operations import create_jira_issue, save_jira_project_key
from modules.jira_board_operations import (
    check_project_name_exists,
    assign_project_workflow_scheme,
    assign_issue_type_scheme,
    assign_issue_type_screen_scheme,
    assign_users_to_role_of_jira_board,
    create_jira_board,
    get_assignable_users,
    get_all_groups,
    assign_permission_scheme,
    JiraAuthenticationError,
    JiraProjectCreationError,
    JiraAPIError,
)
from modules.confluence_native import ConfluenceAPI, get_existing_space_keys


# -----------------------------
# Session State Initialization
# -----------------------------

DEFAULT_SESSION_STATE: Dict[str, Any] = {
    "api_username": "",
    "api_password": "",
    "jira_project_key": "",
    "temp_jira_board_key": "",
    "temp_jira_board_id": "",
    "selected_users": [],
    "selected_user_groups": [],
    "debug_logs": [],
    "last_run_steps": [],
    "last_error": None,
    "last_success": None,
}

for k, v in DEFAULT_SESSION_STATE.items():
    st.session_state.setdefault(k, v)


# -----------------------------
# Logging / Transparency
# -----------------------------

def _redact(value: Any, key: str) -> Any:
    """Redact sensitive information from logs"""
    if any(s in key.lower() for s in ["password", "token", "secret", "auth"]):
        return "***REDACTED***"
    return value


def log_event(level: str, message: str, **context: Any) -> None:
    """Append a log event to session_state."""
    safe_context = {k: _redact(v, k) for k, v in context.items()}
    st.session_state["debug_logs"].append(
        {
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            "level": level.upper(),
            "message": message,
            "context": safe_context,
        }
    )


def reset_run_artifacts() -> None:
    """Reset tracking for current run"""
    st.session_state["last_run_steps"] = []
    st.session_state["last_error"] = None
    st.session_state["last_success"] = None


def add_step_result(step: str, ok: bool, details: Dict[str, Any]) -> None:
    """Record result of a workflow step"""
    st.session_state["last_run_steps"].append(
        {"step": step, "ok": ok, "details": details}
    )


def fail_step(step: str, exc: Exception) -> None:
    """Handle and log step failure"""
    tb = traceback.format_exc()
    details = {"error": str(exc), "traceback": tb}
    log_event("ERROR", f"Step failed: {step}", error=str(exc))
    add_step_result(step, False, details)
    st.session_state["last_error"] = {"step": step, **details}

    st.error(f"❌ {step} failed: {exc}")
    with st.expander("Show technical details", expanded=False):
        st.code(tb)


def debug_panel() -> None:
    """Display debug information in expandable panel"""
    with st.expander("🪵 Debug / Transparency (expand)", expanded=False):
        safe_state = {}
        for k, v in st.session_state.items():
            safe_state[k] = _redact(v, k)
        st.subheader("Session State (redacted)")
        st.json(safe_state)

        st.subheader("Last Run Steps")
        st.json(st.session_state.get("last_run_steps", []))

        st.subheader("Logs (last 200)")
        st.json(st.session_state.get("debug_logs", [])[-200:])


# -----------------------------
# Confluence client init
# -----------------------------

def init_confluence_native() -> ConfluenceAPI:
    """
    Native Confluence client used for fetching existing space keys.
    On Atlassian Cloud: email + API token.
    """
    return ConfluenceAPI(
        base_url=JIRA_URL_CONFLUENCE,
        email=st.session_state["api_username"],
        api_token=st.session_state["api_password"],
    )


# -----------------------------
# Data contract
# -----------------------------

@dataclass
class BoardCreateInputs:
    lead_user: str
    project_key: str
    project_name_raw: str
    project_type: str = "business"

    @property
    def project_name(self) -> str:
        return f"{self.project_name_raw} x Hypatos"

    @property
    def normalized_key(self) -> str:
        return self.project_key.strip().upper()


# -----------------------------
# Guards / Validation
# -----------------------------

def user_is_logged_in() -> bool:
    """Check if user has credentials in session"""
    return bool(st.session_state.get("api_username")) and bool(
        st.session_state.get("api_password")
    )


def user_is_admin() -> bool:
    """Check if current user is in admin list"""
    return st.session_state.get("api_username") in ADMINS


def validate_project_key_format(key: str) -> Optional[str]:
    """
    Validate project key format
    
    Args:
        key: Project key to validate
        
    Returns:
        Error message if invalid, None if valid
    """
    k = key.strip()
    if not k:
        return "Project key is required."
    if len(k) != 3:
        return "Project key must be exactly 3 characters."
    if not k.isalpha():
        return "Project key must contain letters only (A–Z)."
    return None


def validate_project_name_raw(name: str) -> Optional[str]:
    """
    Validate project name
    
    Args:
        name: Project name to validate
        
    Returns:
        Error message if invalid, None if valid
    """
    if not name or not name.strip():
        return "Client name is required."
    return None


# -----------------------------
# Step functions
# -----------------------------

def step_fetch_existing_space_keys() -> List[str]:
    """Fetch existing Confluence space keys"""
    api = init_confluence_native()
    keys = get_existing_space_keys(api)
    return keys


def step_check_project_name_available(project_name: str) -> None:
    """Check if project name is available (raises ValueError if exists)"""
    check_project_name_exists(project_name)


def step_create_project(inputs: BoardCreateInputs) -> Dict[str, str]:
    """
    Create Jira project
    
    Args:
        inputs: Board creation parameters
        
    Returns:
        Dictionary with 'key' and 'id' of created project
        
    Raises:
        JiraAuthenticationError: If authentication fails
        JiraProjectCreationError: If project creation fails
    """
    project_type = inputs.project_type
    template_key = TEMPLATE_MAPPING[project_type]
    lead_account_id = LEAD_USER_MAPPING[inputs.lead_user]

    # Debug: show credentials are present (without exposing them)
    st.write(
        {
            "api_username_present": bool(st.session_state.get("api_username")),
            "api_password_present": bool(st.session_state.get("api_password")),
            "api_username_preview": (st.session_state.get("api_username") or "")[:3]
            + "...",
        }
    )

    created = create_jira_board(
        key=inputs.normalized_key,
        name=inputs.project_name,
        project_type=project_type,
        project_template=template_key,
        lead_account_id=lead_account_id,
    )
    
    # Now returns simple dict with 'key' and 'id'
    return created


def step_assign_schemes(project_id: str) -> None:
    """Assign all required schemes to project"""
    assign_project_workflow_scheme(project_id)
    assign_issue_type_screen_scheme(project_id)
    assign_issue_type_scheme(project_id)
    assign_permission_scheme(project_id)


def step_assign_users_and_groups(
    project_id: str,
    selected_user_account_ids: List[str],
    jira_role_ids: List[int],
    selected_user_groups: List[str],
) -> None:
    """Assign users and groups to project roles"""
    assign_users_to_role_of_jira_board(
        project_id,
        selected_user_account_ids,
        jira_role_ids,
        selected_user_groups,
    )


def step_create_account_issue(project_key: str, project_name_raw: str) -> str:
    """
    Create initial 'Account' issue in project
    
    Args:
        project_key: The project key
        project_name_raw: Raw project name (customer name)
        
    Returns:
        Created issue key
    """
    issue_dict = create_jira_issue(project_name_raw, "Account")
    jira = JIRA(
        JIRA_URL,
        basic_auth=(
            st.session_state["api_username"],
            st.session_state["api_password"],
        ),
    )
    res = jira.create_issue(fields=issue_dict)
    return str(res)


# -----------------------------
# UI helpers
# -----------------------------

def show_access_gates() -> bool:
    """
    Returns True if user may proceed, otherwise shows warning and returns False.
    """
    if not user_is_logged_in():
        st.warning("⚠️ Please log in first via the Authenticate page.")
        return False
    if not user_is_admin():
        st.warning(
            "❌ Sorry, you don't have access to this page. Ask an admin (J.C or S.K.)"
        )
        return False
    return True


def reset_temp_project_state() -> None:
    """Clear temporary project state from session"""
    st.session_state["temp_jira_board_key"] = ""
    st.session_state["temp_jira_board_id"] = ""
    st.session_state["selected_users"] = []
    st.session_state["selected_user_groups"] = []


# -----------------------------
# Main
# -----------------------------

def main():
    st.set_page_config(page_title="Create Jira Board", page_icon="📋")
    st.title("Create Jira Board")

    if not show_access_gates():
        debug_panel()
        return

    # Roles for external users
    jira_role_ids = [JIRA_EXTERNAL_USER_ROLE_ID]

    # ---- Inputs (Board creation) ----
    st.subheader("1) Create Board (Jira Project)")

    lead_user = st.selectbox(
        "Select Account Lead",
        [
            "stephan.kuche",
            "jorge.costa",
            "elena.kuhn",
            "olga.milcent",
            "alex.menuet",
            "yavuz.guney",
            "michael.misterka",
            "ekaterina.mironova",
        ],
        index=0,
    )
    project_key = st.text_input(
        "Enter Board Key",
        max_chars=3,
        help="Use an Alpha-3 UPPERCASE key. If the key is already in use, you won't be able to create a new Board.",
    )
    project_name_raw = st.text_input(
        "Enter Client Name",
        placeholder="Happy Customer",
        help="Naming Convention: Try not to go for a too long version.",
    )

    inputs = BoardCreateInputs(
        lead_user=lead_user,
        project_key=project_key,
        project_name_raw=project_name_raw,
        project_type="business",
    )

    # ---- Validation preview / key availability ----
    key_err = validate_project_key_format(inputs.project_key)
    name_err = validate_project_name_raw(inputs.project_name_raw)

    existing_keys: List[str] = []
    if not key_err:
        # Fetch existing Confluence space keys (once) - for key availability check
        try:
            log_event("INFO", "Fetching existing Confluence space keys")
            existing_keys = step_fetch_existing_space_keys()
            add_step_result(
                "Fetch Confluence space keys", True, {"count": len(existing_keys)}
            )
        except Exception as e:
            fail_step("Fetch Confluence space keys", e)
            st.stop()

        normalized_key = inputs.normalized_key
        if normalized_key not in existing_keys:
            st.success(
                f"✅ The key '{normalized_key}' is valid and available.", icon="✅"
            )
        else:
            st.error(
                f"❌ The key '{normalized_key}' already exists in Confluence (space key conflict)."
            )

    if key_err and project_key:
        st.error(key_err)
    if name_err and project_name_raw:
        st.error(name_err)

    # Check project name exists (server-side)
    if project_name_raw and not name_err:
        try:
            step_check_project_name_available(inputs.project_name)
            st.info(f"ℹ️ Project name looks available: {inputs.project_name}")
        except ValueError as e:
            st.error(str(e))
        except JiraAPIError as e:
            st.error(f"Error checking project name: {str(e)}")

    st.divider()

    # ---- Create button with hard-stop flow ----
    create_clicked = st.button("Create Jira Board", type="primary")

    if create_clicked:
        reset_run_artifacts()
        log_event(
            "INFO",
            "Create Jira Board clicked",
            key=inputs.normalized_key,
            name=inputs.project_name,
        )

        # Re-run validations with hard stops
        if key_err:
            st.error(key_err)
            log_event("WARN", "Validation failed", reason=key_err)
            st.stop()
        if name_err:
            st.error(name_err)
            log_event("WARN", "Validation failed", reason=name_err)
            st.stop()

        normalized_key = inputs.normalized_key
        if existing_keys and normalized_key in existing_keys:
            st.error(
                f"❌ Key '{normalized_key}' is not available (Confluence space key exists)."
            )
            log_event("WARN", "Key conflict with Confluence", key=normalized_key)
            st.stop()

        # Create project
        try:
            with st.status("Creating Jira project…", expanded=True) as status:
                created = step_create_project(inputs)
                add_step_result(
                    "Create Jira project",
                    True,
                    {"created": {"key": created.get("key"), "id": created.get("id")}},
                )
                status.update(
                    label="✅ Jira project created", state="complete", expanded=False
                )

        except JiraAuthenticationError as e:
            fail_step("Authentication", e)
            st.error(
                "💡 **Tip**: Go to the Authenticate page and re-enter your credentials."
            )
            st.stop()
        except JiraProjectCreationError as e:
            fail_step("Create Jira project", e)
            st.stop()
        except Exception as e:
            fail_step("Create Jira project", e)
            st.stop()

        # Extract key and id from response
        created_key = created.get("key")
        created_id = created.get("id")

        if not created_key or not created_id:
            error_msg = "Jira returned an unexpected response (missing 'key' or 'id')."
            st.error(f"❌ {error_msg}")
            log_event("ERROR", error_msg, response=created)
            add_step_result("Validate create response", False, {"response": created})
            st.stop()

        # Persist in session state (single source of truth)
        st.session_state["temp_jira_board_key"] = created_key
        st.session_state["temp_jira_board_id"] = created_id

        try:
            save_jira_project_key(created_key)
            add_step_result("Save project key", True, {"key": created_key})
        except Exception as e:
            fail_step("Save project key", e)
            st.stop()

        st.success(
            f"✅ Project {inputs.project_name} created! (Key: {created_key})"
        )

        # Assign schemes
        try:
            with st.status("Assigning schemes…", expanded=True) as status:
                step_assign_schemes(created_id)
                add_step_result(
                    "Assign schemes", True, {"project_id": created_id}
                )
                status.update(
                    label="✅ Schemes assigned", state="complete", expanded=False
                )
        except JiraAPIError as e:
            fail_step("Assign schemes", e)
            st.stop()
        except Exception as e:
            fail_step("Assign schemes", e)
            st.stop()

        st.session_state["last_success"] = {
            "project": {
                "key": created_key,
                "id": created_id,
                "name": inputs.project_name,
            },
            "inputs": {**asdict(inputs), "project_key": inputs.normalized_key},
        }

    # ---- User assignment section (only after project creation) ----
    if st.session_state.get("temp_jira_board_key"):
        st.subheader("2) Assign Users / Groups to Project")

        project_id = st.session_state["temp_jira_board_id"]
        project_key_created = st.session_state["temp_jira_board_key"]

        # Fetch users/groups outside the form so errors are visible immediately
        try:
            users = get_assignable_users(ASSIGNABLE_USER_GROUP)
            user_options = {u["displayName"]: u["accountId"] for u in users}
            user_names = list(user_options.keys())
            add_step_result(
                "Fetch assignable users", True, {"count": len(user_names)}
            )
        except JiraAPIError as e:
            fail_step("Fetch assignable users", e)
            st.stop()
        except Exception as e:
            fail_step("Fetch assignable users", e)
            st.stop()

        try:
            user_groups = get_all_groups(group_alias="partner")
            add_step_result("Fetch partner groups", True, {"count": len(user_groups)})
        except JiraAPIError as e:
            fail_step("Fetch partner groups", e)
            st.stop()
        except Exception as e:
            fail_step("Fetch partner groups", e)
            st.stop()

        with st.form("user_selection_form"):
            selected_users = st.multiselect(
                "Select one or more users",
                user_names,
                default=st.session_state.get("selected_users", []),
            )
            selected_user_groups = st.multiselect(
                "Select external User Groups",
                user_groups,
                default=st.session_state.get("selected_user_groups", []),
            )
            submit_button = st.form_submit_button("Submit Selection")

        if submit_button:
            reset_run_artifacts()
            log_event(
                "INFO",
                "User assignment submitted",
                project_id=project_id,
                project_key=project_key_created,
            )

            st.session_state["selected_users"] = selected_users
            st.session_state["selected_user_groups"] = selected_user_groups

            selected_user_account_ids = [user_options[name] for name in selected_users]

            # Step: Assign users/groups to role
            try:
                with st.status(
                    "Assigning users/groups to roles…", expanded=True
                ) as status:
                    step_assign_users_and_groups(
                        project_id=project_id,
                        selected_user_account_ids=selected_user_account_ids,
                        jira_role_ids=jira_role_ids,
                        selected_user_groups=selected_user_groups,
                    )
                    add_step_result(
                        "Assign users/groups to project role",
                        True,
                        {
                            "project_id": project_id,
                            "user_count": len(selected_user_account_ids),
                            "group_count": len(selected_user_groups),
                            "role_ids": jira_role_ids,
                        },
                    )
                    status.update(
                        label="✅ Users & groups assigned",
                        state="complete",
                        expanded=False,
                    )
                st.success("✅ Users/groups successfully assigned.")
            except JiraAPIError as e:
                fail_step("Assign users/groups to project role", e)
                st.stop()
            except Exception as e:
                fail_step("Assign users/groups to project role", e)
                st.stop()

            # Step: Create Account issue
            try:
                with st.status('Creating "Account" issue…', expanded=True) as status:
                    issue_key = step_create_account_issue(
                        project_key_created,
                        project_name_raw=inputs.project_name_raw,
                    )
                    add_step_result(
                        'Create "Account" issue', True, {"issue": issue_key}
                    )
                    status.update(
                        label='✅ "Account" issue created',
                        state="complete",
                        expanded=False,
                    )
                st.success(f'✅ New Issue Type "Account" created: {issue_key}')
            except Exception as e:
                fail_step('Create "Account" issue', e)
                st.stop()

            # Final: reset temp state so the flow doesn't repeat accidentally
            reset_temp_project_state()
            st.info("✅ Flow completed. Temporary project state reset.")

    debug_panel()


if __name__ == "__main__":
    main()
