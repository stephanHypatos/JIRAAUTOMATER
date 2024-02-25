import streamlit as st
from jira import JIRA
import pandas as pd
from modules.config import JIRA_EPIC_ISSUE_TYPE, JIRA_TASK_ISSUE_TYPE, JIRA_SUBTASK_ISSUE_TYPE,JIRA_URL


# Initialize session state for JIRA API credentials if not already done
if 'api_username' not in st.session_state:
    st.session_state['api_username'] = ''
if 'api_password' not in st.session_state:
    st.session_state['api_password'] = ''
if 'jira_project_key' not in st.session_state:
    st.session_state['jira_project_key'] = ''


st.set_page_config(page_title="Get Jira Projects", page_icon="🗂")

st.title('List Jira Projects')

st.write('This table gives you an overview about all Jira project Keys and Names company-managed ')    


def get_company_managed_projects_df(jira_url, username, password):
    # Connect to the JIRA server
    jira = JIRA(jira_url, basic_auth=(username, password))
    
    # Retrieve all projects visible to the user
    projects = jira.projects()
    
    # Filter and prepare the data for company-managed projects

    excluded_keys = {'OKR', 'FIPR', 'REQMAN', 'MBZ', 'T3S', 'SKK', 'PMO', 'TESTC', 'DUR', 'PS', 'PE'}
    data = [{'Key': project.key, 'Name': project.name} for project in projects if project.projectTypeKey == 'business' and project.key not in excluded_keys]

    # Create a DataFrame from the filtered data
    df = pd.DataFrame(data)
    return df

# Populate the DF
df = get_company_managed_projects_df(JIRA_URL, st.session_state['api_username'], st.session_state['api_password'])
# Display the DataFrame
st.dataframe(df, use_container_width=True)