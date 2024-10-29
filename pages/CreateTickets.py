import streamlit as st
from jira import JIRA
from modules.config import JIRA_URL,ADMINS,JIRA_SUBTASK_ISSUE_TYPE,JIRA_TASK_ISSUE_TYPE
from modules.jira_operations import get_project_keys,create_jira_issue_ticket_template,save_jira_project_key,get_jira_issue_type_project_key,get_children_issues_ticket_template,get_jira_issue_type_project_key_with_displayname,display_issue_summaries
from templates.ticketTemplates import TICKET_TEMPLATES
from modules.ticket_template_operations import jira_markup_to_html,find_placeholders

if 'api_username' not in st.session_state:
    st.session_state['api_username'] = ''
if 'api_password' not in st.session_state:
    st.session_state['api_password'] = ''
if 'jira_project_key' not in st.session_state:
    st.session_state['jira_project_key'] = ''


# Streamlit app title
st.title("Create a Jira Issue")

## Auth logic

jira_url = JIRA_URL
jira_email = st.session_state['api_username']
jira_api_token = st.session_state['api_password']
  # Connect to Jira instance
jira = JIRA(
    jira_url,
    basic_auth=(jira_email, jira_api_token)
)

with st.expander('Expand for more info '):
    st.write('Read the documentation')
# Get Project Keys from Jira
board_keys = get_project_keys(JIRA_URL, st.session_state['api_username'], st.session_state['api_password'])
# Select Project Key
board_key = st.selectbox("Select the Jira Board where want to create the ticket", board_keys, index=0)
# Save the board key to session state
save_jira_project_key(board_key)

# Step 2: Select a Project from the selected Jira Board


# Process templates to fetch details from Jira where necessary
processed_templates = []

for template in TICKET_TEMPLATES:
    if 'issue_id' in template:
        try:
            issue = jira.issue(template['issue_id'])
            summary = issue.fields.summary
            description = issue.fields.description
            # Include the fetched summary and description in the template
            processed_templates.append({
                "project_key": template['project_key'],
                "summary": summary,
                "description": description
            })
        except Exception as e:
            st.error(f"Failed to fetch issue {template['issue_id']}: {e}")
    else:
        # Template already contains summary and description
        processed_templates.append(template)

# Collect all summaries
summaries = [template['summary'] for template in processed_templates]

# User selects a ticket summary
selected_summary = st.selectbox("Select a ticket to create:", summaries)

# Retrieve the selected template
selected_template = next((template for template in processed_templates if template['summary'] == selected_summary), None)

# Find placeholders in summary and description
summary_placeholders = find_placeholders(selected_template['summary'])
description_placeholders = find_placeholders(selected_template['description'])
# Combine all placeholders
all_placeholders = set(summary_placeholders + description_placeholders)

# Dictionary to hold user inputs for placeholders
placeholder_values = {}

# Prompt user to fill in placeholder values
for placeholder in all_placeholders:
    user_input = st.text_input(f"Enter a value for '{placeholder}':")
    placeholder_values[placeholder] = user_input


# Replace placeholders in summary
final_summary = selected_template['summary']
for placeholder, value in placeholder_values.items():
    final_summary = final_summary.replace(f"{{${placeholder}$}}", value)

# Replace placeholders in description
final_description = selected_template['description']

# When replacing placeholders, check if value is provided

for placeholder, value in placeholder_values.items():
    if value:
        final_summary = final_summary.replace(f"{{${placeholder}$}}", value)
        final_description = final_description.replace(f"{{${placeholder}$}}", value)
    else:
        # Remove the placeholder if no value is provided
        final_summary = final_summary.replace(f"{{${placeholder}$}}", "")
        final_description = final_description.replace(f"{{${placeholder}$}}", "")

st.header("Review and Edit Description")

# Provide a text area for the user to edit the description
edited_description = st.text_area("Issue Description:", value=final_description, height=300)
# Convert the Jira markup to HTML
html_description = jira_markup_to_html(edited_description)
# Render the HTML in Streamlit
# st.markdown(html_description, unsafe_allow_html=True)

# If the template requires additional inputs, prompt the user
additional_fields = {}

if selected_template['summary'] == "xyz":
    # do something selected_template['description'] = selected_template['description'].replace("Date X", start_date).replace("Date Y", end_date).replace("5", total_days)
    # not in use at the moment
    pass

# Add a checkbox for setting the start and due dates
# If the checkbox is selected, show the date input
set_start_date = st.checkbox("Set Start Date")
set_due_date = st.checkbox("Set Due Date")

if set_start_date:
    start_date=st.date_input( "Select StartDate",format="YYYY-MM-DD")
else:
    start_date = None  # No due date is set

if set_due_date:
    due_date = st.date_input("Select Due Date", format="YYYY-MM-DD")
else:
    due_date = None  # No due date is set

possible_statuses = ["Backlog","To Do", "Assign To Coe"] 
# LATER STAGE : # possible_statuses = ["To Do", "Assign To Coe","Assign To ML"] 
# Let the user select the desired status
selected_status = st.selectbox("Select the desired status for the issue:", possible_statuses)

if st.session_state['jira_project_key']:
    # Get all Projects (Issue Types) in a given Jira Board
    jira_template_projects = get_jira_issue_type_project_key_with_displayname(jira,st.session_state['jira_project_key'])
    source_issue_key=display_issue_summaries(jira_template_projects)
    try:
        children_issues=get_children_issues_ticket_template(jira, source_issue_key)
        words_to_exclude = ['milestone'] # Tickets should not be attached to Mile Stone Tasks
        filtered_children_issues = [
            issue for issue in children_issues 
            if not any(word in issue['summary'].lower() for word in words_to_exclude)
        ]
        select_options = [{'key': 'No Parent', 'summary': 'N/A', 'issuetype': 'N/A'}]
        select_options.extend(children_issues)
        parent_issue_key=st.selectbox("Attach the ticket to a parent Task:?", select_options, index=0)
        
    except Exception as e:
        st.warning(f'The project {source_issue_key} seems to have no child issues: {e}')

# Create Issue button
if st.button("Create Ticket"):
    if not all([jira_url, jira_email, jira_api_token]):
        st.error("Please provide all Jira authentication details.")
    else:
        try:
            final_summary=f'[{board_key}] {final_summary}'
           
            issue_type = JIRA_SUBTASK_ISSUE_TYPE
            parent_key = parent_issue_key['key']

            if parent_issue_key['key']== 'No Parent':
                parent_key = None
                issue_type = JIRA_TASK_ISSUE_TYPE
            
            #Input Values
            issue_dict = create_jira_issue_ticket_template(board_key,final_summary,issue_type,start_date=start_date,due_date=due_date,parent_key=parent_key,description=edited_description)
            new_issue = jira.create_issue(fields=issue_dict)
            
            st.success(f"Issue {new_issue.key} created in project {board_key}.")

            transitions = jira.transitions(new_issue)
            transition_name_to_id = {t['name']: t['id'] for t in transitions}

            # Check if the desired status is available via a transition
            transition_id = None
            for t in transitions:
                # Retrieve the target status of each transition
                target_status = t['to']['name']
                if target_status.lower() == selected_status.lower():
                    transition_id = t['id']
                    break

            if transition_id:
                # Perform the transition
                jira.transition_issue(new_issue, transition_id)
                st.success(f"Issue {new_issue.key} transitioned to status '{selected_status}'.")
            else:
                st.warning(f"Cannot transition to the status '{selected_status}' from the current status '{new_issue.fields.status.name}'.")
                st.info("Available transitions are:")
                for t in transitions:
                    st.write(f"- {t['name']} (to status '{t['to']['name']}')")

            st.markdown(f"[View the issue in Jira]({jira_url}/browse/{new_issue.key})")
        except Exception as e:
            st.error(f"An error occurred: {e}")
