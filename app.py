import streamlit as st
import pandas as pd
import psycopg2
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()


@st.cache_resource
def get_connection():
    return psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST"),
        port=os.environ.get("POSTGRES_PORT"),
        dbname=os.environ.get("POSTGRES_DATABASE"),
        user=os.environ.get("POSTGRES_USERNAME"),
        password=os.environ.get("POSTGRES_PASSWORD"),
    )


def load_timesheet_data(conn):
    query = """
        SELECT employee_code as code, 
               timesheet.date as date, 
               CASE WHEN ops_project.project_name IS NOT NULL 
                    THEN ops_project.project_name 
                    ELSE NULL END as project, 
               CASE WHEN ops_static_module.module_name IS NOT NULL 
                    THEN ops_static_module.module_name 
                    ELSE module.module_name END as module, 
               tsp.parameter_name as status, 
               'Billable' as billable, 
               timesheet."manHoursBillable" as man_hours, 
               first_name || ' ' || last_name as name, 
               CASE WHEN project.project_code IS NOT NULL 
                    THEN project.project_code 
                    ELSE NULL END as project_code 
        FROM employee 
        JOIN job ON employee.job_id = job.id 
        JOIN timesheet ON employee.id = timesheet.employee_id 
        JOIN ops_project ON timesheet.ops_project_id = ops_project.id 
        JOIN timesheet_status ON timesheet.timesheet_status_id = timesheet_status.id 
        JOIN parameter tsp ON timesheet_status.status_id = tsp.id 
        LEFT JOIN project ON ops_project.project_id = project.id 
        LEFT JOIN ops_static_module ON timesheet.ops_static_module_id = ops_static_module.id 
        LEFT JOIN ops_project_module ON timesheet.ops_project_module_id = ops_project_module.id 
        LEFT JOIN "module" ON ops_project_module.module_id = "module".id 
        WHERE timesheet."manHoursBillable" > '00:00' 
        UNION ALL 
        SELECT employee_code as code, 
               timesheet.date as date, 
               CASE WHEN ops_project.project_name IS NOT NULL 
                    THEN ops_project.project_name 
                    ELSE NULL END as project, 
               CASE WHEN ops_static_module.module_name IS NOT NULL 
                    THEN ops_static_module.module_name 
                    ELSE module.module_name END as module, 
               tsp.parameter_name as status, 
               'Non-Billable' as billable, 
               "manHoursNonBillable" as man_hours, 
               first_name || ' ' || last_name as name, 
               CASE WHEN project.project_code IS NOT NULL 
                    THEN project.project_code 
                    ELSE NULL END as project_code 
        FROM employee 
        JOIN job ON employee.job_id = job.id 
        JOIN timesheet ON employee.id = timesheet.employee_id 
        JOIN ops_project ON timesheet.ops_project_id = ops_project.id 
        JOIN timesheet_status ON timesheet.timesheet_status_id = timesheet_status.id 
        JOIN parameter tsp ON timesheet_status.status_id = tsp.id 
        LEFT JOIN project ON ops_project.project_id = project.id 
        LEFT JOIN ops_static_module ON timesheet.ops_static_module_id = ops_static_module.id 
        LEFT JOIN ops_project_module ON timesheet.ops_project_module_id = ops_project_module.id 
        LEFT JOIN "module" ON ops_project_module.module_id = "module".id 
        WHERE timesheet."manHoursNonBillable" > '00:00' 
        ORDER BY code, date, project, module, status, billable
    """
    return pd.read_sql(query, conn)


def convert_timedelta_to_hours(duration):
    if isinstance(duration, str):
        duration = pd.to_timedelta(duration)
    elif isinstance(duration, pd.Timedelta):
        pass
    else:
        return 0
    return duration.total_seconds() / 3600


st.title("Timesheet Monitoring Sementara")

conn = get_connection()
df = load_timesheet_data(conn)

mapping_file = "master project mapping.xlsx"
if os.path.exists(mapping_file):
    mapping_df = pd.read_excel(mapping_file, usecols="B:C")
    mapping_df.columns = ["project_name", "project_code"]
    mapping_df = mapping_df.dropna(subset=["project_name", "project_code"])

    df = df.merge(mapping_df, on="project_code", how="left")
    df["project_name"] = df["project_name"].fillna(df["project"])
    df.drop(columns=["project"], inplace=True)
    df.rename(columns={"project_name": "project"}, inplace=True)
    df = df[
        [
            "code",
            "date",
            "project",
            "module",
            "status",
            "billable",
            "man_hours",
            "name",
            "project_code",
        ]
    ]
else:
    st.warning(f"Mapping file '{mapping_file}' not found. Please upload the file.")


st.sidebar.header("Filters")
employee_code = st.sidebar.text_input("Employee Code", "")

today = datetime.today()
start_of_week = today - timedelta(days=today.weekday())
start_of_prev_week = start_of_week - timedelta(weeks=1)
end_of_prev_week = start_of_prev_week + timedelta(days=6)

start_date = st.sidebar.date_input("Start Date", start_of_prev_week.date())
end_date = st.sidebar.date_input("End Date", end_of_prev_week.date())

status_options = df["status"].unique().tolist()
default_status_options = ["Approved", "Modified"]
status_filter = st.sidebar.multiselect(
    "Timesheet Status", status_options, default=default_status_options
)
if status_filter:
    df = df[df["status"].isin(status_filter)]

billable_options = df["billable"].unique().tolist()
default_billable_options = ["Billable", "Non-Billable"]
billable_filter = st.sidebar.multiselect("Billable", billable_options, default=[])
if billable_filter:
    df = df[df["billable"].isin(billable_filter)]

project_options = df["project"].dropna().unique().tolist()
project_filter = st.sidebar.multiselect("Project", project_options, default=[])
if project_filter:
    df = df[df["project"].isin(project_filter)]

if start_date > end_date:
    st.sidebar.error("Start date must be before end date.")


df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
start_date = pd.to_datetime(start_date)
end_date = pd.to_datetime(end_date)

filtered_df = df[
    (df["code"].str.contains(employee_code, case=False, na=False))
    & (df["date"] >= start_date)
    & (df["date"] <= end_date)
]

downloaded_csv_df = filtered_df.copy()
downloaded_csv_df["man_hours"] = downloaded_csv_df["man_hours"].apply(
    convert_timedelta_to_hours
)

csv = downloaded_csv_df.to_csv(index=False).encode("utf-8")
st.download_button(
    label="Download CSV",
    data=csv,
    file_name="filtered_data.csv",
    mime="text/csv",
)

st.subheader("Filtered Data")
st.write(filtered_df)
st.write(f"Number of records: {filtered_df.shape[0]}")


filtered_df["man_hours"] = filtered_df["man_hours"].apply(convert_timedelta_to_hours)

if not filtered_df.empty:
    pivot_df = filtered_df.groupby(["name", "date"])["man_hours"].sum().reset_index()
    pivot_table = pivot_df.pivot(index="name", columns="date", values="man_hours")
    pivot_table = pivot_table.fillna(0)
    pivot_table.columns = [col.strftime("%Y-%m-%d") for col in pivot_table.columns]
    pivot_table["Total"] = pivot_table.sum(axis=1)
    pivot_table.loc["Total"] = pivot_table.sum(axis=0)

    def highlight_zeros(val):
        return "background-color: red" if val == 0 else ""

    styled_pivot = pivot_table.style.applymap(
        highlight_zeros,
        subset=pd.IndexSlice[
            pivot_table.index[:-1],
            pivot_table.columns[:-1],
        ],
    ).format("{:.2f}")

    st.subheader("Summary Table (Person vs Date)")
    st.dataframe(styled_pivot, use_container_width=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Man Hours", f"{pivot_table.loc['Total', 'Total']:.2f}")
    with col2:
        st.metric("Total People", len(pivot_table.index) - 1)
    with col3:
        st.metric("Total Days", len(pivot_table.columns) - 1)
else:
    st.warning("No data available for the selected filters.")
