import requests
from requests.auth import HTTPBasicAuth
import json
import streamlit as st
from jira import JIRA
from modules.config import JIRA_URL,JIRA_DEV_ROLE_ID,JIRA_ADMIN_ROLE_ID,JIRA_API_URL,JIRA_API_URL_V3
from modules.confluence_operations import get_existing_space_keys

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
    
    #st.write(json.dumps(json.loads(response.text), sort_keys=True, indent=4, separators=(",", ": ")))
    json_data = json.loads(response.text)
    st.write(json_data['id'])
    return json_data['id']

def get_project_workflow_scheme():
        url = f"{JIRA_API_URL}/workflowscheme/project"
        #projectId='10248'
        #projectId='10215'
        projectId='10029' ## template project 
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


def assign_users_to_role_of_jira_board(projectIdOrKey, user_list, jira_roles):
    for role in jira_roles:
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
                return  # If you want to stop on the first failure, keep this

        except requests.exceptions.RequestException as e:
            st.write(f"Error while assigning user(s) to role {role}: {e}")
            return
    return

def create_jira_project(key, name, project_type, project_template,lead_account_id):
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
        return response.json()  # Return the list of users
    else:
        st.error(f"Failed to retrieve users: {response.status_code} - {response.text}")
        return []

