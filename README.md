# SIPL HRMS

Custom HRMS Extension for Simple Integral Private Limited (SIPL) on Frappe / ERPNext.

### Features
1. **Gate Pass Management:** Tracks max 2 gate passes per month (up to 2 hrs each). Exceeding instances auto-adjusted to Half Day.
2. **Tiered Overtime (OT) Calculation:** OT starts only after 10 hours of working time. 10 hours = 0 OT, 11 hours = 2 hours OT. Configurable per employee.
3. **Compensatory Off (C-Off / CPL):** Separate tracking for Sunday/Holiday CPL and Late-Stay C-Off. Automatically accumulates 8 hours of eligible late-stay to grant 1 day of C-Off.
4. **Late Coming Policy:** Max 2 instances of late arrival up to 30 mins free per month; 3rd instance adjusted against Gate Pass or Half Day.
5. **Attendance Performance Summary Report (Image 2):** Matrix report showing In, Out, Status, Total Hours, and OT Hours day-by-day.
6. **SIPL Monthly Attendance Register (Image 3):** Excel-style monthly attendance matrix with exact company legend codes (P, A, W/O, H, CL, SL, EL, CO, C, S, E, O) and summary totals (Total Present, WO, H, CL, SL, EL, C/OFF, G Total).

### Installation on Site
```bash
cd /home/frappe/frappe-bench  # (or your bench directory on Hostinger VPS)
bench get-app https://github.com/nexgenerptechnologies/sipl-hrms.git
bench --site erp.simpleintegral.in install-app sipl_hrms
bench --site erp.simpleintegral.in migrate
bench restart
```
