import streamlit as st
from jira import JIRA
import pandas as pd
from modules.config import JIRA_EPIC_ISSUE_TYPE, JIRA_TASK_ISSUE_TYPE, JIRA_SUBTASK_ISSUE_TYPE,JIRA_URL
from modules.jira_operations import get_company_managed_projects_df

st.set_page_config(page_title="Display Jira Boards", page_icon="🗂")
st.title('Jira Boards')

# Initialize session state for JIRA API credentials if not already done
if 'api_username' not in st.session_state:
    st.session_state['api_username'] = ''
if 'api_password' not in st.session_state:
    st.session_state['api_password'] = ''
if 'jira_project_key' not in st.session_state:
    st.session_state['jira_project_key'] = ''


st.write('Overview of all Jira Boards that are "company-managed"')    

# Get a DataFrame with Projects amd Keys
df = get_company_managed_projects_df(JIRA_URL, st.session_state['api_username'], st.session_state['api_password'])

# Display the DataFrame
st.dataframe(df, use_container_width=True)