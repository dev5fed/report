import streamlit as st
import pandas as pd
import psycopg2
import os

# load data from .env file
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()


# Database connection
@st.cache_resource
def get_connection():
    return psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST"),
        port=os.environ.get("POSTGRES_PORT"),
        dbname=os.environ.get("POSTGRES_DATABASE"),
        user=os.environ.get("POSTGRES_USERNAME"),
        password=os.environ.get("POSTGRES_PASSWORD"),
    )


def load_data(conn):
    query = (
        "SELECT employee_code as code, "
        "timesheet.date as date, "
        "CASE WHEN project.project_name IS NOT NULL "
        "THEN project.project_name "
        "ELSE ops_project.project_name END as project, "
        "CASE WHEN ops_static_module.module_name IS NOT NULL "
        "THEN ops_static_module.module_name "
        "ELSE module.module_name END as module, "
        "tsp.parameter_name as status, "
        "'Billable' as billable, "
        'timesheet."manHoursBillable" as man_hours, '
        "first_name || ' ' || last_name as name "
        "FROM employee "
        "JOIN job ON employee.job_id = job.id "
        "JOIN timesheet ON employee.id = timesheet.employee_id "
        "LEFT JOIN ops_project ON timesheet.ops_project_id = ops_project.id "
        "LEFT JOIN project ON ops_project.project_id = project.id "
        "JOIN timesheet_status ON timesheet.timesheet_status_id = timesheet_status.id "
        "JOIN parameter tsp ON timesheet_status.status_id = tsp.id "
        # join with module in ops_static_module or module in project
        "LEFT JOIN ops_static_module ON timesheet.ops_static_module_id = ops_static_module.id "
        "LEFT JOIN ops_project_module ON timesheet.ops_project_module_id = ops_project_module.id "
        'LEFT JOIN "module" ON ops_project_module.module_id = "module".id '
        "WHERE timesheet.\"manHoursBillable\" > '00:00' "
        "UNION ALL "
        "SELECT employee_code as code, "
        "timesheet.date as date, "
        "CASE WHEN project.project_name IS NOT NULL "
        "THEN project.project_name "
        "ELSE ops_project.project_name END as project, "
        "CASE WHEN ops_static_module.module_name IS NOT NULL "
        "THEN ops_static_module.module_name "
        "ELSE module.module_name END as module, "
        "tsp.parameter_name as status, "
        "'Non-Billable' as billable, "
        '"manHoursNonBillable" as man_hours, '
        "first_name || ' ' || last_name as name "
        "FROM employee "
        "JOIN job ON employee.job_id = job.id "
        "JOIN timesheet ON employee.id = timesheet.employee_id "
        # join with module in ops_static_module or module in project
        "LEFT JOIN ops_static_module ON timesheet.ops_static_module_id = ops_static_module.id "
        "LEFT JOIN ops_project_module ON timesheet.ops_project_module_id = ops_project_module.id "
        'LEFT JOIN "module" ON ops_project_module.module_id = "module".id '
        "LEFT JOIN ops_project ON timesheet.ops_project_id = ops_project.id "
        "LEFT JOIN project ON ops_project.project_id = project.id "
        "JOIN timesheet_status ON timesheet.timesheet_status_id = timesheet_status.id "
        "JOIN parameter tsp ON timesheet_status.status_id = tsp.id "
        "WHERE timesheet.\"manHoursNonBillable\" > '00:00' "
        "ORDER BY code, date, project, module, status, billable"
    )
    return pd.read_sql(query, conn)


st.title("Timesheet Monitoring Sementara")

# Load data
conn = get_connection()
df = load_data(conn)

# Filters by employee_code and Date Range
st.sidebar.header("Filters")
employee_code = st.sidebar.text_input("Employee Code", "")

today = datetime.today()
start_of_week = today - timedelta(days=today.weekday())
start_of_prev_week = start_of_week - timedelta(weeks=1)
end_of_prev_week = start_of_prev_week + timedelta(days=6)

start_date = st.sidebar.date_input("Start Date", start_of_prev_week.date())
end_date = st.sidebar.date_input("End Date", end_of_prev_week.date())

# add multi-select filter for timesheet status
status_options = df["status"].unique().tolist()
default_status_options = [
    # "Pending",
    "Approved",
    "Modified",
    # "Draft",
]
status_filter = st.sidebar.multiselect(
    "Timesheet Status", status_options, default=default_status_options
)
# Filter the DataFrame if any status is selected
if status_filter:
    df = df[df["status"].isin(status_filter)]

# add multi-select filter for billable
billable_options = df["billable"].unique().tolist()
default_billable_options = ["Billable", "Non-Billable"]
billable_filter = st.sidebar.multiselect(
    "Billable", billable_options, default=default_billable_options
)
# Filter the DataFrame if any billable option is selected
if billable_filter:
    df = df[df["billable"].isin(billable_filter)]


# Ensure start_date is before end_date
if start_date > end_date:
    st.sidebar.error("Start date must be before end date.")


# Filter the DataFrame based on user input
# Ensure 'date' column is in datetime format (without timezone for comparison)
df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
start_date = pd.to_datetime(start_date)
end_date = pd.to_datetime(end_date)

filtered_df = df[
    (df["code"].str.contains(employee_code, case=False, na=False))
    & (df["date"] >= start_date)
    & (df["date"] <= end_date)
]

# Download button
csv = filtered_df.to_csv(index=False).encode("utf-8")
st.download_button(
    label="Download CSV",
    data=csv,
    file_name="filtered_data.csv",
    mime="text/csv",
)

# Display the filtered DataFrame
st.subheader("Filtered Data")
st.write(filtered_df)
# Display the number of records
st.write(f"Number of records: {filtered_df.shape[0]}")
# Display the DataFrame as a table
# st.dataframe(filtered_df)
# Display the DataFrame as a table
# st.table(filtered_df)


# Convert man_hours from interval to hours
def duration_to_hours(duration):
    if isinstance(duration, str):
        # Convert string to timedelta
        duration = pd.to_timedelta(duration)
    elif isinstance(duration, pd.Timedelta):
        pass  # Already in timedelta format
    else:
        return 0  # Handle unexpected types

    # Convert timedelta to total hours
    return duration.total_seconds() / 3600


# Convert 'man_hours' from interval to hours
filtered_df["man_hours"] = filtered_df["man_hours"].apply(duration_to_hours)

# Create summary table: rows is person, columns is date, cell is sum of man hours
if not filtered_df.empty:
    # Group by name and date, sum the man_hours
    pivot_df = filtered_df.groupby(["name", "date"])["man_hours"].sum().reset_index()

    # Create pivot table with names as rows and dates as columns
    pivot_table = pivot_df.pivot(index="name", columns="date", values="man_hours")

    # Fill NaN values with 0
    pivot_table = pivot_table.fillna(0)

    # Format dates as column headers
    pivot_table.columns = [col.strftime("%Y-%m-%d") for col in pivot_table.columns]

    # Add a total column
    pivot_table["Total"] = pivot_table.sum(axis=1)

    # Add a total row
    pivot_table.loc["Total"] = pivot_table.sum(axis=0)

    # Apply red background to zeros (excluding total row and column)
    def highlight_zeros(val):
        color = "background-color: red" if val == 0 else ""
        return color

    # Create styled dataframe
    styled_pivot = pivot_table.style.applymap(
        highlight_zeros,
        subset=pd.IndexSlice[
            pivot_table.index[:-1],  # Exclude total row
            pivot_table.columns[:-1],  # Exclude total column
        ],
    ).format("{:.2f}")

    st.subheader("Summary Table (Person vs Date)")
    st.dataframe(styled_pivot, use_container_width=True)

    # Show summary statistics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Man Hours", f"{pivot_table.loc['Total', 'Total']:.2f}")
    with col2:
        st.metric("Total People", len(pivot_table.index) - 1)  # Exclude total row
    with col3:
        st.metric("Total Days", len(pivot_table.columns) - 1)  # Exclude total column
else:
    st.warning("No data available for the selected filters.")
