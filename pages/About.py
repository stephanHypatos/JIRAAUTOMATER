import streamlit as st

st.set_page_config(page_title="About the App", page_icon="📈")

st.markdown("# About")

st.markdown("""
            ## The Key Features of version 1 are: ### Jira Connection: Connects to a Jira instance using specified URL, username, and password.
- Issue Creation: Creates Jira issues based on the IssueBluePrint that is currently stored on the server. Supports different issue types, including Epics, Tasks, and Sub-tasks. Handles parent-child relationships and dependencies.
- Issue Links: Establishes links between Jira issues based on specified relationships (e.g., "blocks").
### The Key Features of version 2 are:

- Issue Updates: Updates existing Jira issues with new information from an Excel file, including changes to summary, status, start date, due date, and description
- Transition Handling: Manages transitions between different statuses of Jira issues.
            
""")
