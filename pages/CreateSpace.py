import streamlit as st
from modules.config import (
    JIRA_URL_CONFLUENCE,
    CREATE_SPACE_DOCU,
    TABLE_INDEX,
    PAGE_ID,
    TEMPLATE_SPACE_KEY,
)
# swap the old helpers from atlassian wrapper to our native API module
from modules.confluence_native import (
    ConfluenceAPI,
    get_existing_space_keys,
    create_new_space,
    add_row_to_confluence_table,
    copy_pages_from_space,
)

# ---------------- Session State ----------------
if "api_username" not in st.session_state:
    st.session_state["api_username"] = ""
if "api_password" not in st.session_state:  # for Cloud, this should be the API token
    st.session_state["api_password"] = ""
if "space_created" not in st.session_state:
    st.session_state["space_created"] = False
if "new_space_key" not in st.session_state:
    st.session_state["new_space_key"] = ""

def _init_api() -> ConfluenceAPI:
    """
    Initialize our native Confluence client.
    On Atlassian Cloud: username=email, password=API token.
    On Server/DC: username and password are your normal credentials.
    """
    return ConfluenceAPI(
        base_url=JIRA_URL_CONFLUENCE,
        email=st.session_state["api_username"],
        api_token=st.session_state["api_password"],
    )

# ---------------- UI ----------------
def main():
    st.set_page_config(page_title="Create Space", page_icon="📖")
    st.title("Create Conf. Space | Copy Project Documentation Template to Conf. Space")

    with st.expander("Read the Docu"):
        st.write(f"New here? You might want to read the [documentation]({CREATE_SPACE_DOCU}).")

    if st.session_state["api_password"] == "":
        st.warning("Please log in first (tip: on Cloud, use your email + API token).")
        return
    
    if st.button("Test Confluence API"):
        try:
            api = _init_api()
            keys = get_existing_space_keys(api)
            st.success(f"OK. Found {len(keys)} spaces (e.g., {keys[:5]})")
        except Exception as e:
            st.error(f"Confluence connectivity failed: {e}")

    # Initialize native API client (replaces atlassian.Confluence)
    api = _init_api()

    copyflag = st.selectbox(
        "Do you want to create a new space (Admins only) or only copy project docu template pages to an existing space?",
        ("project", "space"),
        index=None,
        placeholder="Select space or project...",
    )

    if copyflag == "project":
        project_type_key = st.selectbox("Select the project type:", ("PoC", "Pilot", "Custom Demo"))
        space_key = st.text_input("Enter the key of the target Space (alpha-3)")

        # Validate space key
        if space_key and len(space_key) == 3 and space_key.isalpha():
            st.success(f"The key '{space_key}' is valid.", icon="✅")
        elif space_key:
            st.error("The key must be alpha-3.")

        if st.button(f"Copy template pages for a {project_type_key} project to the space: {space_key}.", disabled=not space_key):
            with st.container(height=300):
                try:
                    copy_pages_from_space(
                        api,
                        TEMPLATE_SPACE_KEY,
                        space_key,
                        project_type_key,
                        copyflag=copyflag,
                    )
                except Exception as e:
                    st.error(e)
                    st.session_state["space_created"] = ""

    elif copyflag == "space":
        # Step 1: User input for the new space name
        space_name = st.text_input("Enter the name of the new Confluence Space")
        # Step 2: User input for the new space key
        space_key = st.text_input("Enter a key for the new Confluence Space (ALPHA-3)")
        # Step 3: Project type
        project_type_key = st.selectbox(
            "For what type of project you want to create template pages?",
            ("PoC", "Pilot", "Custom Demo"),
        )
        # Step 4: Existing keys for validation
        existing_keys = get_existing_space_keys(api)

        # Step 5: Validate
        if space_key and len(space_key) == 3 and space_key.isalpha() and space_key not in existing_keys:
            st.success(f"The key '{space_key}' is valid and available.", icon="✅")
        elif space_key:
            st.error("The key must be alpha-3, and it must not already exist.")

        # Step 6: Create space
        if space_name and space_key and len(space_key) == 3 and space_key.isalpha() and space_key not in existing_keys:
            if st.button("Create New Space"):
                try:
                    response = create_new_space(api, space_name, space_key)
                    st.session_state["space_created"] = True
                    st.session_state["new_space_key"] = space_key
                    space_overview_url = f"{JIRA_URL_CONFLUENCE.rstrip('/')}/spaces/{space_key}/overview"
                    st.write(
                        f"New space created: {space_overview_url} — Now copying template pages to the new space."
                    )
                except Exception as e:
                    st.error(f"Space creation failed: {e}")
                    st.session_state["space_created"] = False

        # Step 7: Copy pages into the new space + append to registry table
        if st.session_state.get("space_created"):
            with st.container(height=300):
                try:
                    copy_pages_from_space(
                        api,
                        TEMPLATE_SPACE_KEY,
                        st.session_state["new_space_key"],
                        project_type_key,
                        copyflag=copyflag,
                    )
                    st.session_state["space_created"] = False

                    # Add a row to the registry table (only for storage-format tables)
                    new_row_data = [
                        space_name,
                        f"[{st.session_state['new_space_key']}]",
                        "ONBOARDING",
                        "",
                        f"{JIRA_URL_CONFLUENCE.rstrip('/')}/spaces/{space_key}/overview",
                        "N/A",
                        "ENTERPRISE",
                    ]
                    try:
                        add_row_to_confluence_table(api, PAGE_ID, TABLE_INDEX, new_row_data)
                    except Exception as e:
                        # If the registry page is ADF (live doc), this will warn instead of breaking the flow
                        st.warning(f"Could not append to registry table (likely an ADF page): {e}")

                except Exception as e:
                    st.error(f"An error occurred while copying pages: {e}")
                    st.session_state["space_created"] = False

    else:
        st.warning("Please select an option.")

if __name__ == "__main__":
    main()
