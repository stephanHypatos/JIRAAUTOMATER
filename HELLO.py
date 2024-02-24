import streamlit as st

st.set_page_config(
    page_title="Hello",
    page_icon="👋",
)

st.write("# Welcome to JiraAutomater! 👋")

st.sidebar.success("Select a functionality above.")

st.markdown(
    """
    JiraAutomator is a HYPATOS app built specifically for
    automating recurring and boring project mamagement tasks such as projectsetup and weekly report creation.
    **👈 Select a functionality from the sidebar** to see what you can do with this app.
    ### Want to learn more?
    - Check out [streamlit.io](https://streamlit.io)
    - Jump into our [documentation](https://docs.streamlit.io)
    - Ask a question in our [community forums](https://discuss.streamlit.io)
    ### See more complex demos
"""
)