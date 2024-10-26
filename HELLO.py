import streamlit as st
from modules.config import HYPA_PMO_DOCU

st.set_page_config(
    page_title="About",
    page_icon="👋",
)

st.write("# Welcome to Hypa PMO! 👋")

st.sidebar.success("Select a functionality.")

st.markdown(
    f"""
    Meet *Hypa PMO*: The HY app engineered to supercharge your project management workflow! 
    Wave goodbye to repetitive tasks, from launching new projects, generating weekly status updates to Jira Board Creations. 
    Hypa PMO is here to automate the tedious, freeing you to tackle the bigger picture.
    [Want to learn more?]({HYPA_PMO_DOCU})
    """
)   
with st.expander('Key functionalities of the current version: 1.1.9 (2024-10-20)'):
    st.markdown(
        """ 
        ### Project Creation:

        - Create a new project (PoC, PILOT, Custom Demo) in a given JiraBoard, incorporating a structured hierarchy that spans accounts, projects, epics, tasks, and sub-tasks.
        - The app supports the delineation of issue dependencies, allowing for the specification of relationships such as "blocks" and "is blocked by".
        - It offers the capability to calculate the start and end dates of tasks, based on the specified duration for each issue type.
        - You can provide a name of for your project (default name: the selected "project type")

        ### Weekly Report Generation:

        - The application can retrieve issues from Jira for a specified project, according to the user-defined criteria for inclusion in the report.
        - It facilitates the creation of PowerPoint slide decks, aggregating and presenting the relevant project data succinctly.
        - Users are provided with the option to download the generated slide deck, enabling easy access and distribution of the report.

        ### Delete Jira Issue:
        - Delete a Jira Issue including all its children by providing the issue-key
        - You can delete issues of type: project, epic or tasl
        - You cant delete issues of type account

        ### Display Boards
        - display all Company Managed Jira Boards 

        ### Get Timeline 
        - Get an updated version of your GANTT CHART THINK CELL Timeline of a Project in a given JIRA Board

        ### Find Missing POs
        - A bit offtopic -> Debug PO Line Matching Enrichment
        
        ### Create Jira Board
        - create a new Jira company managed board for a customer
        - assing users to the newly created board

        ### Create Space
        - create a new space for customer including documentaiton
        - copy template page to an already existing customer confluence space
        
        ### Clone Jira Project ( Admins only - still in beta)
        - clone an issue type "project" from a given Jira Board to a given Jira Board
        - presere the original issue hierarchy and issue links 
        - auto adjusts dates based on a selected project start date
        - assign the cloned issues to a designated user
        - select a name for the new project 

        ### Upcoming features
                    
        - Monthly Steer Co Report Generation
        - Sharepoint Connection in order to make downloading and uploading of slidedecks unnecessary
        
        """
    )
with st.expander('Documentation'):
     st.markdown(
        """ 
        ### Prerequisites
        - Get jira credentials. If you are here for the first time you might want to read the [documentation](https://support.atlassian.com/atlassian-account/docs/manage-api-tokens-for-your-atlassian-account/)

        ### First Steps
        - Once done, navigate to Authenticate and input your credentials ( email address and apikey)
        - They will be saved only during your active session.
        - Using more than one tab in one session won't work.

        ### Functionalities

        - Just click on each item in the menu on the left.

        """
    )