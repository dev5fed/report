import os
import streamlit as st
import pandas as pd
from datetime import datetime

from services.db import load_planned_vs_realized_mandays


st.header("Remaining Mandays")

# Sidebar for selecting which remaining mandays to display
st.sidebar.header("Display Options")
mandays_option = st.sidebar.selectbox(
    "Select Remaining Mandays Type:",
    options=[
        "remaining_mandays",
        "remaining_billable_mandays",
        "remaining_non_billable_mandays",
    ],
    format_func=lambda x: {
        "remaining_mandays": "Total Remaining Mandays",
        "remaining_billable_mandays": "Remaining Billable",
        "remaining_non_billable_mandays": "Remaining Non-Billable",
    }[x],
)

mapping_file = "master project mapping.xlsx"
if os.path.exists(mapping_file):
    mapping_df = pd.read_excel(mapping_file, usecols="B:C")
    mapping_df.columns = ["project_name", "project_code"]
    mapping_df = mapping_df.dropna(subset=["project_name", "project_code"])

df = load_planned_vs_realized_mandays()
pivot_df = df.pivot_table(
    columns="employee_code", index="project", values=mandays_option, fill_value=0
)

pivot_df = pivot_df.merge(
    mapping_df, left_index=True, right_on="project_code", how="left"
)
# reset index
pivot_df = pivot_df.reset_index()

# Reorder columns to put project_name first
if "project_name" in pivot_df.columns:
    cols = ["project_code", "project_name"] + [
        col
        for col in pivot_df.columns
        if col not in ["project_code", "project_name", "index"]
    ]
    pivot_df = pivot_df[cols]

# Display the selected mandays type as a subtitle
st.subheader(f"Showing: {mandays_option.replace('_', ' ').title()}")
st.dataframe(pivot_df)

# Add download button
csv_data = pivot_df.to_csv(index=True)
filename = f"timesheet_per_project_{mandays_option}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

st.download_button(
    label="📥 Download CSV",
    data=csv_data,
    file_name=filename,
    mime="text/csv",
    help="Download the current pivot table as a CSV file",
)
