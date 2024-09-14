import streamlit as st
from jira import JIRA
from modules.jira_operations import generate_jql, save_jira_project_key,save_jql,get_jira_project_key,get_project_keys,get_jira_issue_type_project_key,save_jira_issue_type_project,get_users_from_jira_project,create_report_dataframe,filter_dataframe
from modules.config import JIRA_ACCOUNT_ISSUE_TYPE,JIRA_PROJECT_ISSUE_TYPE,JIRA_EPIC_ISSUE_TYPE, JIRA_TASK_ISSUE_TYPE, JIRA_SUBTASK_ISSUE_TYPE,JIRA_URL
from modules.powerpoint_operations import create_powerpoint
from modules.utils import get_calendar_week
    
st.set_page_config(page_title="Create Report", page_icon="📊")
st.title('Create Report :file_folder:')

# Initialize session state for JIRA API credentials if not already done
if 'api_username' not in st.session_state:
    st.session_state['api_username'] = ''
if 'api_password' not in st.session_state:
    st.session_state['api_password'] = ''
if 'jira_project_key' not in st.session_state:
    st.session_state['jira_project_key'] = ''
if 'jira_issue_type_project' not in st.session_state:
    st.session_state['jira_issue_type_project'] = ''
if 'data_frame_for_report' not in st.session_state:
    st.session_state['data_frame_for_report'] = ''


with st.expander("Expand to read the instructions!"):
    st.markdown(
        """
        With this tool you can easily create your weekly status reports. The output format is a powerpoint slide deck. 
        
        ### Prerequisite: 
        - Template for your weekly report is uploaded to Github
        - Jira API credentials - see Authenticate
        
        ### How does it work? 


        1. Select a JIRA Board by choosing a the Board Key
        2. Select a JIRA Issue type "project" from the given JIRA Board
        3. Click "Fetch Issue"
        4. Filter according to your needs. ( You can also select specific issues by selecting one or several id's)
        5. Click "Apply Filter"
        6. Click "Create Status Report"
        7. Click  "Download Power Point Status Report"
        
    """
    )

# Step 1: Select Jira Board
project_keys = get_project_keys(JIRA_URL, st.session_state['api_username'], st.session_state['api_password'])
project = st.selectbox("Select Jira Board", project_keys, index=0)

# If the selected project changes, clear session state data
if 'selected_project' not in st.session_state or st.session_state['selected_project'] != project:
    st.session_state['df'] = None  # Clear the existing dataframe
    st.session_state['selected_project'] = project  # Track the selected project

save_jira_project_key(project)

# Step 2: Select a Project from the selected Jira Board
if st.session_state['jira_project_key']:
    jira = JIRA(JIRA_URL, basic_auth=(st.session_state['api_username'], st.session_state['api_password']))
    
    # Get all Projects (Issue Types)
    jira_projects = get_jira_issue_type_project_key(JIRA_URL, st.session_state['api_username'], st.session_state['api_password'])
    project_issue_key = st.selectbox("Select a Project from the given Jira Board", jira_projects, index=0)
    
    # Clear DataFrame if a new project issue key is selected
    if 'selected_project_issue_key' not in st.session_state or st.session_state['selected_project_issue_key'] != project_issue_key:
        st.session_state['df'] = None  # Clear the existing dataframe
        st.session_state['selected_project_issue_key'] = project_issue_key  # Track the selected project issue key

    # Step 3: Fetch data only after a project issue key is selected
    if project_issue_key:
        if st.button("Fetch Issues"):
            # Fetch issues and store them in session state
            if 'df' not in st.session_state or st.session_state['df'] is None:
                st.session_state['df'] = create_report_dataframe(jira, project_issue_key)
                st.success("Issues fetched and stored!")
            else:
                st.warning("Issues already fetched. You can apply filters.")
        
        # Display the fetched DataFrame
        if 'df' in st.session_state and st.session_state['df'] is not None:
            st.write("Fetched Issues:")
            st.write(st.session_state['df'])
        
            # Step 4: Apply Filters (Only if data is available)
            df = st.session_state['df']
            
            # Issue Type Filter
            issue_type = st.multiselect('Select Issue Type:', options=df['Issue Type'].unique()) if 'Issue Type' in df.columns else []
            
            # Status Filter
            statuses = st.multiselect('Select Status:', options=df['Status'].unique()) if 'Status' in df.columns else []
            
            # Owner Filter
            owner_list = st.multiselect('Select Owner:', options=df['Owner'].unique()) if 'Owner' in df.columns else []
            
            #Ids selected by user
            selected_rows = st.multiselect('Select issues to filter by ID:',options=df['Id'].unique())

            # Days Filter (Filter by Due Date range)
            days = st.slider('Due in next X days:', 0, 30, 0)
            
            # Apply Filters when button is clicked
            if st.button('Apply Filters'):
                st.session_state['data_frame_for_report'] = filter_dataframe(
                    df=df,
                    issue_type=issue_type,
                    statuses=statuses,
                    days=days,
                    owner_list=owner_list,
                    selected_rows=selected_rows
                )
                
                st.write("Filtered Issues:")
                st.write(st.session_state['data_frame_for_report'])
                
        else:
            st.warning("No data available to filter. Please fetch the issues first.")

    if not st.session_state['data_frame_for_report'].empty:
        if st.button("Create Status Report"):
            
            presentation_path= create_powerpoint(st.session_state['data_frame_for_report'])
            st.success("Weekly Report created.")
            # Create a download button in the Streamlit app
            with open(presentation_path, "rb") as f:
                st.download_button(
                    label="Download PowerPoint Status Report",
                    data=f,
                    #file_name="presentation.pptx",
                    file_name=f'{get_jira_project_key()}_Weekly_Status_Report_CW_{get_calendar_week()}.pptx',
                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation"
                )
