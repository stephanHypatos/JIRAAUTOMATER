import math
import pandas as pd
from dateutil.parser import parse
from datetime import datetime, timedelta
import zipfile
import io

def normalize_NaN(str): 
    # Normalize the date format to yyyy-MM-dd
    try:
        # Check if date_str is a float (e.g., NaN)
        if isinstance(str, float) and math.isnan(str):
            return None  # Set to None if NaN
        else:
            return str

    except Exception as e:
        print(f"Error parsing string: {e}")
        return None
    
def normalize_date(date_str):
    # Normalize the date format to yyyy-MM-dd
    try:
        # Check if date_str is a float (e.g., NaN)
        if isinstance(date_str, float) and math.isnan(date_str):
            return None  # Set to None if NaN
        else:
            date_obj = parse(str(date_str))
            return date_obj.strftime('%Y-%m-%d')
    except Exception as e:
        print(f"Error parsing date: {e}")
        return None
    
def get_calendar_week():
    today = datetime.now()
    calendar_week = today.isocalendar()[1]
    return calendar_week

def get_current_month():
    today = datetime.now()
    current_month = today.strftime("%B") # today.strftime("%b") - return short notation Decemeber - Dec
    return current_month

def get_current_year():
    return datetime.now().year
   #current_year = today.strftime("%Y")
   # return current_year

def calculate_end_date(start_date, duration):
    if start_date is None or pd.isnull(duration):
        return None
    return start_date + pd.Timedelta(days=duration)

def get_current_day():
    now = datetime.now()
    current_day = now.strftime("%d.%m.%Y") # 01.01.2024
    current_day_short = now.strftime("%d.%m.%y") # 01.01.24
    return current_day


