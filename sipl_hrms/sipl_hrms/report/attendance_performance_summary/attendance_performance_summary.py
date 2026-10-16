import frappe
from frappe.utils import getdate, add_days, formatdate

def execute(filters=None):
    if not filters:
        filters = {}

    from_date = getdate(filters.get("from_date"))
    to_date = getdate(filters.get("to_date"))
    
    # Generate list of dates
    dates = []
    curr = from_date
    while curr <= to_date:
        dates.append(curr)
        curr = add_days(curr, 1)

    columns = [
        {"label": "Employee", "fieldname": "employee", "fieldtype": "Link", "options": "Employee", "width": 140},
        {"label": "Employee Name", "fieldname": "employee_name", "fieldtype": "Data", "width": 160},
        {"label": "Metric", "fieldname": "metric", "fieldtype": "Data", "width": 80}
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

    # Fetch employees
    emp_filters = {"status": "Active"}
    if filters.get("company"): emp_filters["company"] = filters.get("company")
    if filters.get("department"): emp_filters["department"] = filters.get("department")
    if filters.get("employee"): emp_filters["name"] = filters.get("employee")

    employees = frappe.get_all("Employee", filters=emp_filters, fields=["name", "employee_name"], order_by="employee_name asc")

    # Fetch attendance records
    att_filters = {
        "attendance_date": ["between", [from_date, to_date]],
        "docstatus": ["!=", 2]
    }
    if filters.get("company"): att_filters["company"] = filters.get("company")
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
        emp_name = emp.employee_name

        row_in = {"employee": emp_id, "employee_name": emp_name, "metric": "in"}
        row_out = {"employee": "", "employee_name": "", "metric": "out"}
        row_status = {"employee": "", "employee_name": "", "metric": "Status"}
        row_thrs = {"employee": "", "employee_name": "", "metric": "T Hrs."}
        row_othrs = {"employee": "", "employee_name": "", "metric": "Ot Hrs"}

        p_count = 0.0
        ot_total = 0.0

        for d in dates:
            d_str = str(d)
            rec = att_map.get((emp_id, d_str))

            if rec:
                in_t = formatdate(rec.in_time, "HH:mm") if rec.in_time else ""
                out_t = formatdate(rec.out_time, "HH:mm") if rec.out_time else ""
                st = "P" if rec.status == "Present" else ("A" if rec.status == "Absent" else ("HD" if rec.status == "Half Day" else rec.status))
                thrs = str(round(rec.working_hours, 1)) if rec.working_hours else ""
                
                # OT calculation per 10h rule
                othrs = ""
                wh = float(rec.working_hours or 0.0)
                if wh > 10.0:
                    ot_val = round(wh - 9.0, 1)
                    othrs = str(ot_val)
                    ot_total += ot_val
                elif rec.custom_overtime_hours:
                    othrs = str(round(rec.custom_overtime_hours, 1))
                    ot_total += float(rec.custom_overtime_hours)

                if rec.status == "Present": p_count += 1.0
                elif rec.status == "Half Day": p_count += 0.5

                row_in[d_str] = in_t
                row_out[d_str] = out_t
                row_status[d_str] = st
                row_thrs[d_str] = thrs
                row_othrs[d_str] = othrs
            else:
                row_in[d_str] = ""
                row_out[d_str] = ""
                row_status[d_str] = ""
                row_thrs[d_str] = ""
                row_othrs[d_str] = ""

        row_in["total_p"] = p_count
        row_othrs["total_ot"] = round(ot_total, 1)

        data.extend([row_in, row_out, row_status, row_thrs, row_othrs])

    return columns, data
