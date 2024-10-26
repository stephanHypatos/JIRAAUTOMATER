import streamlit as st
from atlassian import Confluence
from modules.config import JIRA_URL,CREATE_SPACE_DOCU,TABLE_INDEX,PAGE_ID,TEMPLATE_SPACE_KEY
from modules.confluence_operations import get_existing_space_keys,create_new_space,add_row_to_confluence_table,copy_pages_from_space 

## Auth 

if 'api_username' not in st.session_state:
     st.session_state['api_username']= ''
if 'api_password' not in st.session_state:
    st.session_state['api_password'] = ''
if 'space_created' not in st.session_state:
    st.session_state['space_created'] = False
if 'new_space_key' not in st.session_state:
    st.session_state['new_space_key'] = ''

CONFLUENCE_URL=JIRA_URL
CONFLUENCE_TOKEN=st.session_state['api_password']
CONFLUENCE_USERNAME =st.session_state['api_username']

confluence = Confluence(
    url=CONFLUENCE_URL,
    username=CONFLUENCE_USERNAME,
    password=CONFLUENCE_TOKEN
)

# Streamlit app
def main():
    st.title("Create Conf. Space | Copy Project Documentation Template to Conf. Space")
    with st.expander('Read the Docu'):
        st.write(f'If you are here for the first time you might want to read the [documentation]({CREATE_SPACE_DOCU}).')
    if st.session_state['api_password'] == '':
        st.warning("Please log in first.")
    else:

        copyflag = st.selectbox("Do you want to create a new space (Admins only) or only copy project docu template pages to an existing space?",
                                ("project", "space"),
                                index=None,
                                placeholder="Select space or project...")
        
        if copyflag == 'project':
            st.write(copyflag)
            project_type_key=st.selectbox("Select the project type:",("PoC", "Pilot", "Custom Demo"))
            space_key = st.text_input("Enter the key of the target Space (alpha-3)")
            # Check if the space key is valid
            if space_key and len(space_key) == 3 and space_key.isalpha():
                st.success(f"The key '{space_key}' is valid.",icon="✅")
            elif space_key:
                st.error("The key must be alpha-3.")

            if st.button(f"Copy template pages for a {project_type_key} project to the space: {space_key}."):
                with st.container(height=300):
                    try:            
                        copy_pages_from_space(TEMPLATE_SPACE_KEY,space_key,project_type_key,copyflag=copyflag)
                    except Exception as e:
                        st.error(e)
                        st.session_state['space_created']= ''                             

        elif copyflag == 'space':
            # Step 1: User input for the new space name
            space_name = st.text_input("Enter the name of the new Confluence Space")
            # Step 2: User input for the new space key
            space_key = st.text_input("Enter a key for the new Confluence Space (ALPHA-3)")
            # Step 3: User input for the project type
            project_type_key=st.selectbox("For what type of project you want to create template pages?",("PoC", "Pilot", "Custom Demo"))
            # Step 4:  Fetch all existing space keys for validation
            existing_keys = get_existing_space_keys()
            # Step 5: Check if the space key is valid
            if space_key and len(space_key) == 3 and space_key.isalpha() and space_key not in existing_keys:
                st.success(f"The key '{space_key}' is valid and available.",icon="✅")
            elif space_key:
                st.error("The key must be alpha-3, and it must not already exist.")
            # Step 6: Create a new confluence pace if inputs are valid
            if space_name and space_key and len(space_key) == 3 and space_key.isalpha() and space_key not in existing_keys:
                if st.button("Create New Space"):
                    response = create_new_space(space_name, space_key)
                    st.session_state['space_created'] = True  # Set flag when space is created
                    st.session_state['new_space_key'] = space_key  # Store the new space key
                    st.write(f"New space created: https://hypatos.atlassian.net/wiki/spaces/{space_key}/overview Now copying template pages to the new space.")

            # Step 7: Copy pages from template space to the newly created space
            if 'space_created' in st.session_state and st.session_state['space_created']:

                with st.container(height=300):
                    try:            
                        copy_pages_from_space(
                            TEMPLATE_SPACE_KEY,
                            st.session_state['new_space_key'],
                            project_type_key,
                            copyflag=copyflag)
                        st.session_state['space_created'] = False
                        
                        # Add a row to the Confluence table in the CS Space  
                        new_row_data = [space_name, f"[{st.session_state['new_space_key']}]", "ONBOARDING","",f"https://hypatos.atlassian.net/wiki/spaces/{space_key}/overview", "N/A","ENTERPRISE"]
                        add_row_to_confluence_table(confluence,PAGE_ID, TABLE_INDEX, new_row_data)    

                    except Exception as e:
                        st.error(f"An error occurred while copying pages: {e}")
                        st.session_state['space_created'] = False

        else: 
            st.warning('Please first answer the question.')

if __name__ == "__main__":
    main()