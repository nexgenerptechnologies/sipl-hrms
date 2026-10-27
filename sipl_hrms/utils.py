import frappe

def parse_time_str(val, default="09:30"):
    """
    Parses various time representations (str, timedelta, datetime.time) into "HH:MM".
    """
    if not val:
        return default
    if isinstance(val, str):
        parts = val.strip().split(":")
        if len(parts) >= 2:
            try:
                h = int(parts[0])
                m = int(parts[1])
                return f"{h:02d}:{m:02d}"
            except ValueError:
                return default
        return default
    elif hasattr(val, "total_seconds"):
        total_seconds = int(val.total_seconds())
        h = (total_seconds // 3600) % 24
        m = (total_seconds % 3600) // 60
        return f"{h:02d}:{m:02d}"
    elif hasattr(val, "hour") and hasattr(val, "minute"):
        return f"{val.hour:02d}:{val.minute:02d}"
    return default

def add_minutes_to_time_str(time_str, minutes_to_add):
    """
    Adds given minutes to an "HH:MM" string, returning a new "HH:MM" string.
    """
    try:
        parts = time_str.split(":")
        h = int(parts[0])
        m = int(parts[1])
    except Exception:
        h, m = 9, 30
    total_mins = h * 60 + m + int(minutes_to_add)
    new_h = (total_mins // 60) % 24
    new_m = total_mins % 60
    return f"{new_h:02d}:{new_m:02d}"

def get_all_shift_details():
    """
    Returns a dict mapping shift_name -> dict with start_time, end_time, grace_cutoff, gp_max_cutoff.
    """
    shift_map = {}
    default_details = {
        "start_time": "09:30",
        "end_time": "18:30",
        "grace_cutoff": "10:00",
        "gp_max_cutoff": "11:30"
    }
    try:
        shifts = frappe.get_all("Shift Type", fields=["name", "start_time", "end_time"])
        for s in shifts:
            s_name = s.get("name") if isinstance(s, dict) else getattr(s, "name", None)
            if not s_name:
                continue
            st_raw = s.get("start_time") if isinstance(s, dict) else getattr(s, "start_time", None)
            et_raw = s.get("end_time") if isinstance(s, dict) else getattr(s, "end_time", None)

            st = parse_time_str(st_raw, default="09:30")
            et = parse_time_str(et_raw, default="18:30")
            shift_map[s_name] = {
                "start_time": st,
                "end_time": et,
                "grace_cutoff": add_minutes_to_time_str(st, 30),
                "gp_max_cutoff": add_minutes_to_time_str(st, 120)
            }
    except Exception as e:
        frappe.log_error(f"Error loading Shift Types: {e}", "Shift Details Loader")

    if "General" not in shift_map:
        shift_map["General"] = default_details
    return shift_map

def get_shift_details(shift_name=None):
    """
    Returns shift details for the specified shift_name or fallback to General shift.
    """
    shifts = get_all_shift_details()
    if shift_name and shift_name in shifts:
        return shifts[shift_name]
    return shifts.get("General") or {
        "start_time": "09:30",
        "end_time": "18:30",
        "grace_cutoff": "10:00",
        "gp_max_cutoff": "11:30"
    }
