import streamlit as st
import datetime  # Import datetime to work with dates
from jira import JIRA
from modules.config import JIRA_URL, ADMINS, JIRA_SUBTASK_ISSUE_TYPE, JIRA_TASK_ISSUE_TYPE,HYPA_PMO_TICKET_DOCU
from modules.jira_operations import (
    get_project_keys,
    create_jira_issue_ticket_template,
    save_jira_project_key,
    get_jira_issue_type_project_key,
    get_children_issues_ticket_template,
    get_jira_issue_type_project_key_with_displayname,
    display_issue_summaries,
    authenticate
)
from templates.ticketTemplates import TICKET_TEMPLATES
from modules.ticket_template_operations import jira_markup_to_html, find_placeholders

# Initialize session state variables
if 'api_username' not in st.session_state:
    st.session_state['api_username'] = ''
if 'api_password' not in st.session_state:
    st.session_state['api_password'] = ''
if 'jira_project_key' not in st.session_state:
    st.session_state['jira_project_key'] = ''
if 'processed_templates' not in st.session_state:
    st.session_state['processed_templates'] = []
if 'board_keys' not in st.session_state:
    st.session_state['board_keys'] = []
if 'jira' not in st.session_state:
    st.session_state['jira'] = None

def main():
    st.set_page_config(page_title="Create Ticket", page_icon="🎫")
    st.title("Create Ticket")

    if st.session_state['api_password'] == '':
        st.warning("Please log in first.")
        return  # Exit the function if not logged in
    elif st.session_state['api_username'] not in ADMINS:
        st.warning("❌ Sorry, you don't have access to this page. Ask an admin (J.C or S.K.)")
        return

    try:
        # Authenticate only once and store in session state
        if not st.session_state['jira']:
            st.session_state['jira'] = authenticate(JIRA_URL, st.session_state['api_username'], st.session_state['api_password'])
        jira = st.session_state['jira']

        with st.expander('Expand for more information.'):
            st.write(f'''Read the [documentation]({HYPA_PMO_TICKET_DOCU}) here.
                         ''')
        # Process templates once and store in session state
        if not st.session_state['processed_templates']:
            process_templates(jira)
        processed_templates = st.session_state['processed_templates']

        st.header("Select and Input")

        # Ticket template selection and input (outside of form to allow dynamic updates)
        final_summary, edited_description = ticket_selection_and_input(processed_templates)

        # Board selection and project/parent issue selection (outside of form)
        board_key = board_selection()
        st.session_state['jira_project_key'] = board_key

        if st.session_state['jira_project_key']:
            parent_issue_key, project_name = project_and_parent_selection(jira)

            # Start and due dates (outside the form)
            start_date, due_date = date_selection(parent_issue_key, jira)

            # Now proceed to the form for static inputs and ticket creation
            create_ticket_form(jira, final_summary, edited_description, parent_issue_key, project_name, start_date, due_date)

    except Exception as e:
        st.error(f'An error has occurred: {e}.')

def process_templates(jira):
    """Process ticket templates and store them in session state."""
    processed_templates = []
    for template in TICKET_TEMPLATES:
        if 'issue_id' in template:
            try:
                issue = jira.issue(template['issue_id'])
                summary = issue.fields.summary
                description = issue.fields.description
                processed_templates.append({
                    "project_key": template['project_key'],
                    "summary": summary,
                    "description": description
                })
            except Exception as e:
                st.error(f"Failed to fetch issue {template['issue_id']}: {e}")
        else:
            processed_templates.append(template)
    st.session_state['processed_templates'] = processed_templates

def ticket_selection_and_input(processed_templates):
    """Handle ticket template selection and placeholder inputs."""
    summaries = [template['summary'] for template in processed_templates]
    selected_summary = st.selectbox("Select a ticket to create:", summaries, key='selected_summary')

    selected_template = next(
        (template for template in processed_templates if template['summary'] == selected_summary), None)

    # Find placeholders
    summary_placeholders = find_placeholders(selected_template['summary'])
    description_placeholders = find_placeholders(selected_template['description'])
    all_placeholders = set(summary_placeholders + description_placeholders)

    placeholder_values = {}
    for placeholder in all_placeholders:
        user_input = st.text_input(f"Enter a value for '{placeholder}':", key=f'placeholder_{placeholder}')
        placeholder_values[placeholder] = user_input

    # Replace placeholders
    final_summary = replace_placeholders(selected_template['summary'], placeholder_values)
    final_description = replace_placeholders(selected_template['description'], placeholder_values)

    st.header("Review and Edit")
    edited_description = st.text_area("Issue Description:", value=final_description, height=300, key='edited_description')

    return final_summary, edited_description

def replace_placeholders(text, placeholder_values):
    """Replace placeholders in text with user-provided values."""
    for placeholder, value in placeholder_values.items():
        if value:
            text = text.replace(f"{{${placeholder}$}}", value)
        else:
            text = text.replace(f"{{${placeholder}$}}", "")
    return text

def board_selection():
    """Handle board selection."""
    # Get Board Keys once and store in session state
    if not st.session_state['board_keys']:
        st.session_state['board_keys'] = get_project_keys(JIRA_URL, st.session_state['api_username'], st.session_state['api_password'])
    board_keys = st.session_state['board_keys']

    # Board selection
    board_key = st.selectbox(
        "Select the Jira Board where you want to create the ticket",
        board_keys,
        index=0,
        key='board_key'
    )
    return board_key

def project_and_parent_selection(jira):
    """Handle project and parent issue selection."""
    jira_template_projects = get_jira_issue_type_project_key_with_displayname(
        jira, st.session_state['jira_project_key'])
    source_issue_key = display_issue_summaries(jira_template_projects)
    issue = jira.issue(source_issue_key)
    project_name = issue.fields.summary

    try:
        children_issues = get_children_issues_ticket_template(jira, source_issue_key)
        words_to_exclude = ['milestone']
        filtered_children_issues = [
            issue for issue in children_issues
            if not any(word in issue['summary'].lower() for word in words_to_exclude)
        ]
        select_options = [{'key': 'No Parent', 'summary': 'N/A', 'issuetype': 'N/A'}]
        select_options.extend(filtered_children_issues)
        parent_issue_key = st.selectbox(
            "Attach the ticket to a parent Task?",
            select_options,
            format_func=lambda x: f"{x['key']} - {x['summary']}",
            index=0,
            key='parent_issue_key'
        )
    except Exception as e:
        st.warning(f'The project {source_issue_key} seems to have no child issues: {e}')
        parent_issue_key = {'key': 'No Parent', 'summary': 'N/A', 'issuetype': 'N/A'}

    return parent_issue_key, project_name

def date_selection(parent_issue_key, jira):
    """Handle start and due date selection."""
    # Import datetime module
    import datetime

    # Initialize start_date and due_date
    start_date = None
    due_date = None

    # Set Start Date
    set_start_date = st.checkbox("Set Start Date", key='set_start_date')
    if set_start_date:
        start_date = st.date_input("Select Start Date",format="YYYY-MM-DD", key='start_date')
    else:
        # If no start date is set, and a parent issue is selected
        if parent_issue_key['key'] != 'No Parent':
            start_date = datetime.date.today()
            st.info(f"Start date set to today: {start_date}")

    # Set Due Date
    set_due_date = st.checkbox("Set Due Date", key='set_due_date')
    if set_due_date:
        due_date = st.date_input("Select Due Date",format="YYYY-MM-DD", key='due_date')
    else:
        # If no due date is set, and a parent issue is selected
        if parent_issue_key['key'] != 'No Parent':
            # Retrieve the parent issue's due date
            parent_issue = jira.issue(parent_issue_key['key'])
            parent_due_date = parent_issue.fields.duedate
            if parent_due_date:
                due_date = datetime.datetime.strptime(parent_due_date, '%Y-%m-%d').date()
                st.info(f"Due date set to parent's due date: {due_date}")
            else:
                st.warning("Parent issue has no due date. Please input a due date.")
        else:
            due_date = None

    return start_date, due_date

def create_ticket_form(jira, final_summary, edited_description, parent_issue_key, project_name, start_date, due_date):
    """Display the form for static inputs and ticket creation."""
    # Start a form for static inputs and ticket creation
    with st.form("creation_form"):
        # Status selection
        possible_statuses = ["To Do", "Assign To Coe"]
        selected_status = st.selectbox(
            "Select the desired status for the issue:",
            possible_statuses,
            key='selected_status'
        )
        # Submit button for ticket creation
        create_submitted = st.form_submit_button("Create Ticket")

    if create_submitted:
        create_ticket(jira, final_summary, edited_description, parent_issue_key, project_name, start_date, due_date, selected_status)

def create_ticket(jira, final_summary, edited_description, parent_issue_key, project_name, start_date, due_date, selected_status):
    """Create the ticket in Jira."""
    try:
        final_summary = f'[{st.session_state["jira_project_key"]}][{project_name}] {final_summary}'
        issue_type = JIRA_SUBTASK_ISSUE_TYPE
        parent_key = parent_issue_key['key']

        if parent_issue_key['key'] == 'No Parent':
            parent_key = None
            issue_type = JIRA_TASK_ISSUE_TYPE

        issue_dict = create_jira_issue_ticket_template(
            st.session_state['jira_project_key'],
            final_summary,
            issue_type,
            start_date=start_date,
            due_date=due_date,
            parent_key=parent_key,
            description=edited_description
        )
        new_issue = jira.create_issue(fields=issue_dict)

        st.success(f"Issue {new_issue.key} created in project {st.session_state['jira_project_key']}.")

        transition_issue_status(jira, new_issue, selected_status)

        st.markdown(f"[View the issue in Jira]({JIRA_URL}/browse/{new_issue.key})")
    except Exception as e:
        st.error(f"An error occurred: {e}")

def transition_issue_status(jira, issue, selected_status):
    """Transition the issue to the selected status."""
    transitions = jira.transitions(issue)
    transition_id = None
    for t in transitions:
        target_status = t['to']['name']
        if target_status.lower() == selected_status.lower():
            transition_id = t['id']
            break

    if transition_id:
        jira.transition_issue(issue, transition_id)
        st.success(f"Issue {issue.key} transitioned to status '{selected_status}'.")
    else:
        st.warning(f"Cannot transition to the status '{selected_status}' from the current status '{issue.fields.status.name}'.")
        st.info("Available transitions are:")
        for t in transitions:
            st.write(f"- {t['name']} (to status '{t['to']['name']}')")

if __name__ == "__main__":
    main()
