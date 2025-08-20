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


def load_planned_vs_realized_mandays():
    """
    Load planned vs realized mandays comparison using CTEs
    """
    engine = get_engine()
    query = """
        WITH planned AS (
          SELECT
          ANY_VALUE(p.project_code) project,
          m.ops_project_id,
          SUM(m."mandaysBillable") billable_mandays,
          SUM(m."mandaysNonBillable") non_billable_mandays,
          SUM(m."mandaysBillable") +
          SUM(m."mandaysNonBillable") total_mandays,
          ANY_VALUE(e.employee_code) employee_code
          FROM public.project p
          LEFT JOIN client c ON c.id = p.client_id 
          LEFT JOIN ops_project op ON op.project_id = p.id
          LEFT JOIN mandays m ON m.ops_project_id = op.id
          LEFT JOIN employee e ON e.id = m.employee_id 
          GROUP BY m.ops_project_id, m.employee_id
        ),
        realized AS (
          SELECT 
          ANY_VALUE(p.project_code) project,
          op.id as ops_project_id,
          SUM(EXTRACT(epoch FROM t."manHoursBillable"))/3600/8 billable_mandays,
          SUM(EXTRACT(epoch FROM t."manHoursNonBillable"))/3600/8 non_billable_mandays,
          SUM(EXTRACT(epoch FROM t."manHoursBillable"))/3600/8 +
          SUM(EXTRACT(epoch FROM t."manHoursNonBillable"))/3600/8 total_mandays,
          ANY_VALUE(e.employee_code) employee_code
          FROM timesheet t
          LEFT JOIN employee e ON t.employee_id = e.id
          LEFT JOIN ops_project op ON op.id = t.ops_project_id 
          JOIN project p ON p.id = op.project_id
          GROUP BY op.id, e.id
        )
        SELECT
          p.project,
          p.ops_project_id,
          p.total_mandays,
          p.employee_code,
          COALESCE(r.billable_mandays, 0) AS total_realized_mandays,
          (p.billable_mandays - COALESCE(r.billable_mandays, 0)) AS remaining_billable_mandays,
          COALESCE(r.non_billable_mandays, 0) AS total_realized_mandays,
          (p.non_billable_mandays - COALESCE(r.non_billable_mandays, 0)) AS remaining_non_billable_mandays,
          COALESCE(r.total_mandays, 0) AS total_realized_mandays,
          (p.total_mandays - COALESCE(r.total_mandays, 0)) AS remaining_mandays
        FROM planned p
        LEFT JOIN realized r
            ON p.ops_project_id = r.ops_project_id
            AND p.employee_code = r.employee_code
        ORDER BY p.ops_project_id
    """

    df = pd.read_sql(query, engine)
    return df
