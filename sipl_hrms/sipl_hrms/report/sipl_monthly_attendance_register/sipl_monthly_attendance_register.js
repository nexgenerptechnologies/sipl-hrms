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
            "default": frappe.defaults.get_user_default("Company")
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
    ]
};
