# pages/CreateReport.py  — v3-only

import streamlit as st
from modules.utils import get_calendar_week
from modules.jira_v3 import JiraV3
from modules.config import (
    JIRA_URL,
    JIRA_ACCOUNT_ISSUE_TYPE,
    JIRA_PROJECT_ISSUE_TYPE,
    JIRA_EPIC_ISSUE_TYPE,
    JIRA_TASK_ISSUE_TYPE,
    JIRA_SUBTASK_ISSUE_TYPE,
)
from modules.powerpoint_operations import create_powerpoint
from modules.jira_operations import (
    generate_jql,
    save_jira_project_key,
    save_jql,
    get_jira_project_key,
    get_project_keys,                         
    get_jira_issue_type_project_key_with_displayname,          
    save_jira_issue_type_project,
    get_users_from_jira_project,              
    create_report_dataframe,                  
    filter_dataframe,
)

st.set_page_config(page_title="Create Report", page_icon="📊")
st.title('Create Report :file_folder:')

# ---- Session defaults
for k in ("api_username", "api_password", "jira_project_key", "jira_issue_type_project", "data_frame_for_report"):
    st.session_state.setdefault(k, "" if k != "data_frame_for_report" else None)

# ---- How-to (top)
with st.expander("📖 How to use this page", expanded=False):
    st.markdown(
        """
        Create your **weekly status report** as a PowerPoint deck directly from Jira data.

        **Prerequisites**
        - Your report **PowerPoint template** is uploaded in the repo.
        - You have your **Jira Cloud email + API token** (see *Authenticate* page).

        **Steps**
        1. Select a **Jira board** (by key).
        2. Pick a **Project** (issue type “Project”) from that board.
        3. Click **Fetch Issues**.
        4. Use filters (Issue Type / Status / Owner / Due-in-days / specific Ids).
        5. Click **Apply Filters**.
        6. Click **Create Status Report**.
        7. Click **Download PowerPoint Status Report**.

        The slide deck uses your template and the filtered data to fill in the content.
        """
    )

# ---- Build v3 client when creds exist
client = None
if st.session_state["api_password"]:
    client = JiraV3(JIRA_URL, st.session_state["api_username"], st.session_state["api_password"])
else:
    st.warning("Please provide Jira credentials on the Authenticate page.")

# ---- Step 1: Select Jira Board
project_keys = get_project_keys(JIRA_URL, st.session_state["api_username"], st.session_state["api_password"])
project = st.selectbox("Select Jira Board", project_keys, index=0 if project_keys else 0)

# Reset cached df when project changes
if 'selected_project' not in st.session_state or st.session_state['selected_project'] != project:
    st.session_state['df'] = None
    st.session_state['selected_project'] = project

save_jira_project_key(project)

# ---- Step 2: Select a Project (Issue Type) from the chosen board
if st.session_state['jira_project_key']:
    jira_projects = get_jira_issue_type_project_key_with_displayname(client, st.session_state['jira_project_key'])
    project_names = [p["summary"] for p in jira_projects]
    choice = st.selectbox("Select a Project from the given Jira Board", project_names, index=0 if project_names else 0)
    project_issue_key = next((p["key"] for p in jira_projects if p["summary"] == choice), "")

    # Reset cached df when parent project issue changes
    if 'selected_project_issue_key' not in st.session_state or st.session_state['selected_project_issue_key'] != project_issue_key:
        st.session_state['df'] = None
        st.session_state['selected_project_issue_key'] = project_issue_key

    # ---- Step 3: Fetch issues (only after a Project issue is selected)
    if project_issue_key:
        if st.button("Fetch Issues"):
            if st.session_state.get('df') is None:
                if not client:
                    st.warning("Please log in first.")
                else:
                    # v3: pass JiraV3 client
                    st.session_state['df'] = create_report_dataframe(client, project_issue_key)
                    st.success("Issues fetched and stored!")
            else:
                st.info("Issues already fetched. You can apply filters below.")

        # Show fetched data
        if st.session_state.get('df') is not None:
            st.write("Fetched Issues:")
            st.write(st.session_state['df'])

            # ---- Step 4: Filters
            df = st.session_state['df']

            issue_type = st.multiselect('Select Issue Type:', options=df['Issue Type'].unique()) if 'Issue Type' in df.columns else []
            statuses   = st.multiselect('Select Status:', options=df['Status'].unique()) if 'Status' in df.columns else []
            owner_list = st.multiselect('Select Owner:', options=df['Owner'].unique()) if 'Owner' in df.columns else []
            selected_rows = st.multiselect('Select issues to filter by ID:', options=df['Id'].unique()) if 'Id' in df.columns else []

            days = st.slider('Due in next X days (0 = no filter):', 0, 30, 0)

            if st.button('Apply Filters'):
                st.session_state['data_frame_for_report'] = filter_dataframe(
                    df=df,
                    issue_type=issue_type,
                    statuses=statuses,
                    days=days,
                    owner_list=owner_list,
                    selected_rows=selected_rows,
                )
                st.write("Filtered Issues:")
                st.write(st.session_state['data_frame_for_report'])
        else:
            st.warning("No data to filter. Click **Fetch Issues** first.")

        # ---- Step 5–7: Generate + Download PPTX
        if st.session_state.get('data_frame_for_report') is not None:
            if st.button("Create Status Report"):
                try:
                    presentation_path = create_powerpoint(st.session_state['data_frame_for_report'], project_issue_key)
                    st.success("Weekly Report created.")
                    with open(presentation_path, "rb") as f:
                        st.download_button(
                            label="Download PowerPoint Status Report",
                            data=f,
                            file_name=f'{project_issue_key}_Weekly_Status_Report_CW_{get_calendar_week()}.pptx',
                            mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                        )
                except Exception as e:
                    st.error(f"Error creating the report: {e}")
        else:
            st.info("No filtered data yet. Apply filters first.")