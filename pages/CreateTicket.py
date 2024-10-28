import streamlit as st
from jira import JIRA
from modules.config import JIRA_URL,ADMINS
from modules.jira_operations import get_jira_project_key,get_issue_key

if 'api_username' not in st.session_state:
     st.session_state['api_username']= ''
if 'api_password' not in st.session_state:
    st.session_state['api_password'] = ''
if 'jira_project_key' not in st.session_state:
    st.session_state['jira_project_key'] = ''

# Jira connection setup
jira_url = JIRA_URL
jira_username = st.session_state['api_username']
jira_api_token = st.session_state['api_password']


# Jira Authentication (replace with your Jira credentials or use OAuth)
def authenticate_jira(server, email, api_token):
    jira_options = {'server': server}
    jira = JIRA(options=jira_options, basic_auth=(email, api_token))
    return jira

# Predefined template tickets for each department
templates = {
    'IT': [
        {"summary": "Reset Password", "description": "Please reset my password for the system."},
        {"summary": "Software Installation", "description": "Install the required software."}
    ],
    'HR': [
        {"summary": "New Hire Onboarding", "description": "Prepare onboarding tasks for new hire."},
        {"summary": "Vacation Approval", "description": "Request for vacation approval."}
    ],
    'Finance': [
        {"summary": "Expense Report Submission", "description": "Submit the expense report for approval."},
        {"summary": "Budget Allocation Request", "description": "Request for budget allocation."}
    ]
}

def main():

    st.set_page_config(page_title="Create Jira Board", page_icon="📋")
    st.title("Jira Ticket Request App")
    

    if st.session_state['api_password'] == '':
            st.warning("Please log in first.")
    elif st.session_state['api_username'] not in ADMINS:
        st.warning(f"❌ Sorry, you dont have access to this page. Ask an admin (J.C or S.K.)")

    else:

        # 1. Department Selection
        department = st.selectbox("Select Department", list(templates.keys()))

        # 2. Ticket Template Selection based on department
        if department:
            ticket_options = templates[department]
            ticket_template = st.selectbox("Select a Ticket Template", ticket_options, format_func=lambda x: x["summary"])

            if ticket_template:
                st.write("Ticket Template Selected")
                st.write(f"Summary: {ticket_template['summary']}")
                st.write(f"Description: {ticket_template['description']}")

                # 3. Populate the Template
                summary = st.text_input("Edit Summary", value=ticket_template['summary'])
                description = st.text_area("Edit Description", value=ticket_template['description'])

                # 4. Jira Configuration (Board, Project Key, etc.)
                st.subheader("Jira Configuration")
                jira_server = st.text_input("Jira Server URL (e.g. https://your-domain.atlassian.net)")
                jira_email = st.text_input("Jira Email")
                jira_token = st.text_input("Jira API Token", type="password")
                project_key = st.text_input('KEy')
                issue_type = st.selectbox("Issue Type", ["Task", "Bug", "Story", "Epic"])

                # Button to submit the request
                if st.button("Create Jira Ticket"):
                    if not all([jira_server, jira_email, jira_token]):
                        st.error("Please provide all Jira configuration details.")
                    else:
                        try:
                            # Authenticate and create Jira issue
                            jira = authenticate_jira(jira_server, jira_email, jira_token)
                            
                            #keysss = get_issue_key(jira,'POC_TEST')
                            #print(keysss)

                            new_issue = jira.create_issue(
                                project=project_key,
                                summary=summary,
                                description=description,
                                issuetype={'name': issue_type}
                            )
                            st.success(f"Ticket created successfully: {new_issue.key}")
                            st.write(f"[View Ticket in Jira]({jira_server}/browse/{new_issue.key})")
                        except Exception as e:
                            st.error(f"Failed to create Jira ticket: {e}")


if __name__ == "__main__":
    main()