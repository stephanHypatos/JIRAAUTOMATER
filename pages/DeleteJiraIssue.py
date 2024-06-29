import streamlit as st
from jira import JIRA
import pandas as pd 
from modules.jira_operations import delete_jira_issue
from modules.config import JIRA_URL

st.set_page_config(page_title="Delete Jira Issue", page_icon="🚨")
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