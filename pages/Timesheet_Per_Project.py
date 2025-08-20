import streamlit as st
import pandas as pd
from datetime import datetime

from services.db import load_planned_vs_realized_mandays


st.header("Timesheet Per Project")

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
        "remaining_billable_mandays": "Remaining Billable Mandays",
        "remaining_non_billable_mandays": "Remaining Non-Billable Mandays",
    }[x],
)

mapping_file = "master project mapping.xlsx"

df = load_planned_vs_realized_mandays()
pivot_df = df.pivot_table(
    columns="employee_code", index="project", values=mandays_option, fill_value=0
)

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
