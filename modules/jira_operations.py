from jira import JIRA
import pandas as pd
import streamlit as st
import math
from datetime import datetime,timedelta
from pptx import Presentation
from pptx.util import Inches
from modules.config import JIRA_ACCOUNT_ISSUE_TYPE,JIRA_PROJECT_ISSUE_TYPE,JIRA_EPIC_ISSUE_TYPE, JIRA_TASK_ISSUE_TYPE, JIRA_SUBTASK_ISSUE_TYPE,JIRA_URL,EXCEL_FILE_PATH,EXCEL_FILE_PATH_BLUE_PRINT_PILOT,EXCEL_FILE_PATH_BLUE_PRINT_ROLLOUT,EXCEL_FILE_PATH_BLUE_PRINT_POC,EXCEL_FILE_PATH_BLUE_PRINT_TEST,EXCEL_FILE_PATH_BLUE_PRINT_ROLLOUT_WIL,JIRA_TEMPLATE_BOARD_KEY,EXCLUDED_BOARD_KEYS
from modules.utils import normalize_NaN, normalize_date, calculate_end_date


## generice Jira Auth Function that returns a new instance of JIRA
def authenticate(jira_url,jira_email,jira_api_token):
    
    jira = JIRA(jira_url,basic_auth=(jira_email, jira_api_token))
    return jira

# JIRA Credentials Handling

# Function to store credentials in session state
def save_credentials(username, password):
    if username and password:
        st.session_state['api_username'] = username
        st.session_state['api_password'] = password
        st.success("Credentials stored successfully!")
    else:
        st.warning('Provide Jira Credentials')


# JIRA Project relelated Functions

# Function to update the parent issue key of a given issue
def update_parent_key(jira,issue_key, new_parent_key):
    # Get the issue object for the given issue key
    issue = jira.issue(issue_key)
    # Update the parent field with the new parent issue key
    issue.update(fields={'parent': {'key': new_parent_key}})
    st.write(f"Parent key of issue {issue_key} updated to {new_parent_key}")

# Function to store jira project key in session state
def save_jira_project_key(projektkey):
    st.session_state['jira_project_key'] = projektkey

# Function to store jira project type in session state ( ROLLOUT, POC, PILOT)
def save_jira_project_type(projecttype): 
    st.session_state['jira_project_type'] = projecttype

# Function to store JQL in session state
def save_jql(jql):
    st.session_state['jira_query'] = jql

# Function to get Jira Project Key from session state   
def get_jira_project_key():
    return st.session_state['jira_project_key']



# Function to store the selected Account Parent Issue in session state
def save_jira_account_type_parent(parent):
    st.session_state['jira_issue_type_account'] = parent

# Function to store the selected Project Issue in session state
def save_jira_issue_type_project(project):
    st.session_state['jira_issue_type_project'] = project

# Function retunrns a GLOBAL FILEPATH to Blueprintfile
def get_blue_print_filepath(sessionStateProjectType):
    filepath=None
    if sessionStateProjectType == 'POC':
        filepath=EXCEL_FILE_PATH_BLUE_PRINT_POC
    if sessionStateProjectType == 'PILOT':
        filepath=EXCEL_FILE_PATH_BLUE_PRINT_PILOT
    if sessionStateProjectType == 'ROLLOUT':
        filepath=EXCEL_FILE_PATH_BLUE_PRINT_ROLLOUT
    if sessionStateProjectType == 'ROLLOUT_WIL':
        filepath=EXCEL_FILE_PATH_BLUE_PRINT_ROLLOUT_WIL
    if sessionStateProjectType == 'TEST':
        filepath=EXCEL_FILE_PATH_BLUE_PRINT_TEST
    
    return filepath

# Function to get all keys of company-managed projects in Jira
def get_project_keys(jira_url, username, password):
    # Connect to the JIRA server
    jira = JIRA(jira_url, basic_auth=(username, password))
    
    # Retrieve all projects visible to the user
    projects = jira.projects()
    
    # Extract and return the project keys
    excluded_keys = {'BXIMH','DFM','SE','ROP','OKR', 'FIPR', 'REQMAN', 'MBZ', 'T3S', 'SKK', 'PMO', 'TESTC', 'DUR', 'PS', 'PE', 'TESTB', 'KATE', 'MDG', 'TESTA', 'UGI', 'TESTD', 'TOH', 'MON','DBFM'}
    company_managed_project_keys = [project.key for project in projects if project.projectTypeKey == 'business' and project.key not in excluded_keys]
    select_options = [""]
    select_options.extend(company_managed_project_keys)
    return select_options

# Function returns a list of JIRA ISSUES ON a JWM Board of type= Account
def get_jira_issue_type_account_key(jira_url, username, password):
    jira =  JIRA(jira_url, basic_auth=(username, password))
    project_key = get_jira_project_key()
    query = f'project="{project_key}" AND issuetype="Account"'
    parent_issue_keys = jira.search_issues(query, maxResults=10)
    parent_keys= [project.key for project in parent_issue_keys]
    select_options = ["No_Parent"]
    select_options.extend(parent_keys)
    return select_options

# Function returns a list of JIRA ISSUES ON a JWM Board of type= Project
def get_jira_issue_type_project_key(jira_url, username, password):
    jira =  JIRA(jira_url, basic_auth=(username, password))
    project_key = get_jira_project_key()
    query = f'project="{project_key}" AND issuetype="Project"'
    project_issue_keys = jira.search_issues(query, maxResults=10)
    project_keys= [project.key for project in project_issue_keys]
    select_options = [" "]
    select_options.extend(project_keys)
    return select_options

# Function returns a list of JIRA Project Templates from the Template Board
def get_jira_issue_type_project_key_with_displayname(jira,project_key):
    # the jira board key of the template board
    #project_key = JIRA_TEMPLATE_BOARD_KEY
    query = f'project="{project_key}" AND issuetype="Project"'
    project_issue_keys = jira.search_issues(query, maxResults=10)
    project_keys= [{'key': issue.key, 'summary': issue.fields.summary}for issue in project_issue_keys]
    return project_keys

def display_issue_summaries(issue_list):
    # Extract summaries for display in the selectbox
    issue_summaries = [issue['summary'] for issue in issue_list]
    
    # Display the selectbox with summaries
    selected_summary = st.selectbox("Select Project:", issue_summaries)

    # Find the issue with the selected summary
    selected_issue = next(issue for issue in issue_list if issue['summary'] == selected_summary)
    
    # Pass the key of the selected issue to another function
    
    return selected_issue['key']


# get all child issues of a jira issue
def get_children_issues(jira, issue_key):
    issue = jira.issue(issue_key)
    # List to store children issues
    children_issues = []
    
    #Helper function to find issues linked to the given issue
    def get_linked_issues(issue_key):
        jql = f'"parent" = {issue_key}'
        return jira.search_issues(jql)

    linked_issues=get_linked_issues(issue_key)
    # Add linked issues to the list "children_issues"
    if linked_issues:
        for linked_issue in linked_issues:
            if linked_issue.fields.issuetype.name.lower() == 'epic':
                linked_issues_tasks=get_linked_issues(linked_issue)
                for linked_issues_task in linked_issues_tasks:
                    children_issues.append(linked_issues_task.key)
            children_issues.append(linked_issue.key)
        return children_issues
    return

# updates the parent issue type project of one or more epics 
def update_parent_issue_type_project(jira, current_project_issue_key, new_project_issue_key):
    """
    Update the parent of all issues currently having `current_project_issue_key`
    as their parent, so that they will point to `new_project_issue_key` instead.
    (For team-managed/next-gen projects)
    """
    jql = f'parent = {current_project_issue_key}'
    try:
        children_issues = jira.search_issues(jql)
    except Exception as e:
        st.write(f"Failed to search issues with JQL '{jql}'")
        return

    for child_issue in children_issues:
        child_issue.update(fields={'parent': {'key': new_project_issue_key}})
    return


def delete_newly_created_project(jira,issue_key):
    try:
        issue = jira.issue(issue_key)
        issue.delete(deleteSubtasks=True)
    except Exception as e:
        st.warning(f"Could not delete newly created issue type project: {e}")
    return

# get all child issues of a jira issue
def get_children_issues_ticket_template(jira, issue_key):
    issue = jira.issue(issue_key)
    # List to store children issues
    children_issues = []
    
    #Helper function to find issues linked to the given issue
    def get_linked_issues(issue_key):
        jql = f'"parent" = {issue_key}'
        return jira.search_issues(jql)
    linked_issues=get_linked_issues(issue_key)
    # Add linked issues to the list "children_issues"
    if linked_issues:
        for linked_issue in linked_issues:
            if linked_issue.fields.issuetype.name.lower() == 'epic':
                # children_issues.append(
                # {'key': linked_issue.key,
                # 'summary': linked_issue.fields.summary,
                # 'issuetype': linked_issue.fields.issuetype.name})
                linked_issues_tasks=get_linked_issues(linked_issue)
                for linked_issues_task in linked_issues_tasks:
                    children_issues.append(
                    {'key': linked_issues_task.key,
                    'summary': linked_issues_task.fields.summary,
                    'issuetype': linked_issues_task.fields.issuetype.name})
            # children_issues.append(
            #         {'key': linked_issues_task.key,
            #         'summary': linked_issues_task.fields.summary,
            #         'issuetype': linked_issues_task.fields.issuetype.name})
        return children_issues
    return []

             

def get_children_issues_for_timeline(jira, issue_key):
    issue = jira.issue(issue_key)
    # List to store children issues
    children_issues = []
    
    #Helper function to find issues linked to the given issue
    def get_linked_issues(issue_key):
        jql = f'"parent" = {issue_key}'
        return jira.search_issues(jql)

    linked_issues=get_linked_issues(issue_key)
    # Add linked issues to the list "children_issues"
    if linked_issues:
        for linked_issue in linked_issues:
            if linked_issue.fields.issuetype.name.lower() == 'epic':
                linked_issues_tasks=get_linked_issues(linked_issue)
                for linked_issues_task in linked_issues_tasks:
                    if linked_issues_task.fields.issuetype.name.lower() == 'task':
                        linked_issues_subtasks=get_linked_issues(linked_issues_task)
                        for linked_issues_subtask in linked_issues_subtasks:
                            children_issues.append(linked_issues_subtask.key)        
                    children_issues.append(linked_issues_task.key)
            children_issues.append(linked_issue.key)
        return children_issues
    return


def create_report_dataframe(jira,issuekey):
    """
    Fetches all child issues for a given Jira issue key and returns a DataFrame.
    
    Args:
    - jira: The Jira client object
    - issuekey: The key of the Jira issue to get children for
    
    Returns:
    - df (DataFrame): A DataFrame containing all the children issues.
    """
    # Get issues from Jira using issuekey
    jira_issues = get_children_issues_for_report(jira, issuekey)

    if not jira_issues:
        st.warning(f'The selected project: {issuekey} has no children issues. Choose another project.')
        return pd.DataFrame()  # Return an empty DataFrame

    # Initialize an empty list to store the results
    issue_data = []

    # Iterate over the issue keys and fetch details
    for key in jira_issues:
        try:
            issue = jira.issue(key)
            # Fetch the required fields
            name = issue.fields.summary
            issuetype = issue.fields.issuetype.name
            duedate = issue.fields.duedate
            start_date = issue.fields.customfield_10015
            status = issue.fields.status.name
            owner = getattr(issue.fields.assignee, 'displayName', None)
            ext_owner = issue.fields.customfield_10127

            # Add the data to the list
            issue_data.append({
                'Id': key,
                'Name': name,
                'Due Date': duedate,
                'Start Date': start_date,
                'Status': status,
                'Owner': owner,
                'Ext.Owner': ext_owner,
                'Issue Type': issuetype
            })

        except Exception as e:
            print(f"Error fetching data for issue {key}: {e}")

    # Convert to DataFrame
    df = pd.DataFrame(issue_data)

    # Convert 'Due Date' to datetime and then to date
    df['Due Date'] = pd.to_datetime(df['Due Date'], errors='coerce').dt.date

    # Store the DataFrame in session state for later use
    st.session_state['df'] = df

    return df


def filter_dataframe(df, issue_type=None, statuses=None, days=None, owner_list=None,selected_rows=None):
    """
    Dynamically filters the DataFrame based on the provided conditions.

    Args:
    - df (DataFrame): The DataFrame to be filtered.
    - issue_type (list): List of issue types to filter by.
    - statuses (list): List of statuses to filter by.
    - days (int): Number of days from today to filter 'Due Date'.
    - owner_list (list): List of owners to filter by.
    - selected_rows list: List of ids a user has selected

    Returns:
    - filtered_df (DataFrame): The filtered DataFrame.
    """
    # Start with a filter that includes all rows
    filter_condition = pd.Series([True] * len(df))

    # Filter by issue type
    if issue_type:
        filter_condition &= df['Issue Type'].isin(issue_type)

    # Filter by statuses
    if statuses:
        filter_condition &= df['Status'].isin(statuses)

    # Filter by Due Date if 'days' is provided
    if days is not None and days > 0:
        today = datetime.now().date()
        date_from_today = today + timedelta(days=days)
        filter_condition &= (df['Due Date'].notna()) & (df['Due Date'] >= today) & (df['Due Date'] <= date_from_today)

    # Filter by owner list
    if owner_list:
        filter_condition &= df['Owner'].isin(owner_list)
    
    # Filter by Id selected by User
    if selected_rows:
        filter_condition &= df['Id'].isin(selected_rows)

    # Apply the filter to the DataFrame
    filtered_df = df[filter_condition]

    return filtered_df


def get_users_from_jira_project(jira, project_key):
    
    try:
        # Use search_assignable_users_for_projects to fetch users
        users = jira.search_assignable_users_for_projects('', project_key)
        
        # Extract display names from the user objects
        user_names = [user.displayName for user in users]
        select_options = ['None']
        select_options.extend(user_names)

    except Exception as e:
        print(f"An error occurred: {e}")
        user_names = []
    
    return select_options



### fast fetching of all children issues of a given jira parent issue
def get_children_issues_for_report(jira, issue_key):
    # List to store children issues
    children_issues = []

    # Fetch all issues linked directly as children (epics) of the parent issue
    jql = f'"parent" = {issue_key}'
    linked_issues = jira.search_issues(jql, maxResults=1000)
    
    if not linked_issues:
        return
    # Process fetched issues (initially should be epics or direct tasks)
    for linked_issue in linked_issues:
        children_issues.append(linked_issue.key)

        # If the issue is an epic, fetch all its tasks
        if linked_issue.fields.issuetype.name.lower() == 'epic':
            epic_jql = f'"Epic Link" = {linked_issue.key}'
            epic_tasks = jira.search_issues(epic_jql, maxResults=1000)
            
            # Add tasks and their subtasks
            for epic_task in epic_tasks:
                children_issues.append(epic_task.key)

                # Fetch subtasks for each task (if any)
                if hasattr(epic_task.fields, 'subtasks'):
                    for subtask in epic_task.fields.subtasks:
                        children_issues.append(subtask.key)
        
        # If the issue is a task, fetch all its subtasks directly
        elif linked_issue.fields.issuetype.name.lower() == 'task':
            # Fetch subtasks for each task (if any)
            if hasattr(linked_issue.fields, 'subtasks'):
                for subtask in linked_issue.fields.subtasks:
                    children_issues.append(subtask.key)

    return children_issues

def delete_jira_issue(jira,parent_issue_key):
    if parent_issue_key:
        child_issues = get_children_issues(jira,parent_issue_key)
        if child_issues:
            for issue_key in child_issues:
                issue = jira.issue(issue_key)
                issue.delete(deleteSubtasks=True)
                st.write(f"Jira Issue: {issue} deleted")
                st.empty()
    else: 
        return
    issue = jira.issue(parent_issue_key)
    issue.delete(deleteSubtasks=True)
    st.write(f"Jira Issue: {issue} deleted")
    
    return

def create_jira_issue(summary, issue_type, start_date=None, due_date=None, parent_key=None, description_key=None):
    issue_dict = {
        'project': {'key': get_jira_project_key()},
        'summary': summary,
        'issuetype': {'name': issue_type}
    }
    
    if parent_key:
        issue_dict['parent'] = {'key': parent_key}

    if start_date:
        start_date_normalized = normalize_date(start_date)
        if start_date_normalized:
            issue_dict['customfield_10015'] = start_date_normalized

    if due_date:
        due_date_normalized = normalize_date(due_date)
        if due_date_normalized:
            issue_dict['duedate'] = due_date_normalized
    
    if description_key:
       issue_dict['description'] = description_key

    return issue_dict

def create_jira_issue_ticket_template(board_key,summary, issue_type, start_date=None, due_date=None, parent_key=None, description=None):
    issue_dict = {
        'project': board_key,
        'summary': summary,
        'issuetype': {'name': issue_type},
        'description': description
    }
    
    if parent_key:
        issue_dict['parent'] = {'key': parent_key}

    if start_date:
        start_date_normalized = normalize_date(start_date)
        if start_date_normalized:
            issue_dict['customfield_10015'] = start_date_normalized

    if due_date:
        due_date_normalized = normalize_date(due_date)
        if due_date_normalized:
            issue_dict['duedate'] = due_date_normalized

    return issue_dict

# Get the Jira Issue Key - ( search by using the summary)
def get_issue_key(jira, summary):
    # Find the issue key using the summary
    issues = jira.search_issues(f'project={get_jira_project_key()} AND summary~"{summary}"', maxResults=1)
    return issues[0].key if issues else None

# Add Links between Issues Blocking and Blocked
def add_issue_links(jira, excel_data):
    for index, row in excel_data.iterrows():
        issue_type = row['IssueType']
        link1_key = row.get('SummaryName')
        blocks = normalize_NaN(row.get('Blocks'))

        # Add issue links if link1 is provided
        if link1_key and blocks:
            link1_key_normalized = get_issue_key(jira, link1_key)
            if link1_key_normalized:
                # Split the blocks into a list of individual issue keys
                blocks_list = [block.strip() for block in blocks.split(',')]
                
                for block_key in blocks_list:
                    link2_key_normalized = get_issue_key(jira, block_key)
                    if link2_key_normalized:
                        jira.create_issue_link(
                            type="blocks",
                            inwardIssue=link1_key_normalized,
                            outwardIssue=link2_key_normalized
                        )
                    else:
                        st.write(f"Link2 issue '{block_key}' not found. Skipping link creation.")
            else:
                st.write(f"Link1 issue '{link1_key}' not found. Skipping link creation.")

def create_issues_from_excel(jira, excel_data,project_startdate):
    # Returns a List of Issues with start and enddates

    dates=compute_dates(excel_data, project_startdate)
    # Iterate through rows and create Jira issues and subtasks
    for index, row in excel_data.iterrows():
        summary = row['Summary']
        issue_type = row['IssueType']
        parent_key = row.get('Parent')
        start_date= None
        due_date= None
        # Get Start & End Dates 
        start_date = getIssueDate(dates,summary,date_type='start_date')#row.get('StartDate')
        due_date = getIssueDate(dates,summary,date_type='end_date')#row.get('StartDate')
        description = normalize_NaN(row.get('Description'))

        # Normalize the dates # can be deleted
        start_date_normalized = normalize_date(start_date) if start_date else None
        due_date_normalized = normalize_date(due_date) if due_date else None

        # Check if parent_key is NaN
        if isinstance(parent_key, float) and math.isnan(parent_key):
            parent_key = None  # Set to None if NaN

        ###### NEW START
        if issue_type == JIRA_ACCOUNT_ISSUE_TYPE:
            # Create only the Account issue
            if parent_key is not None:
                st.write("An Account can't have a parent. Skipping Account Issue creation.")
            else:
                
                issue_dict = create_jira_issue(summary, JIRA_ACCOUNT_ISSUE_TYPE, start_date, due_date, description_key=description)
                account_issue = jira.create_issue(fields=issue_dict)
                st.write(f"Created Jira Issue Type Account: {account_issue.key} - Summary: {account_issue.fields.summary}")    

        elif issue_type == JIRA_PROJECT_ISSUE_TYPE:
            # Check if the issue has a parent issue
            if parent_key is not None:
                # Find parent issue using summary
                parent_issue = jira.search_issues(f'project={get_jira_project_key()} AND summary~"{parent_key}"', maxResults=1)

                if parent_issue:
                    parent_key = parent_issue[0].key
                    issue_dict = create_jira_issue(summary, JIRA_PROJECT_ISSUE_TYPE, start_date, due_date, parent_key,description)
                    project_issue = jira.create_issue(fields=issue_dict)
                    st.write(f"Created Jira Issue Type Project: {project_issue.key} - Summary: {project_issue.fields.summary}, Linked to parent: {parent_key}")

                else:
                    st.write(f"Parent issue '{parent_key}' not found. Skipping task creation.")
            else:
                # Check if an Account Issue as parent was selected 
                if st.session_state['jira_issue_type_account'] and st.session_state['jira_issue_type_account'] != "No_Parent":
                    parent_key = st.session_state['jira_issue_type_account']
                    issue_dict = create_jira_issue(summary, JIRA_PROJECT_ISSUE_TYPE, start_date, due_date, parent_key,description)
                    project_issue = jira.create_issue(fields=issue_dict)
                    st.write(f"Created Jira Issue Type Project: {project_issue.key} - Summary: {project_issue.fields.summary}, Linked to parent: {parent_key}")
                else: 
                    # Create task on its own without adding an Issue Type "Account" to the Issue
                    issue_dict = create_jira_issue(summary, JIRA_PROJECT_ISSUE_TYPE, start_date, due_date, description_key=description)
                    project_issue = jira.create_issue(fields=issue_dict)
                    st.write(f"Created Jira Issue Type Project: {project_issue.key} - Summary: {project_issue.fields.summary}")

        elif issue_type == JIRA_EPIC_ISSUE_TYPE:
            # Check if the issue has a parent issue 
            if parent_key is not None:
                # Find parent issue using summary
                parent_issue = jira.search_issues(f'project={get_jira_project_key()} AND summary~"{parent_key}"', maxResults=1)

                if parent_issue:
                    parent_key = parent_issue[0].key
                    issue_dict = create_jira_issue(summary, JIRA_EPIC_ISSUE_TYPE, start_date_normalized, due_date_normalized, parent_key,description)
                    epic_issue = jira.create_issue(fields=issue_dict)
                    st.write(f"Created Jira Issue Type Epic: {epic_issue.key} - Summary: {epic_issue.fields.summary}, Linked to parent: {parent_key}")

                else:
                    st.write(f"Parent issue '{parent_key}' not found. Skipping task creation.")
            else:
                # Create task on its own
                issue_dict = create_jira_issue(summary, JIRA_EPIC_ISSUE_TYPE, start_date_normalized, due_date_normalized, description_key=description)
                epic_issue = jira.create_issue(fields=issue_dict)
                st.write(f"Created Jira Issue Type Epic: {epic_issue.key} - Summary: {epic_issue.fields.summary}")
        

        elif issue_type == JIRA_TASK_ISSUE_TYPE:
            # Check if the task has a parent issue
            if parent_key is not None:
                # Find parent issue using summary
                parent_issue = jira.search_issues(f'project={get_jira_project_key()} AND summary~"{parent_key}" AND issuetype = {JIRA_EPIC_ISSUE_TYPE}', maxResults=1)
                if parent_issue:
                    parent_key = parent_issue[0].key
                    issue_dict = create_jira_issue(summary, JIRA_TASK_ISSUE_TYPE, start_date_normalized, due_date_normalized, parent_key,description)
                    task_issue = jira.create_issue(fields=issue_dict)
                    st.write(f"Created Jira task: {task_issue.key} - Summary: {task_issue.fields.summary}, Linked to parent: {parent_key}")

                else:
                    st.write(f"Parent issue '{parent_key}' not found. Skipping task creation.")
            else:
                # Create task on its own
                issue_dict = create_jira_issue(summary, JIRA_TASK_ISSUE_TYPE, start_date_normalized, due_date_normalized, description_key=description)
                task_issue = jira.create_issue(fields=issue_dict)
                st.write(f"Created Jira task: {task_issue.key} - Summary: {task_issue.fields.summary}")
                
        elif issue_type == JIRA_SUBTASK_ISSUE_TYPE:
            # Check if the sub-task has a parent issue
            if parent_key is not None:
                # Find parent issue using summary
                parent_issue = jira.search_issues(f'project={get_jira_project_key()} AND summary~"{parent_key}" AND issuetype = {JIRA_TASK_ISSUE_TYPE}', maxResults=1)
                if parent_issue:
                    parent_key = parent_issue[0].key
                    issue_dict = create_jira_issue(summary, JIRA_SUBTASK_ISSUE_TYPE, start_date_normalized, due_date_normalized, parent_key, description)
                    subtask_issue = jira.create_issue(fields=issue_dict)
                    st.write(f"Created Jira subtask: {subtask_issue.key} - Summary: {subtask_issue.fields.summary}, Linked to parent: {parent_key}")
                else:
                    st.write(f"Parent issue '{parent_key}' not found. Skipping subtask creation.")
            else:
                st.write("A Sub-task must have a parent. Skipping subtask creation.")

    # Add issue links after all issues are created
    add_issue_links(jira, excel_data)

    # Update Jira Issue type Project if user provided project name
    if st.session_state['project_name_user']:
        issue=jira.issue(project_issue.key)
        issue.update(summary=st.session_state['project_name_user'])
    return

def update_issue_overview_sheet(excel_data, issue_data):
    # Create a DataFrame for the "IssueOverview" sheet with selected columns
    issue_overview_df = pd.DataFrame(issue_data, columns=['IssueKey', 'Summary', 'IssueType', 'ParentSummary', 'Status', 'StartDate', 'DueDate', 'Description', 'Assignee', 'ExternalAssignee','IssueLinks'])


    # Write updated data to the "IssueOverview" sheet
    with pd.ExcelWriter(EXCEL_FILE_PATH, engine='openpyxl') as writer:
        # Write "IssueOverview" with the specified columns
        issue_overview_df.to_excel(writer, index=False, sheet_name='IssueOverview')



def get_issues_from_jira(jira):
    # Query issues from Jira
    issues = jira.search_issues(f'project={get_jira_project_key()}', maxResults=None)
    
    # Extract relevant information for the "IssueOverview" sheet
    issue_data = []
    
    for issue in issues:
        # Extract information about parent issue if exists
        parent_summary = issue.fields.parent.fields.summary if hasattr(issue.fields, 'parent') and issue.fields.parent else None
        
        # Extract information about issue links
        issue_links = []
        for link in issue.fields.issuelinks:
            if hasattr(link, 'inwardIssue') and hasattr(link.inwardIssue.fields, 'summary'):
                issue_links.append({
                    'LinkType': link.type.inward,
                    'LinkedIssueSummary': link.inwardIssue.fields.summary
                    #'LinkedIssueKey': link.inwardIssue.key
                })
            elif hasattr(link, 'outwardIssue') and hasattr(link.outwardIssue.fields, 'summary'):
                issue_links.append({
                    'LinkType': link.type.outward,
                    'LinkedIssueSummary': link.outwardIssue.fields.summary
                    #'LinkedIssueKey': link.outwardIssue.key

                })
        
        assignee = issue.fields.assignee if issue.fields.assignee else None
        
        issue_info = {
            'Summary': issue.fields.summary,
            'IssueKey': issue.key,
            'ParentSummary': parent_summary,
            'IssueType': issue.fields.issuetype.name,
            'Status': issue.fields.status.name,
            'StartDate': issue.fields.customfield_10015,
            'DueDate': issue.fields.duedate,
            'Description': issue.fields.description,
            'Assignee': issue.fields.assignee,
            'ExternalAssignee': issue.fields.customfield_10127,
            'IssueLinks': issue_links
        }
        
        issue_info.update(issue_links)
        issue_data.append(issue_info)

    return issue_data


# Function to update Jira issues with status, start date, and due date comparison
def update_jira_issues(jira, excel_data):
    for index, row in excel_data.iterrows():
        issue_key = row['IssueKey']
        new_status = row.get('Status')
        issue_key_checked = normalize_NaN(issue_key)
        
        if issue_key_checked and new_status:
            try:
                existing_issue = jira.issue(issue_key)
                # Check if status, start date, or due date is different
                if (
                    new_status != existing_issue.fields.status.name
                    or normalize_date(row['StartDate']) != existing_issue.fields.customfield_10015
                    or normalize_date(row['DueDate']) != existing_issue.fields.duedate
                    #or row['Description'] != existing_issue.fields.description
                    # customfield_10127 is Other in Jira and used to assign an external User as an Owner of an Issue
                    or (existing_issue.fields.customfield_10127 and row['ExternalAssignee'] != existing_issue.fields.customfield_10127)
                ):
                    # Transition the issue to the new status
                    transition_issue(jira, issue_key, new_status)
                    
                    # Update issue details
                    if existing_issue.fields.customfield_10127:
                        existing_issue.update(
                            summary=row['Summary'],
                            #description=row['Description'],
                            customfield_10015=normalize_date(row['StartDate']),
                            duedate=normalize_date(row['DueDate']),
                            customfield_10127=row['ExternalAssignee']
                        )
                    else:
                        existing_issue.update(
                            summary=row['Summary'],
                            #description=row['Description'],
                            customfield_10015=normalize_date(row['StartDate']),
                            duedate=normalize_date(row['DueDate']),
                        )

                    st.write(f"Updated Jira issue: {issue_key} - Summary: {row['Summary']}")
            except Exception as e:
                st.write(f"Error updating issue {issue_key} in Jira: {e}")

        else:
            parent_key=row['ParentSummary']
            if parent_key is not None:
                # Find parent issue using summary
                parent_issue = jira.search_issues(f'project={get_jira_project_key()} AND summary~"{parent_key}"', maxResults=1)

                if parent_issue:
                    parent_key_id = parent_issue[0].key

                #TO DO IMPLEMENT HANDLING FOR EPICs

                else:
                    st.write(f"Parent issue '{parent_key}' not found. Tasks can only be created if ParentName is provided. Skipping task creation.")

            # Mandatory Input Values
            issue_dict = create_jira_issue(
                summary=row['Summary'],
                issue_type=row['IssueType'],
                parent_key=parent_key_id
            )
            # Optional Input Values 
            if normalize_NaN(row['StartDate']):
                start_date_normalized = normalize_date(row['StartDate'])
                issue_dict['customfield_10015'] = start_date_normalized

            if normalize_NaN(row['DueDate']):
                due_date_normalized = normalize_date(row['DueDate'])
                issue_dict['duedate'] = due_date_normalized
    
            if normalize_NaN(row['Description']):
                issue_dict['description'] = row['Description']
            
            if normalize_NaN(row['ExternalAssignee']) and existing_issue.fields.customfield_10127:
                issue_dict['customfield_10127'] = row['ExternalAssignee']

            new_issue = jira.create_issue(fields=issue_dict)
            st.write(f"Created Jira issue: {new_issue.key} - Summary: {new_issue.fields.summary}")
        

# Function to transition Jira issue to a new status
def transition_issue(jira, issue_key, new_status):
    # Get the transition ID based on the destination status
    transition_id = get_transition_id(jira, issue_key, new_status)
    
    if transition_id:
        # Perform the transition
        jira.transition_issue(issue_key, transition_id)
        st.write(f"Issue {issue_key} transitioned to status: {new_status}")
    else:
        st.write(f"Transition to status {new_status} failed. Transition from current status to {new_status} not allowed.")

# Function to get the transition ID for a specific status
def get_transition_id(jira, issue_key, target_status):
    transitions = jira.transitions(issue_key)
    for transition in transitions:
        
        if transition['to']['name'] == target_status:
            return transition['id']
    return None
    
def has_cf(jira):
    # UPDATE the function as follows: use JQL to check if a specific project has a customfield

    try:
        # Get all custom fields from Jira
        #fields = jira.search_issues(f'project={JIRA_PROJECT} AND "Other" is not EMPTY', maxResults=1)
        fields = jira.search_issues(f'project={get_jira_project_key()} AND cf[10127] is not EMPTY', maxResults=1)
        if fields: 
            st.write(f'CustomField is available in {get_jira_project_key()}')
            return True
        st.write(f'CustomField is not available in {get_jira_project_key()}')
        return False

    except Exception as e:
        st.write(f"Error retrieving custom fields: {e}")
        return False

# Function that computes start and enddates of subtasks and epics based on start and enddate of Issue Type Task
def compute_dates(excel_data, project_startdate):
    task_info = []
    # First Iteration: compute start and enddates for Tasks
    for index, row in excel_data.iterrows():
        
        summary = row['Summary']
        issue_type = row['IssueType']
        duration = row.get('Duration', 0)
        blocks = normalize_NaN(row.get('Blocks'))

        if issue_type =='Account':
            start_date = project_startdate
            end_date = project_startdate
            task_info.append({
                    'summary': summary,
                    'parent': 'NoParent',
                    'start_date': project_startdate,
                    'end_date': end_date
                })
        
        #    if issue_type =='Project':
        #        start_date = project_startdate
        #        end_date = project_startdate
        #        task_info.append({
        #                'summary': summary,
        #                'parent': row['Parent'],
        #                'start_date': project_startdate,
        #                'end_date': end_date
        #            })

        if issue_type == 'Task':
            # Check if there's already a task with the same summary in task_info
            existing_task = next((task for task in task_info if task['summary'] == summary), None)

            if existing_task:
                # Task with the same summary already exists, use existing start date
                start_date = existing_task['start_date']
                # Compute end date based on duration
                end_date = calculate_end_date(start_date, duration)
                 # Update existing task in task_info with computed end date
                existing_task['end_date'] = end_date
                
                # also check if task has a value in Blocks
                summary = existing_task['summary']
                blocks = excel_data.loc[excel_data['Summary'] == summary, 'Blocks'].iloc[0]
                dependendy_blocks = normalize_NaN(blocks)

                if dependendy_blocks:
                    for block_summary in dependendy_blocks.split(','):
                        task_info.append({
                                'summary': block_summary.strip(),
                                'start_date': end_date  # Use end date as start date
                                
                        })
            else:
                # Create a new task in task_info
                task_info.append({
                    'summary': summary,
                    'parent': row['Parent'],
                    'start_date': project_startdate,
                    'end_date': calculate_end_date(project_startdate, duration)
                })
                
                if blocks:

                    for block_summary in blocks.split(','):
                        task_info.append({
                                'summary': block_summary.strip(),
                                'start_date': calculate_end_date(project_startdate, duration)  # Use end date as start date
                        })

    # Second Iteration: Look up correct parent for tasks with 'Blocks'
    for task in task_info:
        if 'parent' not in task:
            # This task has no parent information, look it up in excel_data
            summary = task['summary']
            parent_from_excel = excel_data.loc[excel_data['Summary'] == summary, 'Parent'].iloc[0]
            task['parent'] = normalize_NaN(parent_from_excel)
            

    # Third Iteration: compute start and enddates for Sub-tasks
    for index, row in excel_data.iterrows():
        summary = row['Summary']
        issue_type = row['IssueType']
        parent = row['Parent']

        if issue_type == 'Sub-task':
            # Check for the parent Task of the current Sub-task in task_info
            existing_task = next((task for task in task_info if task['summary'] == parent), None)

            if existing_task:
                # Create a new task in task_info
                task_info.append({
                    'summary': summary,
                    'parent': row['Parent'],
                    'start_date': existing_task['start_date'],
                    'end_date': existing_task['end_date']
                })
    
    # Fourth Iteration: compute start and enddates for Epics
    for index, row in excel_data.iterrows():
        summary = row['Summary']
        issue_type = row['IssueType']
        parent = row['Parent']
        
        if issue_type == 'Epic':
            epic_start_date = min(task['start_date'] for task in task_info if task['parent'] == summary)
            epic_end_date = max(task['end_date'] for task in task_info if task['parent'] == summary)
            
            # Update epic information in task_info
            epic_task = next((task for task in task_info if task['summary'] == summary), None)

            if epic_task:
                epic_task['start_date'] = epic_start_date
                epic_task['end_date'] = epic_end_date
            else:
                # If epic not found in task_info (should not happen), create a new entry
                task_info.append({
                    'summary': summary,
                    'parent': parent,
                    'start_date': epic_start_date,
                    'end_date': epic_end_date,
                })
    
    # Fifth Iteration: compute start and enddates for Issue Type "Project"
    for index, row in excel_data.iterrows():
        summary = row['Summary']
        issue_type = row['IssueType']
        parent = row['Parent']
        
        if issue_type == 'Project':
            start_date = project_startdate
            # iterate through all tasks in the temp dict task_info - look for those that have Pilot or Rollout as parent - get the max endate
            project_end_date = max(task['end_date'] for task in task_info if task['parent'] == summary)
            end_date = project_end_date
            task_info.append({
                    'summary': summary,
                    'parent': 'NoParent',
                    'start_date': project_startdate,
                    'end_date': end_date
                })
            
    return task_info

def getIssueDate(dates,summary,date_type='start_date'):
    issue_date = None
    datesDF=pd.DataFrame(dates)
    for index, row in datesDF.iterrows():
        taskInfoSummary = row['summary']
        if taskInfoSummary == summary:
            issue_date=row[date_type]
            
        
    # Convert Timestamp to datetime
    issue_date_datetime = issue_date.to_pydatetime()
    # Format datetime as string
    issue_date_string = issue_date_datetime.strftime('%Y-%m-%d')
    return issue_date_string


# Generate a JQL string based on the selected project, issue type, and status etc
def generate_jql(project, issue_type, status,parent,owner,days,custom_jql):
    jql_parts = []
    if project:
        jql_parts.append(f'project = "{project}"')
    else:
        st.write('Please select a project key!')
        return
    if issue_type:
        joined_issue_type = '","'.join(issue_type)
        jql_parts.append(f'issuetype in ( "{joined_issue_type}")')

    if status:
        string_status = '","'.join(status)
        jql_parts.append(f'status in ("{string_status}")')


    if parent:
        if ',' in parent:
            # assume more then one issue was input
            parents = parent.split(",")
            # Initialize an empty string to hold the final result
            result_string = "parent in ("
            # Iterate over each element in the list
            for i, element in enumerate(parents):
                # Add "projectkey-" prefix to each element and a comma , if it's not the last element
                if i < len(parents) - 1:
                    result_string += f'"{project}-{element}",'
                else:
                    # If it's the last element don't add the )
                    result_string += f'"{project}-{element}")'
            jql_parts.append(f'{result_string}')
        else:
        # only one issue
            jql_parts.append(f'parent = "{project}-{parent}"')
    if owner:
        if owner == "Customer":
            jql_parts.append(f'cf[10127] is not EMPTY')
        else:
            pass
    if days:
        jql_parts.append(f'due >= startOfDay() AND due <= endOfDay("+{days}d")')
    if custom_jql:
        jql_parts.append(f'{custom_jql}')

    return " AND ".join(jql_parts)

# Function returns a list of Jira Projects and theirKeys
def get_company_managed_projects_df(jira_url, username, password):
    # Connect to the JIRA server
    jira = JIRA(jira_url, basic_auth=(username, password))
    
    # Retrieve all projects visible to the user
    projects = jira.projects()
    
    # Filter and prepare the data for company-managed projects
    excluded_keys = EXCLUDED_BOARD_KEYS
    data = [{'Key': project.key, 'Name': project.name} for project in projects if project.projectTypeKey == 'business' and project.key not in excluded_keys]

    # Create a DataFrame from the filtered data
    df = pd.DataFrame(data)
    return df


# Function to retrieve all issues of a project that are relevant for updating the powerpoint timeline (gantt)
def get_all_jira_issues_of_project(jira, parent_issue_key):
    issue_data = []

    # Change the names according to your needs - those are the issue summaries (names)
    workshop_summaries_pilot= [
    'Perform Technical Workshop', 
    'Perform Assessment Workshop', 
    'Perform Functional Workshop', 
    'User Training', 
    'Project Management', 
    'Assessment', 
    'Design', 
    'Machine Learning', 
    'Application Implementation', 
    'Integration Implementation', 
    'Testing', 
    'Delivery'
    ]
    
    def get_issue_details(issue):
        return {
            'summary': issue.fields.summary,
            'customfield_10015': getattr(issue.fields, 'customfield_10015', None),
            'duedate': issue.fields.duedate
        }

    if parent_issue_key:
        child_issues = get_children_issues_for_timeline(jira, parent_issue_key)
        if child_issues:
            for issue_key in child_issues:
                issue = jira.issue(issue_key)
                summary = issue.fields.summary
                if summary in workshop_summaries_pilot:
                    issue_data.append(get_issue_details(issue))
    else:
        return
   
    return issue_data


def get_due_date_by_summary(issue_data, summary):
    try:
        for issue in issue_data:
            if issue.get('summary') == summary:
                duedate = issue.get('duedate')
                if duedate:
                    return datetime.strptime(duedate, '%Y-%m-%d')
        return None
    except (ValueError, KeyError, TypeError) as e:
        print(f"Error: {e}")
        return None

def get_start_date_by_summary(issue_data, summary):
    try:
        for issue in issue_data:
            if issue.get('summary') == summary:
                startdate = issue.get('customfield_10015')
                if startdate:
                    return datetime.strptime(startdate, '%Y-%m-%d')
        return None
    except (ValueError, KeyError, TypeError) as e:
        print(f"Error: {e}")
        return None


##################################################################################################
#################################### THIS PART WILL BE USED FOR THE NEXT RELEASE #################
#################################### IMPORTANT WHEN WORKING WITH EXCEL AS THE MAIN PM TOOL #######
##################################################################################################

# This Sections updates EndDates dependent Tasks if an EndDate (Due_date) of an Issue changed (Sub-tasks and Epcis are updated accordingly)

def get_issues_from_jira_to_update(jira):
    # Query issues from Jira
    issues = jira.search_issues(f'project={get_jira_project_key()}', maxResults=None)
    
    # Extract relevant information for the "IssueOverview" sheet
    issue_data = []
    
    for issue in issues:
        # Extract information about parent issue if exists
        parent_summary = issue.fields.parent.fields.summary if hasattr(issue.fields, 'parent') and issue.fields.parent else None
        
        # Extract information about issue links
        issue_links = []
        for link in issue.fields.issuelinks:
            if link.type.name == 'blocks':
                if hasattr(link, 'inwardIssue') and hasattr(link.inwardIssue.fields, 'summary'):
                    issue_links.append({
                        'LinkType': link.type.inward,
                        'LinkedIssueSummary': link.inwardIssue.fields.summary
                    })
                elif hasattr(link, 'outwardIssue') and hasattr(link.outwardIssue.fields, 'summary'):
                    issue_links.append({
                        'LinkType': link.type.outward,
                        'LinkedIssueSummary': link.outwardIssue.fields.summary
                    })
        
        if not issue_links:
            # If there are no blocking relationships, add the issue without duplicates
            issue_info = {
                'Summary': issue.fields.summary,
                'IssueKey': issue.key,
                'ParentSummary': parent_summary,
                'IssueType': issue.fields.issuetype.name,
                'StartDate': issue.fields.customfield_10015,
                'DueDate': issue.fields.duedate
            }
            issue_data.append(issue_info)
        else:
            # If there are blocking relationships, add each relationship as a separate row
            for link in issue_links:
                issue_info = {
                    'Summary': issue.fields.summary,
                    'IssueKey': issue.key,
                    'ParentSummary': parent_summary,
                    'IssueType': issue.fields.issuetype.name,
                    'StartDate': issue.fields.customfield_10015,
                    'DueDate': issue.fields.duedate,
                    'LinkType': link['LinkType'],
                    'LinkedIssueSummary': link['LinkedIssueSummary']
                }
                issue_data.append(issue_info)

    return pd.DataFrame(issue_data)
# LEGACY: Function that gets all issues from a given Jira Project - Currently this is handled by get_issues_from_jira

def get_issues_from_jira_v2(jira):
    # Query issues from Jira
    issues = jira.search_issues(f'project={get_jira_project_key()}', maxResults=None)
    
    # Extract relevant information for the "IssueOverview" sheet
    issue_data = []
    
    for issue in issues:
        # Extract information about parent issue if exists
        parent_summary = issue.fields.parent.fields.summary if hasattr(issue.fields, 'parent') and issue.fields.parent else None
        
        # Extract information about issue links
        issue_links = []
        for link in issue.fields.issuelinks:
            if hasattr(link, 'inwardIssue'):
                issue_links.append({
                    'LinkType': link.type.inward,
                    'LinkedIssueKey': link.inwardIssue.key
                })
            elif hasattr(link, 'outwardIssue'):
                issue_links.append({
                    'LinkType': link.type.outward,
                    'LinkedIssueKey': link.outwardIssue.key

                })
        
        assignee = issue.fields.assignee if issue.fields.assignee else None
        
        issue_info = {
            'IssueKey': issue.key,
            'ParentSummary': parent_summary,
            'IssueType': issue.fields.issuetype.name,
            'StartDate': issue.fields.customfield_10015,
            'DueDate': issue.fields.duedate,
            'IssueLinks': issue_links
        }
        
        issue_info.update(issue_links)
        issue_data.append(issue_info)

    return issue_data

def update_dates_for_blocked_issues(issue_data):
    for row in issue_data:
        # Check if the issue has a blocking relationship
        if row['IssueLinks']:
            for link in row['IssueLinks']:
                if link['LinkType'] == 'blocks':
                    blocking_issue_key = link['LinkedIssueKey']
                    
                    
                    # Find the blocking issue in issue_data - 
                    # the blocking issue is the issue that is blocked

                    blocking_issue = next((issue for issue in issue_data if issue['IssueKey'] == blocking_issue_key), None)
                    
                    # Check if the due_date (end_date) is equal to the start_date of the blocking issue
                    if row['DueDate'] != blocking_issue['StartDate']:
                        st.write(row['IssueKey'])
                        st.write(blocking_issue['StartDate'])
                        st.write(blocking_issue['DueDate'])
                        
                        # Convert date strings to datetime objects
                        start_date = pd.to_datetime(blocking_issue['StartDate'])
                        due_date = pd.to_datetime(row['DueDate'])
                        
                        # Update the start_date of the blocked issue
                        blocking_issue['StartDate'] = row['DueDate']

                        # Calculate the delta between start_date and due_date
                        delta_days = (due_date-start_date).days
                        # Convert end_date of the to datetime object and add the delta
                        blocking_issue['DueDate'] = (pd.to_datetime(blocking_issue['DueDate']) + pd.to_timedelta(delta_days, unit='D')).strftime('%Y-%m-%d')
                        st.write(blocking_issue['StartDate'])
                        st.write(blocking_issue['DueDate'])

    return issue_data