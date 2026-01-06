import streamlit as st
from modules.jira_operations import save_credentials
from modules.config import HYPA_PMO_AUTH_DOCU
st.set_page_config(page_title="Authenticate", page_icon="🔐")

st.sidebar.header("Authenticate")
st.title("Authenticate 🤝")
st.write(f'First thing to do is to provide your jira credentials. If you are here for the first time you might want to read the [documentation]({HYPA_PMO_AUTH_DOCU})')

# Initialize session state for JIRA API credentials if not already done
if 'api_username' not in st.session_state:
    st.session_state['api_username'] = ''
if 'api_password' not in st.session_state:
    st.session_state['api_password'] = ''
if 'jira_project_key' not in st.session_state:
    st.session_state['jira_project_key'] = ''


api_username = st.text_input("UserName ( email address )", value=st.session_state['api_username'])
api_password = st.text_input("API Password", type="password", value=st.session_state['api_password'])

# Button to save credentials
if st.button('Save Session Credentials'):
    save_credentials(api_username, api_password)

# Button to clear credentials from the session
if st.button('Clear Credentials'):
    st.session_state['api_username'] = ''
    st.session_state['api_password'] = ''
    st.rerun()
