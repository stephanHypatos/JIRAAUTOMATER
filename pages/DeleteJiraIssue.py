# pages/DeleteJiraIssue.py  (v3-only)

import streamlit as st
from modules.config import JIRA_URL
from modules.jira_v3 import JiraV3
from modules.jira_operations import delete_jira_issue

st.set_page_config(page_title="Delete Jira Issue", page_icon="🚨")
st.title("Delete Jira Issue")

# Session defaults
if "api_username" not in st.session_state:
    st.session_state["api_username"] = ""
if "api_password" not in st.session_state:
    st.session_state["api_password"] = ""
if "jira_project_key" not in st.session_state:
    st.session_state["jira_project_key"] = ""

jira_issue = st.text_input("Provide Jira Issue Key")

st.warning(
    "WARNING: This will delete the provided Jira issue **and all its children**!\n\n"
    "You can delete issues of type: Project (issue type), Epic, or Task. "
    "You **cannot** delete issues of type *Account*.",
    icon="⚠️",
)

if st.button("Delete Jira Issue"):
    if not jira_issue:
        st.warning("Please provide a Jira Issue Key.")
    elif not (st.session_state["api_username"] and st.session_state["api_password"]):
        st.warning("Please provide Jira credentials (username & API token) on the Authenticate page.")
    else:
        client = JiraV3(JIRA_URL, st.session_state["api_username"], st.session_state["api_password"])
        with st.container():
            try:
                delete_jira_issue(client, jira_issue)
                st.success("Deleted issue(s) in Jira.")
            except Exception as e:
                st.warning(f"Error: {e}")
