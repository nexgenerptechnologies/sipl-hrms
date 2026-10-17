frappe.ui.form.on('Employee Gate Pass', {
    refresh: function(frm) {
        frm.trigger('toggle_return_fields');
        frm.trigger('set_status_alert');
    },
    gate_pass_type: function(frm) {
        frm.trigger('set_status_alert');
    },
    will_return: function(frm) {
        frm.trigger('toggle_return_fields');
        frm.trigger('calculate_hours');
        frm.trigger('set_status_alert');
    },
    departure_time: function(frm) {
        frm.trigger('calculate_hours');
    },
    expected_return_time: function(frm) {
        frm.trigger('calculate_hours');
    },
    actual_return_time: function(frm) {
        frm.trigger('calculate_hours');
    },
    toggle_return_fields: function(frm) {
        let is_returning = (frm.doc.will_return === 'Yes');
        frm.toggle_display(['expected_return_time', 'actual_return_time'], is_returning);
        frm.toggle_reqd('expected_return_time', is_returning);
    },
    calculate_hours: function(frm) {
        if (!frm.doc.departure_time) return;

        if (frm.doc.will_return === 'Yes') {
            let end = frm.doc.actual_return_time || frm.doc.expected_return_time;
            if (end) {
                let t1 = new Date('1970-01-01T' + frm.doc.departure_time);
                let t2 = new Date('1970-01-01T' + end);
                let diff = (t2 - t1) / (1000 * 60 * 60);
                if (diff > 0) {
                    frm.set_value('total_duration_hours', Math.round(diff * 100) / 100);
                }
            }
        } else {
            // Hours remaining until shift end (18:30)
            let t1 = new Date('1970-01-01T' + frm.doc.departure_time);
            let t2 = new Date('1970-01-01T18:30:00');
            let diff = (t2 - t1) / (1000 * 60 * 60);
            if (diff > 0) {
                frm.set_value('total_duration_hours', Math.round(diff * 100) / 100);
            }
        }
    },
    set_status_alert: function(frm) {
        frm.dashboard.clear_headline();
        if (frm.doc.gate_pass_type === 'Official Duty (OD)') {
            frm.dashboard.set_headline_alert(
                __('✅ Official Duty Gate Pass: Time spent on official company duty is counted as working hours and is exempt from personal gate pass limits.'),
                'green'
            );
        } else if (frm.doc.will_return === 'No (Direct to Home)') {
            frm.dashboard.set_headline_alert(
                __('⚠️ Personal Early Departure: Day will be adjusted to Half Day (if $\\ge 4$ hours worked before leaving) or Absent.'),
                'orange'
            );
        } else if (frm.doc.exceeds_policy) {
            frm.dashboard.set_headline_alert(
                __('⚠️ Exceeds monthly limit (Max 2 personal passes / 2 hrs each). Attendance will be adjusted against Half Day.'),
                'orange'
            );
        }
    }
});
