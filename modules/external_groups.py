
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
    "712020:562d8f98-f0f3-402e-b725-0bd490a624b3": 'EY', # Lynn
    "712020:1cb5d869-7511-45ec-9df6-c8e54fdc014c": 'EY', # JUnior
     
    # KPMG external contractors
    "712020:fe650ad4-f5fd-4a76-b12e-2cad83b46228": "KPMG", # eligio
    
    # KPMG external contractors
    "1212": "PWC"
    
}

