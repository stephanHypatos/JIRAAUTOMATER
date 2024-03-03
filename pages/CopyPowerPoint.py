import streamlit as st
from jira import JIRA
import pandas as pd
from modules.config import JIRA_URL,TIMELINE_POWER_POINT_SLIDE,EXCEL_TIMELINE_ELEMENTS
from modules.jira_operations import get_company_managed_projects_df
import tempfile
from pptx import Presentation
from openpyxl import load_workbook


# Get the excelfile and the slidedeck template
##########################################################################


# Create a copy using tempfile
##########################################################################

def copy_excel():
    
    # Path to excel template
    template_path_excel = f'templates/ThinkCell/{EXCEL_TIMELINE_ELEMENTS}'
    # Load the workbook and create a copy
    template_workbook = load_workbook(template_path_excel)
    sheet = template_workbook.active  # This selects the first sheet
    # Modify a cell's value
    sheet['M2'] = '80' 
    
    # Save the presentation to a temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmpfile:
        template_workbook.save(tmpfile.name)
        return tmpfile.name

def copy_powerpoint():
    
    # Path to template and output PowerPoint files (Weekly Report)
    original_pptx_path = f'templates/ThinkCell/{TIMELINE_POWER_POINT_SLIDE}'
    # Load PowerPoint template
    presentation = Presentation(original_pptx_path)


    # Save the presentation to a temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pptx") as tmpfile:
        presentation.save(tmpfile.name)
        return tmpfile.name


presentation_path= copy_powerpoint()
# Create a download button in the Streamlit app
with open(presentation_path, "rb") as f:
    st.download_button(
        label="Download PowerPoint presentation",
        data=f,
        #file_name="presentation.pptx",
        file_name=f'timeline_ppt_copy.pptx',
        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation"
    )


excel_path= copy_excel()
# Create a download button in the Streamlit app
with open(excel_path, "rb") as f:
    st.download_button(
        label="Download Excel File",
        data=f,
        #file_name="presentation.pptx",
        file_name=f'timeline_xlsx_copy.xlsx',
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

