# pages/CreateTicket.py  — Jira Cloud REST v3

import datetime
import requests
import streamlit as st

from modules.config import (
    JIRA_URL,
    ADMINS,
    JIRA_SUBTASK_ISSUE_TYPE,
    JIRA_TASK_ISSUE_TYPE,
    HYPA_PMO_TICKET_DOCU,
)
from modules.jira_v3 import JiraV3
from modules.jira_operations import (
    get_project_keys,
    create_jira_issue_ticket_template,     
    save_jira_project_key,
    get_children_issues_ticket_template,   
    get_jira_issue_type_project_key_with_displayname,  
    display_issue_summaries,               
)
from modules.ticket_template_operations import (
    find_placeholders
)

# --- Temporary notice for non-Stephan users ---
if st.session_state.get("api_username", "").lower() != "stephan.kuche@hypatos.ai":
    st.warning("🚧 This page is currently under construction. Some features may not work as expected.")
    st.stop()  # Optional: stop execution so nothing else runs



# ────────────────────────────────────────────────────────────────
# Helper
# ────────────────────────────────────────────────────────────────

def adf_to_plain_text(node) -> str:
    """
    Minimal ADF → text extractor. Safely handles dicts/lists/strings.
    We only care about harvesting 'text' fields.
    """
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return " ".join(adf_to_plain_text(n) for n in node if n is not None)
    if isinstance(node, dict):
        # leaf text
        if isinstance(node.get("text"), str):
            return node["text"]
        pieces = []
        # common container key in ADF
        if isinstance(node.get("content"), list):
            pieces.append(adf_to_plain_text(node["content"]))
        # generically scan nested nodes
        for v in node.values():
            if isinstance(v, (dict, list)):
                pieces.append(adf_to_plain_text(v))
        return " ".join(pieces).strip()
    return str(node)


def replace_placeholders(text, placeholder_values: dict) -> str:
    """
    Replace {$placeholder$} occurrences with provided values.
    Accepts either plain strings or ADF dicts for 'text'.
    """
    s = adf_to_plain_text(text) if not isinstance(text, str) else text
    for ph, val in (placeholder_values or {}).items():
        s = s.replace(f"{{$" + ph + "$}}", val or "")
    return s

# ────────────────────────────────────────────────────────────────
# Session defaults
# ────────────────────────────────────────────────────────────────
for k in ("api_username", "api_password", "jira_project_key", "processed_templates", "board_keys"):
    if k not in st.session_state:
        st.session_state[k] = [] if k in ("processed_templates", "board_keys") else ""

if "jira_client" not in st.session_state:
    st.session_state["jira_client"] = None


def main():
    st.set_page_config(page_title="Create Ticket", page_icon="🎫")
    st.title("Create Ticket")

    if not st.session_state["api_password"]:
        st.warning("Please log in first.")
        return

    # Build JiraV3 client once
    if not st.session_state["jira_client"]:
        st.session_state["jira_client"] = JiraV3(
            JIRA_URL,
            st.session_state["api_username"],
            st.session_state["api_password"],
        )
    client: JiraV3 = st.session_state["jira_client"]

    with st.expander("Expand for more information."):
        st.write(f"Read the [documentation]({HYPA_PMO_TICKET_DOCU}) here.")

    # Process templates (fetch dynamic ones from Jira issues)
    if not st.session_state["processed_templates"]:
        process_templates(client)
    processed_templates = st.session_state["processed_templates"]

    st.header("Select and Input")

    # 1) Select a template + fill placeholders
    final_summary, edited_description = ticket_selection_and_input(processed_templates)

    # 2) Select board
    board_key = board_selection()
    st.session_state["jira_project_key"] = board_key
    save_jira_project_key(board_key)

    if st.session_state["jira_project_key"]:
        # 3) Select parent Project issue + optional parent task
        parent_issue_key, project_name = project_and_parent_selection(client)

        # 4) Start/Due date selection
        start_date, due_date = date_selection(parent_issue_key, client)

        # 5) Create ticket form (status & action)
        create_ticket_form(client, final_summary, edited_description, parent_issue_key, project_name, start_date, due_date)


# ────────────────────────────────────────────────────────────────
# Template processing
# ────────────────────────────────────────────────────────────────
def process_templates(client: JiraV3):
    """Process ticket templates and store them in session state."""
    from templates.ticketTemplates import TICKET_TEMPLATES  # local import to avoid circulars

    processed_templates = []
    for template in TICKET_TEMPLATES:
        if "issue_id" in template:
            try:
                data = client.get_issue(template["issue_id"], fields=["summary", "description"])
                fields = data.get("fields", {}) or {}
                summary = fields.get("summary", "")
                description = fields.get("description", "")
                # Description in Cloud may be ADF dict; keep as-is (your template creator will handle it).
                processed_templates.append(
                    {
                        "project_key": template.get("project_key", ""),
                        "summary": summary or "",
                        "description": description or "",
                    }
                )
            except Exception as e:
                st.error(f"Failed to fetch issue {template['issue_id']}: {e}")
        else:
            processed_templates.append(template)

    st.session_state["processed_templates"] = processed_templates


# ────────────────────────────────────────────────────────────────
# Template selection & placeholders
# ────────────────────────────────────────────────────────────────
def ticket_selection_and_input(processed_templates):
    summaries = [template['summary'] for template in processed_templates]
    selected_summary = st.selectbox("Select a ticket to create:", summaries, key='selected_summary')

    selected_template = next(
        (template for template in processed_templates if template['summary'] == selected_summary), None)

    raw_description = (selected_template or {}).get("description", "") or ""
    description_text = adf_to_plain_text(raw_description)

    summary_placeholders = find_placeholders(selected_template['summary']) if selected_template else []
    description_placeholders = find_placeholders(description_text)
    all_placeholders = sorted(set(summary_placeholders + description_placeholders))

    placeholder_values = {}
    for ph in all_placeholders:
        placeholder_values[ph] = st.text_input(f"Enter a value for '{ph}':", key=f'placeholder_{ph}')

    final_summary = replace_placeholders(selected_template['summary'] if selected_template else "", placeholder_values)
    final_description = replace_placeholders(description_text, placeholder_values)

    st.header("Review and Edit")

    tab_edit, tab_preview = st.tabs(["✏️ Edit", "👁️ Preview"])

    with tab_edit:
        edited_description = st.text_area(
            "Issue Description (supports *Markdown*):",
            value=final_description,
            height=300,
            key='edited_description'
        )

    with tab_preview:
        current_text = st.session_state.get('edited_description', final_description)
        if current_text.strip():
            st.markdown(current_text, unsafe_allow_html=False)
        else:
            st.info("No description text to preview.")

    return final_summary, st.session_state.get('edited_description', final_description)



# ────────────────────────────────────────────────────────────────
# Board selection
# ────────────────────────────────────────────────────────────────
def board_selection() -> str:
    """Handle board selection (company-managed project keys)."""
    if not st.session_state["board_keys"]:
        st.session_state["board_keys"] = get_project_keys(
            JIRA_URL,
            st.session_state["api_username"],
            st.session_state["api_password"],
        )
    board_keys = st.session_state["board_keys"]
    return st.selectbox(
        "Select the Jira Board where you want to create the ticket",
        board_keys,
        index=0 if board_keys else 0,
        key="board_key",
    )


# ────────────────────────────────────────────────────────────────
# Project + parent selection
# ────────────────────────────────────────────────────────────────
def project_and_parent_selection(client: JiraV3):
    """Handle project and parent issue selection (v3)."""
    # 1) Choose the Project (issue type) within this board
    candidates = get_jira_issue_type_project_key_with_displayname(
        client, st.session_state["jira_project_key"]
    )  # -> [{ "key": "KEY-123", "summary": "..." }, ...]
    source_issue_key = display_issue_summaries(candidates)

    # Fetch the chosen project's summary for the title prefix
    issue_json = client.get_issue(source_issue_key, fields=["summary"])
    project_name = (issue_json.get("fields", {}) or {}).get("summary", "")

    # 2) Optional parent task under that Project
    try:
        children_issues = get_children_issues_ticket_template(client, source_issue_key)  # should return [{key, summary, issuetype}, ...]
        words_to_exclude = ["milestone"]
        filtered_children_issues = [
            item for item in (children_issues or [])
            if not any(word in str(item.get("summary", "")).lower() for word in words_to_exclude)
        ]
        select_options = [{"key": "No Parent", "summary": "N/A", "issuetype": "N/A"}]
        select_options.extend(filtered_children_issues)
        parent_issue_key = st.selectbox(
            "Attach the ticket to a parent Task?",
            select_options,
            format_func=lambda x: f"{x['key']} - {x['summary']}",
            index=0,
            key="parent_issue_key",
        )
    except Exception as e:
        st.warning(f"The project {source_issue_key} seems to have no child issues: {e}")
        parent_issue_key = {"key": "No Parent", "summary": "N/A", "issuetype": "N/A"}

    return parent_issue_key, project_name


# ────────────────────────────────────────────────────────────────
# Date selection
# ────────────────────────────────────────────────────────────────
def date_selection(parent_issue_key, client: JiraV3):
    """Handle start and due date selection (v3)."""
    start_date = None
    due_date = None

    set_start_date = st.checkbox("Set Start Date", key="set_start_date")
    if set_start_date:
        start_date = st.date_input("Select Start Date", format="YYYY-MM-DD", key="start_date")
    else:
        if parent_issue_key["key"] != "No Parent":
            start_date = datetime.date.today()
            st.info(f"Start date set to today: {start_date}")

    set_due_date = st.checkbox("Set Due Date", key="set_due_date")
    if set_due_date:
        due_date = st.date_input("Select Due Date", format="YYYY-MM-DD", key="due_date")
    else:
        if parent_issue_key["key"] != "No Parent":
            # read parent's duedate
            try:
                par = client.get_issue(parent_issue_key["key"], fields=["duedate"])
                parent_due_date = (par.get("fields", {}) or {}).get("duedate")
                if parent_due_date:
                    due_date = datetime.datetime.strptime(parent_due_date[:10], "%Y-%m-%d").date()
                    st.info(f"Due date set to parent's due date: {due_date}")
                else:
                    st.warning("Parent issue has no due date. Please input a due date.")
            except Exception as e:
                st.warning(f"Could not read parent due date: {e}")
        else:
            due_date = None

    return start_date, due_date


# ────────────────────────────────────────────────────────────────
# Create ticket form & transition
# ────────────────────────────────────────────────────────────────
def create_ticket_form(client: JiraV3, final_summary, edited_description, parent_issue_key, project_name, start_date, due_date):
    """Display the form for static inputs and ticket creation."""
    with st.form("creation_form"):
        possible_statuses = ["To Do", "Assign To Coe"]
        selected_status = st.selectbox("Select the desired status for the issue:", possible_statuses, key="selected_status")
        create_submitted = st.form_submit_button("Create Ticket")

    if create_submitted:
        create_ticket(client, final_summary, edited_description, parent_issue_key, project_name, start_date, due_date, selected_status)


def create_ticket(client: JiraV3, final_summary, edited_description, parent_issue_key, project_name, start_date, due_date, selected_status):
    """Create the ticket in Jira (v3) and transition it."""
    try:
        final_summary = f'[{st.session_state["jira_project_key"]}][{project_name}] {final_summary}'
        issue_type = JIRA_SUBTASK_ISSUE_TYPE
        parent_key = parent_issue_key["key"]

        if parent_issue_key["key"] == "No Parent":
            parent_key = None
            issue_type = JIRA_TASK_ISSUE_TYPE

        # Build the v3 fields dict using your existing helper (already updated to v3)
        fields = create_jira_issue_ticket_template(
            st.session_state["jira_project_key"],
            final_summary,
            issue_type,
            start_date=start_date,
            due_date=due_date,
            parent_key=parent_key,
            description=edited_description,
        )

        # Create via v3
        created = client.create_issue(fields)  # returns {"id","key","self"}
        new_key = created.get("key")
        if not new_key:
            raise RuntimeError(f"Create issue failed: {created}")

        st.success(f"Issue {new_key} created in project {st.session_state['jira_project_key']}.")

        # Transition if requested
        transition_issue_status(client, new_key, selected_status)

        st.markdown(f"[View the issue in Jira]({JIRA_URL}/browse/{new_key})")
    except Exception as e:
        st.error(f"An error occurred: {e}")


def transition_issue_status(client: JiraV3, issue_key: str, selected_status: str):
    ok = client.transition_issue_by_status_name(issue_key, selected_status)
    if ok:
        st.success(f"Issue {issue_key} transitioned to status '{selected_status}'.")
    else:
        # Show available transitions if mismatch
        transitions = client.list_transitions(issue_key)
        st.warning(f"Cannot transition to '{selected_status}' from the current status.")
        if transitions:
            st.info("Available transitions are:")
            for t in transitions:
                st.write(f"- {t.get('name')} (to status '{(t.get('to') or {}).get('name','')}')")

# ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    main()
