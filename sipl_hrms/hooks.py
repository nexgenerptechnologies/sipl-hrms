app_name = "sipl_hrms"
app_title = "SIPL HRMS"
app_publisher = "Nexgen ERP Technologies"
app_description = "Custom HRMS Extension for SIPL (Overtime, Gate Pass, C-Off, Attendance Performance, Monthly Register)"
app_email = "contact@nexgenerptechnologies.com"
app_license = "mit"
app_version = "0.0.1"

# Installation & Migration Hooks
after_install = "sipl_hrms.setup.install.after_install"
after_migrate = "sipl_hrms.setup.install.after_migrate"

# Document Event Hooks
doc_events = {
    "Attendance": {
        "before_save": "sipl_hrms.tasks.attendance.process_attendance_rules"
    },
    "Department": {
        "before_insert": "sipl_hrms.overrides.department.before_insert_department"
    }
}

override_doctype_class = {
    "Department": "sipl_hrms.overrides.department.CustomDepartment"
}

# Scheduler Hooks
scheduler_events = {
    "hourly": [
        "sipl_hrms.tasks.scheduler.hourly_attendance_processor"
    ]
}
