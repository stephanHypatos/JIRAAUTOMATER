
"""
modules/external_groups.py
--------------------------

Maps Jira *accountIds* to the business group that should appear in
TimeReport when the user's e-mail domain is not visible.


"""
EXTERNAL_ACCOUNT_GROUPS: dict[str, str] = {

    # EY external contractors
    "712020:aab56863-b848-42e3-9564-2d6f5ae4b591": "EY GERMANY", # m schütz
    "712020:5d66a452-3d4a-426c-900b-b04170734bc1": "EY GERMANY",  # a schummer 
    "712020": "EY GERMANY", # m schütz
    "62d686240824ad5c19c6c86c": "EY GERMANY", # a schummer 
    "712020:731b39c7-91e3-443b-a7ae-1065a1cead7d": "EY GERMANY", # Maniwh
    "712020:562d8f98-f0f3-402e-b725-0bd490a624b3": 'EY GERMANY', # Lynn
    "712020:1cb5d869-7511-45ec-9df6-c8e54fdc014c": 'EY GERMANY', # Junior
    "5dd52348e7ceef0eed1f010f": "EY GERMANY", # "Christopher.Rautzenberg"
    "712020:3042d035-7aec-46ae-bc13-b71d01f9a9e1": "EY GERMANY", # "ravi.ravi",
    "712020:51b44178-481b-44a2-8d53-61f582d1e876": "EY GERMANY", # " "Tim Brake",
    "712020:731b39c7-91e3-443b-a7ae-1065a1cead7d": "EY GERMANY", # " "Manish
    "712020:70c90d00-8479-4856-a4fe-81f9c56447b3": "EY GERMANY", # monica
    "712020:4a40e412-8855-4d08-ad30-47e4c7a55971": "EY GERMANY", # "Kriti Sood",
    "712020:2668348d-b4fc-49fa-b23c-48a7797860dd": "EY GERMANY", #"Shahab Akhtar Khan",
    "631069d26856bdd60a9ed28a": "EY GERMANY", #"Andreas.Muzzu",
     "712020:0d01dd6e-d274-4c92-a6ef-6c83800aca86": "EY GERMANY", #  "Karen Gorantsyan",
    "712020:8e08af8b-5b10-4fe6-a777-c5982b17a61d": "EY GERMANY", # "Diyi Huang",
    "712020:20406f95-2567-478f-b526-2b22fdd6eae5": "EY GERMANY", # "Janik Dausend",

    # KPMG external contractors
    "712020:fe650ad4-f5fd-4a76-b12e-2cad83b46228": "KPMG NL", # eligio
    "5dccf98b500b7d0dfdcade51": "KPMG NL",  # "Hans Schut",
    "712020:95231b9d-7447-450c-9bd3-6bd627527c64": "KPMG NL",  # "Lard van Zuylen
    "712020:635ac5c6-fe6a-405b-9a71-6ea51c896a52": "KPMG NL",  # "Boekstaaf.hosny
    "712020:05a54db0-8d56-4b8a-8199-a2b2e9fde44c": "KPMG NL",  # "Lalescu, Nicolle",

    # PWC external contractors
    "712020:e48a7d13-5774-4e2d-978f-10c85f3e2e96": "PWC GERMANY", # "Filip Faryna",
    "70121:f6b18ee2-28c5-4ec6-afb4-89ead2d89202": "PWC GERMANY", #Katrin
    "712020:18850c1b-7e62-442f-a9e8-097bc112a6e4": "PWC GERMANY", #"Desiree Gansch",
    "712020:3ac6dbc9-4279-40f5-b5fd-1ed600c5e68d": "PWC GERMANY", # "Jadwiga Szewczuk",
    "5ea694b586d01b0b7dc8d855": "PWC GERMANY", #"Jan Wamhoff",
    "6371e16e5fc160544e16e6d3": "PWC GERMANY",  #"Malgorzata Lipiarz",
    "62d7cf8896f239ca6ae81527": "PWC GERMANY", #"Niklas van der Linde",
    "63bc61a18a7d2f693bf68893": "PWC GERMANY", #"stol.marcin@pwc.com",
    "70121:d36f9367-a04b-408a-ac1e-bda7151054c9":"PWC GERMANY",  #"niklas.sengteller",
    "712020:f897f73e-1954-4b7d-9d43-faf0884a10ad":"PWC GERMANY" #"Victoria Knopf",
    
}

