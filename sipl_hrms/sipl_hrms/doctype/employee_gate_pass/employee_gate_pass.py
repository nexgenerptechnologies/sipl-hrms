import frappe
from frappe.model.document import Document
from frappe.utils import getdate, time_diff_in_seconds

class EmployeeGatePass(Document):
    def validate(self):
        self.calculate_duration()
        self.validate_monthly_limit()

    def calculate_duration(self):
        end_t = self.actual_return_time or self.expected_return_time
        if self.departure_time and end_t:
            diff_secs = time_diff_in_seconds(f"2000-01-01 {end_t}", f"2000-01-01 {self.departure_time}")
            if diff_secs > 0:
                self.total_duration_hours = round(diff_secs / 3600.0, 2)
            else:
                self.total_duration_hours = 0.0

    def validate_monthly_limit(self):
        """
        Rules:
        - Max 2 gate passes per month.
        - Max 2 hours each.
        - Exceeding instances adjusted against Half Day.
        """
        if not self.employee or not self.date:
            return
            
        pass_date = getdate(self.date)
        first_day = pass_date.replace(day=1)
        
        # Count submitted gate passes in this calendar month
        count = frappe.db.count("Employee Gate Pass", {
            "employee": self.employee,
            "date": [">=", first_day],
            "name": ["!=", self.name or ""],
            "docstatus": 1
        })
        self.gate_passes_this_month = count + 1
        
        if (self.gate_passes_this_month > 2) or (self.total_duration_hours > 2.0):
            self.exceeds_policy = 1
            self.status = "Adjusted to Half Day"
        else:
            self.exceeds_policy = 0
            if self.docstatus == 1:
                self.status = "Submitted"
            else:
                self.status = "Draft"

    def on_submit(self):
        if self.exceeds_policy:
            self.apply_half_day_deduction()

    def apply_half_day_deduction(self):
        # Adjust attendance on this date to Half Day
        att = frappe.db.get_value("Attendance", {"employee": self.employee, "attendance_date": self.date, "docstatus": ["!=", 2]}, "name")
        if att:
            frappe.db.set_value("Attendance", att, "status", "Half Day")
            frappe.db.set_value("Attendance", att, "custom_gate_pass_linked", self.name)
            frappe.msgprint(f"⚠️ Gate Pass exceeds monthly allowance. Attendance for {self.employee_name} on {self.date} marked as Half Day.")
