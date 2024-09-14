import streamlit as st
import pandas as pd 
import io 

st.set_page_config(page_title="Find Missing PO", page_icon="ℹ️")
st.title('Find non-existent Purchase Orders in HY DATABASE')

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
    

    def convert_df_to_excel(df):
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Filtered Data')
        processed_data = output.getvalue()
        return processed_data


    # Function to load file based on its extension
    def load_file(file):
        if file.name.endswith(".csv"):
            return pd.read_csv(file)
        elif file.name.endswith(".xlsx"):
            return pd.read_excel(file)
        else:
            st.error(f"Unsupported file format: {file.name}")
            return None

    # Normalize and split PO numbers: remove curly braces and split by comma
    def normalize_and_split_po(po_value):
        if isinstance(po_value, str):
            # Remove curly braces and strip spaces
            po_value = po_value.replace("{", "").replace("}", "").strip()
            # Split by comma to handle multiple PO numbers
            po_numbers = po_value.split(",")
            # Strip spaces from each PO number and return the list
            return [po.strip() for po in po_numbers]
        return [str(po_value)]  # Return the value as a string inside a list if it's a single PO number

    # Only proceed if both files are uploaded

    if uploaded_po is not None and uploaded_de is not None:
        # Load the uploaded files
        df_po = load_file(uploaded_po)
        df_de = load_file(uploaded_de)

        # Ensure files were successfully loaded
        if df_po is not None and df_de is not None:
            # Rename column "Raw Data → ExternalId" to "PO_Number" in df_po
            #df_po.rename(columns={"Raw Data → ExternalId": "PO_Number"}, inplace=True)

            # Normalize and split the PO numbers in df_de
            df_de["Studio Normalized Value"] = df_de["Studio Normalized Value"].apply(normalize_and_split_po)
            
            # Expand the rows: each PO number gets its own row (explode function)
            df_de_exploded = df_de.explode("Studio Normalized Value").reset_index(drop=True)

            # Ensure PO numbers in df_po are treated as strings
            df_po["PO_Number"] = df_po["PO_Number"].apply(str).apply(normalize_and_split_po).explode().str.strip()

            # Ensure PO numbers in df_de_exploded are treated as strings
            df_de_exploded["Studio Normalized Value"] = df_de_exploded["Studio Normalized Value"].apply(str).str.strip()

            # Debugging: Check exploded dataframe
            st.write("### All documents in Studio with PO number extracted")
            st.dataframe(df_de_exploded)

            # Now, process the data by checking if PO numbers in df_de_exploded match those in df_po
            def check_po_found(po):
                # Check if PO is found in df_po["PO_Number"].values
                return 1 if po in df_po["PO_Number"].values else 0

            # Apply the check_po_found function for each PO number
            df_de_exploded["po_found"] = df_de_exploded["Studio Normalized Value"].apply(check_po_found)

            # Filter rows where po_found == 0
            df_filtered = df_de_exploded[df_de_exploded["po_found"] == 0]
            
            # Display filtered dataframe with po_found == 0
            st.write("### Documents in Studio with missing POs in DB:")
            st.dataframe(df_filtered)
            
            # Display clickable URLs where po_found == 0
            if "URL" in df_filtered.columns:
                st.write("### Documents with missing POs in DB:")
                for url in df_filtered["URL"]:
                    if pd.notna(url):  # Ensure the URL is not NaN
                        st.markdown(f"[{url}]({url})")
            else:
                st.error("The 'URL' column does not exist in the uploaded Studio Data file.")

# Total number of documents (total rows in exploded dataframe)
        total_documents = df_de_exploded.shape[0]
        
        # Number of documents without PO (where po_found == 0)
        documents_without_po = df_filtered.shape[0]
        
        # Percentage of documents without PO
        if total_documents > 0:
            percentage_without_po = (documents_without_po / total_documents) * 100
        else:
            percentage_without_po = 0

        # Display results
        st.write("### Summary:")
        st.write(f"**Total number of documents:** {total_documents}")
        st.write(f"**Number of documents without PO:** {documents_without_po}")
        st.write(f"**Percentage of documents without PO:** {percentage_without_po:.2f}%")

        # Convert the filtered dataframe to Excel for download
        excel_data = convert_df_to_excel(df_filtered)

        # Provide download button for the Excel file
        st.download_button(
            label="Download filtered data as Excel",
            data=excel_data,
            file_name="filtered_data.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

else:
     st.warning("Please provide Jira credentials.")


