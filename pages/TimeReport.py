import pandas as pd
import streamlit as st
import io
from jira import JIRA
from modules.config import JIRA_URL,ADMINS,JIRA_TEMPLATE_BOARD_KEY
from modules.jira_operations import get_children_issues_for_report,get_project_keys,get_users_from_jira_project,get_jira_issue_type_project_key_with_displayname,display_issue_summaries,get_jira_issue_type_account_key,update_parent_key,save_jira_account_type_parent,save_jira_project_key,get_jira_issue_type_project_key,update_parent_issue_type_project,delete_newly_created_project,filter_dataframe,create_report_dataframe


# -----------------------------------------------------------------------------
# ⚙️  CONFIG –  # Jira connection setup
# -----------------------------------------------------------------------------
JIRA_STATE_KEY = 'jira'  # 🔑  

jira_url = JIRA_URL
jira_username = st.session_state['api_username']
jira_api_token = st.session_state['api_password']
jira = JIRA(server=jira_url, basic_auth=(jira_username, jira_api_token))

if 'api_username' not in st.session_state:
     st.session_state['api_username']= ''
if 'api_password' not in st.session_state:
    st.session_state['api_password'] = ''   
if 'jira_project_key' not in st.session_state:
    st.session_state['jira_project_key'] = ''
if JIRA_STATE_KEY not in st.session_state:
    st.session_state[JIRA_STATE_KEY] = ''

# -----------------------------------------------------------------------------
# 🗃️  Cache decorator compatible with old Streamlit versions
# -----------------------------------------------------------------------------
if hasattr(st, "cache_data"):
    _cache = st.cache_data
elif hasattr(st, "cache"):
    _cache = st.cache  # Streamlit ≤ 1.17
else:
    _cache = st.experimental_memo


@_cache(show_spinner=False)
def fetch_worklogs(_jira: JIRA, issue_keys: list[str]) -> pd.DataFrame:  # «_» = don’t hash client
    """Download *all* work‑logs for the provided issues and return a tidy DataFrame.

    • Filters out the *service account* (or any other account) whose **accountId**
      is listed in ``IGNORE_ACCOUNT_IDS`` as early as possible – so downstream
      code never sees those rows.

    Supports both Jira‑Python API flavours:
    • ``issue_worklogs`` (modern, paginated)
    • ``worklogs`` (legacy, no pagination)

    Returned columns:
        * issue_key – e.g. PROJ‑123
        * author_id – Jira accountId (stable)
        * author    – work‑log author display name (for UI)
        * date      – *naive* UTC midnight Timestamp (no tz)
        * hours     – float hours
    """

    IGNORE_ACCOUNT_IDS = {  # ← add more IDs here if needed
        "557058:f58131cb-b67d-43c7-b30d-6b58d40bd077",
    }

    rows: list[dict] = []

    def _append_rows(worklogs, issue_key):
        """Helper to DRY‑up row building for both API variants."""
        for wl in worklogs:
            if wl.author and wl.author.accountId in IGNORE_ACCOUNT_IDS:
                continue  # 🚫 skip unwanted author rows immediately

            rows.append(
                {
                    "issue_key": issue_key,
                    "author_id": wl.author.accountId if wl.author else "unknown",  # noqa: E501
                    "author": wl.author.displayName if wl.author else "Unknown",
                    "date": (
                        pd.to_datetime(wl.started, utc=True)
                        .normalize()
                        .tz_localize(None)
                    ),
                    "hours": wl.timeSpentSeconds / 3600,
                }
            )

    for key in issue_keys:
        if hasattr(_jira, "issue_worklogs"):
            # paginated – Jira Cloud & recent SDKs
            start_at = 0
            while True:
                try:
                    wls = _jira.issue_worklogs(key, startAt=start_at, maxResults=100)
                except Exception as exc:
                    st.warning(f"Failed reading work‑logs for {key}: {exc}")
                    break

                if not wls:
                    break

                _append_rows(wls, key)

                if len(wls) < 100:
                    break
                start_at += len(wls)
        else:
            # legacy single‑call API
            try:
                wls = _jira.worklogs(key)
            except Exception as exc:
                st.warning(f"Failed reading work‑logs for {key}: {exc}")
                continue

            _append_rows(wls, key)

    return pd.DataFrame(rows)



# -----------------------------------------------------------------------------
# 🚀  Page logic
# -----------------------------------------------------------------------------

def app(jira: JIRA) -> None:
    """Interactive time‑report page (child issues of a parent)."""

    st.header("⏱️ Time Report – Children Issues")

    parent_key = None
    jira_board_key = None
    
    jira_board = get_project_keys(JIRA_URL, st.session_state['api_username'], st.session_state['api_password'])
    jira_board_key = st.selectbox("Select Jira Board Key:", jira_board, index=0)
    if not jira_board_key:
        st.info("Select a Jira Board to begin.")
        st.stop()
    
    if jira_board_key: 
        jira_issue_type_project = get_jira_issue_type_project_key_with_displayname(jira,jira_board_key)
        source_issue_key=display_issue_summaries(jira_issue_type_project)
        parent_key = source_issue_key

    if not parent_key:
        st.info("Enter a project issue key to begin.")
        st.stop()

    # ------------------------------------------------------------------
    # Pull child issues
    # ------------------------------------------------------------------
    try:
        with st.spinner("Fetching child issues …"):
            issue_keys = get_children_issues_for_report(jira, parent_key)
    except Exception as exc:
        st.exception(exc)
        st.stop()

    if not issue_keys:
        st.warning("No children found for that parent.")
        st.stop()

    # ------------------------------------------------------------------
    # Work‑logs
    # ------------------------------------------------------------------
    with st.spinner("Gathering work‑logs …"):
        df = fetch_worklogs(jira, issue_keys)
    if df.empty:
        st.warning("No work‑logs under this parent.")
        st.stop()

    # ------------------------------------------------------------------
    # Sidebar controls
    # ------------------------------------------------------------------
    st.sidebar.header("🔎 Filters & Grouping")

    # Authors multi‑select
    author_opts = sorted(df["author"].unique())
    sel_authors = st.sidebar.multiselect(
        "Authors",
        options=author_opts,
        default=author_opts,
    )

    # Date range selector
    min_d, max_d = df["date"].min(), df["date"].max()
    raw_start, raw_end = st.sidebar.date_input(
        "Date range",
        value=(min_d.date(), max_d.date()),
        min_value=min_d,
        max_value=max_d,
    )
    start_ts, end_ts = pd.Timestamp(raw_start), pd.Timestamp(raw_end)

    # Grouping mode (NEW!)
    group_mode = st.sidebar.radio(
        "Group results by",
        ["Author × Date", "Author only"],
        index=0,
    )

    # ------------------------------------------------------------------
    # Apply filters
    # ------------------------------------------------------------------
    fdf = df[
        (df["author"].isin(sel_authors))
        & (df["date"] >= start_ts)
        & (df["date"] <= end_ts)
    ]

    if fdf.empty:
        st.info("No data after filters.")
        st.stop()

    # ------------------------------------------------------------------
    # Group & display
    # ------------------------------------------------------------------
    if group_mode == "Author × Date":
        grouped = (
            fdf.groupby(["author", "date"], as_index=False)["hours"].sum()
            .sort_values(["author", "date"])
        )
        grouped["hours"] = grouped["hours"].round().astype(int)
        st.subheader("Hours by author × date")
    else:  # Author only
        grouped = (
            fdf.groupby("author", as_index=False)["hours"].sum()
            .sort_values("author")
        )
        grouped["hours"] = grouped["hours"].round().astype(int)
        st.subheader("Total hours per work log author (date‑agnostic)")

    st.dataframe(grouped, use_container_width=True)

    # Raw data expander & export
    with st.expander("Show raw work‑logs"):
        st.dataframe(fdf, use_container_width=True)

    # Build an in‑memory XLSX so users get native Excel formatting
    excel_buf = io.BytesIO()
    with pd.ExcelWriter(excel_buf, engine="xlsxwriter") as writer:
        fdf.to_excel(writer, index=False, sheet_name="Worklogs")
    excel_buf.seek(0)

    st.download_button(
        "📥 Download filtered XLSX",
        data=excel_buf,
        file_name=f"{parent_key}_worklogs.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )




# -----------------------------------------------------------------------------
# 🔄  Bootstrap the page when Streamlit loads this file
# -----------------------------------------------------------------------------

if JIRA_STATE_KEY not in st.session_state:
    st.error(
        f"No Jira client found in st.session_state['{JIRA_STATE_KEY}']. "
        "Initialise it in your main script so all pages can use it."
    )
else:
    app(st.session_state[JIRA_STATE_KEY])