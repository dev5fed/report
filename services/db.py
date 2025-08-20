import config
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


def get_engine() -> Engine:
    return create_engine(config.SQLALCHEMY_DATABASE_URL, pool_size=10, max_overflow=20)


def load_timesheet_data(start_date, end_date):
    engine = get_engine()
    query = """
        SELECT employee_code as code, 
               timesheet.date as date, 
               CASE WHEN ops_project.project_name IS NOT NULL 
                    THEN ops_project.project_name 
                    ELSE NULL END as project, 
               CASE WHEN ops_static_module.module_name IS NOT NULL 
                    THEN ops_static_module.module_name 
                    WHEN ops_general_module.module_name IS NOT NULL
                    THEN ops_general_module.module_name
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
        LEFT JOIN ops_general_module ON ops_project_module.ops_general_module_id = ops_general_module.id
        WHERE timesheet."manHoursBillable" > '00:00' 
        AND timesheet.date BETWEEN %(start_date)s AND %(end_date)s
        UNION ALL 
        SELECT employee_code as code, 
               timesheet.date as date, 
               CASE WHEN ops_project.project_name IS NOT NULL 
                    THEN ops_project.project_name 
                    ELSE NULL END as project, 
               CASE WHEN ops_static_module.module_name IS NOT NULL 
                    THEN ops_static_module.module_name 
                    WHEN ops_general_module.module_name IS NOT NULL
                    THEN ops_general_module.module_name
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
        LEFT JOIN ops_general_module ON ops_project_module.ops_general_module_id = ops_general_module.id
        WHERE timesheet."manHoursNonBillable" > '00:00' 
        AND timesheet.date BETWEEN %(start_date)s AND %(end_date)s
        ORDER BY code, date, project, module, status, billable
    """
    df = pd.read_sql(
        query, engine, params={"start_date": start_date, "end_date": end_date}
    )
    return df
