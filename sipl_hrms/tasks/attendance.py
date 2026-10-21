import frappe
from frappe.utils import getdate, get_datetime, time_diff_in_seconds, add_days

def process_attendance_rules(doc, method=None):
    """
    Applies SIPL company rules before saving Attendance:
    1. Overtime vs CPL (Late Stay):
       - If OT Applicable: Extra hours (>10h) count towards OT. CPL = 0.
       - If OT Not Applicable: Extra hours (>9h) count towards CPL / Late Stay Ledger. OT = 0.
    2. Late Coming & Gate Pass Policy:
       - 1st & 2nd late entry <= 30 mins (up to 10:00 AM): Free / Present.
       - 30 mins to 2 hours late (10:00 - 11:30 AM): Allowed only if approved Gate Pass (<=2h). Otherwise Half Day.
       - Arrival after 11:30 AM (even with gate pass): Always Half Day (A/P).
       - Exceeding 2 gate passes per month: Half Day.
    """
    if not doc.employee or not doc.attendance_date:
        return

    working_hours = float(doc.working_hours or 0.0)
    ot_applicable = frappe.db.get_value("Employee", doc.employee, "custom_overtime_applicable")
    
    # ----------------------------------------------------
    # 1. OVERTIME vs CPL (LATE STAY)
    # ----------------------------------------------------
    if ot_applicable == "OT Applicable":
        doc.custom_late_stay_hours = 0.0
        # OT Rule: Calculated after completing 10 hours in a day (working_hours - 9.0)
        if working_hours > 10.0:
            doc.custom_overtime_hours = round(working_hours - 9.0, 2)
        else:
            doc.custom_overtime_hours = 0.0
    else:
        # OT Not Applicable -> Extra hours accumulate towards CPL (Compensatory Off)
        doc.custom_overtime_hours = 0.0
        if working_hours > 9.0:
            extra_h = round(working_hours - 9.0, 2)
            doc.custom_late_stay_hours = min(extra_h, 7.0)
            accumulate_late_stay_c_off(doc)
        else:
            doc.custom_late_stay_hours = 0.0

    # ----------------------------------------------------
    # 2. LATE COMING & GATE PASS POLICY
    # ----------------------------------------------------
    if doc.in_time:
        in_dt = get_datetime(doc.in_time)
        shift_start_dt = get_datetime(f"{doc.attendance_date} 09:30:00")
        
        if in_dt > shift_start_dt:
            diff_secs = time_diff_in_seconds(in_dt, shift_start_dt)
            late_mins = int(diff_secs // 60)
            doc.custom_late_minutes = late_mins
            doc.late_entry = 1
            
            att_date = getdate(doc.attendance_date)
            first_day_of_month = att_date.replace(day=1)
            
            # Count prior late arrivals this month
            prior_late_count = frappe.db.count("Attendance", {
                "employee": doc.employee,
                "attendance_date": [">=", first_day_of_month],
                "name": ["!=", doc.name or ""],
                "late_entry": 1,
                "docstatus": ["!=", 2]
            })
            
            # Fetch approved gate pass for this date if any
            gate_pass = frappe.db.get_value("Employee Gate Pass", {
                "employee": doc.employee,
                "date": doc.attendance_date,
                "docstatus": 1
            }, ["name", "gate_pass_type", "total_duration_hours", "gate_passes_this_month", "exceeds_policy"], as_dict=True)
            
            if gate_pass:
                doc.custom_gate_pass_linked = gate_pass.name

            # Evaluate Policy:
            # Case A: Arriving after 11:30 AM (late_mins > 120)
            # Gate pass is max 2 hours (09:30 - 11:30). Arriving after 11:30 AM means 1st half was missed -> Half Day (A/P)
            if late_mins > 120:
                if doc.status == "Present":
                    doc.status = "Half Day"
                    
            # Case B: Arriving between 10:00 AM and 11:30 AM (30 < late_mins <= 120)
            elif late_mins > 30:
                has_valid_gp = (gate_pass and not gate_pass.exceeds_policy and float(gate_pass.total_duration_hours or 0.0) <= 2.0)
                if not has_valid_gp:
                    if doc.status == "Present":
                        doc.status = "Half Day"
                        
            # Case C: Arriving between 09:30 AM and 10:00 AM (late_mins <= 30)
            else:
                # 3rd late entry onwards without gate pass -> Half Day
                if prior_late_count >= 2 and not gate_pass:
                    if doc.status == "Present":
                        doc.status = "Half Day"
        else:
            doc.custom_late_minutes = 0
            doc.late_entry = 0

    # Ensure status is at least Half Day if working hours between 4.0 and 7.5
    if working_hours < 7.5 and working_hours >= 4.0:
        if doc.status == "Present":
            doc.status = "Half Day"
    elif working_hours < 4.0 and working_hours > 0:
        doc.status = "Absent"

def accumulate_late_stay_c_off(att_doc):
    """
    Accumulates eligible late stay hours.
    Upon reaching 8 hours total, automatically creates 1 day C-Off allocation.
    """
    if not frappe.db.exists("DocType", "Employee Late Stay Ledger"):
        return
        
    existing = frappe.db.get_value("Employee Late Stay Ledger", {
        "attendance": att_doc.name or "",
        "employee": att_doc.employee
    }, ["name", "status"], as_dict=True)
    
    if existing:
        if existing.status == "Accumulating":
            frappe.db.set_value("Employee Late Stay Ledger", existing.name, "late_stay_hours", att_doc.custom_late_stay_hours)
    elif att_doc.custom_late_stay_hours > 0:
        ledger = frappe.new_doc("Employee Late Stay Ledger")
        ledger.employee = att_doc.employee
        ledger.attendance_date = att_doc.attendance_date
        ledger.attendance = att_doc.name
        ledger.late_stay_hours = att_doc.custom_late_stay_hours
        ledger.status = "Accumulating"
        ledger.insert(ignore_permissions=True)
        
    # Check total uncredited hours
    uncredited_logs = frappe.get_all("Employee Late Stay Ledger", filters={
        "employee": att_doc.employee,
        "status": "Accumulating"
    }, fields=["name", "late_stay_hours"])
    
    total_hours = sum([float(x.late_stay_hours or 0.0) for x in uncredited_logs])
    
    # 8 eligible hours = 1 C-Off
    if total_hours >= 8.0:
        credit_c_off_leave(att_doc.employee, att_doc.attendance_date)
        for log in uncredited_logs:
            frappe.db.set_value("Employee Late Stay Ledger", log.name, "status", "Credited to C-Off")
        frappe.db.commit()

def credit_c_off_leave(employee, date):
    leave_type = "Compensatory Off (Late Stay)"
    if not frappe.db.exists("Leave Type", leave_type):
        leave_type = "Compensatory Off"
        
    alloc = frappe.new_doc("Leave Allocation")
    alloc.employee = employee
    alloc.leave_type = leave_type
    alloc.from_date = date
    alloc.to_date = add_days(date, 90) # Valid for 90 days
    alloc.new_leaves_allocated = 1.0
    alloc.description = "Auto-credited for 8 accumulated late-stay hours"
    alloc.docstatus = 1
    alloc.insert(ignore_permissions=True)
