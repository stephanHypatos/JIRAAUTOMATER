from requests.auth import HTTPBasicAuth
from atlassian import Confluence
import json
import streamlit as st
from jira import JIRA
from modules.config import JIRA_DEV_ROLE_ID,JIRA_ADMIN_ROLE_ID,LEAD_USER_MAPPING,TEMPLATE_MAPPING,ASSIGNABLE_USER_GROUP,ADMINS,JIRA_URL
from modules.confluence_operations import get_existing_space_keys
from modules.jira_operations import create_jira_issue,save_jira_project_key
from modules.jira_board_operations import check_project_name_exists,assign_project_workflow_scheme,assign_issue_type_scheme,assign_issue_type_screen_scheme,assign_users_to_role_of_jira_board,create_jira_board,get_assignable_users

# TO Do
# Name validation 

# # projectId='10029' ## template project - put that in a env var 
# # add an issue type account with the customer name 

# create diagram. 
# 0. select name, key and users 1. create board 2. get project id 3. assing user to role 4. assign all schemes  5. add automations 6. update the issue field layout

# DONE 
# for role in project roleids  - assign users DONE
# let user select the users that should be assigned to the board

# jira_board_Id="10249"
# jira_board_key='BX'

def main():

    if 'api_username' not in st.session_state:
        st.session_state['api_username'] = ''
    if 'api_password' not in st.session_state:
        st.session_state['api_password'] = ''
    if 'jira_project_key' not in st.session_state:
        st.session_state['jira_project_key'] = ''
    if 'temp_jira_board_key' not in st.session_state:
        st.session_state['temp_jira_board_key'] = ''
    if 'temp_jira_board_id' not in st.session_state:
        st.session_state['temp_jira_board_id'] = ''
    if 'selected_users' not in st.session_state:
        st.session_state['selected_users'] = []

    st.set_page_config(page_title="Create Jira Board", page_icon="📋")
    st.title("Create Jira Board")

    if st.session_state['api_password'] == '':
            st.warning("Please log in first.")
    elif st.session_state['api_username'] not in ADMINS:
        st.warning(f"❌ Sorry, you dont have access to this page. Ask an admin (J.C or S.K.)")

    else:
        try:
            jira_role_ids = [JIRA_DEV_ROLE_ID,JIRA_ADMIN_ROLE_ID]
            confluence = Confluence(
                url=JIRA_URL,
                username=st.session_state['api_username'],
                password=st.session_state['api_password']
            )
            # Get inputs from the user
            lead_user = st.selectbox("Select Account Lead", ['stephan.kuche','jorge.costa','elena.kuhn','erik.roa','alex.menuet','yavuz.guney','michael.misterka','ekaterina.mironova'])
            project_key = st.text_input("Enter Project Key", max_chars=3,help='Use an Alpha-3 UPPERCASE key. If the key is already in use, you wont be able to create a new Board')
            
            existing_keys = get_existing_space_keys(confluence)

            # Check if the space key is valid
            if project_key and len(project_key) == 3 and project_key.isalpha() and project_key not in existing_keys:
                st.success(f"The key '{project_key}' is valid and available.",icon="✅")
            elif project_key:
                st.error("The key must be alpha-3, and it must not already exist.")

            project_name_raw = st.text_input("Enter Client Name", placeholder='Happy Customer', help='Naming Convention: Try not to go for a too long version.')
        
            # append Hypatos to create the new board name
            project_name = f"{project_name_raw} x Hypatos"

            if project_name and project_name_raw != '':
                try:
                    check_project_name_exists(project_name)
                except ValueError as e:
                    st.error(str(e))
            
                project_type = "business" #currently not in use: project_type = st.selectbox("Select Project Type", ["business", "software", "service_desk"])
                lead_user_mapping = LEAD_USER_MAPPING

                # Define default templates for each project type
                template_mapping = TEMPLATE_MAPPING

                project_key_created = None
                # Create project button
                if st.button("Create Jira Board"):
                    if project_key and project_name:
                        project_key_created=create_jira_board(
                            key=project_key.upper(),
                            name=project_name,
                            project_type=project_type,
                            project_template=template_mapping[project_type],
                            lead_account_id=lead_user_mapping[lead_user]
                        )

                        if project_key:
                            st.session_state['temp_jira_board_key'] = project_key_created['key']
                            save_jira_project_key(st.session_state['temp_jira_board_key'])
                            st.session_state['temp_jira_board_id'] = project_key_created['id']
                            st.success(f"Project {project_name} created!")  

                            # assign Workflowschemes
                            assign_project_workflow_scheme(st.session_state['temp_jira_board_id'])
                            assign_issue_type_screen_scheme(st.session_state['temp_jira_board_id'])
                            assign_issue_type_scheme(st.session_state['temp_jira_board_id'])
                            
                    else:
                        st.error("Please fill all the fields.")

                # If project is created, show a form to select users
                if st.session_state['temp_jira_board_key'] != '' :
                    
                    st.subheader("Assign Users to Project")

                    # Create a form for user selection
                    with st.form("user_selection_form"):
                        users = get_assignable_users(ASSIGNABLE_USER_GROUP)

                        # Prepare user options for multiselect
                        user_options = {user['displayName']: user['accountId'] for user in users}
                        user_names = list(user_options.keys())
                        
                        # Initialize session state for selected users if not already
                        if 'selected_users' not in st.session_state:
                            st.session_state['selected_users'] = []

                        # Display multiselect widget for user selection inside the form
                        selected_users = st.multiselect("Select one or more users", user_names, default=st.session_state['selected_users'])

                        # Submit button inside the form
                        submit_button = st.form_submit_button("Submit Selection")

                        if submit_button:
                            st.session_state['selected_users'] = selected_users
                            selected_user_account_ids = [user_options[user] for user in selected_users]
                            try:
                                assign_users_to_role_of_jira_board(st.session_state['temp_jira_board_id'],selected_user_account_ids,jira_role_ids)
                                st.write("Selected Users assigned to Board:", selected_user_account_ids)
                            except Exception as e:
                                st.warning(f'Error occured while assigne users to Board: {e}')
                            # Last Step add an issue Type Account to the created Jira Board
                            try:
                                issue_dict=create_jira_issue(project_name_raw, 'Account')
                                jira = JIRA(JIRA_URL, basic_auth=(st.session_state['api_username'], st.session_state['api_password']))
                                res = jira.create_issue(fields=issue_dict)
                                st.success(f'New Issue Type "Account" {res} created.')
                            except Exception as e:
                                st.warning(f'Error occured while creating Issue Type "Account" on Board: {e}')

                            del st.session_state['temp_jira_board_key']
                            del st.session_state['jira_project_key']
        except Exception as e:
            st.error(f'Unable to connect to Atlassian: {e}. Ask the admin for more details.')

if __name__ == "__main__":
    main()

        ### DOCU
        # https://developer.atlassian.com/cloud/jira/platform/rest/v2/api-group-projects/#api-rest-api-2-project-get
        # "assigneeType": "PROJECT_LEAD",
        #   "avatarId": 10200,
        #   "categoryId": 10120,
        #   "description": "Cloud migration initiative",
        #   "issueSecurityScheme": 10001,
        #   "key": "EX",
        #   "leadAccountId": "5b10a0effa615349cb016cd8",
        #   "name": "Example",
        #   "notificationScheme": 10021,
        #   "permissionScheme": 10011,
        #   "projectTemplateKey": "com.atlassian.jira-core-project-templates:jira-core-simplified-process-control",
        #   "projectTypeKey": "business",
        #   "url": "http://atlassian.com"


        ## Role - ID Mapping: 


        #      "atlassian-addons-project-access": 10003
        #     "Service Desk Team":10013
        #     "Developers": 10071
        #     "Service Desk Customers": 10012
        #     "Administrators": 10002
        #     "Viewers": 10070
        #     "Sprint Manager": 10076
        #     "External users": 10224

