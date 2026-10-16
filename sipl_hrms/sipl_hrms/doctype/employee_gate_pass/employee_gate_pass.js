frappe.ui.form.on('Employee Gate Pass', {
    refresh: function(frm) {
        if (frm.doc.exceeds_policy) {
            frm.dashboard.set_headline_alert(
                __('⚠️ This gate pass exceeds the monthly limit (Max 2 passes / 2 hrs each) and will be adjusted against a Half Day leave.'),
                'orange'
            );
        }
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
    calculate_hours: function(frm) {
        let end = frm.doc.actual_return_time || frm.doc.expected_return_time;
        if (frm.doc.departure_time && end) {
            let t1 = new Date('1970-01-01T' + frm.doc.departure_time);
            let t2 = new Date('1970-01-01T' + end);
            let diff = (t2 - t1) / (1000 * 60 * 60);
            if (diff > 0) {
                frm.set_value('total_duration_hours', Math.round(diff * 100) / 100);
            }
        }
    }
});
