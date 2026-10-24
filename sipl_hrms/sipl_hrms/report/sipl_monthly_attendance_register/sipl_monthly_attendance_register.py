import frappe
from frappe.utils import getdate, formatdate, add_days
import calendar
import re

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
        {"label": "Employee Number", "fieldname": "employee_number", "fieldtype": "Data", "width": 125},
        {"label": "Emp Name", "fieldname": "employee_name", "fieldtype": "Data", "width": 140},
        {"label": "Father's Name", "fieldname": "father_name", "fieldtype": "Data", "width": 140},
        {"label": "Deptt.", "fieldname": "department", "fieldtype": "Link", "options": "Department", "width": 110},
        {"label": "Dsign.", "fieldname": "designation", "fieldtype": "Link", "options": "Designation", "width": 110}
    ]

    # Add 1 to 31 day columns
    for day in range(1, total_days + 1):
        columns.append({
            "label": str(day),
            "fieldname": f"day_{day}",
            "fieldtype": "Data",
            "width": 44
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
        {"label": "G Total", "fieldname": "g_total", "fieldtype": "Float", "width": 65},
        {"label": "Total OT (Hrs)", "fieldname": "total_ot", "fieldtype": "Float", "width": 100},
        {"label": "Att. Bonus (₹)", "fieldname": "attendance_bonus", "fieldtype": "Currency", "width": 105}
    ])

    # Determine cutoff day for counting WO and H for current/past/future months
    today = getdate()
    if year == today.year and month == today.month:
        max_day_to_count = today.day
    elif (year < today.year) or (year == today.year and month < today.month):
        max_day_to_count = total_days
    else:
        max_day_to_count = 0

    # Fetch active employees
    emp_filters = {"status": "Active"}
    if company: emp_filters["company"] = company
    if filters.get("department"): emp_filters["department"] = filters.get("department")
    if filters.get("branch"): emp_filters["branch"] = filters.get("branch")

    employees = frappe.get_all(
        "Employee",
        filters=emp_filters,
        fields=[
            "name", "employee_name", "employee_number", "custom_fathers_name",
            "department", "designation", "custom_overtime_applicable"
        ]
    )

    # Requirement 2: Order employee list according to Employee Number (natural sort)
    def natural_sort_key(emp):
        emp_num = emp.get("employee_number") or ""
        digits = re.findall(r'\d+', emp_num)
        num_part = int(digits[0]) if digits else 999999
        return (num_part, emp_num, emp.get("name") or "")

    employees.sort(key=natural_sort_key)

    # Fetch holidays for company holiday list
    holiday_list = frappe.db.get_value("Company", company, "default_holiday_list") or "Holiday List 2026"
    holidays = frappe.get_all("Holiday", filters={
        "parent": holiday_list,
        "holiday_date": ["between", [f"{year}-{month:02d}-01", f"{year}-{month:02d}-{total_days:02d}"]]
    }, fields=["holiday_date", "weekly_off"])

    holiday_map = {str(h.holiday_date): ("W/O" if h.weekly_off else "H") for h in holidays}

    # Helper: Check if a given day is a scheduled off-day (Sunday or holiday)
    def is_day_off(d_num):
        d_str_check = f"{year}-{month:02d}-{d_num:02d}"
        is_sun = (calendar.weekday(year, month, d_num) == 6)
        h_val = holiday_map.get(d_str_check)
        return is_sun or (h_val in ["W/O", "H"])

    # Fetch Attendance records for the month
    attendances = frappe.get_all(
        "Attendance",
        filters={
            "attendance_date": ["between", [f"{year}-{month:02d}-01", f"{year}-{month:02d}-{total_days:02d}"]],
            "docstatus": ["!=", 2]
        },
        fields=[
            "employee", "attendance_date", "status", "leave_type",
            "in_time", "out_time", "working_hours", "custom_overtime_hours", "late_entry"
        ]
    )

    att_map = {(a.employee, str(a.attendance_date)): a for a in attendances}

    data = []
    s_no = 1

    for emp in employees:
        is_ot_applicable = (emp.get("custom_overtime_applicable") == "OT Applicable")

        # Requirement 5: Display Father's Name from custom_fathers_name
        row = {
            "s_no": s_no,
            "employee": emp.name,
            "employee_number": emp.employee_number or "",
            "employee_name": emp.employee_name,
            "father_name": emp.custom_fathers_name or "",
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
        absent_count = 0
        total_ot = 0.0

        # Helper to check if an employee is qualified (Present or approved EL) on a specific day
        def is_qualified(d_num):
            if d_num < 1 or d_num > total_days:
                # Query adjacent month if necessary
                check_d = getdate(f"{year}-{month:02d}-01")
                if d_num < 1:
                    adj_date = add_days(check_d, d_num - 1)
                else:
                    adj_date = add_days(getdate(f"{year}-{month:02d}-{total_days:02d}"), d_num - total_days)
                rec_adj = frappe.db.get_value("Attendance", {
                    "employee": emp.name,
                    "attendance_date": adj_date,
                    "docstatus": ["!=", 2]
                }, ["status", "leave_type"], as_dict=True)
                if rec_adj:
                    st_adj = rec_adj.status
                    lt_adj = (rec_adj.leave_type or "").upper()
                    if st_adj in ["Present", "Half Day"]: return True
                    if st_adj == "On Leave" and ("EARNED" in lt_adj or "PRIVILEGE" in lt_adj or "EL" in lt_adj): return True
                return False

            d_s = f"{year}-{month:02d}-{d_num:02d}"
            rec = att_map.get((emp.name, d_s))
            if rec:
                st_val = rec.status
                lt_val = (rec.leave_type or "").upper()
                if st_val in ["Present", "Half Day"]:
                    return True
                if st_val == "On Leave" and ("EARNED" in lt_val or "PRIVILEGE" in lt_val or "EL" in lt_val):
                    return True
            return False

        # Helper for Sandwich Rule: find nearest preceding working day
        def get_prev_working_day(d_num):
            cur = d_num - 1
            while cur >= 1 and is_day_off(cur):
                cur -= 1
            return cur

        # Helper for Sandwich Rule: find nearest following working day
        def get_next_working_day(d_num):
            cur = d_num + 1
            while cur <= total_days and is_day_off(cur):
                cur += 1
            return cur

        for day in range(1, total_days + 1):
            d_str = f"{year}-{month:02d}-{day:02d}"
            att = att_map.get((emp.name, d_str))
            cell_code = ""
            is_sunday = (calendar.weekday(year, month, day) == 6)
            h_code = holiday_map.get(d_str)

            if att:
                st = att.status
                lt = (att.leave_type or "").upper()

                if st == "Present":
                    # Requirement 6: If present on Sunday/Weekly off, display as PWO
                    if is_sunday or h_code == "W/O":
                        cell_code = "PWO"
                    else:
                        cell_code = "P"
                    p_days += 1.0

                    # Accumulate OT if applicable
                    if is_ot_applicable:
                        wh = float(att.working_hours or 0.0)
                        if wh > 10.0:
                            total_ot += round(wh - 9.0, 1)
                        elif att.custom_overtime_hours:
                            total_ot += float(att.custom_overtime_hours)

                elif st == "Absent":
                    cell_code = "A"
                    if day <= max_day_to_count:
                        absent_count += 1

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
                        # Determine A/P (late arrival / 2nd half present) vs P/A (early exit)
                        in_t_str = str(att.in_time or "")
                        if in_t_str and len(in_t_str) >= 16:
                            t_part = in_t_str[11:16]
                            if t_part >= "11:30" or (att.late_entry and t_part > "10:00"):
                                cell_code = "A/P"
                            else:
                                cell_code = "P/A"
                        else:
                            cell_code = "A/P" if att.late_entry else "P/A"

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
                # No attendance record exists for this day
                is_wo = (is_sunday or h_code == "W/O")
                is_hol = (h_code == "H")

                if is_wo or is_hol:
                    # Requirement 4: Sandwich Rule check
                    # Eligible only if present or approved EL on preceding OR following working day
                    prev_w_day = get_prev_working_day(day)
                    next_w_day = get_next_working_day(day)

                    is_sandwich_eligible = is_qualified(prev_w_day) or is_qualified(next_w_day)

                    if is_sandwich_eligible:
                        if is_wo:
                            cell_code = "W/O"
                            if day <= max_day_to_count:
                                wo_count += 1
                        else:
                            cell_code = "H"
                            if day <= max_day_to_count:
                                h_count += 1
                    else:
                        # Sandwich rule: absent on both preceding & following working days
                        # Treated as Absent / Loss of Pay
                        cell_code = "A"
                        if day <= max_day_to_count:
                            absent_count += 1
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

        # Requirement 7: Total OT and ₹2,000 Attendance Bonus
        row["total_ot"] = round(total_ot, 1) if is_ot_applicable else 0.0
        # ₹2,000 Attendance Bonus is awarded for full attendance (0 absent days)
        row["attendance_bonus"] = 2000.0 if (p_days > 0 and absent_count == 0) else 0.0

        data.append(row)

    return columns, data
