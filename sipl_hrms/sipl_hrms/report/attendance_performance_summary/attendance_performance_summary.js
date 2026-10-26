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
        if (!data) return value;

        if (data.metric === "Status") {
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
            } else if (value === "H/D") {
                value = `<span style="color: #00838f; font-weight: bold;">H/D</span>`;
            } else if (["CL", "SL", "EL", "CO", "L", "C", "S", "E", "O"].includes(value)) {
                value = `<span style="color: #d84315; font-weight: 600;">${value}</span>`;
            }
        } else if (data.metric === "Late Coming" || data.metric === "Gate Pass") {
            if (value === "1") {
                value = `<span style="color: #e65100; font-weight: bold;">1</span>`;
            }
        } else if (data.metric === "CPL") {
            if (value === "1" || value === "1.0") {
                value = `<span style="color: #4a148c; font-weight: bold;">1</span>`;
            } else if (value === "0.5") {
                value = `<span style="color: #7b1fa2; font-weight: bold;">0.5</span>`;
            }
        } else if (data.metric === "OT Hours" && value && value !== "0.0") {
            value = `<span style="color: #0277bd; font-weight: 600;">${value}</span>`;
        } else if (data.metric === "CPL Hours" && value && value !== "0") {
            value = `<span style="color: #2e7d32; font-weight: 600;">${value}</span>`;
        }

        return value;
    }
};
