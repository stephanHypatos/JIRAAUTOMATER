## TO DO
- [ ] Check if issues already exist in Project to avoid to recreate issues
- [x] Add the real issues to the Blueprint
- [ ] delete def add_issue_links_v1 from jiraoperations
- [ ] update computedates functions in jiraoperations
- [x] document that blocks can have several values seperated by comma
- [x] Update the Weekly Report Template
- [ ] delete create_Start_and_End_date function
- [x] LInkedIssues
- [ ] formentry for new tasks in excel - instead of putting working directly in the excel sheet the user should only use the formentry to avoid falsy input
- [ ] testing UPDATE function
- [ ] UPDATE has_customfield function as follows: use JQL to check if a specific project has a customfield - use this function in update jira 
- [] Assignee of an Issue if no external User is added to JWM
    - add customfield_10127 ( Other ) to all Jira WM projects
    - user this customfields if customer has not external user but you still want to display the assignee in a field in Jira and the excel sheet 
    - update the UPDATE function and add the customfield_10127 to the dictionary to also update this - done
- [x] PowerPoint Formatting -Table needs to be formatted
- [x] PowerPoint delete "Content Placeholder 2" if exists
- [x] PowerPoint colors
- [x] JQL add JQL to input in Streamlit app
- [x] define JQL for Report ( all issues status=open, duedate in 5 days,)
- [x] Fix Project Selection Global var assignment
- [x] Save Jira Credentials within a session
- [ ] Sharepoint Connection

## TESTCASES UDPDATE JIRA Issues from Excel
- create epic should return - not possible
- create task / sub task only possible with parent that exists
- update description - should not work
- update external assignee
- update startdate
- update enddate
- update status

## LINKEDISSUES - DONE
This "old" function creates a new row - if an issue has more than one linkedissue, excel sheet 
 archive/update_issue_overview_sheet_org_add_rows.py
`
def update_issue_overview_sheet(excel_data, issue_data):
    # Create a DataFrame for the "IssueOverview" sheet with selected columns
    issue_overview_df = pd.DataFrame(issue_data, columns=['IssueKey', 'Summary', 'IssueType', 'ParentSummary', 'Status','StartDate', 'DueDate', 'Description','Assignee','ExternalAssignee'])

    # Update the DataFrame with dynamic columns for issue links
    link_info = []
    for issue_info in issue_data:
        link_num = 1
        while True:
            link_type_key = f'LinkType{link_num}'
            linked_issue_key = f'LinkedIssueSummary{link_num}'

            if link_type_key in issue_info and linked_issue_key in issue_info:
                link_info.append({
                    'IssueKey': issue_info['IssueKey'],
                    'LinkType': issue_info[link_type_key],
                    'LinkedIssueSummary': issue_info[linked_issue_key]
                })
                link_num += 1
            else:
                break

    # Convert the link_info list to a DataFrame
    link_info_df = pd.DataFrame(link_info)

    # Merge the link_info DataFrame with the main DataFrame on 'IssueKey'
    merged_df = pd.merge(issue_overview_df, link_info_df, on='IssueKey', how='left')

    # Write updated data to the "IssueOverview" sheet
    with pd.ExcelWriter(EXCEL_FILE_PATH, engine='openpyxl') as writer:
        # Write "IssueOverview" with the specified columns
        merged_df.to_excel(writer, index=False, sheet_name='IssueOverview')

    print(f"Updated 'IssueOverview' sheet with dynamic columns for issue links.")
    `



##  compute dates (start and end dates)


Loop over each row in the Excel data.
Check if the issue type is "Task."
Check if a task with the same summary already exists in the task_info list.
If yes, use the existing start date and compute the end date.
If no, create a new task in task_info with the summary and parent key from the Excel data.
Use the project start date as the start date.
Compute the end date using the duration from the Excel data.
If there is a value in the "Blocks" column, create a new task in task_info with the value in "Blocks" as the summary.
Use the end date of the current task as the start date for the new task.

(In each for loop it read every value in the columns "Summary" , "IssueType", "Duration", "Blocks"
-  it only takes issues of Type "Task" into consideration
- for each task in  excel_data a new task is created in task_info
BUT there are a few conditions.
First check: Is there already a task with the same summary in task_info? 
if yes: 
-  use the start_date, that is already in task_info and compute the end_date by using the computation
- go to the next item
if no:
- create a new task with the summary and parent_key that is found in the excel_data
- use the project_startdate as start_date, write it to the start_date in task_info, compute the end_date by using duration of the excel_data, write the computed end_date to end_date in task_info
nested check: 
- check if there is a value in "Blocks"
if yes:
- create a new task in task_info and use the value in "Blocks" for the summary in task_info
- use the end_date of the task and set it as the start_date of the task that is being created
if no:
- go to the next item or next row in excel_data))



Compute Dates of Epic and Subtasks
- an Epic start& enddate is always the min(start_date) &t max(end_date) of all its child issues
- a Sub-Task start & enddate is always the same as its parent start & enddate ( this was implemented in order to reduce complexity )