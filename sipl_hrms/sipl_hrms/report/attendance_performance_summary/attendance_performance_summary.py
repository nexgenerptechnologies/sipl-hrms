import frappe
from frappe.utils import getdate, add_days, formatdate
import calendar
import re

def execute(filters=None):
    if not filters:
        filters = {}

    from_date = getdate(filters.get("from_date"))
    to_date = getdate(filters.get("to_date"))
    company = filters.get("company") or "SIMPLE INTEGRAL PVT. LTD."
    
    # Generate list of dates
    dates = []
    curr = from_date
    while curr <= to_date:
        dates.append(curr)
        curr = add_days(curr, 1)

    columns = [
        {"label": "Employee", "fieldname": "employee", "fieldtype": "Link", "options": "Employee", "width": 110},
        {"label": "Employee Number", "fieldname": "employee_number", "fieldtype": "Data", "width": 125},
        {"label": "Employee Name", "fieldname": "employee_name", "fieldtype": "Data", "width": 150},
        {"label": "Metric", "fieldname": "metric", "fieldtype": "Data", "width": 75}
    ]

    for d in dates:
        col_label = formatdate(d, "dd-MMM")
        col_name = str(d)
        columns.append({
            "label": col_label,
            "fieldname": col_name,
            "fieldtype": "Data",
            "width": 85
        })

    # Summary columns
    columns.extend([
        {"label": "Total Present", "fieldname": "total_p", "fieldtype": "Float", "width": 95},
        {"label": "Total OT (Hrs)", "fieldname": "total_ot", "fieldtype": "Float", "width": 100}
    ])

    # Fetch holidays for the company
    holiday_list = frappe.db.get_value("Company", company, "default_holiday_list") or "Holiday List 2026"
    holidays = frappe.get_all("Holiday", filters={
        "parent": holiday_list,
        "holiday_date": ["between", [from_date, to_date]]
    }, fields=["holiday_date", "weekly_off"])

    holiday_map = {str(h.holiday_date): ("W/O" if h.weekly_off else "H") for h in holidays}

    # Fetch active employees
    emp_filters = {"status": "Active"}
    if company: emp_filters["company"] = company
    if filters.get("department"): emp_filters["department"] = filters.get("department")
    if filters.get("employee"): emp_filters["name"] = filters.get("employee")

    employees = frappe.get_all(
        "Employee",
        filters=emp_filters,
        fields=["name", "employee_name", "employee_number", "custom_overtime_applicable"]
    )

    # Requirement 2: Order according to Employee Number (natural sort)
    def natural_sort_key(emp):
        emp_num = emp.get("employee_number") or ""
        digits = re.findall(r'\d+', emp_num)
        num_part = int(digits[0]) if digits else 999999
        return (num_part, emp_num, emp.get("name") or "")

    employees.sort(key=natural_sort_key)

    # Fetch attendance records
    att_filters = {
        "attendance_date": ["between", [from_date, to_date]],
        "docstatus": ["!=", 2]
    }
    if company: att_filters["company"] = company
    if filters.get("employee"): att_filters["employee"] = filters.get("employee")

    attendances = frappe.get_all("Attendance", filters=att_filters, fields=[
        "employee", "attendance_date", "status", "in_time", "out_time", "working_hours", "custom_overtime_hours", "late_entry"
    ])

    att_map = {}
    for a in attendances:
        key = (a.employee, str(a.attendance_date))
        att_map[key] = a

    data = []

    for emp in employees:
        emp_id = emp.name
        emp_num = emp.employee_number or ""
        emp_name = emp.employee_name
        is_ot_applicable = (emp.get("custom_overtime_applicable") == "OT Applicable")

        row_in = {"employee": emp_id, "employee_number": emp_num, "employee_name": emp_name, "metric": "in"}
        row_out = {"employee": "", "employee_number": "", "employee_name": "", "metric": "out"}
        row_status = {"employee": "", "employee_number": "", "employee_name": "", "metric": "Status"}
        row_thrs = {"employee": "", "employee_number": "", "employee_name": "", "metric": "T Hrs."}
        row_othrs = {"employee": "", "employee_number": "", "employee_name": "", "metric": "Ot Hrs"}

        p_count = 0.0
        ot_total = 0.0

        for d in dates:
            d_str = str(d)
            rec = att_map.get((emp_id, d_str))
            is_sunday = (d.weekday() == 6)
            h_type = holiday_map.get(d_str)

            if rec:
                in_t = str(rec.in_time)[11:16] if rec.in_time else ""
                out_t = str(rec.out_time)[11:16] if rec.out_time else ""

                # Distinguish P, PWO, A, A/P (late arrival), P/A (early departure)
                if rec.status == "Present":
                    # Requirement 6 & 12: Sunday presence is marked as PWO
                    if is_sunday or h_type == "W/O":
                        st = "PWO"
                    else:
                        st = "P"
                    p_count += 1.0
                elif rec.status == "Absent":
                    st = "A"
                elif rec.status == "Half Day":
                    if in_t >= "11:30" or (rec.late_entry and in_t > "10:00"):
                        st = "A/P"
                    else:
                        st = "P/A"
                    p_count += 0.5
                else:
                    st = rec.status

                thrs = str(round(rec.working_hours, 1)) if rec.working_hours else ""
                
                # OT calculation strictly for OT Applicable employees only
                othrs = ""
                if is_ot_applicable:
                    wh = float(rec.working_hours or 0.0)
                    if wh > 10.0:
                        ot_val = round(wh - 9.0, 1)
                        othrs = str(ot_val)
                        ot_total += ot_val
                    elif rec.custom_overtime_hours:
                        othrs = str(round(rec.custom_overtime_hours, 1))
                        ot_total += float(rec.custom_overtime_hours)

                row_in[d_str] = in_t
                row_out[d_str] = out_t
                row_status[d_str] = st
                row_thrs[d_str] = thrs
                row_othrs[d_str] = othrs
            else:
                # Requirement 12: Display W/O on weekly offs and H on holidays
                if is_sunday or h_type == "W/O":
                    off_code = "W/O"
                elif h_type == "H":
                    off_code = "H"
                else:
                    off_code = ""

                row_in[d_str] = ""
                row_out[d_str] = ""
                row_status[d_str] = off_code
                row_thrs[d_str] = ""
                row_othrs[d_str] = ""

        row_in["total_p"] = p_count
        row_othrs["total_ot"] = round(ot_total, 1) if is_ot_applicable else 0.0

        data.extend([row_in, row_out, row_status, row_thrs, row_othrs])

    return columns, data
