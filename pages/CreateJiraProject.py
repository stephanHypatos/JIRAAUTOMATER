import streamlit as st
from jira import JIRA
import pandas as pd

from modules.excel_operations import read_excel
from modules.jira_operations import create_jira_issue,get_issue_key,add_issue_links,create_issues_from_excel,get_issues_from_jira,update_issue_overview_sheet,update_jira_issues,has_cf,compute_dates,get_issues_from_jira_to_update,get_issues_from_jira_v2,update_dates_for_blocked_issues,get_jira_project_key,save_jira_project_key,save_credentials,save_jql
from modules.config import EXCEL_FILE_PATH_BLUE_PRINT,EXCEL_FILE_PATH,JIRA_URL

# Initialize session state for JIRA API credentials if not already done
if 'api_username' not in st.session_state:
    st.session_state['api_username'] = ''
if 'api_password' not in st.session_state:
    st.session_state['api_password'] = ''
if 'jira_project_key' not in st.session_state:
    st.session_state['jira_project_key'] = ''


st.set_page_config(page_title="Create Jira Project", page_icon="📊")
st.title('Create Jira Project :construction_worker:')

preparationTime = None
#project_startdate = pd.to_datetime('2024-01-01')  

with st.expander("Upload a project BLUE PRINT (not yet available)"):
    # Allow user to upload an Excel file
    uploaded_file = None #st.file_uploader("Upload an BLUE PRINT excel file", type=["xls", "xlsx"])

project = st.selectbox("Select Project", ["", "FNK", "SKK", "KTM","WHL"], index=0)
project_startdate_raw = st.text_input('Project Startdate','2024-01-01')
project_startdate = pd.to_datetime(project_startdate_raw)
save_jira_project_key(project)

st.write('Your project starts at: ', project_startdate)
st.write(st.session_state['jira_project_key'])

if st.button("Create Jira Project"):
    
    if st.session_state['api_username'] and st.session_state['api_password']:
        jira = JIRA(JIRA_URL, basic_auth=(st.session_state['api_username'], st.session_state['api_password']))
    else:
        st.warning("Please provide Jira credentials.")

    if uploaded_file:
       pass
        #excel_data_blue_print = read_excel(uploaded_file)
    
    if not st.session_state['jira_project_key']:
        st.warning("Please provide Jira Project Key.")
    
    else: 
        
        excel_data_blue_print = read_excel(EXCEL_FILE_PATH_BLUE_PRINT)
        create_issues_from_excel(jira, excel_data_blue_print,project_startdate)
        # after succesful creation of the issues in JIRA the file JiraIssues.xls is updated
        excel_data = read_excel(EXCEL_FILE_PATH)
        issue_data = get_issues_from_jira(jira)
        update_issue_overview_sheet(excel_data, issue_data)
        st.success("Created issues in Jira.")



