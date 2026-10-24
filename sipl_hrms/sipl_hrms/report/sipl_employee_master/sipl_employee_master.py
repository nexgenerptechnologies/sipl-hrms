import frappe
import re

def execute(filters=None):
    if not filters:
        filters = {}

    columns = [
        {"label": "S.No.", "fieldname": "s_no", "fieldtype": "Int", "width": 50},
        {"label": "Employee Number", "fieldname": "employee_number", "fieldtype": "Data", "width": 125},
        {"label": "E.Code", "fieldname": "name", "fieldtype": "Link", "options": "Employee", "width": 110},
        {"label": "Employee Name", "fieldname": "employee_name", "fieldtype": "Data", "width": 160},
        {"label": "Father's / Husband's Name", "fieldname": "custom_fathers_name", "fieldtype": "Data", "width": 160},
        {"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 90},
        {"label": "Date of Joining", "fieldname": "date_of_joining", "fieldtype": "Date", "width": 105},
        {"label": "Relieving Date", "fieldname": "relieving_date", "fieldtype": "Date", "width": 105},
        {"label": "Designation", "fieldname": "designation", "fieldtype": "Link", "options": "Designation", "width": 130},
        {"label": "Department", "fieldname": "department", "fieldtype": "Link", "options": "Department", "width": 130},
        {"label": "Branch", "fieldname": "branch", "fieldtype": "Link", "options": "Branch", "width": 110},
        {"label": "Mobile", "fieldname": "cell_number", "fieldtype": "Data", "width": 115},
        {"label": "Company Email", "fieldname": "company_email", "fieldtype": "Data", "width": 160},
        {"label": "Personal Email", "fieldname": "personal_email", "fieldtype": "Data", "width": 160},
        {"label": "Overtime Policy", "fieldname": "custom_overtime_applicable", "fieldtype": "Data", "width": 125},
        {"label": "Gender", "fieldname": "gender", "fieldtype": "Data", "width": 80},
        {"label": "Date of Birth", "fieldname": "date_of_birth", "fieldtype": "Date", "width": 100},
        {"label": "PAN Number", "fieldname": "pan_number", "fieldtype": "Data", "width": 110},
        {"label": "UAN Number", "fieldname": "custom_uan_number", "fieldtype": "Data", "width": 120},
        {"label": "ESI Number", "fieldname": "custom_esi_number", "fieldtype": "Data", "width": 120},
        {"label": "Bank Name", "fieldname": "bank_name", "fieldtype": "Data", "width": 130},
        {"label": "Bank A/C No.", "fieldname": "bank_ac_no", "fieldtype": "Data", "width": 130},
        {"label": "IFSC Code", "fieldname": "ifsc_code", "fieldtype": "Data", "width": 110},
        {"label": "Emergency Phone", "fieldname": "emergency_phone_number", "fieldtype": "Data", "width": 120}
    ]

    emp_filters = {}
    status_filter = filters.get("status") or "Active"
    if status_filter != "All":
        emp_filters["status"] = status_filter

    if filters.get("company"):
        emp_filters["company"] = filters.get("company")
    if filters.get("department"):
        emp_filters["department"] = filters.get("department")
    if filters.get("branch"):
        emp_filters["branch"] = filters.get("branch")

    fields = [
        "name", "employee_name", "employee_number", "custom_fathers_name", "status",
        "date_of_joining", "relieving_date", "designation", "department", "branch",
        "cell_number", "company_email", "personal_email", "custom_overtime_applicable",
        "gender", "date_of_birth", "pan_number", "custom_uan_number", "custom_esi_number",
        "bank_name", "bank_ac_no", "ifsc_code", "emergency_phone_number"
    ]

    employees = frappe.get_all("Employee", filters=emp_filters, fields=fields)

    def natural_sort_key(emp):
        emp_num = emp.get("employee_number") or ""
        digits = re.findall(r'\d+', emp_num)
        num_part = int(digits[0]) if digits else 999999
        return (num_part, emp_num, emp.get("name") or "")

    employees.sort(key=natural_sort_key)

    data = []
    for idx, emp in enumerate(employees, start=1):
        row = dict(emp)
        row["s_no"] = idx
        data.append(row)

    return columns, data
