import frappe
from frappe.utils import getdate, formatdate, add_days
from datetime import datetime
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
        {"label": "H/D", "fieldname": "total_h", "fieldtype": "Int", "width": 45},
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

    # Order according to Employee Number (natural sort)
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

    # Item 5: Use H/D instead of H
    holiday_map = {str(h.holiday_date): ("W/O" if h.weekly_off else "H/D") for h in holidays}

    # Helper: Check if a given day is a scheduled off-day (Sunday or holiday)
    def is_day_off(d_num):
        d_str_check = f"{year}-{month:02d}-{d_num:02d}"
        is_sun = (calendar.weekday(year, month, d_num) == 6)
        h_val = holiday_map.get(d_str_check)
        return is_sun or (h_val in ["W/O", "H/D"])

    # Fetch Attendance records for the month
    from_d = f"{year}-{month:02d}-01"
    to_d = f"{year}-{month:02d}-{total_days:02d}"

    attendances = frappe.get_all(
        "Attendance",
        filters={
            "attendance_date": ["between", [from_d, to_d]],
            "docstatus": ["!=", 2]
        },
        fields=[
            "employee", "attendance_date", "status", "leave_type",
            "in_time", "out_time", "working_hours", "custom_overtime_hours", "late_entry"
        ]
    )

    att_map = {(a.employee, str(a.attendance_date)): a for a in attendances}

    # Fetch approved leave applications (Item: CL, SL, EL, C/OFF applied/approved)
    leave_applications = frappe.get_all(
        "Leave Application",
        filters={
            "employee": ["in", [e.name for e in employees]],
            "docstatus": ["!=", 2],
            "status": ["in", ["Approved", "Open"]],
            "to_date": [">=", from_d],
            "from_date": ["<=", to_d]
        },
        fields=["employee", "leave_type", "from_date", "to_date", "half_day", "half_day_date"]
    )

    leave_app_map = {}
    for la in leave_applications:
        cur_d = getdate(la.from_date)
        end_d = getdate(la.to_date)
        while cur_d <= end_d:
            if getdate(from_d) <= cur_d <= getdate(to_d):
                key = (la.employee, str(cur_d))
                leave_app_map[key] = la
            cur_d = add_days(cur_d, 1)

    data = []
    s_no = 1

    for emp in employees:
        is_ot_applicable = (emp.get("custom_overtime_applicable") == "OT Applicable")

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

        # State tracking for gate pass & late grace
        gate_pass_used = 0
        late_grace_used = 0

        # Helper to check if an employee is qualified (Present or ANY leave) on a specific day (Item 15)
        def is_qualified(d_num):
            if d_num < 1 or d_num > total_days:
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
                    if rec_adj.status in ["Present", "Half Day"] or rec_adj.leave_type:
                        return True
                return False

            d_s = f"{year}-{month:02d}-{d_num:02d}"
            rec = att_map.get((emp.name, d_s))
            if rec:
                if rec.status in ["Present", "Half Day"] or rec.leave_type:
                    return True
            return False

        def get_prev_working_day(d_num):
            cur = d_num - 1
            while cur >= 1 and is_day_off(cur):
                cur -= 1
            return cur

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

            has_in = bool(att and att.in_time)
            has_out = bool(att and att.out_time)

            # -------------------------------------------------------------
            # 1. LEAVE CHECK (Direct in Attendance OR via Approved Leave Application)
            # -------------------------------------------------------------
            la_rec = leave_app_map.get((emp.name, d_str))
            leave_type_str = ""
            is_half_day_leave = False

            if att and (att.status in ["On Leave", "Half Day"] or att.leave_type):
                leave_type_str = (att.leave_type or "").upper()
                is_half_day_leave = (att.status == "Half Day")
            elif la_rec:
                leave_type_str = (la_rec.leave_type or "").upper()
                is_half_day_leave = bool(la_rec.half_day and (not la_rec.half_day_date or getdate(la_rec.half_day_date) == getdate(d_str)))

            if leave_type_str:
                if "CASUAL" in leave_type_str or "CL" in leave_type_str:
                    cell_code = ("C" if is_half_day_leave else "CL")
                    cl_count += (0.5 if is_half_day_leave else 1.0)
                elif "SICK" in leave_type_str or "SL" in leave_type_str:
                    cell_code = ("S" if is_half_day_leave else "SL")
                    sl_count += (0.5 if is_half_day_leave else 1.0)
                elif "EARNED" in leave_type_str or "PRIVILEGE" in leave_type_str or "EL" in leave_type_str:
                    cell_code = ("E" if is_half_day_leave else "EL")
                    el_count += (0.5 if is_half_day_leave else 1.0)
                elif "COMPENSATORY" in leave_type_str or "CO" in leave_type_str or "C-OFF" in leave_type_str or "CPL" in leave_type_str:
                    cell_code = ("O" if is_half_day_leave else "CO")
                    coff_count += (0.5 if is_half_day_leave else 1.0)
                else:
                    cell_code = "L"

                if is_half_day_leave and has_in and has_out:
                    wh = float(att.working_hours or 0.0)
                    p_days += 0.5

            # -------------------------------------------------------------
            # 2. MISSING PUNCH LOGIC (Items 12 & 13)
            # -------------------------------------------------------------
            elif has_in != has_out:
                # Single punch
                if is_sunday or h_code == "W/O":
                    cell_code = "W/O" # Item 13: Single punch on Sunday shows W/O
                    if day <= max_day_to_count:
                        wo_count += 1
                elif h_code == "H/D":
                    cell_code = "H/D"
                    if day <= max_day_to_count:
                        h_count += 1
                else:
                    cell_code = "A"   # Item 12: Single punch on working day shows A
                    if day <= max_day_to_count:
                        absent_count += 1

            elif not has_in and not has_out:
                # No attendance / punch for this day
                is_wo = (is_sunday or h_code == "W/O")
                is_hol = (h_code == "H/D")

                if is_wo:
                    # Weekly Off on Sunday (e.g. Day 18, Day 25)
                    cell_code = "W/O"
                    if day <= max_day_to_count:
                        wo_count += 1
                elif is_hol:
                    # Item 15: Sandwich rule check for Holiday (e.g. 2nd Oct)
                    prev_w_day = get_prev_working_day(day)
                    next_w_day = get_next_working_day(day)

                    is_sandwich_eligible = is_qualified(prev_w_day) or is_qualified(next_w_day)

                    if is_sandwich_eligible:
                        cell_code = "H/D"
                        if day <= max_day_to_count:
                            h_count += 1
                    else:
                        cell_code = "A"
                        if day <= max_day_to_count:
                            absent_count += 1
                else:
                    cell_code = "A" if day <= max_day_to_count else ""
                    if cell_code == "A":
                        absent_count += 1

            else:
                # Both Check In and Check Out exist!
                wh = float(att.working_hours or 0.0)
                in_t = str(att.in_time)[11:16]
                out_t = str(att.out_time)[11:16]

                if is_sunday or h_code == "W/O":
                    # Sunday Presence (Items 6 & 7)
                    # Status displays as PWO; compensation is credited to CPL (C/OFF column)
                    cell_code = "PWO"
                    if wh >= 7.0:
                        coff_count += 1.0
                    elif wh > 3.5:
                        coff_count += 0.5
                    # Note: Sunday work is not counted in regular shift p_days (Actual Present Days)

                else:
                    # Working day logic (Items 1, 8, 9)
                    if wh < 4.0 and wh > 0:
                        cell_code = "A"
                        if day <= max_day_to_count:
                            absent_count += 1
                    else:
                        if in_t > "09:30":
                            if in_t <= "10:00":
                                late_grace_used += 1
                                if late_grace_used <= 2:
                                    cell_code = "P"
                                    p_days += 1.0
                                else:
                                    cell_code = "A/P"
                                    p_days += 0.5
                            elif in_t <= "11:30":
                                if gate_pass_used < 2:
                                    gate_pass_used += 1
                                    cell_code = "P" # Items 1 & 8: 1st & 2nd gate pass allowed -> P
                                    p_days += 1.0
                                else:
                                    cell_code = "A/P" # Item 9: after 2 gate passes -> A/P
                                    p_days += 0.5
                            else:
                                # Arrived after 11:30 AM
                                cell_code = "A/P"
                                p_days += 0.5
                        else:
                            # On-time arrival
                            cell_code = "P"
                            p_days += 1.0

                        # Check early departure
                        if out_t < "18:30" and wh < 8.5:
                            if cell_code == "P":
                                if gate_pass_used < 2:
                                    gate_pass_used += 1
                                    cell_code = "P"
                                else:
                                    cell_code = "P/A"
                                    p_days -= 0.5

                # OT Calculation (Item 16: Option A)
                if is_ot_applicable:
                    if wh > 10.0:
                        total_ot += round(wh - 10.0, 1)

            row[f"day_{day}"] = cell_code

        row["total_p"] = p_days
        row["total_wo"] = wo_count
        row["total_h"] = h_count
        row["total_cl"] = cl_count
        row["total_sl"] = sl_count
        row["total_el"] = el_count
        row["total_coff"] = coff_count
        # CPL is a credited leave balance, not added to current month's regular G. Total
        row["g_total"] = p_days + wo_count + h_count + cl_count + sl_count + el_count

        row["total_ot"] = round(total_ot, 1) if is_ot_applicable else 0.0
        row["attendance_bonus"] = 2000.0 if (p_days > 0 and absent_count == 0) else 0.0

        data.append(row)

    return columns, data
