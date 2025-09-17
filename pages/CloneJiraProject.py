# pages/CloneJiraProject.py

from datetime import datetime, timedelta
import os
import streamlit as st

from modules.jira_v3 import JiraV3
from modules.config import JIRA_URL, ADMINS, JIRA_TEMPLATE_BOARD_KEY

# These helpers should now be v3-aware inside your repo
from modules.jira_operations import (
    get_project_keys,                              # (JIRA_URL, email, token) -> [board_keys]
    get_users_from_jira_project,                   # (client, project_key) -> [assignees]
    get_jira_issue_type_project_key_with_displayname,  # (client, key_or_prefix) -> [{'key','summary',...}]
    display_issue_summaries,                       # (list_of_candidates) -> source_issue_key
    get_jira_issue_type_account_key,               # (JIRA_URL, email, token) -> [account_issue_keys]
    update_parent_key,                             # (client, child_issue_key, parent_issue_key) -> None
    save_jira_account_type_parent,                 # (issue_key) -> None (stores in session)
    save_jira_project_key,                         # (project_key) -> None (stores in session)
    update_parent_issue_type_project,              # (client, child_issue_key, target_project_issue_key) -> None
    delete_newly_created_project                   # (client, child_issue_key) -> None
)

from modules.jira_clone_issue_operations import (
    get_time_delta,                        # (client, project_start_date: date, source_issue_key: str) -> int
    clone_issue_recursive_first_pass,      # (client, source_issue_key, target_project_key, cloned_issues: dict, day_delta: int, project_assignee: str) -> None
    add_issue_links,                       # (client, cloned_issues_mapping: dict) -> None
    update_project_name                    # (client, root_issue_key, new_name) -> None
)

# --- Session defaults ---
if 'api_username' not in st.session_state:
    st.session_state['api_username'] = ''
if 'api_password' not in st.session_state:
    st.session_state['api_password'] = ''
if 'new_project_name' not in st.session_state:
    st.session_state['new_project_name'] = ''
if 'jira_issue_type_account' not in st.session_state:
    st.session_state['jira_issue_type_account'] = ''
if 'jira_project_key' not in st.session_state:
    st.session_state['jira_project_key'] = ''


def _extract_issue_key(value):
    """
    cloned_issues may map source -> string key OR -> object with .key or {'key': ...}.
    This helper normalizes to a string key.
    """
    if isinstance(value, str):
        return value
    if hasattr(value, 'key'):
        return value.key
    if isinstance(value, dict) and 'key' in value:
        return value['key']
    return str(value)


def main():
    # Jira connection setup (Cloud)
    JIRA_BASE_URL = JIRA_URL
    JIRA_EMAIL = st.session_state['api_username']
    JIRA_TOKEN = st.session_state['api_password']
    template_key_prefix = JIRA_TEMPLATE_BOARD_KEY  # avoid shadowing the import name

    if not JIRA_EMAIL or not JIRA_TOKEN:
        st.warning("Please log in first.")
        return

    # Instantiate the lightweight v3 client
    client = JiraV3(JIRA_BASE_URL, JIRA_EMAIL, JIRA_TOKEN)

    # --- UI ---
    st.title("Clone Jira Issue Type Project")
    st.warning(
        "Before you proceed, make sure that your user is in the People section of the **target** Jira board."
    )

    project_start_date = st.date_input("Enter the project start date:", value=None, format="YYYY-MM-DD")

    # 1) Pick source (template) issue from template projects
    #    This function should internally use /project/search and (optionally) /search/jql via the v3 client.
    jira_template_projects = get_jira_issue_type_project_key_with_displayname(client, template_key_prefix)
    source_issue_key = display_issue_summaries(jira_template_projects)
    if not source_issue_key:
        st.stop()  # or st.warning("Pick a source issue"); return

    # 2) Compute the scheduling delta (based on source tree dates and chosen start)
    if project_start_date and source_issue_key:
        delta_days = get_time_delta(client, project_start_date, source_issue_key)
    else:
        delta_days = None

    # 3) Choose target board (where the new hierarchy will be cloned)
    jira_boards = get_project_keys(JIRA_URL, JIRA_EMAIL, JIRA_TOKEN)
    target_project = st.selectbox("Select Target Board Key:", jira_boards, index=0 if jira_boards else None)

    # Persist chosen target board
    if target_project:
        save_jira_project_key(target_project)

    # 4) Assignee, new project name, and parent "Account" issue selection
    if target_project:
        users = get_users_from_jira_project(client, target_project)

        if not users:
            st.warning("No assignable users found for this project.")
            project_assignee = None
        else:
            assignee_obj = st.selectbox(
                "Select Project Assignee:",
                users,
                format_func=lambda u: f"{u['displayName']} ({u['accountId'][:6]}…)" if u else "",
            )
            project_assignee = assignee_obj["accountId"] if assignee_obj else None  # accountId only    

    new_project_name = st.text_input('Provide a project name:', placeholder="My new project")
    st.session_state['new_project_name'] = new_project_name

    # Issue Type "Account" (parent) options come via direct REST helpers
    parent_keys = get_jira_issue_type_account_key(JIRA_URL, JIRA_EMAIL, JIRA_TOKEN)
    parent_issue_key = st.selectbox(
        "Select the issue type 'Account' to which your project should be attached:",
        parent_keys,
        index=0 if parent_keys else None
    )
    if parent_issue_key:
        save_jira_account_type_parent(parent_issue_key)

    # Optional: attach new project under an existing Project issue
    project_keys = get_jira_issue_type_project_key_with_displayname(client, target_project) if target_project else []
    project_keys_names = [proj['summary'] for proj in project_keys]
    project_keys_names.insert(0, None)
    new_project_issue_key_label = st.selectbox(
        "Optional. Attach the new project to an existing Project (Issue Type):",
        project_keys_names,
        index=0
    )
    selected_issue_type_project = next(
        (proj for proj in project_keys if proj['summary'] == new_project_issue_key_label), None
    )

    # --- ACTION: Clone ---
    
    if st.button("Clone Issues"):
        if not (project_start_date and source_issue_key and target_project and project_assignee):
            st.warning("Please enter project start date, source project, target board key, and project assignee.")
            return

        try:
            st.write(f"Cloning issue hierarchy starting from: {source_issue_key}")
            st.write('Cloned Issue Delta Days: ', delta_days)
            st.write('Assignee: ', {assignee_obj["displayName"]})
            st.write('Target Board: ', target_project)
            

            cloned_issues = {}

            # Step 1: Clone all issues (without links)
            clone_issue_recursive_first_pass(
                client,
                source_issue_key,
                target_project= target_project,
                cloned_issues=cloned_issues,
                day_delta=(delta_days or 0),
                project_assignee=project_assignee,
            )

            # Step 2: Create links between cloned issues
            st.write("All issues cloned. Now creating links between issues...")
            add_issue_links(client, cloned_issues)

            # Determine the root of the new clone (mapped from source root)
            new_root_issue_key = _extract_issue_key(cloned_issues.get(source_issue_key))

            # Step 3: Update the project name
            if new_project_name:
                update_project_name(client, new_root_issue_key, new_project_name)

            # Step 4: Update Parent Issue Type Account (if selected)
            if st.session_state.get('jira_issue_type_account') not in ('', None, 'No_Parent'):
                try:
                    update_parent_key(client, new_root_issue_key, st.session_state['jira_issue_type_account'])
                except Exception as e:
                    st.error(f"An error occurred while updating Account parent: {str(e)}")

            # Step 5: Optional — attach under an existing Project issue
            if selected_issue_type_project is not None:
                try:
                    update_parent_issue_type_project(client, new_root_issue_key, selected_issue_type_project["key"])
                    # If your logic requires deleting the initially created "Project" wrapper:
                    delete_newly_created_project(client, new_root_issue_key)
                    st.success(
                        f"Project issues have been created and attached to the Project: "
                        f"{selected_issue_type_project['summary']}"
                    )
                except Exception:
                    st.warning('Unable to change the parent Project (Issue Type).')
            else:
                st.success(
                    f"Project: {st.session_state.get('new_project_name','(unnamed)')} "
                    f"Issue Key: {new_root_issue_key} has been created and assigned to {assignee_obj['displayName']}."
                )

            # Clear project name after success
            st.session_state['new_project_name'] = ''

        except Exception as e:
            st.error(f"An error occurred: {str(e)}")


if __name__ == "__main__":
    main()
