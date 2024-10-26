
# PATH to excelfile on server FS
EXCEL_FILE_PATH = 'templates/jiraissues.xlsx'
EXCEL_FILE_PATH_BLUE_PRINT = 'templates/IssueBluePrint.xlsx'

EXCEL_FILE_PATH_BLUE_PRINT_PILOT = 'templates/IssueBluePrintPilot.xlsx'
EXCEL_FILE_PATH_BLUE_PRINT_ROLLOUT = 'templates/IssueBluePrintRollout.xlsx'
EXCEL_FILE_PATH_BLUE_PRINT_POC = 'templates/IssueBluePrintPoc.xlsx'
EXCEL_FILE_PATH_BLUE_PRINT_TEST = 'templates/IssueBluePrintTest.xlsx'
EXCEL_FILE_PATH_BLUE_PRINT_ROLLOUT_WIL = 'templates/IssueBluePrintRolloutWIL.xlsx'

EXCEL_TIMELINE_ELEMENTS = 'timeline_v2.xlsx'
TIMELINE_POWER_POINT_SLIDE = 'timeline_v2.pptx'
EXCEL_TIMELINE_ELEMENTS_POC = 'timeline_v2_POC.xlsx'
TIMELINE_POWER_POINT_SLIDE_POC = 'timeline_v2_POC.pptx'

# Jira connection settings
ADMINS = ['stephan.kuche@hypatos.ai','jorge.costa@hypatos.ai']
JIRA_URL = 'https://hypatos.atlassian.net/'
JIRA_ACCOUNT_ISSUE_TYPE = 'Account'
JIRA_PROJECT_ISSUE_TYPE = 'Project'
JIRA_EPIC_ISSUE_TYPE = 'Epic'
JIRA_TASK_ISSUE_TYPE = 'Task'
JIRA_SUBTASK_ISSUE_TYPE = 'Sub-task'
# switch key if a new board is used as the template board
JIRA_TEMPLATE_BOARD_KEY = 'TD'
JIRA_DEV_ROLE_ID='10071'
JIRA_ADMIN_ROLE_ID='10002'
JIRA_API_URL = "https://hypatos.atlassian.net/rest/api/2"
JIRA_API_URL_V3 = "https://hypatos.atlassian.net/rest/api/3"

EXCLUDED_BOARD_KEYS = {'CSLP','CSNEW','EM','ZZZ','SIM','BXIMH','DFM','SE','ROP','OKR', 'FIPR', 'REQMAN', 'MBZ', 'T3S', 'SKK', 'PMO', 'TESTC', 'DUR', 'PS', 'PE', 'TESTB', 'KATE', 'MDG', 'TESTA', 'UGI', 'TESTD', 'TOH', 'MON','DBFM'}
# Assignable users in HY jira 
ASSIGNABLE_USER_GROUP = 'CSR'
# user who can be assigned as lead to a jira board
LEAD_USER_MAPPING = {
            'elena.kuhn':'712020:9de34ad3-f71e-4093-bd04-354b08b4a982',
            'erik.roa':"712020:21733a1a-064e-49e9-a3b8-29a232a4ebe6",
            'alex.menuet':"61ae5486744c4d0069633e7f",
            'jorge.costa': '621d1acfb7e7c700715583e7',
            'stephan.kuche': "630cd2ab3310c2492b59c51f",
            'yavuz.guney':"712020:37b7fd3e-db24-433f-88d7-e84bb8d27551",
            'michael.misterka':"712020:a72d1b25-ec0d-49ed-9313-f02b3cd36b8c",
            'ekaterina.mironova':"712020:45df7004-d0c2-4759-a3d6-c5737d5be307"
        }

TEMPLATE_MAPPING = {
            'software': 'com.atlassian.jira-software-project-templates:jira-software-simplified-kanban-classic',
            'business': 'com.atlassian.jira-core-project-templates:jira-core-simplified-project-management',
            'service_desk': 'com.atlassian.servicedesk:itil-v2-service-desk-project'
        }

# Confluence URLs
TEMPLATE_SPACE_KEY = 'TESTCUST'
    # Page ID of the Confluence page to update customer success page 
PAGE_ID = "607224585"  # ID of the page
    # Index of the table on the page (0 if it's the first table)
TABLE_INDEX = 0

# Documenation Links
CREATE_SPACE_DOCU = 'https://hypatos.atlassian.net/wiki/spaces/PD/pages/1289814125/Confluence+Customer+Space+Creation'
HYPA_PMO_DOCU = 'https://hypatos.atlassian.net/wiki/spaces/PD/pages/1115947248/Project+Management+Playbook+HYPA+PMO'