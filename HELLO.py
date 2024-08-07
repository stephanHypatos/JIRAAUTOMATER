import streamlit as st

st.set_page_config(
    page_title="About",
    page_icon="👋",
)

st.write("# Welcome to Hypa PMO! 👋")

st.sidebar.success("Select a functionality.")

st.markdown(
    """
    Meet *Hypa PMO*: The HY app engineered to supercharge your project management workflow! 
    Wave goodbye to the drudgery of repetitive tasks, from launching new projects to generating those weekly status updates. 
    Hypa PMO is here to automate the tedious, freeing you to tackle the bigger picture.
    [Want to learn more?](https://hypatos.atlassian.net/wiki/spaces/PD/pages/1115947248/Project+Management+-+HYPA+PMO)
    """
)   
with st.expander('Key functionalities of the current version'):
    st.markdown(
        """ 
        ### Project Creation:

        - It enables the establishment of projects within Jira, incorporating a structured hierarchy that spans accounts, projects, epics, tasks, and sub-tasks.
        - The app supports the delineation of issue dependencies, allowing for the specification of relationships such as "blocks" and "is blocked by".
        - It offers the capability to calculate the start and end dates of tasks, based on the specified duration for each issue type.
        - You can provide the name of the project if you dont provide one the name of the newly created project will be the selected project type

        ### Weekly/Monthly Report Generation:

        - The application can retrieve issues from Jira for a specified project, according to the user-defined criteria for inclusion in the report.
        - It facilitates the creation of PowerPoint slide decks, aggregating and presenting the relevant project data succinctly.
        - Users are provided with the option to download the generated slide deck, enabling easy access and distribution of the report.

        ### Delete Jira Issue:
        - Delete a Jira Issue including all its children by providing the issue-key
        - You can delete issues of type: project, epic or tasl
        - You cant delete issues of type account

        ### Upcoming features
                    
        - Update the Timeline ( GANTT CHART THINK CELL ) if changes are made to the dates
        - Sharepoint Connection in order to make downloading and uploading of slidedecks unnecessary
        - Update the underlying excel blueprint file in the app
        - Issue Updates: Updating existing Jira issues based on changes in an Excel file (including changes to summary, status, start date, due date, and description)
        - Transition Handling: Manages transitions between different statuses of Jira issues.
        """
    )
with st.expander('Documentation'):
     st.markdown(
        """ 
        ### Prerequits
        - Get jira credentials. If you are here for the first time you might want to read the [documentation](https://support.atlassian.com/atlassian-account/docs/manage-api-tokens-for-your-atlassian-account/)
        - Jira Workmangagement Board and a project key ( i.e. CUS, STR, etc)
    

        ### First Steps
        - Once done, navigate to Authenticate and input your credentials
        - They will be saved only during a session

        ### Project Creation:

        - Just click on the menu item on the left to get more information

        ### Weekly/Monthly Report Generation:

        - Just click on the menu item on the left to get more information

        """
    )