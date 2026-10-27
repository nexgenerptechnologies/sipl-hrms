import frappe
from frappe.model.document import Document
from frappe.utils import getdate, time_diff_in_seconds, get_datetime
from sipl_hrms.utils import get_shift_details

class EmployeeGatePass(Document):
    def validate(self):
        self.calculate_duration()
        self.validate_monthly_limit()

    def calculate_duration(self):
        if not self.departure_time:
            self.total_duration_hours = 0.0
            return

        if self.will_return == "Yes":
            end_t = self.actual_return_time or self.expected_return_time
            if end_t:
                diff_secs = time_diff_in_seconds(f"2000-01-01 {end_t}", f"2000-01-01 {self.departure_time}")
                self.total_duration_hours = max(0.0, round(diff_secs / 3600.0, 2)) if diff_secs > 0 else 0.0
            else:
                self.total_duration_hours = 0.0
        else:
            # Did not return -> duration away from work until scheduled shift end
            shift_end_time = "18:30:00"
            if self.employee:
                emp_shift = frappe.db.get_value("Employee", self.employee, "default_shift") or "General"
                shift_info = get_shift_details(emp_shift)
                shift_end_time = f"{shift_info.get('end_time', '18:30')}:00"
            diff_secs = time_diff_in_seconds(f"2000-01-01 {shift_end_time}", f"2000-01-01 {self.departure_time}")
            self.total_duration_hours = max(0.0, round(diff_secs / 3600.0, 2)) if diff_secs > 0 else 0.0

    def validate_monthly_limit(self):
        if not self.employee or not self.date:
            return

        # 1. OFFICIAL DUTY: Unlimited, does not count against personal limit
        if self.gate_pass_type == "Official Duty (OD)":
            self.gate_passes_this_month = 0
            self.exceeds_policy = 0
            self.status = "Official Duty Approved" if self.docstatus == 1 else "Draft"
            return

        # 2. PERSONAL WORK: Max 2 passes per month, max 2 hours each
        pass_date = getdate(self.date)
        first_day = pass_date.replace(day=1)

        count = frappe.db.count("Employee Gate Pass", {
            "employee": self.employee,
            "date": [">=", first_day],
            "gate_pass_type": "Personal Work",
            "name": ["!=", self.name or ""],
            "docstatus": 1
        })
        self.gate_passes_this_month = count + 1

        if self.will_return == "Yes":
            if (self.gate_passes_this_month > 2) or (self.total_duration_hours > 2.0):
                self.exceeds_policy = 1
                self.status = "Adjusted to Half Day"
            else:
                self.exceeds_policy = 0
                self.status = "Submitted" if self.docstatus == 1 else "Draft"
        else:
            # Does not return for personal work -> always adjusted against Half Day / Absent
            self.exceeds_policy = 1
            self.status = "Adjusted to Half Day"

    def on_submit(self):
        self.apply_attendance_integration()

    def apply_attendance_integration(self):
        att_name = frappe.db.get_value("Attendance", {
            "employee": self.employee,
            "attendance_date": self.date,
            "docstatus": ["!=", 2]
        }, "name")

        # -----------------------------------------------------------
        # CASE 1: OFFICIAL DUTY (OD)
        # -----------------------------------------------------------
        if self.gate_pass_type == "Official Duty (OD)":
            emp = frappe.get_doc("Employee", self.employee)
            emp_shift = emp.default_shift or "General"
            shift_info = get_shift_details(emp_shift)
            shift_start_t = f"{shift_info.get('start_time', '09:30')}:00"
            shift_end_t = f"{shift_info.get('end_time', '18:30')}:00"

            if att_name:
                frappe.db.set_value("Attendance", att_name, "status", "Present")
                frappe.db.set_value("Attendance", att_name, "working_hours", 9.0)
                frappe.db.set_value("Attendance", att_name, "custom_gate_pass_linked", self.name)
                if self.will_return == "No (Direct to Home)":
                    frappe.db.set_value("Attendance", att_name, "out_time", f"{self.date} {shift_end_t}")
            else:
                new_att = frappe.new_doc("Attendance")
                new_att.employee = self.employee
                new_att.attendance_date = self.date
                new_att.company = emp.company or "SIMPLE INTEGRAL PVT. LTD."
                new_att.status = "Present"
                new_att.shift = emp_shift
                new_att.in_time = f"{self.date} {shift_start_t}"
                new_att.out_time = f"{self.date} {shift_end_t}"
                new_att.working_hours = 9.0
                new_att.custom_gate_pass_linked = self.name
                new_att.docstatus = 1
                new_att.insert(ignore_permissions=True)
            frappe.msgprint(f"✅ Official Duty Gate Pass applied. {self.employee_name} marked as Present (Full Day) on {self.date}.")
            return

        # -----------------------------------------------------------
        # CASE 2: PERSONAL WORK
        # -----------------------------------------------------------
        if self.will_return == "No (Direct to Home)":
            # Early departure - check actual hours worked before leaving
            in_time_val = None
            if att_name:
                in_time_val = frappe.db.get_value("Attendance", att_name, "in_time")
            if not in_time_val:
                earliest_ckin = frappe.db.get_value("Employee Checkin", {
                    "employee": self.employee,
                    "time": ["between", [f"{self.date} 00:00:00", f"{self.date} 23:59:59"]]
                }, "time", order_by="time asc")
                in_time_val = earliest_ckin

            hours_worked = 4.0
            if in_time_val:
                dep_dt = f"{self.date} {self.departure_time}"
                diff = time_diff_in_seconds(dep_dt, in_time_val)
                if diff > 0:
                    hours_worked = round(diff / 3600.0, 2)

            status = "Half Day" if hours_worked >= 4.0 else "Absent"

            if att_name:
                frappe.db.set_value("Attendance", att_name, "status", status)
                frappe.db.set_value("Attendance", att_name, "working_hours", hours_worked)
                frappe.db.set_value("Attendance", att_name, "out_time", f"{self.date} {self.departure_time}")
                frappe.db.set_value("Attendance", att_name, "custom_gate_pass_linked", self.name)
            else:
                emp = frappe.get_doc("Employee", self.employee)
                emp_shift = emp.default_shift or "General"
                shift_info = get_shift_details(emp_shift)
                shift_start_t = f"{shift_info.get('start_time', '09:30')}:00"

                new_att = frappe.new_doc("Attendance")
                new_att.employee = self.employee
                new_att.attendance_date = self.date
                new_att.company = emp.company or "SIMPLE INTEGRAL PVT. LTD."
                new_att.status = status
                new_att.shift = emp_shift
                new_att.in_time = in_time_val or f"{self.date} {shift_start_t}"
                new_att.out_time = f"{self.date} {self.departure_time}"
                new_att.working_hours = hours_worked
                new_att.custom_gate_pass_linked = self.name
                new_att.docstatus = 1
                new_att.insert(ignore_permissions=True)
            frappe.msgprint(f"⚠️ Personal Early Exit Gate Pass applied: {self.employee_name} marked as {status} ({hours_worked} hrs worked).")

        else:
            # Returns to office, but exceeded 2h or 2-pass monthly limit
            if self.exceeds_policy and att_name:
                frappe.db.set_value("Attendance", att_name, "status", "Half Day")
                frappe.db.set_value("Attendance", att_name, "custom_gate_pass_linked", self.name)
                frappe.msgprint(f"⚠️ Personal Gate Pass exceeds monthly allowance. Attendance for {self.employee_name} on {self.date} marked as Half Day.")
