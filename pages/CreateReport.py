import streamlit as st
from jira import JIRA
from modules.jira_operations import generate_jql, save_jira_project_key,save_jql,get_jira_project_key
from modules.config import JIRA_EPIC_ISSUE_TYPE, JIRA_TASK_ISSUE_TYPE, JIRA_SUBTASK_ISSUE_TYPE,JIRA_URL
from modules.powerpoint_operations import create_powerpoint
from modules.utils import get_calendar_week

# Initialize session state for JIRA API credentials if not already done
if 'api_username' not in st.session_state:
    st.session_state['api_username'] = ''
if 'api_password' not in st.session_state:
    st.session_state['api_password'] = ''
if 'jira_project_key' not in st.session_state:
    st.session_state['jira_project_key'] = ''


st.set_page_config(page_title="Create Report", page_icon="📊")

st.title('Create Report')
with st.expander("Expand to read the instructions!"):
    st.markdown(
        """
        With this tool you can easily create your weekly status reports. The output format is a powerpoint slide deck. 
        
        ## How does it work? 
        1. Create a Jira Query using the form below in order to select Jira issues for your report. You can either construt the query or provide you custom query in JQL format.
        2. Click "Generate JQL" - You will see the output below.
        3. Click "Create Status Report"
        4. A Download Button will appear
        5. Download your slidedeck
        
    """
    )


with st.form("jql_form", clear_on_submit=False):
    # Example selections - these could be dynamically generated based on your JIRA setup
    project = st.selectbox("Select Project", ["", "FNK", "SKK", "KTM"], index=0)
    issue_type = st.selectbox("Select Issue Type", ["", JIRA_EPIC_ISSUE_TYPE, JIRA_TASK_ISSUE_TYPE, JIRA_SUBTASK_ISSUE_TYPE], index=0)
    status = st.selectbox("Select Status", ["", "Open", "In Progress", "Done"], index=0)
    parent = st.text_input("Parent Issue(s) (Want to input >1 issue? Use a comma i.e. 23,12,12)")
    days = st.slider('Select days to due', 0, 30)
    st.markdown('Or Input Your Custom JQL.')
    manual_jql = st.text_input('Custom JQL ( Project must selected in the dropdown)')
    
    with st.expander('Additional JQLs'):
        st.write('issuetype = "Task" AND due >= startOfDay() AND due <= endOfDay("+21d") || issueType = sub-task AND (parent = "FNK-2464" OR parent = "FNK-2436" OR parent = "FNK-2450")')
    # Form submission button
    submitted = st.form_submit_button("Generate JQL")

if submitted and (project or issue_type or status or parent or manual_jql):
    jql_query = generate_jql(project, issue_type, status,parent,days,manual_jql)
    save_jira_project_key(project)
    save_jql(jql_query)
    st.code(jql_query, language='sql')
else:
    st.write("Please select at least one criteria to generate a JQL query.")

if st.button("Create Status Report"):
    if st.session_state['api_username'] and st.session_state['api_password']:
        jira = JIRA(JIRA_URL, basic_auth=(st.session_state['api_username'], st.session_state['api_password']))
    else:
        st.warning("Please provide Jira credentials.")
    presentation_path= create_powerpoint(jira, st.session_state['jira_query'])
    st.success("Weekly Report created.")
    # Create a download button in the Streamlit app
    with open(presentation_path, "rb") as f:
        st.download_button(
            label="Download PowerPoint presentation",
            data=f,
            #file_name="presentation.pptx",
            file_name=f'{get_jira_project_key()}_Weekly_Status_Report_CW_{get_calendar_week()}.pptx',
            mime="application/vnd.openxmlformats-officedocument.presentationml.presentation"
        )