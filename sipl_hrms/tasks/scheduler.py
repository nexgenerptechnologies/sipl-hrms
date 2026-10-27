import frappe

def hourly_attendance_processor():
    """
    Hourly background job:
    Picks up newly arrived punches from Employee Checkin,
    pairs them, calculates working hours, and creates/updates Attendance records.
    """
    unlinked = frappe.get_all(
        "Employee Checkin",
        filters={"attendance": ["is", "not set"]},
        fields=["name", "employee", "time", "log_type"],
        order_by="time asc",
        limit=500
    )
    if not unlinked:
        return

    groups = {}
    for c in unlinked:
        emp = c.employee
        dt = str(c.time).split(" ")[0]
        key = (emp, dt)
        if key not in groups:
            groups[key] = []
        groups[key].append(c)

    for (emp_id, att_date), logs in groups.items():
        logs = sorted(logs, key=lambda x: str(x.time))
        in_time = logs[0].time
        out_time = logs[-1].time
        
        diff_seconds = frappe.utils.time_diff_in_seconds(out_time, in_time)
        hours = round(diff_seconds / 3600.0, 2)
        
        # Working hours status evaluation
        if len(logs) == 1:
            status = "Half Day"
            hours = 4.0
        elif hours >= 7.5:
            status = "Present"
        elif hours >= 4.0:
            status = "Half Day"
        else:
            status = "Half Day" if hours > 1.5 else "Absent"

        emp_doc = frappe.get_doc("Employee", emp_id)
        company = emp_doc.company or "SIMPLE INTEGRAL PVT. LTD."
        
        # Determine employee's shift dynamically for this date
        shift_name = frappe.db.get_value("Shift Assignment", {
            "employee": emp_id,
            "start_date": ["<=", att_date],
            "end_date": [">=", att_date],
            "docstatus": 1,
            "status": "Active"
        }, "shift_type") or frappe.db.get_value("Shift Assignment", {
            "employee": emp_id,
            "start_date": ["<=", att_date],
            "end_date": ["is", "not set"],
            "docstatus": 1,
            "status": "Active"
        }, "shift_type") or emp_doc.default_shift or "General"

        existing_att = frappe.db.get_value("Attendance", {
            "employee": emp_id,
            "attendance_date": att_date,
            "docstatus": ["!=", 2]
        }, "name")
        
        if not existing_att:
            att = frappe.new_doc("Attendance")
            att.employee = emp_id
            att.attendance_date = att_date
            att.company = company
            att.status = status
            att.shift = shift_name
            att.in_time = in_time
            att.out_time = out_time
            att.working_hours = hours
            att.docstatus = 1
            att.insert(ignore_permissions=True)
            att_name = att.name
        else:
            att_name = existing_att
            frappe.db.set_value("Attendance", att_name, "out_time", out_time)
            frappe.db.set_value("Attendance", att_name, "working_hours", hours)
            if hours >= 7.5:
                frappe.db.set_value("Attendance", att_name, "status", "Present")
                
        for l in logs:
            frappe.db.set_value("Employee Checkin", l.name, "attendance", att_name)
            frappe.db.set_value("Employee Checkin", l.name, "shift", shift_name)
            frappe.db.set_value("Employee Checkin", l.name, "offshift", 0)

    frappe.db.commit()
