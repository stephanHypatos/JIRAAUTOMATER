from atlassian import Confluence
from modules.config import JIRA_URL
import streamlit as st
from bs4 import BeautifulSoup


# Initialize Confluence API connection (replace these variables with your credentials)
CONFLUENCE_URL = JIRA_URL
CONFLUENCE_TOKEN= st.session_state['api_password']
CONFLUENCE_USERNAME = st.session_state['api_username']

confluence = Confluence(
    url=CONFLUENCE_URL,
    username=CONFLUENCE_USERNAME,
    password=CONFLUENCE_TOKEN
)

def add_row_to_confluence_table(confluence, page_id, table_index, row_data):
    """
    Add a new row to a given table in a Confluence page and insert the space key in a specific cell.
    
    Parameters:
    - confluence: An instance of the Confluence class from the atlassian-python-api library.
    - page_id: The ID of the page you want to modify.
    - table_index: Index of the table on the page (0 if it's the first table).
    - row_data: List of values for the new row.
    """

    # 1. Get the current page content (expand the body and version information)
    page_content = confluence.get_page_by_id(page_id, expand="body.storage,version")

    if not page_content:
        raise Exception(f"Failed to retrieve page content for page ID: {page_id}")
    
    page_body = page_content["body"]["storage"]["value"]  # The page content in storage format (HTML)
    version_number = page_content["version"]["number"]    # Current version of the page

    # 2. Parse the content to find the table
    soup = BeautifulSoup(page_body, "html.parser")
    
    # Find the table by index
    tables = soup.find_all("table")
    if len(tables) <= table_index:
        raise Exception(f"Table at index {table_index} not found on the page")
    
    table = tables[table_index]
    
    # 3. Create a new row and add data
    new_row = soup.new_tag("tr")
    for cell_data in row_data:
        new_cell = soup.new_tag("td")
        new_cell.string = cell_data  # Add text data to each cell
        new_row.append(new_cell)     # Append cell to the new row
    
    table.append(new_row)  # Append the new row to the table

    # 4. Convert the updated content back to a string
    updated_body = str(soup)

    # 5. Update the page with the modified content
    update_response = confluence.update_page(
        page_id=page_id,
        title=page_content["title"],  # Keep the same title
        body=updated_body,
        representation="storage"
    )

    if not update_response:
        raise Exception(f"Failed to update the page content for page ID: {page_id}")
    
    st.write("Added new row to customer's table.")
    return update_response

# Function to get all existing Confluence space keys
def get_existing_space_keys():
    spaces = confluence.get_all_spaces()
    return [space['key'] for space in spaces['results']]

# Function to create a new space
def create_new_space(space_name, space_key):
    response = confluence.create_space(space_key, space_name)  # Only 2 arguments needed
    return response

# Function to check if a page with the same title exists in the target space
def page_exists(space_key, page_title):
    pages = confluence.get_all_pages_from_space('OLL')
    for page in pages:
        if page['title'] == page_title:
            return True
    return False

# Function to get child pages of a specific page
def get_child_pages(parent_page_id):
    return confluence.get_child_pages(parent_page_id)

# Function to copy child pages while maintaining hierarchy (skips the first page)
def copy_child_pages(source_page_id, target_space_key, target_parent_id=None,project_type_key='default'):
    try:
        # Get all child pages of the source page
        child_pages = get_child_pages(source_page_id)
        
        for child_page in child_pages:
            # Get the content of the child page
            page_content = confluence.get_page_by_id(child_page['id'], expand='body.storage')
            page_title = page_content['title']
            page_body = page_content['body']['storage']['value']

            # Initialize the new page title
            new_page_title = page_title

            # Define your replacements
            replacements = {
                '[*CUS*]': f'[{target_space_key}]',
                '[*PROJECTTYPE*]': project_type_key
            }

            # Perform the replacements
            for placeholder, replacement in replacements.items():
                if placeholder in new_page_title:
                    new_page_title = new_page_title.replace(placeholder, replacement)



            # Check if the page already exists in the target space
            if page_exists(target_space_key, new_page_title):
                st.warning(f"Page '{new_page_title}' already exists in space '{target_space_key}'. Skipping creation.")
                continue

            # Create the page in the target space
            new_page = confluence.create_page(
                space=target_space_key,
                title=new_page_title,
                body=page_body,
                parent_id=target_parent_id
            )
            st.success(f"Created page: '{new_page_title}' in space '{target_space_key}'.")

            # Recursively copy the child pages of the current page
            copy_child_pages(child_page['id'], target_space_key, new_page['id'],project_type_key=project_type_key)

    except Exception as e:
        st.error(f"Error copying pages: {e}")

# Function to initiate copyingall pages from one space to another, skipping the first page ( which is the space page )
def copy_pages_from_space(source_space_key, target_space_key,project_type_key,copyflag='space'):
    try:
        # Get the home page of the source space
        space = confluence.get_space(source_space_key, expand='homepage')
        home_page_id = space['homepage']['id']
        
        if copyflag == 'project':
            home_page_id = '1290109126' # page id of the the projects page in the TESTCUS space
        
        # Start copying child pages of the home page
        copy_child_pages(home_page_id, target_space_key,project_type_key=project_type_key)
        st.success(f"All template pages for project type: {project_type_key} copied to the space: {target_space_key}",icon="✅")
    except Exception as e:
        st.error(f"Error copying pages from space: {e}")

