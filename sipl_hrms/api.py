import frappe
from frappe.utils import getdate, get_datetime
from datetime import datetime
import json
import re

def parse_punch_datetime(dt_str):
    if not dt_str:
        return None
    dt_str = str(dt_str).strip()
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%d-%m-%Y %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%d-%m-%Y %H:%M",
        "%Y/%m/%d %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%d/%m/%Y %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(dt_str, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    try:
        return str(get_datetime(dt_str))
    except Exception:
        return None

def find_employee(emp_code):
    if not emp_code:
        return None
    code_str = str(emp_code).strip()
    
    # 1. Match attendance_device_id
    emp = frappe.db.get_value("Employee", {"attendance_device_id": code_str, "status": "Active"}, "name")
    if emp:
        return emp
        
    # 2. Match employee_number (e.g. SIPL0273)
    emp = frappe.db.get_value("Employee", {"employee_number": code_str, "status": "Active"}, "name")
    if emp:
        return emp

    # 3. If numeric (e.g. 273), match numeric part of employee_number
    digits = re.findall(r'\d+', code_str)
    if digits:
        target_num = int(digits[0])
        active_emps = frappe.get_all("Employee", filters={"status": "Active"}, fields=["name", "employee_number"])
        for e in active_emps:
            emp_num = e.get("employee_number") or ""
            emp_digits = re.findall(r'\d+', emp_num)
            if emp_digits and int(emp_digits[0]) == target_num:
                return e.name

    # 4. Fallback: match by name or user_id
    emp = frappe.db.get_value("Employee", {"name": code_str, "status": "Active"}, "name")
    return emp

@frappe.whitelist(allow_guest=True)
def receive_easytimepro_punch(*args, **kwargs):
    """
    Receives punch data posted from EasyTimePro API Settings push.
    Handles raw JSON array, JSON object with list, or form_dict.
    """
    raw_data = None
    try:
        raw_data = frappe.request.get_data(as_text=True)
    except Exception:
        pass

    punches = []

    # 1. Try parsing raw JSON body (standard JSON or single-quoted Python dict/list)
    if raw_data:
        try:
            parsed = json.loads(raw_data)
        except Exception:
            try:
                import ast
                parsed = ast.literal_eval(raw_data)
            except Exception:
                try:
                    # Clean up quotes if needed
                    cleaned = raw_data.replace("'", '"')
                    parsed = json.loads(cleaned)
                except Exception:
                    pass

        if parsed:
            if isinstance(parsed, list):
                punches = parsed
            elif isinstance(parsed, dict):
                if "data" in parsed and isinstance(parsed["data"], list):
                    punches = parsed["data"]
                elif "punches" in parsed and isinstance(parsed["punches"], list):
                    punches = parsed["punches"]
                elif "EMP_CODE" in parsed or "emp_code" in parsed or "employee_id" in parsed:
                    punches = [parsed]

    # 2. Try frappe.form_dict if not parsed from raw body
    if not punches and frappe.form_dict:
        data_field = frappe.form_dict.get("data") or frappe.form_dict.get("punches")
        if data_field and isinstance(data_field, str):
            try:
                parsed = json.loads(data_field)
                if isinstance(parsed, list):
                    punches = parsed
            except Exception:
                pass
        
        if not punches and ("EMP_CODE" in frappe.form_dict or "emp_code" in frappe.form_dict):
            punches = [dict(frappe.form_dict)]

    if not punches:
        return {
            "status": "ignored",
            "message": "No punch records found in request payload"
        }

    created_count = 0
    skipped_count = 0
    errors = []

    for item in punches:
        if not isinstance(item, dict):
            continue

        emp_code = (
            item.get("EMP_CODE") or item.get("emp_code") or 
            item.get("Employee ID") or item.get("employee_id") or 
            item.get("user_id") or item.get("badge_number")
        )
        punch_dt_raw = (
            item.get("PUNCH_DATETIME") or item.get("punch_datetime") or 
            item.get("Punch Date & Time") or item.get("time") or 
            item.get("timestamp")
        )

        if not punch_dt_raw and item.get("PUNCH_DATE") and item.get("PUNCH_TIME"):
            punch_dt_raw = f"{item['PUNCH_DATE']} {item['PUNCH_TIME']}"

        punch_time = parse_punch_datetime(punch_dt_raw)
        if not emp_code or not punch_time:
            continue

        emp_name = find_employee(emp_code)
        if not emp_name:
            errors.append(f"Employee not found for code: {emp_code}")
            continue

        device_sn = item.get("TERMINAL_SN") or item.get("terminal_sn") or item.get("device_id") or "EasyTimePro"
        punch_state = (item.get("PUNCH_STATE") or item.get("punch_state") or "").upper()
        log_type = "IN" if "IN" in punch_state else ("OUT" if "OUT" in punch_state else "")

        # Check for existing checkin to avoid duplicates
        existing = frappe.db.exists("Employee Checkin", {
            "employee": emp_name,
            "time": punch_time
        })

        if existing:
            skipped_count += 1
            continue

        try:
            checkin = frappe.new_doc("Employee Checkin")
            checkin.employee = emp_name
            checkin.time = punch_time
            checkin.device_id = device_sn

            # Geolocation coordinates (default to SIPL plant location if not sent by device)
            lat = item.get("LATITUDE") or item.get("latitude")
            lon = item.get("LONGITUDE") or item.get("longitude")
            try:
                checkin.latitude = float(lat) if lat else 28.4787974
            except Exception:
                checkin.latitude = 28.4787974

            try:
                checkin.longitude = float(lon) if lon else 76.9881728
            except Exception:
                checkin.longitude = 76.9881728

            if log_type:
                checkin.log_type = log_type
            checkin.insert(ignore_permissions=True)
            created_count += 1
        except Exception as e:
            errors.append(f"Error inserting checkin for {emp_name} at {punch_time}: {str(e)}")

    if created_count > 0:
        frappe.db.commit()
        # Trigger attendance processing
        try:
            from sipl_hrms.tasks.scheduler import hourly_attendance_processor
            hourly_attendance_processor()
        except Exception as e:
            frappe.log_error(f"Error in auto attendance processor: {e}", "EasyTimePro Punch Sync")

    return {
        "status": "success",
        "created": created_count,
        "skipped": skipped_count,
        "errors": errors
    }
