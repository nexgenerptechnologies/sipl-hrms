import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

def after_install():
    setup_custom_fields()
    setup_leave_types()
    clean_department_names()
    setup_property_setters()

def after_migrate():
    setup_custom_fields()
    setup_leave_types()
    clean_department_names()
    setup_property_setters()

def clean_department_names():
    # If 'ERP - SIPL' exists, rename cleanly to 'ERP'
    if frappe.db.exists("Department", "ERP - SIPL"):
        frappe.db.sql("UPDATE `tabDepartment` SET name = 'ERP' WHERE name = 'ERP - SIPL'")
        frappe.db.sql("UPDATE `tabEmployee` SET department = 'ERP' WHERE department = 'ERP - SIPL'")
        frappe.db.commit()
        frappe.clear_cache(doctype="Department")

def setup_custom_fields():
    custom_fields = {
        "Employee": [
            {
                "fieldname": "custom_overtime_applicable",
                "label": "Overtime Applicable",
                "fieldtype": "Select",
                "options": "OT Not Applicable\nOT Applicable",
                "default": "OT Not Applicable",
                "insert_after": "employment_type"
            }
        ],
        "Attendance": [
            {
                "fieldname": "custom_overtime_hours",
                "label": "Overtime Hours",
                "fieldtype": "Float",
                "read_only": 1,
                "insert_after": "working_hours"
            },
            {
                "fieldname": "custom_late_stay_hours",
                "label": "Late Stay Hours (for C-Off)",
                "fieldtype": "Float",
                "read_only": 1,
                "insert_after": "custom_overtime_hours"
            },
            {
                "fieldname": "custom_late_minutes",
                "label": "Late Minutes",
                "fieldtype": "Int",
                "read_only": 1,
                "insert_after": "late_entry"
            },
            {
                "fieldname": "custom_gate_pass_linked",
                "label": "Linked Gate Pass",
                "fieldtype": "Link",
                "options": "Employee Gate Pass",
                "read_only": 1,
                "insert_after": "custom_late_minutes"
            }
        ]
    }
    create_custom_fields(custom_fields, ignore_validate=True)

def setup_leave_types():
    leave_types = [
        {"leave_type_name": "Compensatory Off (Holiday)", "is_compensatory": 1},
        {"leave_type_name": "Compensatory Off (Late Stay)", "is_compensatory": 1}
    ]
    for lt in leave_types:
        if not frappe.db.exists("Leave Type", lt["leave_type_name"]):
            doc = frappe.new_doc("Leave Type")
            doc.leave_type_name = lt["leave_type_name"]
            doc.is_compensatory = lt["is_compensatory"]
            doc.insert(ignore_permissions=True)
            frappe.db.commit()

def setup_property_setters():
    """
    Enables allow_on_submit on key Attendance fields so HR Manager can edit
    back-dated and current-dated submitted attendance records without errors.
    """
    fields_to_allow = [
        'status', 'in_time', 'out_time', 'working_hours',
        'late_entry', 'early_exit', 'custom_late_minutes',
        'custom_overtime_hours', 'custom_late_stay_hours', 'custom_gate_pass_linked'
    ]
    for field in fields_to_allow:
        ps_name = f"Attendance-{field}-allow_on_submit"
        if not frappe.db.exists("Property Setter", ps_name):
            ps = frappe.new_doc("Property Setter")
            ps.name = ps_name
            ps.doc_type = "Attendance"
            ps.field_name = field
            ps.property = "allow_on_submit"
            ps.property_type = "Check"
            ps.value = "1"
            ps.doctype_or_field = "DocField"
            ps.insert(ignore_permissions=True)
        else:
            frappe.db.set_value("Property Setter", ps_name, "value", "1")
    frappe.clear_cache(doctype="Attendance")
