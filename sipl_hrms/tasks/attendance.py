import frappe
from frappe.utils import getdate, get_datetime, time_diff_in_seconds, add_days
from sipl_hrms.utils import get_shift_details

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
    
    att_date = getdate(doc.attendance_date)
    is_sunday = (att_date.weekday() == 6)

    # Fetch dynamic shift details
    shift_name = doc.shift or frappe.db.get_value("Employee", doc.employee, "default_shift") or "General"
    shift_info = get_shift_details(shift_name)
    shift_start_str = shift_info.get("start_time", "09:30")
    shift_end_str = shift_info.get("end_time", "18:30")

    # ----------------------------------------------------
    # 1. OVERTIME vs CPL (LATE STAY)
    # ----------------------------------------------------
    if ot_applicable == "OT Applicable":
        doc.custom_late_stay_hours = 0.0
        # No overtime up to 10 hours, but if employee worked > 10.0 hrs (e.g. 10.5 hrs), OT is 1.5 hrs (wh - 9.0)
        if round(working_hours, 1) > 10.0:
            doc.custom_overtime_hours = round(working_hours - 9.0, 2)
        else:
            doc.custom_overtime_hours = 0.0
    else:
        # OT Not Applicable -> Extra stay beyond scheduled shift end counts towards CPL only if >= 2.0 hours
        doc.custom_overtime_hours = 0.0
        if not is_sunday and doc.out_time:
            out_dt = get_datetime(doc.out_time)
            shift_end_dt = get_datetime(f"{doc.attendance_date} {shift_end_str}:00")
            if out_dt > shift_end_dt:
                diff_secs = time_diff_in_seconds(out_dt, shift_end_dt)
                extra_stay_h = round(diff_secs / 3600.0, 2)
                if extra_stay_h >= 2.0:
                    doc.custom_late_stay_hours = extra_stay_h
                    accumulate_late_stay_c_off(doc)
                else:
                    doc.custom_late_stay_hours = 0.0
            else:
                doc.custom_late_stay_hours = 0.0
        else:
            doc.custom_late_stay_hours = 0.0

    # ----------------------------------------------------
    # 2. LATE COMING & GATE PASS POLICY
    # ----------------------------------------------------
    if is_sunday:
        doc.late_entry = 0
        doc.custom_late_minutes = 0
        if working_hours >= 3.5:
            doc.status = "Present"
        elif working_hours > 0.0:
            doc.status = "Half Day"
        else:
            doc.status = "Absent"
    elif doc.in_time:
        in_dt = get_datetime(doc.in_time)
        shift_start_dt = get_datetime(f"{doc.attendance_date} {shift_start_str}:00")
        
        if in_dt > shift_start_dt:
            diff_secs = time_diff_in_seconds(in_dt, shift_start_dt)
            late_mins = int(diff_secs // 60)
            doc.custom_late_minutes = late_mins
            doc.late_entry = 1
            
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
            # Case A: Arriving after 11:30 AM (late_mins > 120) -> Half Day (A/P)
            if late_mins > 120:
                doc.status = "Half Day"
                    
            # Case B: Arriving between 10:00 AM and 11:30 AM (30 < late_mins <= 120)
            elif late_mins > 30:
                has_valid_gp = (gate_pass and not gate_pass.exceeds_policy and float(gate_pass.total_duration_hours or 0.0) <= 2.0)
                if not has_valid_gp and prior_late_count >= 2:
                    doc.status = "Half Day"
                else:
                    doc.status = "Present"
                        
            # Case C: Arriving between 09:30 AM and 10:00 AM (late_mins <= 30)
            else:
                # 3rd late entry onwards -> Half Day
                if prior_late_count >= 2 and not gate_pass:
                    doc.status = "Half Day"
                else:
                    doc.status = "Present"
        else:
            doc.custom_late_minutes = 0
            doc.late_entry = 0

    if not is_sunday:
        # Item 12: Missing punch check on working days
        if not doc.in_time or not doc.out_time:
            doc.status = "Absent"
        elif working_hours < 7.5 and working_hours >= 4.0:
            if doc.status == "Present" and (not doc.custom_gate_pass_linked and (doc.custom_late_minutes or 0) <= 30):
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
