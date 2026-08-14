// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

frappe.query_reports["Schedule of Offences"] = {
    filters: [],

    // The datatable's own row-number column is "serialNoColumn" - there's no
    // "showIndexColumn" property on the datamanager at all (the previous
    // onload code set one that doesn't exist, so the numbered column it was
    // trying to hide was never actually hidden). This is the real, documented
    // way to turn it off, applied when the datatable is first constructed
    // rather than mutated after the fact.
    //
    // cellHeight: the grid is virtualised with a single fixed row height for
    // every row (frappe-datatable has no working "dynamic row height" - the
    // option exists in its defaults but nothing in the library actually
    // reads it), so there's no way to size each row to its own content. 66px
    // is picked to comfortably fit ~3 wrapped lines, which covers the large
    // majority of this report's rows without wasting too much space on the
    // many short ones; a handful of the longest Notes will still clip - the
    // full text is still available on hover (the cell's title attribute).
    get_datatable_options(options) {
        return Object.assign(options, { serialNoColumn: false, cellHeight: 66 });
    },

    onload: function(report) {
        // Ensure report refreshes automatically on load
        report.refresh();

        // Same visual language as the "Schedule of Offences Standard" print
        // format: light-gray/red-accent category banners, and Notes
        // respecting embedded newlines instead of collapsing them.
        //
        // frappe.utils.add_custom_style() doesn't exist - this call always
        // threw, it was just masked until now by the datamanager crash above
        // throwing first. frappe.dom.set_style() is the real API.
        //
        // frappe.dom.set_style() injects a genuinely global <style> tag that
        // outlives this report (Frappe's SPA routing doesn't tear it down
        // when the user navigates to a different report), and every query
        // report shares the exact same "#page-query-report" container - so
        // there is no selector prefix that would actually scope a rule like
        // ".dt-cell__content" to just this report. Every class below
        // (schedule-*) is instead only ever emitted by this report's own
        // formatter() further down, so the rules can only ever match this
        // report's own cells no matter how long the <style> tag sticks
        // around or which other report gets viewed afterwards.
        frappe.dom.set_style(`
            .schedule-category-banner,
            .schedule-header-blank {
                position: absolute;
                inset: 0;
                display: flex;
                align-items: center;
                justify-content: center;
                background-color: #f0f0f0;
                border-bottom: 1px solid #b40000;
                font-weight: 700;
                text-align: center;
            }

            .schedule-cell-content {
                display: block;
                white-space: pre-line;
                overflow-wrap: break-word;
                line-height: 1.35;
            }
        `, "schedule-of-offences-style");
    },

    // Called by Frappe for every cell as it's rendered (including rows that
    // scroll into view later, unlike a one-off DOM pass after refresh) -
    // this is the actual, working replacement for the old `refresh` hook
    // below, which Frappe never calls at all (its `.header-row` selector
    // never matched anything either - this report's category rows were
    // never actually banner-styled on screen until now).
    formatter: function(value, row, column, data, default_formatter) {
        if (data.is_header) {
            if (column.fieldname === "offence_description") {
                return `<div class="schedule-category-banner">${value || ""}</div>`;
            }
            return `<div class="schedule-header-blank"></div>`;
        }

        // Every column (not just the description) gets wrapped the same way -
        // the base datatable CSS truncates with an ellipsis on a single line
        // by default, which is exactly what was cutting off "Final Written
        // Warning" etc. in the sanction columns too.
        const formatted = column.fieldname === "offence_description"
            ? (value || "")
            : default_formatter(value, row, column, data);
        return `<div class="schedule-cell-content">${formatted}</div>`;
    },
};
