import streamlit as st
from jira import JIRA
from modules.config import JIRA_URL,ADMINS
from modules.jira_operations import get_project_keys
import re  # For regular expression matching

if 'api_username' not in st.session_state:
    st.session_state['api_username'] = ''
if 'api_password' not in st.session_state:
    st.session_state['api_password'] = ''

## DOCU: https://jira.atlassian.com/secure/WikiRendererHelpAction.jspa?section=all

# Predefined ticket templates

templates = [
    {
        "project_key": "CC",
        "issue_id": "COE-989",  # Reference to an existing Jira issue
    },
    {
        "project_key": "CC",  # Project key for Customer Care
        "summary": "Create Studio Company",
        "description": (
            "Adjust lines as per requirement and delete this you dont need. Do not worry about the format.\n"
            
            "Hi Team,\n\n"
            "h2. Ask    \n\n"
            "*Create a new studio company.*\n\n"
            "|| Customername || cluster || Env ||\n"
            "| {customername} | PROD-EU |[TEST] |\n"
            "| {customername} | PROD-US |[PROD] |\n\n"
            
            "*Assign hypatos default users*\n\n"
            "- mluser\n"
            "- productuser\n"
            "- coeuser\n" 
            "- ccuser\n"
            "*Assign Users as per Stakeholder Matrix*\n\n"
            "[Customer Card|https://hypatos.atlassian.net/wiki/spaces/TESTCUST/pages/1290108968/CUS+Customer+Card#%F0%9F%94%91--Key-Project-Stakeholders]\n"
            "h2. Acceptance Criteria\n\n"
            "- api v1 created and stored in 1pw link in ticket\n"
            "- api v2 created and stored in 1pw link in ticket\n" 
            "- shared companyid\n" 
            "- ticket reporter invited to company\n"
        )

    },
    {
        "project_key": "CC",
        "summary": "Software Installation",
        "description": (
            "h2. Software Installation Request\n\n"
            "*Software Needed:*\n"
            "- Application A\n"
            "- Application B\n\n"
            "*Purpose:*\n"
            "To improve productivity in data analysis tasks."
        )
    },
    {
        "project_key": "COE",  # Project key for Center of Excellence
        "summary": "New Hire Onboarding",
        "description": (
            "h2. New Hire Onboarding\n\n"
            "Please prepare onboarding tasks for the new hire.\n\n"
            "*Start Date:*\n"
            "Date X\n\n"
            "*Department:*\n"
            "Engineering"
        )
    },
    {
        "project_key": "COE",
        "summary": "Vacation Approval",
        "description": (
            "h2. Vacation Approval Request\n\n"
            "Requesting approval for vacation from *Date X* to *Date Y*.\n\n"
            "*Total Days:*\n"
            "5"
        )
    },
    {
        "project_key": "ML",  # Project key for Marketing and Logistics
        "summary": "Expense Report Submission",
        "description": (
            "h2. Expense Report Submission\n\n"
            "Please find attached the expense report for last month.\n\n"
            "*Total Amount:*\n"
            "$1,000"
        )
    },
    {
        "project_key": "ML",
        "summary": "Budget Allocation Request",
        "description": (
            "h2. Budget Allocation Request\n\n"
            "Requesting budget allocation for *Project Z*.\n\n"
            "*Amount:*\n"
            "$10,000"
        )
    }
]


def find_placeholders(text):
    return re.findall(r"\{(.*?)\}", text)

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

# Get Project Keys from Jira
project_keys = get_project_keys(JIRA_URL, st.session_state['api_username'], st.session_state['api_password'])
# Select Project Key
board_key = st.selectbox("Select Jira Board", project_keys, index=0)

######### NEW Code with ticket id
# Process templates to fetch details from Jira where necessary
processed_templates = []

for template in templates:
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

################ NEW CODE END ##


# OLD CODE Collect all summaries
# summaries = [template['summary'] for template in templates]
# # User selects a ticket summary
# selected_summary = st.selectbox("Select a ticket to create:", summaries)

# # Retrieve the selected template
# selected_template = next((template for template in templates if template['summary'] == selected_summary), None)

### OLD CODE END


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
    final_summary = final_summary.replace(f"{{{placeholder}}}", value)

# Replace placeholders in description
final_description = selected_template['description']
# When replacing placeholders, check if value is provided

for placeholder, value in placeholder_values.items():
    if value:
        final_summary = final_summary.replace(f"{{{placeholder}}}", value)
        final_description = final_description.replace(f"{{{placeholder}}}", value)
    else:
        # Remove the placeholder if no value is provided
        final_summary = final_summary.replace(f"{{{placeholder}}}", "")
        final_description = final_description.replace(f"{{{placeholder}}}", "")

st.header("Review and Edit Description")

# Provide a text area for the user to edit the description
edited_description = st.text_area("Issue Description:", value=final_description, height=300)
st.markdown(edited_description)
# If the template requires additional inputs, prompt the user
additional_fields = {}

if selected_template['summary'] == "Vacation Approval":
    start_date = st.text_input("Enter the start date of your vacation (YYYY-MM-DD):")
    end_date = st.text_input("Enter the end date of your vacation (YYYY-MM-DD):")
    total_days = st.text_input("Enter the total number of vacation days:")
    if start_date and end_date and total_days:
        selected_template['description'] = selected_template['description'].replace("Date X", start_date).replace("Date Y", end_date).replace("5", total_days)
elif selected_template['summary'] == "New Hire Onboarding":
    start_date = st.text_input("Enter the new hire's start date (YYYY-MM-DD):")
    department = st.text_input("Enter the department:")
    if start_date and department:
        selected_template['description'] = selected_template['description'].replace("Date X", start_date).replace("Engineering", department)


# Create Issue button
if st.button("Create Jira Issue"):
    if not all([jira_url, jira_email, jira_api_token]):
        st.error("Please provide all Jira authentication details.")
    else:
        try:
            
            # Create a new issue
            new_issue = jira.create_issue(
                project=board_key,
                summary=final_summary,
                description=edited_description,
                issuetype={'name': 'Task'}
            )
            
            st.success(f"Issue {new_issue.key} created in project {board_key}.")
            st.markdown(f"[View the issue in Jira]({jira_url}/browse/{new_issue.key})")
        except Exception as e:
            st.error(f"An error occurred: {e}")
