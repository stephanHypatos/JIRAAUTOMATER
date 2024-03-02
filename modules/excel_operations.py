import pandas as pd


# Return a dataframe based on a given excel file
def read_excel(file_path):
    df = pd.read_excel(file_path)
    return df