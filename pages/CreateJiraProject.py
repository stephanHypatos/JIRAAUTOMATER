import streamlit as st
from jira import JIRA
import pandas as pd 

from modules.excel_operations import read_excel
from modules.jira_operations import create_jira_issue,get_issue_key,add_issue_links,create_issues_from_excel,get_issues_from_jira,update_issue_overview_sheet,update_jira_issues,has_cf,compute_dates,get_issues_from_jira_to_update,get_issues_from_jira_v2,update_dates_for_blocked_issues,get_jira_project_key,save_jira_project_key,save_credentials,save_jql,get_project_keys,save_jira_project_type,get_blue_print_filepath,get_jira_issue_type_account_key,save_jira_account_type_parent
from modules.config import EXCEL_FILE_PATH,JIRA_URL

st.set_page_config(page_title="Create Jira Project", page_icon="🏗️")
st.title('Create Jira Project :construction_worker:')

# Initialize session state for JIRA API credentials if not already done
if 'api_username' not in st.session_state:
    st.session_state['api_username'] = ''
if 'api_password' not in st.session_state:
    st.session_state['api_password'] = ''
if 'jira_project_key' not in st.session_state:
    st.session_state['jira_project_key'] = ''
if 'jira_project_type' not in st.session_state:
    st.session_state['jira_project_type'] = ''
if 'jira_issue_type_account' not in st.session_state:
    st.session_state['jira_issue_type_account'] = ''

preparationTime = None

with st.expander("Upload a project BLUE PRINT FILE (not yet available)"):
    # TO DO - NOT YET IMPLEMENTED Allow user to upload an Excel file
    uploaded_file = None #st.file_uploader("Upload an BLUE PRINT excel file", type=["xls", "xlsx"])

# Get Project Keys from Jira
project_keys = get_project_keys(JIRA_URL, st.session_state['api_username'], st.session_state['api_password'])
# Select Project Key
project = st.selectbox("Select Jira Board", project_keys, index=0)
with st.expander('Expand for more info on how to find the Jira Project Key'):
    st.write('You can find the key of your jira board by clicking on GetProjects on the left.')
save_jira_project_key(project)

# Select and Save Project Type
project_type = st.selectbox("Select Projecttype", ["POC", "PILOT", "ROLLOUT","ROLLOUT_WIL","TEST"], index=0)
with st.expander('Expand for more info about the Project Type'):
    st.markdown("""
          There are two scenarios: 
          - You create a project for the first time choose: POC or ROLLOUT. (A generic Issue Type= "Account" called "CustomerName" will be created this Issue will be the parent of you Project. After successful project creation you can rename this Issue.)
          - You want to create a Rollout project and an Issue Type= "Account" already exists: choose ROLLOUT
          """)
    
save_jira_project_type(project_type)

# Get all Issues in a given project of type Account
if st.session_state['jira_project_key']:
    parent_keys = get_jira_issue_type_account_key(JIRA_URL, st.session_state['api_username'], st.session_state['api_password'])
    # Select Project Parent (most likely an Issue Type Account)
    parent = st.selectbox("Select Parent", parent_keys, index=0)
    with st.expander('Expand for more info about Parent Selction'):
        st.markdown("""
            There are two scenarios: 
            - You want to create a Rollout or a Pilot project and an Issue Type= "Account" already exists, you can select the Key of that Issue that will serve as the parent here. 
            - You dont want to attach the project to a parent, select "No_parent"
            """)
    save_jira_account_type_parent(parent)

# Get the project start date
project_startdate_raw = st.text_input('Project Startdate','2024-01-01')
project_startdate = pd.to_datetime(project_startdate_raw)

st.session_state['project_name_user']= st.text_input('Provide a project name',placeholder="Optional, if empty project name is project type (PILOT, POC,...)")


if st.session_state["jira_project_key"]:
        st.write(f'Jira Project will be created on the Jira Work Management Board: {st.session_state["jira_project_key"]}')
        st.write('Your project starts at: ', project_startdate)
        st.write('Your project will be attached to the parent issue: ', parent)
        if st.session_state["project_name_user"]:
            st.write(f'Your project will be named: {st.session_state["project_name_user"]}')

if st.button("Create Jira Project"):
    
    if st.session_state['api_username'] and st.session_state['api_password']:
        jira = JIRA(JIRA_URL, basic_auth=(st.session_state['api_username'], st.session_state['api_password']))
    else:
        st.warning("Please provide Jira credentials.")

    if uploaded_file:
        pass
        #TO DO excel_data_blue_print = read_excel(uploaded_file) NOT YET IMPLEMENTED
    
    if not st.session_state['jira_project_key']:
        st.warning("Please select Jira Project Key.")
    if not st.session_state['jira_project_type']:
        st.warning("Please select Project Type.")

    else: 
        with st.container(height=300):
            try:
                    # Get the filepath of the respective BlueprintFile
                filepath = get_blue_print_filepath(st.session_state['jira_project_type'])
                excel_data_blue_print = read_excel(filepath)
                create_issues_from_excel(jira, excel_data_blue_print,project_startdate)

                # After succesful creation of the issues in JIRA the file JiraIssues.xls is updated ( Currently this File is not used)
                excel_data = read_excel(EXCEL_FILE_PATH)
                issue_data = get_issues_from_jira(jira)
                update_issue_overview_sheet(excel_data, issue_data)
                st.success("Created issues in Jira.")
            except Exception as e:
                st.warning(f"Error Msg: {e}")
