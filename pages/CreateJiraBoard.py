from __future__ import annotations

from typing import Any, Dict, List

import streamlit as st
from jira import JIRA

from modules.config import (
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


# Initialize session state
for key in ["api_username", "api_password", "temp_jira_board_key", "temp_jira_board_id", 
            "selected_users", "selected_user_groups"]:
    if key not in st.session_state:
        st.session_state[key] = "" if "temp" in key or "api" in key else []


def user_is_logged_in() -> bool:
    return bool(st.session_state.get("api_username")) and bool(st.session_state.get("api_password"))


def user_is_admin() -> bool:
    return st.session_state.get("api_username") in ADMINS


def validate_key(key: str) -> str:
    """Returns error message or empty string if valid"""
    k = key.strip().upper()
    if not k:
        return "Project key is required"
    if len(k) != 3:
        return "Project key must be exactly 3 characters"
    if not k.isalpha():
        return "Project key must contain only letters (A-Z)"
    return ""


def get_confluence_keys() -> List[str]:
    api = ConfluenceAPI(
        base_url=JIRA_URL_CONFLUENCE,
        email=st.session_state["api_username"],
        api_token=st.session_state["api_password"],
    )
    return get_existing_space_keys(api)


def main():
    st.set_page_config(page_title="Create Jira Board", page_icon="📋")
    st.title("Create Jira Board")

    # Check access
    if not user_is_logged_in():
        st.warning("⚠️ Please log in first via the Authenticate page")
        return
    if not user_is_admin():
        st.warning("❌ Admin access required")
        return

    # ===== SECTION 1: CREATE PROJECT =====
    st.subheader("1) Create Board")
    
    lead_user = st.selectbox(
        "Select Account Lead",
        ["stephan.kuche", "jorge.costa", "elena.kuhn", "olga.milcent", 
         "alex.menuet", "yavuz.guney", "michael.misterka", "ekaterina.mironova"],
    )
    
    project_key = st.text_input("Enter Board Key (3 letters)", max_chars=3).upper()
    project_name_raw = st.text_input("Enter Client Name")

    # Validate key format
    key_error = validate_key(project_key) if project_key else ""
    if key_error:
        st.error(key_error)
    
    # Check key availability
    if project_key and not key_error:
        try:
            existing_keys = get_confluence_keys()
            if project_key in existing_keys:
                st.error(f"❌ Key '{project_key}' already exists in Confluence")
            else:
                st.success(f"✅ Key '{project_key}' is available")
        except Exception as e:
            st.error(f"Error checking key: {e}")

    st.divider()

    # Create button
    if st.button("Create Jira Board", type="primary"):
        # Final validation
        if key_error:
            st.error(key_error)
            st.stop()
        if not project_name_raw.strip():
            st.error("Client name is required")
            st.stop()

        # Check key availability one more time
        try:
            existing_keys = get_confluence_keys()
            if project_key in existing_keys:
                st.error(f"❌ Key '{project_key}' already exists")
                st.stop()
        except Exception as e:
            st.error(f"Error checking key: {e}")
            st.stop()

        # Create project
        project_name = f"{project_name_raw.strip()} x Hypatos"
        template_key = TEMPLATE_MAPPING["business"]
        lead_account_id = LEAD_USER_MAPPING[lead_user]

        try:
            with st.spinner("Creating project..."):
                result = create_jira_board(
                    key=project_key,
                    name=project_name,
                    project_type="business",
                    project_template=template_key,
                    lead_account_id=lead_account_id,
                )
            
            created_key = result.get("key")
            created_id = result.get("id")
            
            if not created_key or not created_id:
                st.error("❌ Failed to create project: Missing key or id in response")
                st.stop()
            
            # Save to session
            st.session_state["temp_jira_board_key"] = created_key
            st.session_state["temp_jira_board_id"] = created_id
            save_jira_project_key(created_key)
            
            # Assign schemes
            with st.spinner("Assigning schemes..."):
                assign_project_workflow_scheme(created_id)
                assign_issue_type_screen_scheme(created_id)
                assign_issue_type_scheme(created_id)
                assign_permission_scheme(created_id)
            
            project_url = f"https://hypatos.atlassian.net/jira/core/projects/{created_key}/board"
            
            st.success(f"✅ Project created successfully!")
            st.info(f"**Key:** {created_key}")
            st.info(f"**URL:** {project_url}")
            
        except JiraAuthenticationError as e:
            st.error(f"❌ Authentication failed: {e}")
            st.info("💡 Go to Authenticate page and re-enter credentials")
            st.stop()
        except JiraProjectCreationError as e:
            st.error(f"❌ Project creation failed: {e}")
            st.stop()
        except Exception as e:
            st.error(f"❌ Error: {e}")
            st.stop()

    # ===== SECTION 2: ASSIGN USERS/GROUPS =====
    if st.session_state.get("temp_jira_board_key"):
        st.divider()
        st.subheader("2) Assign Users & Groups")
        
        project_id = st.session_state["temp_jira_board_id"]
        project_key = st.session_state["temp_jira_board_key"]
        
        # Fetch users and groups
        try:
            users = get_assignable_users(ASSIGNABLE_USER_GROUP)
            user_options = {u["displayName"]: u["accountId"] for u in users}
            user_names = list(user_options.keys())
        except Exception as e:
            st.error(f"Error fetching users: {e}")
            user_names = []
            user_options = {}
        
        try:
            user_groups = get_all_groups(group_alias="partner")
        except Exception as e:
            st.error(f"Error fetching groups: {e}")
            user_groups = []
        
        with st.form("user_selection_form"):
            selected_users = st.multiselect(
                "Select users",
                user_names,
                default=st.session_state.get("selected_users", []),
            )
            selected_user_groups = st.multiselect(
                "Select external user groups",
                user_groups,
                default=st.session_state.get("selected_user_groups", []),
            )
            submit = st.form_submit_button("Assign Users & Groups")
        
        if submit:
            st.session_state["selected_users"] = selected_users
            st.session_state["selected_user_groups"] = selected_user_groups
            
            selected_account_ids = [user_options[name] for name in selected_users]
            
            try:
                with st.spinner("Assigning users and groups..."):
                    assign_users_to_role_of_jira_board(
                        project_id,
                        selected_account_ids,
                        [JIRA_EXTERNAL_USER_ROLE_ID],
                        selected_user_groups,
                    )
                st.success("✅ Users and groups assigned")
                
                # Create Account issue
                with st.spinner("Creating Account issue..."):
                    issue_dict = create_jira_issue(project_name_raw, "Account")
                    jira = JIRA(JIRA_URL, basic_auth=(
                        st.session_state["api_username"],
                        st.session_state["api_password"]
                    ))
                    issue = jira.create_issue(fields=issue_dict)
                st.success(f"✅ Account issue created: {issue}")
                
                # Clear temp state
                st.session_state["temp_jira_board_key"] = ""
                st.session_state["temp_jira_board_id"] = ""
                st.session_state["selected_users"] = []
                st.session_state["selected_user_groups"] = []
                st.info("✅ Complete! You can create another board now.")
                
            except Exception as e:
                st.error(f"❌ Error: {e}")


if __name__ == "__main__":
    main()
