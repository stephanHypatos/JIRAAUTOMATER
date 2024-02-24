from office365.sharepoint.files.file import File
from office365.sharepoint.client_context import ClientContext
from office365.runtime.auth.authentication_context import AuthenticationContext
# SharePoint and Folder urls
sharepoint_url = 'https://hypatos.sharepoint.com/:f:/s/Projects/'
folder_in_sharepoint = '/EnzIsVltlDpMkb849IkO66kBa6VgC3-nJLDZsKqhj-ongw?e=gQOlKV'


# First section: e-mail and password as input
placeholder = st.empty()
with placeholder.container():
  col1, col2, col3 = st.columns(3)
  with col1:
    st.markdown("## **SharePoint connection with Streamlit**")
    st.markdown("--------------")
    email_user = st.text_input("Your e-mail")
    password_user = st.text_input("Your password", type="password")

    # Save the button status
    Button = st.button("Connect")
    if st.session_state.get('button') != True:
      st.session_state['button'] = Button


# Authentication and connection to SharePoint
def authentication(email_user, password_user, sharepoint_url) :
  auth = AuthenticationContext(sharepoint_url) 
  auth.acquire_token_for_user(email_user, password_user)
  ctx = ClientContext(sharepoint_url, auth)
  web = ctx.web
  ctx.load(web)
  ctx.execute_query()
  return ctx

# Second section: display results
# Check if the button "Connect" has been clicked
if st.session_state['button'] :                              
  placeholder.empty()
  if "ctx" not in st.session_state :
      st.session_state["ctx"] = authentication(email_user,   
                                               password_user, 
                                               sharepoint_url)
  
  st.write("Authentication: successfull!")
  st.write("Connected to SharePoint: **{}**".format( st.session_state["ctx"].web.properties['Title']))