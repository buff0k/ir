// Copyright (c) 2025, BuFf0k and contributors
// For license information, please see license.txt

/* global frappe, cint */

const EE_CHILD = "Employment Equity Table";
const SECTOR_CHILD = "Employment Equity Sectoral Target Table";

const HTML_FIELD = "employment_equity_input";
const PREV_HTML_FIELD = "previous_employment_equity";
const SECTOR_HTML_FIELD = "employment_equity_sectoral_target";

// Matrix column mapping (short labels for the UI)
const GROUPS = [
  { key: "african_male",  label: "A", section: "Male"   },
  { key: "coloured_male", label: "C", section: "Male"   },
  { key: "indian_male",   label: "I", section: "Male"   },
  { key: "white_male",    label: "W", section: "Male"   },

  { key: "african_female",  label: "A", section: "Female" },
  { key: "coloured_female", label: "C", section: "Female" },
  { key: "indian_female",   label: "I", section: "Female" },
  { key: "white_female",    label: "W", section: "Female" },

  { key: "foreign_male",   label: "Male",   section: "Foreign" },
  { key: "foreign_female", label: "Female", section: "Foreign" },
];

const GROUP_FIELDS = GROUPS.map(g => g.key);

// Paterson sort: F (6) -> A (1)
const PATERSON_RANK = { "F": 6, "E": 5, "D": 4, "C": 3, "B": 2, "A": 1 };

/**
 * Ensure one row exists for every Occupational Level (sorted F->A).
 * - On new/empty docs, rebuild from scratch to avoid a blank starter row.
 * - On existing docs, only add missing levels (no reordering).
 */
async function ensure_rows_for_all_occupational_levels(frm, { force_rebuild = false } = {}) {
  if (force_rebuild) {
    frm.clear_table("employment_equity_table");
  } else {
    // Remove a single fully-blank starter row if present
    const grid = frm.get_field("employment_equity_table").grid;
    const rows = (frm.doc.employment_equity_table || []).slice();
    for (const r of rows) {
      const blank_level = !r.occupational_level;
      const all_zero = GROUP_FIELDS.every((f) => !cint(r[f]));
      if (blank_level && all_zero) {
        const grid_row = grid.grid_rows_by_docname[r.name];
        if (grid_row) grid_row.remove();
      }
    }
  }

  const levels = await frappe.db.get_list("Occupational Level", {
    fields: ["name", "paterson_band"],
    limit_page_length: 0,
  });

  // Sort F->A, then by name
  levels.sort((a, b) => {
    const rb = PATERSON_RANK[b.paterson_band] || 0;
    const ra = PATERSON_RANK[a.paterson_band] || 0;
    if (rb !== ra) return rb - ra;
    return (a.name || "").localeCompare(b.name || "");
  });

  const existing = new Set(
    (frm.doc.employment_equity_table || []).map((r) => r.occupational_level)
  );

  let added = 0;
  for (const lvl of levels) {
    if (!existing.has(lvl.name)) {
      const row = frm.add_child("employment_equity_table");
      row.occupational_level = lvl.name;
      GROUP_FIELDS.forEach((f) => (row[f] = 0));
      row.total = 0;
      added++;
    }
  }

  if (force_rebuild || added > 0) {
    frm.refresh_field("employment_equity_table");
  }
}

function sum_row_total(row) {
  let total = 0;
  GROUP_FIELDS.forEach((f) => (total += cint(row[f]) || 0));
  row.total = total;
}

/** Build & bind the HTML matrix UI (dark-mode friendly) for CURRENT targets */
function render_matrix(frm) {
  if (!frm.fields_dict[HTML_FIELD]) return;
  const $wrap = $(frm.fields_dict[HTML_FIELD].wrapper);
  const rows = (frm.doc.employment_equity_table || []).slice();

  // Recompute totals & column/grand totals from current doc
  const colTotals = {};
  GROUP_FIELDS.forEach((f) => (colTotals[f] = 0));
  let grandTotal = 0;

  rows.forEach((r) => {
    sum_row_total(r);
    GROUP_FIELDS.forEach((f) => (colTotals[f] += cint(r[f]) || 0));
    grandTotal += cint(r.total) || 0;
  });

  const html =
    `<style>
      .ee-sticky { position: sticky; top: 0; z-index: 1;
        background: var(--bg-color, var(--card-bg, #f7f7f7)); }
      .ee-occell { text-align: left; white-space: nowrap; }
      .ee-num { width: 64px; text-align: center; }
      .ee-total { font-weight: 600; }
      .ee-subhead { font-size: 11px; }
    </style>
    <table class="table table-bordered table-sm align-middle">
      <thead>
        <tr>
          <th class="ee-sticky" rowspan="2" style="min-width: 260px;">Occupational Levels</th>
          <th class="ee-sticky" colspan="4">Male</th>
          <th class="ee-sticky" colspan="4">Female</th>
          <th class="ee-sticky" colspan="2">Foreign Nationals</th>
          <th class="ee-sticky" rowspan="2">Total</th>
        </tr>
        <tr>
          <th class="ee-sticky ee-subhead">A</th><th class="ee-sticky ee-subhead">C</th>
          <th class="ee-sticky ee-subhead">I</th><th class="ee-sticky ee-subhead">W</th>
          <th class="ee-sticky ee-subhead">A</th><th class="ee-sticky ee-subhead">C</th>
          <th class="ee-sticky ee-subhead">I</th><th class="ee-sticky ee-subhead">W</th>
          <th class="ee-sticky ee-subhead">Male</th><th class="ee-sticky ee-subhead">Female</th>
        </tr>
      </thead>
      <tbody>
        ${rows
          .map((r) => {
            const cells = GROUP_FIELDS
              .map((f) => {
                const val = cint(r[f]) || 0;
                return `<td><input class="ee-cell ee-num"
                  type="number" min="0" step="1"
                  data-row="${frappe.utils.escape_html(r.name)}"
                  data-field="${f}" value="${val}"></td>`;
              })
              .join("");
            return `<tr data-row="${frappe.utils.escape_html(r.name)}">
              <td class="ee-occell">${frappe.utils.escape_html(r.occupational_level || "")}</td>
              ${cells}
              <td class="ee-total" data-total-for="${frappe.utils.escape_html(r.name)}">${cint(r.total) || 0}</td>
            </tr>`;
          })
          .join("")}
      </tbody>
      <tfoot>
        <tr class="fw-semibold">
          <td>GRAND TOTAL</td>
          ${GROUP_FIELDS.map((f) => `<td data-col-total="${f}">${colTotals[f]}</td>`).join("")}
          <td data-grand-total="1">${grandTotal}</td>
        </tr>
      </tfoot>
    </table>`;

  $wrap.empty().append(html);

  // Delegate input handling (mark doc dirty via model.set_value)
  $wrap.off("input.ee").on(
    "input.ee",
    "input.ee-cell",
    frappe.utils.debounce(async function () {
      const $inp = $(this);
      const docname = $inp.data("row");
      const field = $inp.data("field");
      let v = parseInt($inp.val(), 10);
      if (isNaN(v) || v < 0) v = 0;
      $inp.val(v); // normalize UI

      const row = (frm.doc.employment_equity_table || []).find((x) => x.name === docname);
      if (!row) return;

      // 1) set changed field via model API (fires triggers & marks dirty)
      await frappe.model.set_value(row.doctype, row.name, field, v);

      // 2) recompute total and set via model API
      const total = GROUP_FIELDS.reduce((acc, f) => acc + (cint(row[f]) || 0), 0);
      await frappe.model.set_value(row.doctype, row.name, "total", total);

      // 3) update row total in the HTML
      $wrap.find(`[data-total-for="${docname}"]`).text(total);

      // 4) recompute column & grand totals from frm.doc (already updated)
      const colSum = {};
      GROUP_FIELDS.forEach((f) => (colSum[f] = 0));
      let g = 0;
      (frm.doc.employment_equity_table || []).forEach((r) => {
        GROUP_FIELDS.forEach((f) => (colSum[f] += cint(r[f]) || 0));
        g += cint(r.total) || 0;
      });
      GROUP_FIELDS.forEach((f) =>
        $wrap.find(`[data-col-total="${f}"]`).text(colSum[f])
      );
      $wrap.find(`[data-grand-total="1"]`).text(g);

      // 5) silently refresh grid for visual sync (optional)
      frm.refresh_field("employment_equity_table");
    }, 120)
  );
}

/** Read-only matrix for the PREVIOUS target snapshot, aligned to current row order if possible */
function render_previous_matrix(frm) {
  if (!frm.fields_dict[PREV_HTML_FIELD]) return;
  const $wrap = $(frm.fields_dict[PREV_HTML_FIELD].wrapper);

  const prev_rows = (frm.doc.previous_target_table || []).slice();
  if (!frm.doc.previous_target || prev_rows.length === 0) {
    $wrap.html(
      `<div class="text-muted small">Select a <strong>Previous Target</strong> to view its snapshot here.</div>`
    );
    return;
  }

  // Align display order with current table rows where possible
  const order_index = {};
  (frm.doc.employment_equity_table || []).forEach((r, idx) => {
    if (r.occupational_level) order_index[r.occupational_level] = idx;
  });
  prev_rows.sort((a, b) => {
    const ia = order_index[a.occupational_level] ?? Number.MAX_SAFE_INTEGER;
    const ib = order_index[b.occupational_level] ?? Number.MAX_SAFE_INTEGER;
    if (ia !== ib) return ia - ib;
    return (a.occupational_level || "").localeCompare(b.occupational_level || "");
  });

  // Column + grand totals
  const colTotals = {};
  GROUP_FIELDS.forEach((f) => (colTotals[f] = 0));
  let grandTotal = 0;

  prev_rows.forEach((r) => {
    const row_total = GROUP_FIELDS.reduce((acc, f) => acc + (cint(r[f]) || 0), 0);
    r._display_total = cint(r.total) || row_total;
    GROUP_FIELDS.forEach((f) => (colTotals[f] += cint(r[f]) || 0));
    grandTotal += r._display_total;
  });

  const html =
    `<style>
      .ee-sticky { position: sticky; top: 0; z-index: 1;
        background: var(--bg-color, var(--card-bg, #f7f7f7)); }
      .ee-occell { text-align: left; white-space: nowrap; }
      .ee-total { font-weight: 600; }
      .ee-subhead { font-size: 11px; }
    </style>
    <table class="table table-bordered table-sm align-middle">
      <thead>
        <tr>
          <th class="ee-sticky" rowspan="2" style="min-width: 260px;">Previous Occupational Levels</th>
          <th class="ee-sticky" colspan="4">Male</th>
          <th class="ee-sticky" colspan="4">Female</th>
          <th class="ee-sticky" colspan="2">Foreign Nationals</th>
          <th class="ee-sticky" rowspan="2">Total</th>
        </tr>
        <tr>
          <th class="ee-sticky ee-subhead">A</th><th class="ee-sticky ee-subhead">C</th>
          <th class="ee-sticky ee-subhead">I</th><th class="ee-sticky ee-subhead">W</th>
          <th class="ee-sticky ee-subhead">A</th><th class="ee-sticky ee-subhead">C</th>
          <th class="ee-sticky ee-subhead">I</th><th class="ee-sticky ee-subhead">W</th>
          <th class="ee-sticky ee-subhead">Male</th><th class="ee-sticky ee-subhead">Female</th>
        </tr>
      </thead>
      <tbody>
        ${prev_rows
          .map((r) => {
            const cells = GROUP_FIELDS
              .map((f) => `<td>${cint(r[f]) || 0}</td>`)
              .join("");
            return `<tr>
              <td class="ee-occell">${frappe.utils.escape_html(r.occupational_level || "")}</td>
              ${cells}
              <td class="ee-total">${r._display_total}</td>
            </tr>`;
          })
          .join("")}
      </tbody>
      <tfoot>
        <tr class="fw-semibold">
          <td>GRAND TOTAL</td>
          ${GROUP_FIELDS.map((f) => `<td>${colTotals[f]}</td>`).join("")}
          <td>${grandTotal}</td>
        </tr>
      </tfoot>
    </table>`;

  $wrap.empty().append(html);
}

/* -------------------- Sectoral Targets (read-only HTML) -------------------- */

const SECTOR_FIELD_MAP = [
  "top_management_male",
  "top_management_female",
  "top_management_total",
  "senior_management_male",
  "senior_management_female",
  "senior_management_total",
  "mid_management_male",
  "mid_management_female",
  "mid_management_total",
  "skilled_male",
  "skilled_female",
  "skilled_total",
  "disability_only",
];

/** Format float as percentage with one decimal place (e.g., 27.6 => "27.6%"). */
function pct(v) {
  if (v === undefined || v === null || isNaN(v)) return "0%";
  const n = parseFloat(v);
  return `${n.toFixed(1)}%`;
}

/** Load the selected Sectoral Target into the child table (1:1 mapping) */
async function load_sectoral_target_into_table(frm) {
  frm.clear_table("sectoral_target_table");

  const sel = frm.doc.sectoral_target;
  if (!sel) {
    frm.refresh_field("sectoral_target_table");
    render_sectoral_matrix(frm);
    return;
  }

  try {
    const doc = await frappe.db.get_doc("Employment Equity Sectoral Targets", sel);

    // Create a single row with mapped fields
    const row = frm.add_child("sectoral_target_table");
    SECTOR_FIELD_MAP.forEach((f) => (row[f] = doc[f] || 0.0));

    frm.refresh_field("sectoral_target_table");
    render_sectoral_matrix(frm);
    frappe.show_alert({ message: "Sectoral targets loaded.", indicator: "green" });
  } catch (e) {
    console.error(e);
    frappe.msgprint({
      title: "Unable to load sectoral target",
      message: "Could not fetch the selected Sectoral Target’s values.",
      indicator: "red",
    });
  }
}

/** Render read-only HTML view of the sectoral target (from the child table) */
function render_sectoral_matrix(frm) {
  if (!frm.fields_dict[SECTOR_HTML_FIELD]) return;
  const $wrap = $(frm.fields_dict[SECTOR_HTML_FIELD].wrapper);

  const row = (frm.doc.sectoral_target_table || [])[0];
  if (!frm.doc.sectoral_target || !row) {
    $wrap.html(
      `<div class="text-muted small">Select a <strong>Sectoral Target</strong> to view prescribed percentages here.</div>`
    );
    return;
  }

  // NOTE: exactly THREE columns => DESCRIPTION | GENDER | DESIGNATED GROUPS (value).
  const html =
    `<style>
      .ee-sticky { position: sticky; top: 0; z-index: 1;
        background: var(--bg-color, var(--card-bg, #f7f7f7)); }
      .ee-occell { text-align: left; white-space: nowrap; }
      .ee-subhead { font-size: 11px; }
      .ee-right { text-align: right; }
      .ee-w { width: 120px; }
      .ee-descw { min-width: 320px; }
    </style>
    <table class="table table-bordered table-sm align-middle">
      <thead>
        <tr>
          <th class="ee-sticky ee-descw">DESCRIPTION</th>
          <th class="ee-sticky">GENDER</th>
          <th class="ee-sticky">DESIGNATED GROUPS</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td class="ee-occell" rowspan="3">Top management</td>
          <td class="ee-occell">Male</td>
          <td class="ee-right ee-w">${pct(row.top_management_male)}</td>
        </tr>
        <tr>
          <td class="ee-occell">Female</td>
          <td class="ee-right ee-w">${pct(row.top_management_female)}</td>
        </tr>
        <tr class="fw-semibold">
          <td class="ee-occell">Total</td>
          <td class="ee-right ee-w">${pct(row.top_management_total)}</td>
        </tr>

        <tr>
          <td class="ee-occell" rowspan="3">Senior Management</td>
          <td class="ee-occell">Male</td>
          <td class="ee-right ee-w">${pct(row.senior_management_male)}</td>
        </tr>
        <tr>
          <td class="ee-occell">Female</td>
          <td class="ee-right ee-w">${pct(row.senior_management_female)}</td>
        </tr>
        <tr class="fw-semibold">
          <td class="ee-occell">Total</td>
          <td class="ee-right ee-w">${pct(row.senior_management_total)}</td>
        </tr>

        <tr>
          <td class="ee-occell" rowspan="3">Professionally Qualified &amp; Middle Management</td>
          <td class="ee-occell">Male</td>
          <td class="ee-right ee-w">${pct(row.mid_management_male)}</td>
        </tr>
        <tr>
          <td class="ee-occell">Female</td>
          <td class="ee-right ee-w">${pct(row.mid_management_female)}</td>
        </tr>
        <tr class="fw-semibold">
          <td class="ee-occell">Total</td>
          <td class="ee-right ee-w">${pct(row.mid_management_total)}</td>
        </tr>

        <tr>
          <td class="ee-occell" rowspan="3">Skilled Technical</td>
          <td class="ee-occell">Male</td>
          <td class="ee-right ee-w">${pct(row.skilled_male)}</td>
        </tr>
        <tr>
          <td class="ee-occell">Female</td>
          <td class="ee-right ee-w">${pct(row.skilled_female)}</td>
        </tr>
        <tr class="fw-semibold">
          <td class="ee-occell">Total</td>
          <td class="ee-right ee-w">${pct(row.skilled_total)}</td>
        </tr>

        <tr class="fw-semibold">
          <td class="ee-occell">Disability only</td>
          <td class="ee-occell">All</td>
          <td class="ee-right ee-w">${pct(row.disability_only)}</td>
        </tr>
      </tbody>
    </table>`;

  $wrap.empty().append(html);
}

/* -------------------- Loaders -------------------- */

async function load_previous_target_into_readonly_table(frm) {
  frm.clear_table("previous_target_table");
  const prev = frm.doc.previous_target;
  if (!prev) {
    frm.refresh_field("previous_target_table");
    return;
  }
  try {
    const prev_doc = await frappe.db.get_doc("Employment Equity Target", prev);
    const rows = (prev_doc.employment_equity_table || []).map((r) => ({
      occupational_level: r.occupational_level,
      african_male: r.african_male,
      coloured_male: r.coloured_male,
      indian_male: r.indian_male,
      white_male: r.white_male,
      african_female: r.african_female,
      coloured_female: r.coloured_female,
      indian_female: r.indian_female,
      white_female: r.white_female,
      foreign_male: r.foreign_male,
      foreign_female: r.foreign_female,
      total: r.total,
    }));
    rows.forEach((r) => {
      const child = frm.add_child("previous_target_table");
      Object.assign(child, r);
    });
    frm.refresh_field("previous_target_table");
    frappe.show_alert({ message: "Previous target loaded.", indicator: "green" });
  } catch (e) {
    console.error(e);
    frappe.msgprint({
      title: "Unable to load previous target",
      message: "Could not fetch the selected Employment Equity Target’s rows.",
      indicator: "red",
    });
  }
}

/* -------------------- Form Handlers -------------------- */

frappe.ui.form.on("Employment Equity Target", {
  onload: async function (frm) {
    if (frm.doc.previous_target) {
      await load_previous_target_into_readonly_table(frm);
    }
    if (frm.is_new() || !(frm.doc.employment_equity_table || []).length) {
      await ensure_rows_for_all_occupational_levels(frm, { force_rebuild: true });
    }
    // If a sectoral target is set and the table is empty, load it
    if (frm.doc.sectoral_target && !(frm.doc.sectoral_target_table || []).length) {
      await load_sectoral_target_into_table(frm);
    }

    render_matrix(frm);
    render_previous_matrix(frm);
    render_sectoral_matrix(frm);
  },

  refresh: function (frm) {
    // server placeholder button (path per your app)
    frm.add_custom_button("Compute Suggested Targets", () => {
      frappe.call({
        method:
          "ir.industrial_relations.doctype.employment_equity_target.employment_equity_target.compute_suggested_targets",
        freeze: true,
        freeze_message: "Crunching numbers...",
        args: { docname: frm.doc.name },
        callback: (r) => {
          if (r && r.message) frappe.msgprint(r.message);
          else frappe.show_alert("Done.", 5);
        },
        error: () => {
          frappe.msgprint({
            title: "Error",
            message: "The placeholder method failed. Check server logs.",
            indicator: "red",
          });
        },
      });
    });

    // Re-render so all HTML views stay in sync with any changes
    render_matrix(frm);
    render_previous_matrix(frm);
    render_sectoral_matrix(frm);
  },

  previous_target: async function (frm) {
    await load_previous_target_into_readonly_table(frm);
    render_matrix(frm);
    render_previous_matrix(frm);
  },

  // when sectoral_target link changes
  sectoral_target: async function (frm) {
    await load_sectoral_target_into_table(frm);
  },
});

// Keep totals correct if someone edits via the original grid
frappe.ui.form.on(EE_CHILD, {
  form_render(frm, cdt, cdn) {
    const row = frappe.get_doc(cdt, cdn);
    sum_row_total(row);
    frm.refresh_field("employment_equity_table");
    render_matrix(frm);
    render_previous_matrix(frm);
  },

  african_male:   function(frm){ frm.refresh_field("employment_equity_table"); render_matrix(frm); render_previous_matrix(frm); },
  coloured_male:  function(frm){ frm.refresh_field("employment_equity_table"); render_matrix(frm); render_previous_matrix(frm); },
  indian_male:    function(frm){ frm.refresh_field("employment_equity_table"); render_matrix(frm); render_previous_matrix(frm); },
  white_male:     function(frm){ frm.refresh_field("employment_equity_table"); render_matrix(frm); render_previous_matrix(frm); },
  african_female: function(frm){ frm.refresh_field("employment_equity_table"); render_matrix(frm); render_previous_matrix(frm); },
  coloured_female:function(frm){ frm.refresh_field("employment_equity_table"); render_matrix(frm); render_previous_matrix(frm); },
  indian_female:  function(frm){ frm.refresh_field("employment_equity_table"); render_matrix(frm); render_previous_matrix(frm); },
  white_female:   function(frm){ frm.refresh_field("employment_equity_table"); render_matrix(frm); render_previous_matrix(frm); },
  foreign_male:   function(frm){ frm.refresh_field("employment_equity_table"); render_matrix(frm); render_previous_matrix(frm); },
  foreign_female: function(frm){ frm.refresh_field("employment_equity_table"); render_matrix(frm); render_previous_matrix(frm); },
});

// If sectoral child table fields get edited (unlikely), re-render
frappe.ui.form.on(SECTOR_CHILD, {
  top_management_male:   function(frm){ frm.refresh_field("sectoral_target_table"); render_sectoral_matrix(frm); },
  top_management_female: function(frm){ frm.refresh_field("sectoral_target_table"); render_sectoral_matrix(frm); },
  top_management_total:  function(frm){ frm.refresh_field("sectoral_target_table"); render_sectoral_matrix(frm); },
  senior_management_male:   function(frm){ frm.refresh_field("sectoral_target_table"); render_sectoral_matrix(frm); },
  senior_management_female: function(frm){ frm.refresh_field("sectoral_target_table"); render_sectoral_matrix(frm); },
  senior_management_total:  function(frm){ frm.refresh_field("sectoral_target_table"); render_sectoral_matrix(frm); },
  mid_management_male:   function(frm){ frm.refresh_field("sectoral_target_table"); render_sectoral_matrix(frm); },
  mid_management_female: function(frm){ frm.refresh_field("sectoral_target_table"); render_sectoral_matrix(frm); },
  mid_management_total:  function(frm){ frm.refresh_field("sectoral_target_table"); render_sectoral_matrix(frm); },
  skilled_male:   function(frm){ frm.refresh_field("sectoral_target_table"); render_sectoral_matrix(frm); },
  skilled_female: function(frm){ frm.refresh_field("sectoral_target_table"); render_sectoral_matrix(frm); },
  skilled_total:  function(frm){ frm.refresh_field("sectoral_target_table"); render_sectoral_matrix(frm); },
  disability_only:function(frm){ frm.refresh_field("sectoral_target_table"); render_sectoral_matrix(frm); },
});
