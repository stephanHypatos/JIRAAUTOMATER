from datetime import datetime,timedelta
import streamlit as st
from jira import JIRA
import os
from modules.config import JIRA_URL,ADMINS
from modules.jira_operations import get_project_keys,get_users_from_jira_project,get_jira_issue_type_project_key_with_displayname,display_issue_summaries,get_jira_issue_type_account_key,update_parent_key,save_jira_account_type_parent,save_jira_project_key
from collections import OrderedDict

# Jira connection setup
jira_url = JIRA_URL
jira_username = st.session_state['api_username']
jira_api_token = st.session_state['api_password']
admins = ADMINS

# Jira connection setup
jira = JIRA(server=jira_url, basic_auth=(jira_username, jira_api_token))

delta_days = None

def update_project_name(jira,project_issue_key,new_project_name):
        issue=jira.issue(project_issue_key)
        issue.update(summary=new_project_name)
        return

def get_all_subtasks(issue):
    subtasks = jira.search_issues(f'parent = {issue.key}')
    return subtasks

def clone_issue_recursive_first_pass(issue, target_project, parent=None, cloned_issues=None, day_delta=0, project_assignee=None):
    if cloned_issues is None:
        cloned_issues = OrderedDict()  # Use OrderedDict to preserve the order

    # Check if the issue has already been cloned
    if issue.key in cloned_issues:
        return cloned_issues[issue.key]

    # Calculate the new due date and start date based on the delta
    due_date_date = compute_new_due_date(jira, day_delta, issue, 'duedate')
    start_date_date = compute_new_due_date(jira, day_delta, issue, 'customfield_10015')
    due_date = due_date_date.strftime("%Y-%m-%d")
    start_date = start_date_date.strftime("%Y-%m-%d")

    fields = {
        'project': {'key': target_project},
        'summary': issue.fields.summary,
        'description': issue.fields.description,
        'issuetype': {'name': issue.fields.issuetype.name},
        'duedate': due_date,
        'customfield_10015': start_date
    }
    if parent:
        fields['parent'] = {'key': parent.key}  # Ensure parent is set correctly

    try:
        # Create the new issue in the target project
        new_issue = jira.create_issue(fields=fields)
        jira.assign_issue(new_issue, project_assignee)

        st.write(f"Created new issue: {new_issue.key}")
    except Exception as e:
        st.error(f"Error creating issue: {str(e)}")
        return

    # Store the mapping of old issue to new issue
    cloned_issues[issue.key] = new_issue

    # Clone subtasks (without handling links) in order
    subtasks = get_all_subtasks(issue)
    subtasks_sorted = sorted(subtasks, key=lambda x: x.fields.created)  # Sort subtasks by creation date or another relevant field

    for subtask in subtasks_sorted:
        clone_issue_recursive_first_pass(subtask, target_project, new_issue, cloned_issues, day_delta, project_assignee)

    return new_issue

def add_issue_links(cloned_issues):
    created_links = set()  # Track created links to avoid duplication

    for original_issue_key, cloned_issue in cloned_issues.items():
        original_issue = jira.issue(original_issue_key, expand='issuelinks')

        for link in original_issue.fields.issuelinks:
            link_type = link.type.name

            # Check for outward issue
            if hasattr(link, 'outwardIssue'):
                outward_issue = link.outwardIssue
                if outward_issue.key in cloned_issues:
                    cloned_outward_issue = cloned_issues[outward_issue.key]

                    # Create the link in the original direction (cloned_issue -> cloned_outward_issue)
                    link_id = (cloned_issue.key, link_type, cloned_outward_issue.key)
                    if link_id not in created_links:
                        try:
                            jira.create_issue_link(link_type, cloned_issue, cloned_outward_issue)
                            st.write(f"Created link of type '{link_type}' between {cloned_issue.key} and {cloned_outward_issue.key}")
                            created_links.add(link_id)  # Mark this link as created
                        except Exception as e:
                            st.error(f"Error creating link between {cloned_issue.key} and {cloned_outward_issue.key}: {str(e)}")
                    else:
                        st.write(f"Link of type '{link_type}' between {cloned_issue.key} and {cloned_outward_issue.key} already created")

            # Check for inward issue
            if hasattr(link, 'inwardIssue'):
                inward_issue = link.inwardIssue
                if inward_issue.key in cloned_issues:
                    cloned_inward_issue = cloned_issues[inward_issue.key]

                    # Create the link in the original direction (cloned_inward_issue -> cloned_issue)
                    link_id = (cloned_inward_issue.key, link_type, cloned_issue.key)
                    if link_id not in created_links:
                        try:
                            jira.create_issue_link(link_type, cloned_inward_issue, cloned_issue)
                            st.write(f"Created link of type '{link_type}' between {cloned_inward_issue.key} and {cloned_issue.key}")
                            created_links.add(link_id)  # Mark this link as created
                        except Exception as e:
                            st.error(f"Error creating link between {cloned_inward_issue.key} and {cloned_issue.key}: {str(e)}")
                    else:
                        st.write(f"Link of type '{link_type}' between {cloned_inward_issue.key} and {cloned_issue.key} already created")

def get_linked_issues(issue):
    linked_issues = []
    for link in issue.fields.issuelinks:
        if hasattr(link, 'outwardIssue'):
            linked_issues.append((link.type.name, link.outwardIssue))
        if hasattr(link, 'inwardIssue'):
            linked_issues.append((link.type.name, link.inwardIssue))
    return linked_issues

def get_time_delta(jira,project_start_date,issue):
    if project_start_date:
        
        issue = jira.issue(issue)
        #Convert to datetime if input is a string 
        original_project_start = datetime.strptime(issue.fields.customfield_10015, "%Y-%m-%d").date()
        # Calculate the delta (difference in days between project start and current due date)
        return (project_start_date - original_project_start).days

    else:
        st.error('You must provide a project Start Date! (YYYY-MM-DD)')

# function that computes a new start or due date for a given jira issue key and a given field name ( customfield_10015 ( aka startdate) or duedate)
def compute_new_due_date(jira, day_delta, issue,fieldname):
    if day_delta:
        issue = jira.issue(issue)
        date_str = None

        if fieldname == 'duedate':
            # Dynamically get the field value using getattr
            date_str = getattr(issue.fields, fieldname, None)
            if date_str==None:
                st.error('The Template Issue must have a start date and end date!')
                return
    
        elif fieldname == 'customfield_10015':
            date_str = getattr(issue.fields, fieldname, None)
            if date_str==None:
                st.error('The Template Issue must have a start date and end date!')
                return
        else: 
            st.error('Cannot compute a new date. Only "duedate" or "customfield_10015" are valid fieldnames')
            return
    
        # Convert issue due date string to date objects
        current_due_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        #current_due_date = datetime.strptime(issue.fields.fieldname, "%Y-%m-%d").date() - can be deleted

        # Add this delta to the current due date to compute the new due date
        new_due_date = current_due_date + timedelta(days=day_delta)

        return new_due_date
    else:
        st.error('You must provide a Project Start Date!')
        return None  # Handle case where project_start_date is not provided
    

##JUST FOR BACKUP
# def clone_issue_recursive_first_pass(issue, target_project, parent=None, cloned_issues=None,day_delta=0,project_assignee=None):
#     if cloned_issues is None:
#         cloned_issues = {}

#     # Check if the issue has already been cloned
#     if issue.key in cloned_issues:
#         return cloned_issues[issue.key]
    
#     due_date_date=compute_new_due_date(jira, day_delta, issue,'duedate')
#     start_date_date=compute_new_due_date(jira, day_delta, issue,'customfield_10015')
#     due_date=due_date_date.strftime("%Y-%m-%d")
#     start_date=start_date_date.strftime("%Y-%m-%d")

#     fields = {
#         'project': {'key': target_project},
#         'summary': issue.fields.summary,
#         'description': issue.fields.description,
#         'issuetype': {'name': issue.fields.issuetype.name},
#         'duedate' : due_date,
#         'customfield_10015' :start_date
#     }
#     if parent:
#         fields['parent'] = {'key': parent.key}  # Ensure parent is set correctly

#     try:
#         new_issue = jira.create_issue(fields=fields)
#         # Assign issue to selected user
#         jira.assign_issue(new_issue,project_assignee)
        
#         # store the key of the newly created issue type project to be able to update the name at the end 
#         if new_issue.fields.issuetype.name.lower() == 'project':
#             template_project_issue_key = new_issue.key
#             st.session_state['template_project_issue_key']=template_project_issue_key
       
#         st.write(f"Created new issue: {new_issue.key}")
#     except Exception as e:
#         st.error(f"Error creating issue: {str(e)}")
#         return

#     # Store the mapping of old issue to new issue
#     cloned_issues[issue.key] = new_issue

#     # Clone subtasks (without handling links)
#     subtasks = get_all_subtasks(issue)
#     for subtask in subtasks:
#         clone_issue_recursive_first_pass(subtask, target_project, new_issue, cloned_issues,day_delta,project_assignee)

#     return new_issue