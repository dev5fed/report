import streamlit as st
import pandas as pd
import os
from io import BytesIO

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
                        new_mapping.to_excel(mapping_file, index=False, header=False)
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
