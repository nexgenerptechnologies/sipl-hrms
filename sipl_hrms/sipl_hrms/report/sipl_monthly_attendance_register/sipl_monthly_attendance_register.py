import frappe
from frappe.utils import getdate, formatdate
import calendar

def execute(filters=None):
    if not filters:
        filters = {}

    month = int(filters.get("month") or 10)
    year = int(filters.get("year") or 2026)
    company = filters.get("company") or "SIMPLE INTEGRAL PVT. LTD."

    # Days in this month
    _, total_days = calendar.monthrange(year, month)

    columns = [
        {"label": "S.No.", "fieldname": "s_no", "fieldtype": "Int", "width": 50},
        {"label": "E.Code", "fieldname": "employee", "fieldtype": "Link", "options": "Employee", "width": 110},
        {"label": "Emp Name", "fieldname": "employee_name", "fieldtype": "Data", "width": 140},
        {"label": "Father's Name", "fieldname": "father_name", "fieldtype": "Data", "width": 130},
        {"label": "Deptt.", "fieldname": "department", "fieldtype": "Link", "options": "Department", "width": 110},
        {"label": "Dsign.", "fieldname": "designation", "fieldtype": "Link", "options": "Designation", "width": 110}
    ]

    # Add 1 to 31 columns
    for day in range(1, total_days + 1):
        columns.append({
            "label": str(day),
            "fieldname": f"day_{day}",
            "fieldtype": "Data",
            "width": 42
        })

    # Summary columns
    columns.extend([
        {"label": "Actual Present Days", "fieldname": "total_p", "fieldtype": "Float", "width": 135},
        {"label": "WO", "fieldname": "total_wo", "fieldtype": "Int", "width": 45},
        {"label": "H", "fieldname": "total_h", "fieldtype": "Int", "width": 45},
        {"label": "CL", "fieldname": "total_cl", "fieldtype": "Float", "width": 45},
        {"label": "SL", "fieldname": "total_sl", "fieldtype": "Float", "width": 45},
        {"label": "EL", "fieldname": "total_el", "fieldtype": "Float", "width": 45},
        {"label": "C/OFF", "fieldname": "total_coff", "fieldtype": "Float", "width": 55},
        {"label": "G Total", "fieldname": "g_total", "fieldtype": "Float", "width": 65}
    ])

    # Determine cutoff day for counting WO and H for current/past/future months
    today = getdate()
    if year == today.year and month == today.month:
        max_day_to_count = today.day
    elif (year < today.year) or (year == today.year and month < today.month):
        max_day_to_count = total_days
    else:
        max_day_to_count = 0

    # Get active employees
    emp_filters = {"status": "Active"}
    if company: emp_filters["company"] = company
    if filters.get("department"): emp_filters["department"] = filters.get("department")
    if filters.get("branch"): emp_filters["branch"] = filters.get("branch")

    employees = frappe.get_all(
        "Employee",
        filters=emp_filters,
        fields=["name", "employee_name", "department", "designation", "gender"],
        order_by="name asc"
    )

    # Fetch holidays for company holiday list
    holiday_list = frappe.db.get_value("Company", company, "default_holiday_list") or "Holiday List 2026"
    holidays = frappe.get_all("Holiday", filters={
        "parent": holiday_list,
        "holiday_date": ["between", [f"{year}-{month:02d}-01", f"{year}-{month:02d}-{total_days:02d}"]]
    }, fields=["holiday_date", "weekly_off"])

    holiday_map = {str(h.holiday_date): ("W/O" if h.weekly_off else "H") for h in holidays}

    # Fetch Attendance records
    attendances = frappe.get_all(
        "Attendance",
        filters={
            "attendance_date": ["between", [f"{year}-{month:02d}-01", f"{year}-{month:02d}-{total_days:02d}"]],
            "docstatus": ["!=", 2]
        },
        fields=["employee", "attendance_date", "status", "leave_type"]
    )

    att_map = {(a.employee, str(a.attendance_date)): a for a in attendances}

    data = []
    s_no = 1

    for emp in employees:
        row = {
            "s_no": s_no,
            "employee": emp.name,
            "employee_name": emp.employee_name,
            "father_name": "", # can fetch from bio if present
            "department": emp.department or "",
            "designation": emp.designation or ""
        }
        s_no += 1

        p_days = 0.0
        wo_count = 0
        h_count = 0
        cl_count = 0.0
        sl_count = 0.0
        el_count = 0.0
        coff_count = 0.0

        for day in range(1, total_days + 1):
            d_str = f"{year}-{month:02d}-{day:02d}"
            att = att_map.get((emp.name, d_str))
            cell_code = ""
            is_sunday = (calendar.weekday(year, month, day) == 6)

            if att:
                st = att.status
                lt = (att.leave_type or "").upper()

                if st == "Present":
                    cell_code = "P"
                    p_days += 1.0
                elif st == "Absent":
                    cell_code = "A"
                elif st == "Half Day":
                    if "CASUAL" in lt or "CL" in lt:
                        cell_code = "C"
                        cl_count += 0.5
                    elif "SICK" in lt or "SL" in lt:
                        cell_code = "S"
                        sl_count += 0.5
                    elif "EARNED" in lt or "PRIVILEGE" in lt or "EL" in lt:
                        cell_code = "E"
                        el_count += 0.5
                    elif "COMPENSATORY" in lt or "CO" in lt or "C-OFF" in lt:
                        cell_code = "O"
                        coff_count += 0.5
                    else:
                        cell_code = "P/A"
                    p_days += 0.5
                elif st == "On Leave":
                    if "CASUAL" in lt or "CL" in lt:
                        cell_code = "CL"
                        cl_count += 1.0
                    elif "SICK" in lt or "SL" in lt:
                        cell_code = "SL"
                        sl_count += 1.0
                    elif "EARNED" in lt or "PRIVILEGE" in lt or "EL" in lt:
                        cell_code = "EL"
                        el_count += 1.0
                    elif "COMPENSATORY" in lt or "CO" in lt or "C-OFF" in lt:
                        cell_code = "CO"
                        coff_count += 1.0
                    else:
                        cell_code = "L"
            else:
                # Check weekly off (Sunday or holiday list weekly off) or festival holiday
                h_code = holiday_map.get(d_str)
                if is_sunday or h_code == "W/O":
                    cell_code = "W/O"
                    if day <= max_day_to_count:
                        wo_count += 1
                elif h_code == "H":
                    cell_code = "H"
                    if day <= max_day_to_count:
                        h_count += 1
                else:
                    cell_code = ""

            row[f"day_{day}"] = cell_code

        row["total_p"] = p_days
        row["total_wo"] = wo_count
        row["total_h"] = h_count
        row["total_cl"] = cl_count
        row["total_sl"] = sl_count
        row["total_el"] = el_count
        row["total_coff"] = coff_count
        row["g_total"] = p_days + wo_count + h_count + cl_count + sl_count + el_count + coff_count

        data.append(row)

    return columns, data
