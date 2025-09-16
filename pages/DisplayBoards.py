import streamlit as st
from modules.config import JIRA_URL
from modules.jira_operations import get_company_managed_projects_df

st.set_page_config(page_title="Display Jira Boards", page_icon="🗂")
st.title("Jira Boards")

# Session defaults
if "api_username" not in st.session_state:
    st.session_state["api_username"] = ""
if "api_password" not in st.session_state:
    st.session_state["api_password"] = ""
if "jira_project_key" not in st.session_state:
    st.session_state["jira_project_key"] = ""

st.write('Overview of all Jira Boards that are **company-managed**.')

if not (st.session_state["api_username"] and st.session_state["api_password"]):
    st.warning("Please provide Jira credentials (username & API token) on the Authenticate page.")
else:
    try:
        df = get_company_managed_projects_df(
            JIRA_URL,
            st.session_state["api_username"],
            st.session_state["api_password"],
        )
        if df.empty:
            st.info("No company-managed projects found (or none visible with your account).")
        else:
            st.dataframe(df, use_container_width=True)
    except Exception as e:
        st.error(f"Failed to load projects: {e}")
