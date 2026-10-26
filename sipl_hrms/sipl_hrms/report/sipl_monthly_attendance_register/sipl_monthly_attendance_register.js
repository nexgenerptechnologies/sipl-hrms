frappe.query_reports["SIPL Monthly Attendance Register"] = {
    "filters": [
        {
            "fieldname": "month",
            "label": __("Month"),
            "fieldtype": "Select",
            "options": [
                {"value": 1, "label": __("Jan")},
                {"value": 2, "label": __("Feb")},
                {"value": 3, "label": __("Mar")},
                {"value": 4, "label": __("Apr")},
                {"value": 5, "label": __("May")},
                {"value": 6, "label": __("Jun")},
                {"value": 7, "label": __("Jul")},
                {"value": 8, "label": __("Aug")},
                {"value": 9, "label": __("Sep")},
                {"value": 10, "label": __("Oct")},
                {"value": 11, "label": __("Nov")},
                {"value": 12, "label": __("Dec")}
            ],
            "default": frappe.datetime.str_to_obj(frappe.datetime.get_today()).getMonth() + 1,
            "reqd": 1
        },
        {
            "fieldname": "year",
            "label": __("Year"),
            "fieldtype": "Select",
            "options": "2024\n2025\n2026\n2027",
            "default": "2026",
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
            "fieldname": "branch",
            "label": __("Branch"),
            "fieldtype": "Link",
            "options": "Branch"
        }
    ],
    "formatter": function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (column && column.fieldname && column.fieldname.startsWith("day_")) {
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
        }
        return value;
    }
};
