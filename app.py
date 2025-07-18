import streamlit as st
import pandas as pd
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
from io import BytesIO
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

load_dotenv()


@st.cache_resource(ttl=300)  # expires after 5 minutes
def get_engine() -> Engine:
    user = os.environ.get("POSTGRES_USERNAME")
    password = os.environ.get("POSTGRES_PASSWORD")
    host = os.environ.get("POSTGRES_HOST")
    port = os.environ.get("POSTGRES_PORT")
    db = os.environ.get("POSTGRES_DATABASE")
    url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"
    return create_engine(url, pool_size=10, max_overflow=20)


def load_timesheet_data():
    engine = get_engine()
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
    df = pd.read_sql(query, engine)
    return df


def convert_timedelta_to_hours(duration):
    if isinstance(duration, str):
        duration = pd.to_timedelta(duration)
    elif isinstance(duration, pd.Timedelta):
        pass
    else:
        return 0
    return duration.total_seconds() / 3600


st.title("Timesheet Monitoring Sementara")

# Create main tabs
main_tab1, main_tab2 = st.tabs(["📊 Timesheet Dashboard", "🗂️ Project Mapping"])

with main_tab1:
    df = load_timesheet_data()

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

    filtered_df["man_hours"] = (
        filtered_df["man_hours"].apply(convert_timedelta_to_hours).astype(float)
    )

    if not filtered_df.empty:
        pivot_df = (
            filtered_df.groupby(["name", "date"])["man_hours"].sum().reset_index()
        )
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

with main_tab2:
    st.header("🗂️ Project Mapping Editor")

    mapping_file = "master project mapping.xlsx"

    # Create tabs for different functions
    mapping_tab1, mapping_tab2, mapping_tab3 = st.tabs(
        ["View Current Mapping", "Edit Mapping", "Upload New Mapping"]
    )

    with mapping_tab1:
        st.subheader("Current Project Mapping")
        if os.path.exists(mapping_file):
            current_mapping = pd.read_excel(mapping_file, usecols="B:C")
            current_mapping.columns = ["project_name", "project_code"]
            current_mapping = current_mapping.dropna(
                subset=["project_name", "project_code"]
            )

            # Display current mapping
            st.dataframe(current_mapping, use_container_width=True)
            st.write(f"Total mappings: {len(current_mapping)}")

            # Download current mapping as Excel (same format as template)

            excel_mapping = pd.DataFrame()
            excel_mapping["A"] = [""] * len(current_mapping)  # Empty column A
            excel_mapping["B"] = current_mapping["project_name"]
            excel_mapping["C"] = current_mapping["project_code"]

            output = BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                excel_mapping.to_excel(writer, index=False, header=False)

            st.download_button(
                label="Download Current Mapping as Excel",
                data=output.getvalue(),
                file_name="current_project_mapping.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        else:
            st.warning("No mapping file found.")

    with mapping_tab2:
        st.subheader("Edit Project Mapping")

        if os.path.exists(mapping_file):
            # Load current mapping for editing
            edit_mapping = pd.read_excel(mapping_file, usecols="B:C")
            edit_mapping.columns = ["project_name", "project_code"]
            edit_mapping = edit_mapping.dropna(subset=["project_name", "project_code"])

            # Create a form for editing
            with st.form("edit_mapping_form"):
                st.write("Edit existing mappings or add new ones:")

                # Use data editor for interactive editing
                edited_mapping = st.data_editor(
                    edit_mapping,
                    num_rows="dynamic",
                    use_container_width=True,
                    column_config={
                        "project_name": st.column_config.TextColumn(
                            "Project Name",
                            help="Name of the project",
                            max_chars=100,
                            required=True,
                        ),
                        "project_code": st.column_config.TextColumn(
                            "Project Code",
                            help="Unique code for the project",
                            max_chars=50,
                            required=True,
                        ),
                    },
                )

                # Save button
                if st.form_submit_button("💾 Save Changes", type="primary"):
                    try:
                        # Clean the data
                        cleaned_mapping = edited_mapping.dropna(
                            subset=["project_name", "project_code"]
                        )

                        # Create Excel file with proper structure
                        # The original file has headers starting from column B
                        output_df = pd.DataFrame()
                        output_df["A"] = [""] * len(cleaned_mapping)  # Empty column A
                        output_df["B"] = cleaned_mapping["project_name"]
                        output_df["C"] = cleaned_mapping["project_code"]

                        # Save to Excel
                        output_df.to_excel(mapping_file, index=False, header=False)

                        st.success(
                            f"✅ Successfully saved {len(cleaned_mapping)} project mappings to '{mapping_file}'!"
                        )
                        st.rerun()

                    except Exception as e:
                        st.error(f"❌ Error saving file: {str(e)}")
        else:
            st.warning(
                "No existing mapping file found. Please upload a file first or create a new one."
            )

            # Option to create new mapping file
            st.write("**Create New Mapping File:**")
            with st.form("new_mapping_form"):
                new_project_name = st.text_input("Project Name")
                new_project_code = st.text_input("Project Code")

                if st.form_submit_button("Create New Mapping File"):
                    if new_project_name and new_project_code:
                        try:
                            # Create new mapping DataFrame
                            new_mapping = pd.DataFrame(
                                {
                                    "A": [""],
                                    "B": [new_project_name],
                                    "C": [new_project_code],
                                }
                            )

                            # Save to Excel
                            new_mapping.to_excel(
                                mapping_file, index=False, header=False
                            )
                            st.success(
                                f"✅ Created new mapping file '{mapping_file}' with initial entry!"
                            )
                            st.rerun()

                        except Exception as e:
                            st.error(f"❌ Error creating file: {str(e)}")
                    else:
                        st.error("Please enter both project name and project code.")

    # Add some helpful information
    st.info(
        """
    **💡 Tips for Project Mapping:**
    - Column B should contain project names
    - Column C should contain project codes  
    - Avoid duplicate project codes
    - Use the data editor to add, edit, or delete rows
    - Changes are saved immediately when you click 'Save Changes'
    """
    )

with mapping_tab3:
    st.subheader("Upload New Mapping File")

    uploaded_file = st.file_uploader(
        "Choose an Excel file",
        type=["xlsx", "xls"],
        help="Upload an Excel file with project names in column B and project codes in column C",
    )

    if uploaded_file is not None:
        try:
            # Preview the uploaded file
            preview_df = pd.read_excel(uploaded_file, usecols="B:C")
            preview_df.columns = ["project_name", "project_code"]
            preview_df = preview_df.dropna(subset=["project_name", "project_code"])

            st.write("**Preview of uploaded file:**")
            st.dataframe(preview_df, use_container_width=True)
            st.write(f"Total mappings found: {len(preview_df)}")

            # Confirm upload
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Replace Current Mapping", type="primary"):
                    try:
                        # Save the uploaded file
                        with open(mapping_file, "wb") as f:
                            f.write(uploaded_file.getvalue())
                        st.success("✅ Successfully uploaded new mapping file!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error uploading file: {str(e)}")

            with col2:
                if st.button("📥 Download Template"):
                    # Create a template file
                    template_df = pd.DataFrame(
                        {
                            "A": [""],
                            "B": ["PROJECT_NAME_EXAMPLE"],
                            "C": ["PROJECT_CODE_EXAMPLE"],
                        }
                    )

                    # Convert to Excel bytes
                    from io import BytesIO

                    output = BytesIO()
                    with pd.ExcelWriter(output, engine="openpyxl") as writer:
                        template_df.to_excel(writer, index=False, header=False)

                    st.download_button(
                        label="📄 Download Excel Template",
                        data=output.getvalue(),
                        file_name="project_mapping_template.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )

        except Exception as e:
            st.error(f"❌ Error reading uploaded file: {str(e)}")
            st.write(
                "Make sure the file has project names in column B and project codes in column C."
            )
