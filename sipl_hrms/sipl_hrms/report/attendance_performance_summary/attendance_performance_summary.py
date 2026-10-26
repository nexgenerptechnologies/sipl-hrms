import frappe
from frappe.utils import getdate, add_days, formatdate
from datetime import datetime
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
        {"label": "Metric", "fieldname": "metric", "fieldtype": "Data", "width": 95}
    ]

    for d in dates:
        col_label = formatdate(d, "dd-MMM")
        col_name = str(d)
        columns.append({
            "label": col_label,
            "fieldname": col_name,
            "fieldtype": "Data",
            "width": 75
        })

    # Summary column
    columns.append({
        "label": "Total",
        "fieldname": "total_value",
        "fieldtype": "Data",
        "width": 80
    })

    # Fetch holidays for the company
    holiday_list = frappe.db.get_value("Company", company, "default_holiday_list") or "Holiday List 2026"
    holidays = frappe.get_all("Holiday", filters={
        "parent": holiday_list,
        "holiday_date": ["between", [from_date, to_date]]
    }, fields=["holiday_date", "weekly_off", "description"])

    holiday_map = {str(h.holiday_date): ("W/O" if h.weekly_off else "H/D") for h in holidays}

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

    # Order according to Employee Number (natural sort)
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
        "employee", "attendance_date", "status", "leave_type", "in_time", "out_time", 
        "working_hours", "custom_overtime_hours", "custom_late_stay_hours", 
        "custom_gate_pass_linked", "late_entry"
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

        # 9 Metric rows per employee as per requirements
        row_in = {"employee": emp_id, "employee_number": emp_num, "employee_name": emp_name, "metric": "in"}
        row_out = {"employee": "", "employee_number": "", "employee_name": "", "metric": "out"}
        row_status = {"employee": "", "employee_number": "", "employee_name": "", "metric": "Status"}
        row_thrs = {"employee": "", "employee_number": "", "employee_name": "", "metric": "T Hrs."}
        row_late = {"employee": "", "employee_number": "", "employee_name": "", "metric": "Late Coming"}
        row_gp = {"employee": "", "employee_number": "", "employee_name": "", "metric": "Gate Pass"}
        row_ot = {"employee": "", "employee_number": "", "employee_name": "", "metric": "OT Hours"}
        row_cpl_hrs = {"employee": "", "employee_number": "", "employee_name": "", "metric": "CPL Hours"}
        row_cpl = {"employee": "", "employee_number": "", "employee_name": "", "metric": "CPL"}

        p_count = 0.0
        tot_work_hours = 0.0
        tot_late_count = 0
        tot_gp_count = 0
        tot_ot_hours = 0.0
        tot_cpl_hours = 0.0
        tot_sunday_cpl = 0.0

        # Month tracking for gate passes & late grace (<=30 mins)
        gate_pass_used = 0
        late_grace_used = 0

        for d in dates:
            d_str = str(d)
            rec = att_map.get((emp_id, d_str))
            is_sunday = (d.weekday() == 6)
            h_type = holiday_map.get(d_str)

            in_val = ""
            out_val = ""
            st_val = ""
            thrs_val = ""
            late_val = ""
            gp_val = ""
            ot_val = ""
            cpl_hrs_val = ""
            cpl_val = ""

            has_in = bool(rec and rec.in_time)
            has_out = bool(rec and rec.out_time)

            if has_in:
                in_val = str(rec.in_time)[11:16]
            if has_out:
                out_val = str(rec.out_time)[11:16]

            # -------------------------------------------------------------
            # MISSING PUNCH LOGIC (Items 12 & 13)
            # -------------------------------------------------------------
            if has_in != has_out:
                # Single punch
                if is_sunday or h_type == "W/O":
                    st_val = "W/O" # Item 13: On Sunday, single punch shows W/O
                elif h_type == "H/D":
                    st_val = "H/D"
                else:
                    st_val = "A"   # Item 12: On working days, single punch shows A

            elif not has_in and not has_out:
                # No punches
                if is_sunday or h_type == "W/O":
                    st_val = "W/O"
                elif h_type == "H/D":
                    # Item 15: Sandwich rule for Holiday
                    # Check 1 day before and 1 day after
                    prev_d_str = str(add_days(d, -1))
                    next_d_str = str(add_days(d, 1))
                    prev_rec = att_map.get((emp_id, prev_d_str))
                    next_rec = att_map.get((emp_id, next_d_str))

                    prev_qual = prev_rec and (prev_rec.status in ["Present", "Half Day"] or prev_rec.leave_type)
                    next_qual = next_rec and (next_rec.status in ["Present", "Half Day"] or next_rec.leave_type)

                    if prev_qual or next_qual:
                        st_val = "H/D"
                    else:
                        st_val = "A"
                else:
                    # Normal working day without punch
                    st_val = "A" if d <= getdate() else ""

            else:
                # Both Check In and Check Out exist!
                wh = float(rec.working_hours or 0.0)
                tot_work_hours += wh
                thrs_val = str(round(wh, 1)) if wh > 0 else ""

                if is_sunday or h_type == "W/O":
                    # ---------------------------------------------------------
                    # SUNDAY ATTENDANCE & CPL (Items 7 & 11)
                    # ---------------------------------------------------------
                    st_val = "PWO"

                    if wh >= 7.0:
                        cpl_val = "1"
                        tot_sunday_cpl += 1.0
                    elif wh > 3.5:
                        cpl_val = "0.5"
                        tot_sunday_cpl += 0.5
                    else:
                        cpl_val = ""

                    cpl_hrs_val = "" # On Sunday CPL hours should not show
                    # Sunday presence is credited as CPL, not added to regular shift p_count

                else:
                    # ---------------------------------------------------------
                    # WORKING DAY ATTENDANCE, GATE PASS & LATE COMING (Items 1, 8, 9)
                    # ---------------------------------------------------------
                    if wh < 4.0 and wh > 0:
                        st_val = "A"
                    else:
                        is_late_entry = (in_val > "09:30")

                        if is_late_entry:
                            if in_val <= "10:00":
                                # Late Coming grace period (up to 30 mins)
                                late_grace_used += 1
                                late_val = "1"
                                tot_late_count += 1
                                if late_grace_used <= 2:
                                    st_val = "P"
                                    p_count += 1.0
                                else:
                                    st_val = "A/P"
                                    p_count += 0.5

                            elif in_val <= "11:30":
                                # Gate pass allowance window (30 mins to 2 hours)
                                if gate_pass_used < 2:
                                    gate_pass_used += 1
                                    gp_val = "1"
                                    tot_gp_count += 1
                                    st_val = "P" # Items 1 & 8: 1st & 2nd gate pass allowed -> P
                                    p_count += 1.0
                                else:
                                    st_val = "A/P" # Item 9: after 2 gate passes -> A/P
                                    p_count += 0.5
                            else:
                                # Arrived after 11:30 AM
                                st_val = "A/P"
                                p_count += 0.5

                        else:
                            # On-time arrival
                            st_val = "P"
                            p_count += 1.0

                        # Check early departure before 18:30 (Item 9)
                        if out_val and out_val < "18:30" and wh < 8.5:
                            if st_val == "P":
                                if gate_pass_used < 2:
                                    gate_pass_used += 1
                                    gp_val = "1"
                                    tot_gp_count += 1
                                    st_val = "P"
                                else:
                                    st_val = "P/A"
                                    p_count -= 0.5 # adjusted to half day

                    # ---------------------------------------------------------
                    # OVERTIME (Item 16: Option A)
                    # ---------------------------------------------------------
                    if is_ot_applicable:
                        if wh > 10.0:
                            ot_h = round(wh - 10.0, 1)
                            ot_val = str(ot_h)
                            tot_ot_hours += ot_h
                        else:
                            ot_val = ""

                    # ---------------------------------------------------------
                    # CPL HOURS (Items 6 & 10)
                    # ---------------------------------------------------------
                    if not is_ot_applicable:
                        out_dt = datetime.strptime(f"{d_str} {out_val}", "%Y-%m-%d %H:%M")
                        shift_end = datetime.strptime(f"{d_str} 18:30", "%Y-%m-%d %H:%M")
                        if out_dt > shift_end:
                            extra_secs = (out_dt - shift_end).total_seconds()
                            extra_h = round(extra_secs / 3600.0, 1)
                            if extra_h >= 2.0:
                                cpl_hrs_int = int(round(extra_h))
                                cpl_hrs_val = str(cpl_hrs_int)
                                tot_cpl_hours += cpl_hrs_int
                            else:
                                cpl_hrs_val = "" # stays < 2 hours don't count

            # Populate cells
            row_in[d_str] = in_val
            row_out[d_str] = out_val
            row_status[d_str] = st_val
            row_thrs[d_str] = thrs_val
            row_late[d_str] = late_val
            row_gp[d_str] = gp_val
            row_ot[d_str] = ot_val
            row_cpl_hrs[d_str] = cpl_hrs_val
            row_cpl[d_str] = cpl_val

        # Populate Totals for each metric row
        row_in["total_value"] = str(round(p_count, 1))
        row_out["total_value"] = ""
        row_status["total_value"] = ""
        row_thrs["total_value"] = str(round(tot_work_hours, 1)) if tot_work_hours > 0 else ""
        row_late["total_value"] = str(tot_late_count) if tot_late_count > 0 else ""
        row_gp["total_value"] = str(tot_gp_count) if tot_gp_count > 0 else ""
        row_ot["total_value"] = str(round(tot_ot_hours, 1)) if is_ot_applicable and tot_ot_hours > 0 else ""
        row_cpl_hrs["total_value"] = str(int(round(tot_cpl_hours))) if not is_ot_applicable and tot_cpl_hours > 0 else ""
        row_cpl["total_value"] = str(round(tot_sunday_cpl, 1)) if tot_sunday_cpl > 0 else ""

        data.extend([
            row_in, row_out, row_status, row_thrs, 
            row_late, row_gp, row_ot, row_cpl_hrs, row_cpl
        ])

    return columns, data
