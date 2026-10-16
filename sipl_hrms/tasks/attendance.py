import frappe
from frappe.utils import getdate, get_datetime, time_diff_in_seconds, add_days

def process_attendance_rules(doc, method=None):
    """
    Applies SIPL company rules before saving Attendance:
    1. Overtime Calculation: Starts only after 10 working hours. 10h = 0, 11h = 2h.
    2. Late Stay Hours: Hours > 2 beyond regular (9h), accumulated towards C-Off.
    3. Late Coming Policy: Max 2 late entries <= 30 mins free. 3rd or > 30m = Half Day unless Gate Pass.
    """
    if not doc.employee or not doc.attendance_date:
        return

    working_hours = float(doc.working_hours or 0.0)
    
    # ----------------------------------------------------
    # 1. OVERTIME CALCULATION
    # ----------------------------------------------------
    ot_applicable = frappe.db.get_value("Employee", doc.employee, "custom_overtime_applicable")
    if ot_applicable == "OT Applicable":
        # Rule: OT calculated only after completing 10 hours in a day.
        # Example: 10 hrs = 0 OT. 11 hrs = 2 hrs OT (working_hours - 9.0).
        if working_hours > 10.0:
            doc.custom_overtime_hours = round(working_hours - 9.0, 2)
        else:
            doc.custom_overtime_hours = 0.0
    else:
        doc.custom_overtime_hours = 0.0

    # ----------------------------------------------------
    # 2. LATE STAY HOURS ACCUMULATION FOR C-OFF
    # ----------------------------------------------------
    # Rule: If employee works > 2 hours beyond regular working hours (9h) i.e. > 11h,
    # additional hours count towards C-Off generation (max 7 hours per day counted).
    if working_hours > 11.0:
        late_stay_raw = working_hours - 9.0
        doc.custom_late_stay_hours = min(round(late_stay_raw, 2), 7.0)
        accumulate_late_stay_c_off(doc)
    else:
        doc.custom_late_stay_hours = 0.0

    # ----------------------------------------------------
    # 3. LATE COMING POLICY
    # ----------------------------------------------------
    # Rule: Max 2 instances of late coming per month, up to 30 mins per instance.
    # 3rd instance or > 30 mins late = adjusted against Gate Pass or Half Day.
    if doc.in_time:
        in_dt = get_datetime(doc.in_time)
        shift_start_dt = get_datetime(f"{doc.attendance_date} 09:30:00")
        
        if in_dt > shift_start_dt:
            diff_secs = time_diff_in_seconds(in_dt, shift_start_dt)
            late_mins = int(diff_secs // 60)
            doc.custom_late_minutes = late_mins
            
            if late_mins > 0:
                doc.late_entry = 1
                att_date = getdate(doc.attendance_date)
                first_day_of_month = att_date.replace(day=1)
                
                # Count prior late entries this month
                prior_late_count = frappe.db.count("Attendance", {
                    "employee": doc.employee,
                    "attendance_date": [">=", first_day_of_month],
                    "name": ["!=", doc.name or ""],
                    "late_entry": 1,
                    "docstatus": ["!=", 2]
                })
                
                # Check for approved morning gate pass
                gate_pass = frappe.db.get_value("Employee Gate Pass", {
                    "employee": doc.employee,
                    "date": doc.attendance_date,
                    "docstatus": 1
                }, "name")
                
                if gate_pass:
                    doc.custom_gate_pass_linked = gate_pass
                else:
                    # If 3rd instance OR more than 30 mins late without gate pass -> Half Day
                    if (prior_late_count >= 2) or (late_mins > 30):
                        if doc.status == "Present":
                            doc.status = "Half Day"
        else:
            doc.custom_late_minutes = 0
            doc.late_entry = 0

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
    }, "name")
    
    if not existing and att_doc.custom_late_stay_hours > 0:
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
            # Mark these logs as Credited
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
