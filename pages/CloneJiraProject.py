from datetime import datetime,timedelta
import streamlit as st
from jira import JIRA
import os
from modules.config import JIRA_URL,ADMINS,JIRA_TEMPLATE_BOARD_KEY
from modules.jira_operations import get_project_keys,get_users_from_jira_project,get_jira_issue_type_project_key_with_displayname,display_issue_summaries,get_jira_issue_type_account_key,update_parent_key,save_jira_account_type_parent,save_jira_project_key,get_jira_issue_type_project_key,update_parent_issue_type_project,delete_newly_created_project
from modules.jira_clone_issue_operations import get_time_delta,clone_issue_recursive_first_pass,add_issue_links,update_project_name
if 'api_username' not in st.session_state:
     st.session_state['api_username']= ''
if 'api_password' not in st.session_state:
    st.session_state['api_password'] = ''
if 'new_project_name' not in st.session_state:
    st.session_state['new_project_name'] = ''
if 'jira_issue_type_account' not in st.session_state:
    st.session_state['jira_issue_type_account'] = ''
if 'jira_project_key' not in st.session_state:
    st.session_state['jira_project_key'] = ''

def main():
    # Jira connection setup
    jira_url = JIRA_URL
    jira_username = st.session_state['api_username']
    jira_api_token = st.session_state['api_password']
    jira = JIRA(server=jira_url, basic_auth=(jira_username, jira_api_token))
    #Other vars
    admins = ADMINS
    delta_days = None
    if st.session_state['api_password'] == '':
            st.warning("Please log in first.")
    elif st.session_state['api_username'] not in admins:
        st.title("❌ Sorry, you dont have access to this page.")
    else: 
        st.title("Jira Issue Type Project Creator")
        
        project_start_date=st.date_input("Enter the project startdate:", value=None,format="YYYY-MM-DD")
        
        jira_template_projects = get_jira_issue_type_project_key_with_displayname(jira,JIRA_TEMPLATE_BOARD_KEY)
        source_issue_key=display_issue_summaries(jira_template_projects)
        
        delta_days=get_time_delta(jira,project_start_date,source_issue_key)
        jira_board = get_project_keys(JIRA_URL, st.session_state['api_username'], st.session_state['api_password'])
        
        target_project = st.selectbox("Select Target Board Key:", jira_board, index=0)
        
        
        # save the target_jira_board key to session state
        save_jira_project_key(target_project)

        if target_project: 
            users=get_users_from_jira_project(jira, target_project)
            project_assignee = st.selectbox("Select Project Assignee:",users)
            new_project_name= st.text_input('Provide a project name:',placeholder="My new project")
            st.session_state['new_project_name']=new_project_name
            # Key all Issues type 'account' in a given JIRA Work Mgmt board
            parent_keys = get_jira_issue_type_account_key(JIRA_URL, st.session_state['api_username'], st.session_state['api_password'])
            # Select Project Parent (most likely an Issue Type Account)
            parent_issue_key = st.selectbox("Select the issue type 'Account' to which your project should be attached:", parent_keys, index=0)
            save_jira_account_type_parent(parent_issue_key)

            # Optional Select new Project Issue Type 
            project_keys = get_jira_issue_type_project_key_with_displayname(jira,target_project)
            project_keys_names = [project['summary'] for project in project_keys]
            project_keys_names.insert(0, None)
            new_project_issue_key = st.selectbox("Optional. If you like to attach the new project to an already existing Project, select it here:", project_keys_names, index=0)
            selected_issue_type_project_key = next((project for project in project_keys if project['summary'] == new_project_issue_key), None)            
            

        if st.button("Clone Issues"):
            if source_issue_key and target_project and project_assignee and project_start_date:
                try:
                    source_issue = jira.issue(source_issue_key)
                    
                    st.write(f"Cloning issue hierarchy starting from: {source_issue.key}")
                    cloned_issues = {}

                    # Step 1: Clone all issues without linked_issues
                    st.write('Cloned Issue Delta Days: ',delta_days )
                    st.write(project_assignee)
                    clone_issue_recursive_first_pass(source_issue, target_project, cloned_issues=cloned_issues,day_delta=delta_days,project_assignee=project_assignee)
                    
                    # Step 2: After cloning all issues, add linked_issues
                    st.write("All issues cloned. Now creating links between issues...")
                    add_issue_links(cloned_issues)
                    
                    # Step 3: Update the project name
                    update_project_name(jira,cloned_issues[source_issue_key].key,st.session_state['new_project_name'])
                    
                    # Step 4: Update Parent Issue Type Account 
                    if st.session_state['jira_issue_type_account'] != '' and st.session_state['jira_issue_type_account'] != 'No_Parent':
                        try:
                            update_parent_key(jira,cloned_issues[source_issue_key].key, st.session_state['jira_issue_type_account'])
                        except Exception as e:
                            st.error(f"An error occurred: {str(e)}")        

                    # Step 5: Optional Update Project Issue Type 
                    if new_project_issue_key is not None:
                        try:
                            update_parent_issue_type_project(jira, cloned_issues[source_issue_key].key,selected_issue_type_project_key["key"])
                            delete_newly_created_project(jira,cloned_issues[source_issue_key].key)                
                            st.success(f"Project Issues have been created and attached to the Project: {selected_issue_type_project_key['summary']}")
                                       
                        except Exception as e: 
                            st.warning('Unable to change the parent project Id')
                    else:        
                        st.success(f"Project: {st.session_state['new_project_name']} Issue Key: {cloned_issues[source_issue_key].key} has been created and assigned to {project_assignee}.")
                    
                    # Step 5: clear the session state 
                    st.session_state['new_project_name'] = ''

                except Exception as e:
                    st.error(f"An error occurred: {str(e)}")
            else:
                st.warning("Please enter project startdate, source project name, target board key and project assignee")

if __name__ == "__main__":
    main()


## TO DO 
## let the user decide from which board they want to clone from - only admins
## add customer selection
## power point . add error handling if pp template is not present in template
