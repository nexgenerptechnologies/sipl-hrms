frappe.query_reports["Attendance Performance Summary"] = {
    "filters": [
        {
            "fieldname": "from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.month_start(),
            "reqd": 1
        },
        {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.get_today(),
            "reqd": 1
        },
        {
            "fieldname": "company",
            "label": __("Company"),
            "fieldtype": "Link",
            "options": "Company",
            "default": frappe.defaults.get_user_default("Company") || "SIMPLE INTEGRAL PVT. LTD."
        },
        {
            "fieldname": "department",
            "label": __("Department"),
            "fieldtype": "Link",
            "options": "Department"
        },
        {
            "fieldname": "employee",
            "label": __("Employee"),
            "fieldtype": "Link",
            "options": "Employee"
        }
    ],
    "formatter": function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (data && data.metric === "Status") {
            if (value === "P") {
                value = `<span style="color: #2e7d32; font-weight: bold;">P</span>`;
            } else if (value === "PWO") {
                value = `<span style="color: #6a1b9a; font-weight: bold;">PWO</span>`;
            } else if (value === "A") {
                value = `<span style="color: #c62828; font-weight: bold;">A</span>`;
            } else if (value === "A/P" || value === "P/A") {
                value = `<span style="color: #ef6c00; font-weight: bold;">${value}</span>`;
            } else if (value === "W/O") {
                value = `<span style="color: #1565c0; font-weight: bold;">W/O</span>`;
            } else if (value === "H") {
                value = `<span style="color: #00838f; font-weight: bold;">H</span>`;
            }
        }
        return value;
    }
};
