import streamlit as st
import pandas as pd 

st.set_page_config(page_title="Find Missing PO", page_icon="ℹ️")
st.title('FIND non-existent Purchase Orders in HY DATABASE')

# Initialize session state for JIRA API credentials if not already done
if 'api_username' not in st.session_state:
    st.session_state['api_username'] = ''
if 'api_password' not in st.session_state:
    st.session_state['api_password'] = ''


if st.session_state['api_username'] and st.session_state['api_password']:
    with st.expander("Expand to read the instructions!"):
        st.markdown(
            """
            With this tool you can easily identify cases of unsuccesful PO LINE enrichment due to missing PO number in our database. 
            After you identified those case, inform the customer to adjust the PO report in the SAP Addon or in their middleware.
            ## How does it work? 
               1. GO to https://insights.hypatos.ai/dashboard/800-po-exist
            2. Select a company id
            3. Select a project displayname
            4. "Recipient PO Number" returns documents with a value on the datapoint recipient_po_number
            5. "Unique PO" returns all purchase orders (external) in the HY database for the given company id
            6.  Download both files ( click on the three dots ( right upper corner ) of each question & select download results (type ".csv")
            7. Upload both files here: https://hypapmo.streamlit.app/FindMissingPos
            8. Find the results including the links to the documents - PO matching was not successful due to the lack of the PO in the HY DataBase
            
        """
        )

    # Streamlit interface for file upload
    uploaded_po = st.file_uploader("Upload the unique POs file", type=["csv", "xlsx"])
    uploaded_de = st.file_uploader("Upload the query results file", type=["csv", "xlsx"])

    # Function to load file based on its extension
    def load_file(file):
        if file.name.endswith(".csv"):
            return pd.read_csv(file)
        elif file.name.endswith(".xlsx"):
            return pd.read_excel(file)
        else:
            st.error(f"Unsupported file format: {file.name}")
            return None

    # Normalize PO numbers by removing curly braces, commas, and trimming whitespace
    def normalize_po(po_value):
        if isinstance(po_value, str):
            # Remove curly braces, commas, and strip leading/trailing spaces
            po_value = po_value.replace("{", "").replace("}", "").replace(",", "").strip()
        return po_value

    # Only proceed if both files are uploaded
    if uploaded_po is not None and uploaded_de is not None:
        # Load the uploaded files
        df_po = load_file(uploaded_po)
        df_de = load_file(uploaded_de)

        # Ensure files were successfully loaded
        if df_po is not None and df_de is not None:
            # Normalize the PO columns in both dataframes
            df_po["PO_Number"] = df_po["PO_Number"].apply(normalize_po).astype(str).str.strip()
            df_de["Studio Normalized Value"] = df_de["Studio Normalized Value"].apply(normalize_po).astype(str).str.strip()

            # Process the data by comparing normalized PO values
            df_de["po_found"] = df_de["Studio Normalized Value"].apply(
                lambda x: 1 if x in df_po["PO_Number"].values else 0
            )
            
            # Display the entire dataframe with po_found column
            st.write("### Processed Dataframe with po_found Column:")
            st.dataframe(df_de)
            

            # Filter rows where po_found == 0
            df_filtered = df_de[df_de["po_found"] == 0]
            
            # Display filtered dataframe with po_found == 0
            st.write("### Rows where po_found == 0:")
            st.dataframe(df_filtered)
            
            # Display clickable URLs where po_found == 0
            if "URL" in df_filtered.columns:
                st.write("### Document with missing POs in DB:")
                for url in df_filtered["URL"]:
                    if pd.notna(url):  # Ensure the URL is not NaN
                        st.markdown(f"[{url}]({url})")
            else:
                st.error("The 'URL' column does not exist in the uploaded Delivery (DE) file.")   
else:
     st.warning("Please provide Jira credentials.")


