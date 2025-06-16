
"""
modules/external_groups.py
--------------------------

Maps Jira *accountIds* to the business group that should appear in
TimeReport when the user's e-mail domain is not visible.


"""
EXTERNAL_ACCOUNT_GROUPS: dict[str, str] = {

    # EY external contractors
    "712020:aab56863-b848-42e3-9564-2d6f5ae4b591": "EY", # m schütz
    "712020:5d66a452-3d4a-426c-900b-b04170734bc1": "EY",  # a schummer 
    "712020": "EY", # m schütz
    "62d686240824ad5c19c6c86c": "EY", # a schummer 
    "712020:731b39c7-91e3-443b-a7ae-1065a1cead7d": "EY", # Maniwh
    
    # KPMG external contractors
    "12": "KPMG",
    
    # KPMG external contractors
    "1212": "PWC"
    
}

