import streamlit as st
import pandas as pd
import os
from datetime import datetime, timedelta
from io import BytesIO
from services import db
from utils import convert_timedelta_to_hours


st.title("Timesheet Monitoring Sementara")

# Sidebar page selection
st.sidebar.title("Navigation")

st.sidebar.header("Filters")
employee_code = st.sidebar.text_input("Employee Code", "")

today = datetime.today()
start_of_week = today - timedelta(days=today.weekday())
start_of_prev_week = start_of_week - timedelta(weeks=1)
end_of_prev_week = start_of_prev_week + timedelta(days=6)

start_date = st.sidebar.date_input("Start Date", start_of_prev_week.date())
end_date = st.sidebar.date_input("End Date", end_of_prev_week.date())

# Load timesheet data filtered by date range
df = db.load_timesheet_data(start_date, end_date)

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

status_options = ["Approved", "Modified", "Pending", "Draft"]
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

# Convert date column to datetime for consistent handling
df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)

# Filter by employee code only (date filtering is now done in the database)
filtered_df = df[df["code"].str.contains(employee_code, case=False, na=False)]

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

    styled_pivot = pivot_table.style.map(
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
