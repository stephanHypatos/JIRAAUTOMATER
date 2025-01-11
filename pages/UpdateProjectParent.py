from datetime import datetime,timedelta
import streamlit as st
from jira import JIRA
import os
from modules.config import JIRA_URL,ADMINS,JIRA_TEMPLATE_BOARD_KEY
from modules.jira_operations import update_parent_issue_type_project
if 'api_username' not in st.session_state:
     st.session_state['api_username']= ''
if 'api_password' not in st.session_state:
    st.session_state['api_password'] = ''
if 'new_project_name' not in st.session_state:
    st.session_state['new_project_name'] = ''
if 'jira_issue_type_account' not in st.session_state:
    st.session_state['jira_issue_type_account'] = ''
if 'jira_project_key' not in st.session_state:
    st.session_state['jira_project_key'] = ''

def main():
    # Jira connection setup
    jira_url = JIRA_URL
    jira_username = st.session_state['api_username']
    jira_api_token = st.session_state['api_password']
    jira = JIRA(server=jira_url, basic_auth=(jira_username, jira_api_token))
    
    
    if st.session_state['api_password'] == '':
            st.warning("Please log in first.")
    
    else: 
        st.title("Jira project change")
        
        
        
        current_project_key = st.text_input("current project key ")
        target_project_key = st.text_input("new project key ")
         

        if st.button("change project"):
            update_parent_issue_type_project(jira, current_project_key,target_project_key)

if __name__ == "__main__":
    main()
