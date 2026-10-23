import frappe
from erpnext.setup.doctype.department.department import Department

class CustomDepartment(Department):
    def autoname(self):
        # Name the Department cleanly without appending company abbreviation (e.g. 'ERP' instead of 'ERP - SIPL')
        self.name = (self.department_name or "").strip()

def before_insert_department(doc, method=None):
    if doc.department_name:
        doc.name = doc.department_name.strip()

@frappe.whitelist()
def fix_erp_department():
    if frappe.db.exists("Department", "ERP - SIPL"):
        frappe.db.sql("UPDATE `tabDepartment` SET name = 'ERP' WHERE name = 'ERP - SIPL'")
        frappe.db.sql("UPDATE `tabEmployee` SET department = 'ERP' WHERE department = 'ERP - SIPL'")
        frappe.db.commit()
        frappe.clear_cache(doctype="Department")
        return "Renamed ERP - SIPL to ERP successfully"
    return "Department ERP already exists or ERP - SIPL not found"
