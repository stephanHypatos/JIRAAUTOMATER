import streamlit as st
from jira import JIRA
import pandas as pd 

from modules.jira_operations import delete_jira_issue,create_jira_issue,get_issue_key,add_issue_links,create_issues_from_excel,get_issues_from_jira,update_issue_overview_sheet,update_jira_issues,has_cf,compute_dates,get_issues_from_jira_to_update,get_issues_from_jira_v2,update_dates_for_blocked_issues,get_jira_project_key,save_jira_project_key,save_credentials,save_jql,get_project_keys,save_jira_project_type,get_blue_print_filepath,get_jira_issue_type_account_key,save_jira_account_type_parent
from modules.config import JIRA_URL

st.set_page_config(page_title="Delete Jira Project", page_icon="🚨")
st.title('Delete Jira Issue')

# Initialize session state for JIRA API credentials if not already done
if 'api_username' not in st.session_state:
    st.session_state['api_username'] = ''
if 'api_password' not in st.session_state:
    st.session_state['api_password'] = ''
if 'jira_project_key' not in st.session_state:
    st.session_state['jira_project_key'] = ''

jira_issue = st.text_input("Provide Jira Issue-Key")

st.warning("WARNING: This will delete the provided Jira Issue including all its children! You can delete issues of type: project, epic or task. You cant delete issues of type account",icon="⚠️")
if st.button("Delete Jira Ussue"):
    if not jira_issue:
        st.warning("Please provide Jira Issue Key.")
    else:   
        if st.session_state['api_username'] and st.session_state['api_password']:
            jira = JIRA(JIRA_URL, basic_auth=(st.session_state['api_username'], st.session_state['api_password']))
        else:
            st.warning("Please provide Jira credentials.")

        with st.container(height=500):
                try:
                    delete_jira_issue(jira,jira_issue)
                    st.success("Deleted issue(s) in Jira.")
                except Exception as e:
                    st.warning(f"Error Msg: {e}")