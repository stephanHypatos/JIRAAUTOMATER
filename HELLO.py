import streamlit as st

st.set_page_config(
    page_title="Hello",
    page_icon="👋",
)

st.write("# Welcome to Hypa PMO! 👋")

st.sidebar.success("Select a functionality above.")

st.markdown(
    """
    JiraAutomator is a HYPATOS app built specifically for
    automating recurring and boring project mamagement tasks such as the setup of a new project or the creation of a weekly status report.
    
    **👈 Select a functionality from the sidebar** to see what you can do with this app.
    
    ### Want to learn more?
    - Jump into the [documentation](https://hypapmo.streamlit.app/About)
    
    
"""
)