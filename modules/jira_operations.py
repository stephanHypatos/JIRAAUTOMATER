from jira import JIRA
import pandas as pd
import streamlit as st
import math
from datetime import datetime
from pptx import Presentation
from pptx.util import Inches
from modules.config import JIRA_ACCOUNT_ISSUE_TYPE,JIRA_PROJECT_ISSUE_TYPE,JIRA_EPIC_ISSUE_TYPE, JIRA_TASK_ISSUE_TYPE, JIRA_SUBTASK_ISSUE_TYPE,JIRA_URL,EXCEL_FILE_PATH#,JIRA_PROJECT
from modules.utils import normalize_NaN, normalize_date, calculate_end_date

# JIRA Credentials Handling

# Function to store credentials in session state
def save_credentials(username, password):
    if username and password:
        st.session_state['api_username'] = username
        st.session_state['api_password'] = password
        st.success("Credentials stored successfully!")
    else:
        st.warning('Provide Jira Credentials')

# Function to store jira project key in session state
def save_jira_project_key(projektkey):
    st.session_state['jira_project_key'] = projektkey

# Function to store JQL in session state
def save_jql(jql):
    st.session_state['jira_query'] = jql

# Function to get Jira Project Key from session state   
def get_jira_project_key():
    return st.session_state['jira_project_key']


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

# Get the Jira Issue Key - ( search by using the summary)
def get_issue_key(jira, summary):
    # Find the issue key using the summary
    issues = jira.search_issues(f'project={get_jira_project_key()} AND summary~"{summary}"', maxResults=1)
    return issues[0].key if issues else None

# first version of add_issue_links - can be deleted
##### DELETE 
def add_issue_links_v1(jira, excel_data):
    for index, row in excel_data.iterrows():
        issue_type = row['IssueType']
        link1_key = row.get('SummaryName')
        link2_key = row.get('Blocks')

        
        #link1_key = row.get('blocks')
        #link2_key = row.get('isBlockedBy')

        # Add issue links if link1 is provided
        if link1_key and link2_key:
            # Get the key of the issue by searching with the issuesummary
            link1_key_normalized = get_issue_key(jira, link1_key)
            link2_key_normalized = get_issue_key(jira, link2_key)
            if link1_key_normalized:
                jira.create_issue_link(
                    type= "blocks",
                    inwardIssue= link1_key_normalized,
                    outwardIssue=link2_key_normalized 
                )
            else:
                st.write(f"Link1 issue '{link1_key}' not found. Skipping link creation.")

# updated version 
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
                # Create task on its own
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
                    st.write(f"Created Jira Issue Type Epic: {project_issue.key} - Summary: {epic_issue.fields.summary}, Linked to parent: {parent_key}")

                else:
                    st.write(f"Parent issue '{parent_key}' not found. Skipping task creation.")
            else:
                # Create task on its own
                issue_dict = create_jira_issue(summary, JIRA_EPIC_ISSUE_TYPE, start_date_normalized, due_date_normalized, description_key=description)
                epic_issue = jira.create_issue(fields=issue_dict)
                st.write(f"Created Jira Issue Type Epic: {epic_issue.key} - Summary: {epic_issue.fields.summary}")


        
        ###### NEW END
#        if issue_type == JIRA_EPIC_ISSUE_TYPE:
#            # Create only the epic issue
#            if parent_key is not None:
#                print("An Epic can't have a parent. Skipping Epic creation.")
#            else:
#                issue_dict = create_jira_issue(summary, JIRA_EPIC_ISSUE_TYPE, start_date_normalized, due_date_normalized, description_key=description)
#                epic_issue = jira.create_issue(fields=issue_dict)
#                print(f"Created Jira epic: {epic_issue.key} - Summary: {epic_issue.fields.summary}")

        elif issue_type == JIRA_TASK_ISSUE_TYPE:
            # Check if the task has a parent issue
            if parent_key is not None:
                # Find parent issue using summary
                parent_issue = jira.search_issues(f'project={get_jira_project_key()} AND summary~"{parent_key}"', maxResults=1)

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
                parent_issue = jira.search_issues(f'project={get_jira_project_key()} AND summary~"{parent_key}"', maxResults=1)
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

# function that computes start and enddates of subtasks and epics based on start and enddate of Issue Type Task
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
        
        if issue_type =='Project':
            start_date = project_startdate
            end_date = project_startdate
            task_info.append({
                    'summary': summary,
                    'parent': row['Parent'],
                    'start_date': project_startdate,
                    'end_date': end_date
                })

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
                
                # If there is a value in "Blocks," create a new task in task_info
                #    if blocks:
                #        task_info.append({
                #        'summary': blocks,
                #        'parent': row['Parent'],
                #        'start_date': calculate_end_date(project_startdate, duration),  # Use end date as start date
                #        })
                
                # If there is a value in "Blocks," create new tasks in task_info
                if blocks:
                    #st.write(block_summary)
                    #summaryDependentTask = block_summary.strip()
                    #Blocks_from_Dependent = excel_data.loc[excel_data['Summary'] == summaryDependentTask, 'Blocks'].iloc[0]
                    #st.write(Blocks_from_Dependent)


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
    
    # Fourth Iteration: compute start and enddates for Sub-tasks
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
                    'parent': 'NoParent',
                    'start_date': epic_start_date,
                    'end_date': epic_end_date,
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


# Function that gets all issues from a given Jira Project
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


#def update_dates_in_jira(jira, updated_task_df):
    #  code to update the start_date and due_date (or end_date) in Jira
 #   pass


#def update_child_subtasks(jira, parent_key, start_date, end_date):
    #  code to get and update child sub-tasks in Jira
 #   pass
#
#def update_parent_epics(jira, task_df):
    #  code to update parent epics in Jira
 #   pass



# Generate a JQL string based on the selected project, issue type, and status etc
def generate_jql(project, issue_type, status,parent,days,custom_jql):
    jql_parts = []
    if project:
        jql_parts.append(f'project = "{project}"')
    else:
        st.write('Please select a project key!')
        return
    if issue_type:
        jql_parts.append(f'issuetype = "{issue_type}"')
    if status:
        jql_parts.append(f'status = "{status}"')
    if parent:
        if ',' in parent:
            # assume more then one issue was input
            parents = parent.split(",")
            # Initialize an empty string to hold the final result
            result_string = ""
            # Iterate over each element in the list
            for i, element in enumerate(parents):
                # Add "FNK-" prefix to each element and " or " suffix if it's not the last element
                if i < len(parents) - 1:
                    result_string += "parent = FNK-" + element + " or "
                else:
                    # If it's the last element, don't add the " or " suffix
                    result_string += "parent = FNK-" + element 

            jql_parts.append(f'("{result_string}")')
        else:
        # only one issue
            jql_parts.append(f'parent = "{project}-{parent}"')
    if days:
        jql_parts.append(f'due >= startOfDay() AND due <= endOfDay("+{days}d")')
    if custom_jql:
        jql_parts.append(f'{custom_jql}')

    return " AND ".join(jql_parts)