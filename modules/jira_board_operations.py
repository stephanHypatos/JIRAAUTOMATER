import requests
from requests.auth import HTTPBasicAuth
from atlassian import Confluence
import json
import streamlit as st
from jira import JIRA
from modules.config import JIRA_URL,JIRA_API_URL,JIRA_API_URL_V3,TEMPLATE_WF_BOARD_ID,DEFAULT_BOADR_GROUPS

## credentials for JIRA library
# Jira connection setup
jira_url = JIRA_URL
jira_username = st.session_state['api_username']
jira_api_token = st.session_state['api_password']
jira = JIRA(server=jira_url, basic_auth=(jira_username, jira_api_token))

# Jira Auth configuration
auth = HTTPBasicAuth(st.session_state['api_username'], st.session_state['api_password'])
headers = {
"Accept": "application/json",
"Content-Type": "application/json"
}

def check_project_name_exists(project_name):
        # Jira REST API to get all projects
        url = f"{JIRA_API_URL_V3}/project/search"

        response = requests.get(url, headers=headers, auth=auth)
        
        if response.status_code == 200:
            projects = response.json().get('values', [])
            
            # Check if any project has the same name
            for project in projects:
                if project['name'].lower() == project_name.lower():
                    raise ValueError(f"Error: Jira Board with the name '{project_name}' already exists. Try another Board Name")
            
            st.success(f"Jira Board '{project_name}' is available.",icon="✅")
        else:
            st.error(f"Failed to fetch projects: {response.status_code} - {response.text}")

# returns the id for a given jira board - input is a board key 
def get_id_for_jira_board(jira_board_key):
    
    url = f"{JIRA_API_URL}/project/{jira_board_key}"

    response = requests.request(
    "GET",
    url,
    headers=headers,
    auth=auth
    )
    
    json_data = json.loads(response.text)
    st.write(json_data['id'])
    return json_data['id']

def get_project_workflow_scheme():
        url = f"{JIRA_API_URL}/workflowscheme/project"
        projectId=TEMPLATE_WF_BOARD_ID
        query = {
        'projectId': {projectId}
        }
        try:
            response = requests.request(
            "GET",
            url,
            headers=headers,
            params=query,
            auth=auth
            )
            st.write(json.dumps(json.loads(response.text), sort_keys=True, indent=4, separators=(",", ": ")))
        except Exception as e:
            st.error(f"Error occured: {str(e)}")
        
        return

def assign_project_workflow_scheme(jira_board_Id):
    
    url = f"{JIRA_API_URL_V3}/workflowscheme/project"

    payload = json.dumps( {
    "projectId": jira_board_Id,
    "workflowSchemeId": "10145" # MB: Project Management Workflow v2
    } )
    try:
        response = requests.request(
        "PUT",
        url,
        data=payload,
        headers=headers,
        auth=auth
        )
        if response.status_code:
            st.write(f'The request was successful. Workflowscheme assigned to Jira Board {jira_board_Id}')
    
    
    except Exception as e: 
        st.error(f"Error occured: {str(e)}")

def assign_issue_type_scheme(jira_board_Id):
    
    url = f"{JIRA_API_URL_V3}/issuetypescheme/project"

    payload = json.dumps( {
    "issueTypeSchemeId": "10466", #MB: Project Management Issue Type Scheme defaultIssueTypeId": "10351"
    "projectId": jira_board_Id
    } )
    try:
        response = requests.request(
        "PUT",
        url,
        data=payload,
        headers=headers,
        auth=auth
        )
        if response.status_code:
            st.write(f'The request was successful. Issue Type Scheme assigned to Jira Board {jira_board_Id}')

    except Exception as e: 
        st.error(f"Error occured: {str(e)}")

    return

def assign_issue_type_screen_scheme(jira_board_Id):
    
    url = f"{JIRA_API_URL_V3}/issuetypescreenscheme/project"

    payload = json.dumps( {
    "issueTypeScreenSchemeId": "10137", # MB: Project Management Issue Type Screen Scheme"
    "projectId": jira_board_Id
    } )
    try:
        response = requests.request(
        "PUT",
        url,
        data=payload,
        headers=headers,
        auth=auth
        )
        if response.status_code:
            st.write(f'The request was successful. Issue Type Screen Scheme assigned to Jira Board {jira_board_Id}')

    except Exception as e: 
        st.error(f"Error occured: {str(e)}")

    return


def assign_users_to_role_of_jira_board(projectIdOrKey, user_list, jira_roles,user_groups):
    default_groups= DEFAULT_BOADR_GROUPS
    merged_assigned_groups = list(set(user_groups + default_groups))
    
    for role in jira_roles:
        # Assign the COE group first
        assign_groups_to_role(projectIdOrKey, merged_assigned_groups, role)
        
        # Now assign the users
        url = f"{JIRA_API_URL}/project/{projectIdOrKey}/role/{role}"
        data = {
            "user": user_list  # List of users to be assigned
        }
        try:
            response = requests.post(
                url,
                headers={**headers, 'Content-Type': 'application/json'},
                auth=auth,
                data=json.dumps(data)
            )

            if response.status_code in [200, 201]:
                st.write(f"User(s) successfully assigned to role {role}")
            else:
                st.write(f"Failed to assign user(s) to role {role}: {response.status_code} - {response.text}")
                return  

        except requests.exceptions.RequestException as e:
            st.write(f"Error while assigning user(s) to role {role}: {e}")
            return
    return


def create_jira_board(key, name, project_type, project_template,lead_account_id):
    url = f"{JIRA_API_URL}/project"
    payload = json.dumps({
        
        "key": key,
        "name": name,
        "projectTypeKey": project_type,
        "projectTemplateKey": project_template,
        #"leadAccountId": "630cd2ab3310c2492b59c51f",
        "leadAccountId": lead_account_id,
    })
    response = requests.request(
    "POST",
    url,
    data=payload,
    headers=headers,
    auth=auth
    )
    if response.status_code == 201:
        response_data = response.json()
        # Access the 'id' and 'name' fields
        project_id = response_data.get("id")
        project_name = response_data.get("key")
        project_url = f'https://hypatos.atlassian.net/jira/core/projects/{project_name}/board'
        st.write(f"Jira Board {project_name} with the id: {project_id} was successfully created. Access the Board here: {project_url}")
    else:
        st.error(f"Failed to create Jira Board: {response.status_code} - {response.text}")
    return {'id':project_id,'key':project_name}

# Function to get assignable users from Jira API
def get_assignable_users(project_keys):
    url = f"{JIRA_API_URL}/user/assignable/multiProjectSearch"
    params = {
        "projectKeys": (project_keys),
        "maxResults": 150  # Adjust maxResults as needed
    }
    
    response = requests.get(url, headers=headers, params=params, auth=auth)

    if response.status_code == 200:
        st.write(response.json())
        return response.json()  # Return the list of users
    else:
        st.error(f"Failed to retrieve users: {response.status_code} - {response.text}")
        return []


def get_all_groups():
    url = f"{JIRA_API_URL}/groups/picker"
    response = requests.get(url, headers=headers, auth=auth)
    response.raise_for_status()
    return response.json().get("groups", [])


def assign_group_to_role(projectIdOrKey, group_name, role):
    url = f"{JIRA_API_URL}/project/{projectIdOrKey}/role/{role}"
    data = {
        "group": [group_name]  # Only assign the group
    }
    try:
        st.write(f"Assigning group '{group_name}' to role {role}")
        response = requests.post(
            url,
            headers={**headers, 'Content-Type': 'application/json'},
            auth=auth,
            data=json.dumps(data)
        )

        if response.status_code in [200, 201]:
            st.write(f"Group '{group_name}' successfully assigned to role {role}")
        else:
            st.write(f"Failed to assign group '{group_name}' to role {role}: {response.status_code} - {response.text}")
    except requests.exceptions.RequestException as e:
        st.write(f"Error while assigning group '{group_name}' to role {role}: {e}")


def assign_groups_to_role(projectIdOrKey, group_names, role):
    """
    Assigns multiple groups to a specific role in a project.

    Args:
        projectIdOrKey (str): The project ID or key.
        group_names (list): A list of group names to assign.
        role (str): The role ID or name to assign the groups to.
    """
    url = f"{JIRA_API_URL}/project/{projectIdOrKey}/role/{role}"
    data = {
        "group": group_names  # Assign the list of groups
    }
    try:
        st.write(f"Assigning groups {group_names} to role {role}")
        response = requests.post(
            url,
            headers={**headers, 'Content-Type': 'application/json'},
            auth=auth,
            data=json.dumps(data)
        )

        if response.status_code in [200, 201]:
            st.write(f"Groups {group_names} successfully assigned to role {role}")
        else:
            st.write(f"Failed to assign groups {group_names} to role {role}: {response.status_code} - {response.text}")
    except requests.exceptions.RequestException as e:
        st.write(f"Error while assigning groups {group_names} to role {role}: {e}")




def get_all_groups(group_alias=None):
    #If group_alias is "partner", only return groups with names starting with "ext-".

    ##Fetch all groups and return a list of group names.
    url = f"{JIRA_API_URL}/groups/picker"
    try:
        response = requests.get(url, headers=headers, auth=auth)
        response.raise_for_status()
        groups = response.json().get("groups", [])
        # Extract only group names
        group_names = [group['name'] for group in groups]
        # Apply filtering based on group_alias
        if group_alias == "partner":
            group_names = [name for name in group_names if name.startswith("ext-")]
        return group_names
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching groups: {e}")
        return []