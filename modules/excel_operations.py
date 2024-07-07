import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import NamedStyle,PatternFill

# Return a dataframe based on a given excel file
def read_excel(file_path):
    df = pd.read_excel(file_path)
    return df

# Applies a named style and filling to a given sheet and range
def apply_named_style_and_fill_to_range(sheet, cell_range, style, fill):
    for row in sheet[cell_range]:
        for cell in row:
            cell.style = style
            cell.fill = fill
