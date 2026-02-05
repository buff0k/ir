// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

const PY = "ir.industrial_relations.doctype.site_organogram.site_organogram";



// --------------------------
// Promise-safe Select Dialog (replacement for frappe.prompt)
// --------------------------
function so_select_dialog({ title, label, options = [], default_value = null, primary_label = "Clone" }) {
  return new Promise((resolve) => {
    let resolved = false;
    const opts = (options || []).filter(Boolean);

    const d = new frappe.ui.Dialog({
      title: title || "Select",
      fields: [
        {
          fieldname: "choice",
          fieldtype: "Select",
          label: label || "Choose",
          options: opts.join("\n"),
          reqd: 1,
          default: default_value || (opts[0] || ""),
        },
      ],
      primary_action_label: primary_label,
      primary_action(values) {
        resolved = true;
        d.hide();
        resolve(values || {});
      },
    });

    d.onhide = () => {
      if (!resolved) resolve(null);
    };

    d.show();
  });
}

// --------------------------
// localStorage sets for auto-managed rows (employees/assets tables)
// --------------------------
function key(frm, suffix) {
  return `site_organogram:${frm.doc.doctype}:${frm.doc.name}:${suffix}`;
}

function loadSet(frm, suffix) {
  try {
    const raw = localStorage.getItem(key(frm, suffix));
    const arr = raw ? JSON.parse(raw) : [];
    return new Set(Array.isArray(arr) ? arr : []);
  } catch {
    return new Set();
  }
}

function saveSet(frm, suffix, setObj) {
  try {
    localStorage.setItem(key(frm, suffix), JSON.stringify([...setObj]));
  } catch {}
}

function ensureAuto(frm) {
  if (!frm._auto) {
    frm._auto = {
      employees: loadSet(frm, "auto_employees"),
      assets: loadSet(frm, "auto_assets"),
    };
  }
}

function persistAuto(frm) {
  saveSet(frm, "auto_employees", frm._auto.employees);
  saveSet(frm, "auto_assets", frm._auto.assets);
}

// --------------------------
// debounce helper
// --------------------------
function debounce(fn, wait = 250) {
  let t = null;
  return function (...args) {
    clearTimeout(t);
    t = setTimeout(() => fn.apply(this, args), wait);
  };
}

// --------------------------
// Asset category live-read + polling (stable Table MultiSelect behaviour)
// --------------------------
function get_asset_category_rows_live(frm) {
  const grid = frm.fields_dict.asset_categories && frm.fields_dict.asset_categories.grid;
  if (grid && typeof grid.get_data === "function") {
    return grid.get_data() || [];
  }
  return frm.doc.asset_categories || [];
}

function get_selected_asset_categories(frm) {
  const rows = get_asset_category_rows_live(frm);
  const cats = rows.map((r) => r.asset_cateogories).filter(Boolean);
  return [...new Set(cats)];
}

function categories_signature(frm) {
  return JSON.stringify(get_selected_asset_categories(frm).slice().sort());
}

const maybe_sync_assets_after_categories_change = debounce(async (frm) => {
  ensureAuto(frm);

  const sig = categories_signature(frm);
  if (frm._asset_cat_sig === undefined) {
    frm._asset_cat_sig = sig;
    return;
  }
  if (sig !== frm._asset_cat_sig) {
    frm._asset_cat_sig = sig;

    await sync_assets(frm);
    persistAuto(frm);

    await ensure_row_keys_migrated(frm);
    prune_mappings_against_current(frm);
    frm.refresh_field("shift_mappings");

    render_site_organogram(frm);
  }
}, 200);

function start_category_poll(frm) {
  if (frm._asset_cat_poll) return;
  frm._asset_cat_poll = setInterval(() => {
    if (!frm.doc || !frm.doc.location) return;
    maybe_sync_assets_after_categories_change(frm);
  }, 500);
}

function stop_category_poll(frm) {
  if (frm._asset_cat_poll) {
    clearInterval(frm._asset_cat_poll);
    frm._asset_cat_poll = null;
  }
}

// --------------------------
// Designations (GLOBAL) - not branch filtered
// --------------------------
async function ensure_designations_loaded(frm) {
  frm._so = frm._so || {};
  if (Array.isArray(frm._so.all_designations) && frm._so.all_designations.length) return;

  try {
    const res = await frappe.db.get_list("Designation", {
      fields: ["name"],
      limit: 0,
      order_by: "name asc",
    });
    frm._so.all_designations = (res || []).map((r) => r.name).filter(Boolean);
  } catch {
    frm._so.all_designations = [];
  }
}

// --------------------------
// Row Key helpers
// --------------------------
function row_key_asset(asset) {
  return `ASSET::${asset}`;
}

function row_key_desig(desig) {
  return `DESIG::${desig}`;
}

function parse_row_key(rk) {
  if (!rk) return { kind: "unknown" };
  if (rk.startsWith("ASSET::")) return { kind: "asset", asset: rk.slice("ASSET::".length) };
  if (rk.startsWith("DESIG::")) return { kind: "desig", desig: rk.slice("DESIG::".length) };
  return { kind: "unknown" };
}

// Backfill row_key if missing (older docs)
async function ensure_row_keys_migrated(frm) {
  const rows = frm.doc.shift_mappings || [];
  let changed = false;

  for (const r of rows) {
    if (!r.row_key) {
      const rk = r.asset ? row_key_asset(r.asset) : row_key_desig("Unlinked Role");
      frappe.model.set_value(r.doctype, r.name, "row_key", rk);
      changed = true;
    }
  }

  if (changed) {
    frm.refresh_field("shift_mappings");
  }
}

// --------------------------
// Focus retention for pool search
// --------------------------
function capture_pool_focus_state(frm, inputEl) {
  frm._so = frm._so || {};
  frm._so._focus = {
    caretStart: inputEl?.selectionStart ?? null,
    caretEnd: inputEl?.selectionEnd ?? null,
    shouldRestore: true,
  };
}

function restore_pool_focus_state(frm, $wrapper) {
  const st = frm._so && frm._so._focus;
  if (!st || !st.shouldRestore) return;

  const $input = $wrapper.find('[data-so="pool-search"]');
  if (!$input.length) return;

  const el = $input.get(0);
  el.focus();
  try {
    if (typeof st.caretStart === "number" && typeof st.caretEnd === "number") {
      el.setSelectionRange(st.caretStart, st.caretEnd);
    }
  } catch {}

  st.shouldRestore = false;
}

// --------------------------
// Form handlers
// --------------------------
frappe.ui.form.on("Site Organogram", {
  onload(frm) {
    ensureAuto(frm);
    frm._so = frm._so || { pool_mode: "employees", q: "", des: "", _clone_asked: false };
  },

  async refresh(frm) {
    ensureAuto(frm);
    start_category_poll(frm);

    frm._so = frm._so || { pool_mode: "employees", q: "", des: "", _clone_asked: false };

    await ensure_designations_loaded(frm);
    await ensure_row_keys_migrated(frm);

    render_site_organogram(frm);
    maybe_sync_assets_after_categories_change(frm);
  },

  onhide(frm) {
    stop_category_poll(frm);
  },

  async branch(frm) {
    if (frm._so_suppress) return;

    ensureAuto(frm);
    frm._so = frm._so || { pool_mode: "employees", q: "", des: "", _clone_asked: false };

    // Offer clone FIRST on new docs; if user clones we stop here.
    const cloned = await maybe_offer_clone_previous(frm);
    if (cloned) {
      frm._asset_cat_sig = categories_signature(frm);
      persistAuto(frm);
      return;
    }

    // Normal flow
    await sync_employees(frm);
    await set_location_from_branch_if_exists(frm);
    await sync_assets(frm);

    persistAuto(frm);
    frm._asset_cat_sig = categories_signature(frm);

    await ensure_designations_loaded(frm);
    await ensure_row_keys_migrated(frm);

    prune_mappings_against_current(frm);
    frm.refresh_field("shift_mappings");

    render_site_organogram(frm);
  },

  async location(frm) {
    if (frm._so_suppress) return;

    ensureAuto(frm);

    await sync_assets(frm);
    persistAuto(frm);
    frm._asset_cat_sig = categories_signature(frm);

    await ensure_designations_loaded(frm);
    await ensure_row_keys_migrated(frm);

    prune_mappings_against_current(frm);
    frm.refresh_field("shift_mappings");

    render_site_organogram(frm);
  },

  shifts(frm) {
    if (frm._so_suppress) return;

    render_site_organogram(frm);
  },

  group_headings(frm) {
    if (frm._so_suppress) return;

    render_site_organogram(frm);
  },
});

frappe.ui.form.on("Site Organogram Asset Categories", {
  asset_cateogories(frm) {
    maybe_sync_assets_after_categories_change(frm);
  },
  after_delete(frm) {
    maybe_sync_assets_after_categories_change(frm);
  },
});

frappe.ui.form.on("Site Organogram Employees", {
  employee(frm, cdt, cdn) {
    ensureAuto(frm);
    const row = locals[cdt][cdn];
    if (!row.employee) return;

    // mark as manual
    frm._auto.employees.delete(row.employee);
    persistAuto(frm);

    frm.call({
      method: `${PY}.get_employee_details`,
      args: { employee: row.employee },
    }).then((r) => {
      const d = r.message || {};
      frappe.model.set_value(cdt, cdn, "employee_name", d.employee_name || "");
      frappe.model.set_value(cdt, cdn, "designation", d.designation || "");
      render_site_organogram(frm);
    });
  },
});

frappe.ui.form.on("Site Organogram Assets", {
  asset(frm, cdt, cdn) {
    ensureAuto(frm);
    const row = locals[cdt][cdn];
    if (!row.asset) return;

    // mark as manual
    frm._auto.assets.delete(row.asset);
    persistAuto(frm);

    frm.call({
      method: `${PY}.get_asset_details`,
      args: { asset: row.asset },
    }).then((r) => {
      const d = r.message || {};
      frappe.model.set_value(cdt, cdn, "asset_name", d.asset_name || "");
      frappe.model.set_value(cdt, cdn, "asset_category", d.asset_category || "");
      render_site_organogram(frm);
    });
  },
});

// --------------------------
// branch -> location helper
// --------------------------
async function set_location_from_branch_if_exists(frm) {
  if (!frm.doc.branch) return;

  const r = await frm.call({
    method: `${PY}.get_matching_location_for_branch`,
    args: { branch: frm.doc.branch },
  });

  const loc = r.message || "";
  if ((frm.doc.location || "") !== loc) {
    await frm.set_value("location", loc);
  }
}

// --------------------------
// Clone previous organogram (last 5 picker) - PROMPT GUARANTEED
// --------------------------
async function maybe_offer_clone_previous(frm) {
  // Only offer cloning on NEW docs when Branch is set
  if (!frm.is_new() || !frm.doc.branch) return false;

  frm._so = frm._so || { pool_mode: "employees", q: "", des: "", _clone_asked: false };

  // Ask only once per new doc (prevents spam)
  if (frm._so._clone_asked) return false;
  frm._so._clone_asked = true;

  // If user already started mapping, do not prompt
  const hasMeaningfulMappings = (frm.doc.shift_mappings || []).some((r) => {
    return (
      (r.employee && String(r.employee).trim()) ||
      (r.asset && String(r.asset).trim()) ||
      (r.row_key && String(r.row_key).trim())
    );
  });
  if (hasMeaningfulMappings) return false;

  const resp = await frm.call({
    method: `${PY}.list_recent_site_organograms_for_branch`,
    args: { branch: frm.doc.branch, exclude_name: frm.doc.name, limit: 5 },
  });

  const rows = resp.message || [];
  if (!rows.length) return false;

  // ✅ Explicit Yes/No (your "No" should continue normal branch logic)
  const use_previous = await new Promise((resolve) => {
    frappe.confirm(
      `A previous Site Organogram exists for Branch "${frm.doc.branch}".\n\nDo you want to clone one as a starting point?`,
      () => resolve(true),
      () => resolve(false),
      "Clone Previous Organogram"
    );
  });

  if (!use_previous) return false;

  // Show "name — modified" but store actual name
  const labels = rows.map((r) => {
    const dt = r.modified ? frappe.datetime.str_to_user(r.modified) : "";
    return dt ? `${r.name}  —  ${dt}` : r.name;
  });

  const labelToName = new Map(labels.map((label, i) => [label, rows[i].name]));

  // Pick which one to clone
    // Pick which one to clone
  const d = await so_select_dialog({
    title: "Select Organogram to Clone",
    label: "Previous Organogram",
    options: labels,
    default_value: labels[0],
    primary_label: "Clone",
  });



  // Cancel / close => treat as "No clone" and continue normal flow
  if (!d || !d.choice) return false;

  const source = labelToName.get(d.choice);
  if (!source) return false;

  const tpl = await frm.call({
    method: `${PY}.get_site_organogram_template`,
    args: { source_name: source },
  });

  await apply_template_to_form(frm, tpl.message || {});
  return true;
}
async function apply_template_to_form(frm, tpl) {
  // Prevent branch/location/shifts handlers from racing while we apply the template
  frm._so_suppress = true;
  try {
    // Scalars
    if (tpl.shifts != null) {
      await frm.set_value("shifts", tpl.shifts);
    }
    if (tpl.location) {
      await frm.set_value("location", tpl.location);
    }

    // group_headings
    frm.clear_table("group_headings");
    (tpl.group_headings || []).forEach((r) => {
      const row = frm.add_child("group_headings");
      row.group = r.group || "";
      row.shifts = r.shifts || "";
    });

    // asset_categories
    frm.clear_table("asset_categories");
    (tpl.asset_categories || []).forEach((r) => {
      const row = frm.add_child("asset_categories");
      row.asset_cateogories = r.asset_cateogories || "";
    });

    // shift_mappings
    frm.clear_table("shift_mappings");
    (tpl.shift_mappings || []).forEach((r) => {
      const row = frm.add_child("shift_mappings");
      row.group = r.group || "";
      row.shift = r.shift || "";
      row.asset = r.asset || "";
      row.employee = r.employee || "";
      row.row_key = r.row_key || (r.asset ? row_key_asset(r.asset) : "");
    });

    frm.refresh_fields(["group_headings", "asset_categories", "shift_mappings"]);

    // Reconcile with current site reality (employees/assets may have changed)
    await sync_employees(frm);
    await sync_assets(frm);
    await ensure_row_keys_migrated(frm);

    prune_mappings_against_current(frm);
    frm.refresh_field("shift_mappings");

    // Align signature so the category poller doesn't immediately re-sync unexpectedly
    frm._asset_cat_sig = categories_signature(frm);

    render_site_organogram(frm);
  } finally {
    frm._so_suppress = false;
  }
}

// Remove mappings pointing to employees/assets that no longer exist on this site,
// but keep designation rows and any valid mappings.
function prune_mappings_against_current(frm) {
  const empSet = new Set((frm.doc.employees || []).map((r) => r.employee).filter(Boolean));
  const assetSet = new Set((frm.doc.assets || []).map((r) => r.asset).filter(Boolean));

  const rows = (frm.doc.shift_mappings || []).slice();

  for (const r of rows) {
    // Employee no longer valid
    if (r.employee && !empSet.has(r.employee)) {
      frappe.model.clear_doc(r.doctype, r.name);
      continue;
    }

    // Asset rows removed if asset not available anymore
    if ((r.row_key || "").startsWith("ASSET::")) {
      const a = r.asset || String(r.row_key || "").slice("ASSET::".length);
      if (a && !assetSet.has(a)) {
        frappe.model.clear_doc(r.doctype, r.name);
      }
    }
  }
}

// --------------------------
// sync employees/assets
// --------------------------
async function sync_employees(frm) {
  if (!frm.doc.branch) return;

  const current = (frm.doc.employees || []).map((r) => r.employee).filter(Boolean);
  const auto = [...frm._auto.employees];

  const r = await frm.call({
    method: `${PY}.sync_employees`,
    args: {
      branch: frm.doc.branch,
      current_employees: JSON.stringify(current),
      auto_employees: JSON.stringify(auto),
    },
  });

  const plan = r.message || { to_add: [], to_remove: [] };

  for (const emp_id of plan.to_remove || []) {
    const rows = (frm.doc.employees || []).filter((x) => x.employee === emp_id);
    rows.forEach((row) => frappe.model.clear_doc(row.doctype, row.name));
    frm._auto.employees.delete(emp_id);
  }

  for (const row of plan.to_add || []) {
    const child = frm.add_child("employees");
    child.employee = row.employee;
    child.employee_name = row.employee_name || "";
    child.designation = row.designation || "";
    frm._auto.employees.add(row.employee);
  }

  frm.refresh_field("employees");
}

async function sync_assets(frm) {
  if (!frm.doc.location) return;

  const categories = get_selected_asset_categories(frm);
  const current = (frm.doc.assets || []).map((r) => r.asset).filter(Boolean);
  const auto = [...frm._auto.assets];

  const r = await frm.call({
    method: `${PY}.sync_assets`,
    args: {
      location: frm.doc.location,
      asset_categories: JSON.stringify(categories),
      current_assets: JSON.stringify(current),
      auto_assets: JSON.stringify(auto),
    },
  });

  const plan = r.message || { to_add: [], to_remove: [] };

  for (const asset_id of plan.to_remove || []) {
    const rows = (frm.doc.assets || []).filter((x) => x.asset === asset_id);
    rows.forEach((row) => frappe.model.clear_doc(row.doctype, row.name));
    frm._auto.assets.delete(asset_id);

    remove_asset_from_all_group_orders(frm, asset_id);
    remove_mapping_rows(frm, (m) => (m.row_key || "") === row_key_asset(asset_id));
  }

  for (const row of plan.to_add || []) {
    const child = frm.add_child("assets");
    child.asset = row.asset;
    child.asset_name = row.asset_name || "";
    child.asset_category = row.asset_category || "";
    frm._auto.assets.add(row.asset);
  }

  frm.refresh_field("assets");
}

// =====================================================================
// ======================   GRID UI (PER GROUP)   =======================
// =====================================================================

function ensure_org_styles(wrapper) {
  if (wrapper.find("style[data-so-style]").length) return;

  wrapper.prepend(`
    <style data-so-style>
      :root {
        --so-ok: var(--green-500, #22c55e);
        --so-warn: var(--orange-500, #f59e0b);
        --so-bad: var(--red-500, #ef4444);
        --so-ok-bg: color-mix(in srgb, var(--so-ok) 18%, transparent);
        --so-warn-bg: color-mix(in srgb, var(--so-warn) 18%, transparent);
        --so-bad-bg: color-mix(in srgb, var(--so-bad) 18%, transparent);
      }

      .so-wrap { display:flex; gap:12px; align-items:flex-start; }
      .so-left { flex:1 1 auto; min-width:0; }
      .so-right { flex:0 0 290px; max-width:310px; position:sticky; top:12px; }

      .so-panel { border:1px solid var(--border-color); border-radius:12px; background:var(--card-bg); }
      .so-panel__hd { padding:10px 12px; border-bottom:1px solid var(--border-color); display:flex; gap:10px; align-items:center; justify-content:space-between; }
      .so-panel__title { font-weight:800; }
      .so-panel__bd { padding:10px 12px; }

      .so-tabs { display:flex; gap:6px; flex-wrap:wrap; }
      .so-tab { border:1px solid var(--border-color); background:var(--control-bg); border-radius:10px; padding:4px 10px; cursor:pointer; font-size:12px; }
      .so-tab.is-active { background: var(--btn-default-bg, var(--control-bg)); font-weight:700; }

      .so-filters { display:flex; gap:8px; margin-bottom:10px; }
      .so-input, .so-select { width:100%; }

      .so-pool { display:flex; flex-direction:column; gap:8px; max-height:70vh; overflow:auto; padding-right:4px; }
      .so-pool-drop { border:1px dashed var(--border-color); border-radius:10px; padding:10px; text-align:center; opacity:.85; margin-bottom:10px; }
      .so-pool-drop.so-over { background: rgba(0,0,0,0.03); }

      .so-card { cursor:grab; user-select:none; }
      .so-card:active { cursor:grabbing; }
      .so-card__title, .so-card__meta { white-space:normal; overflow-wrap:anywhere; word-break:break-word; }
      .so-card__title { font-size:12px; font-weight:800; }
      .so-card__meta { font-size:11px; opacity:.85; }

      .so-group { margin-bottom:12px; }
      .so-group__hd { padding:10px 12px; border:1px solid var(--border-color); border-radius:12px; background:var(--card-bg); display:flex; justify-content:space-between; align-items:center; }
      .so-group__name { font-weight:900; }

      .so-gridwrap { margin-top:10px; border:1px solid var(--border-color); border-radius:12px; background:var(--card-bg); overflow:auto; }
      .so-grid { min-width: 900px; }

      .so-grid__hdr, .so-grid__row { display:flex; gap:8px; padding:10px; }
      .so-grid__hdr { border-bottom:1px solid var(--border-color); background: var(--control-bg); position:sticky; top:0; z-index:1; }

      .so-hcell { font-size:12px; font-weight:900; opacity:.9; border:1px solid var(--border-color); border-radius:10px; padding:8px; background: var(--card-bg); }
      .so-h-left { width:150px; flex:0 0 150px; }
      .so-h-slot { width:240px; flex:0 0 240px; }

      .so-leftcell { width:150px; flex:0 0 150px; }
      .so-slot { width:240px; flex:0 0 240px; border:1px dashed var(--border-color); border-radius:10px; padding:8px; display:flex; align-items:center; gap:8px; }
      .so-slot.so-over { background: rgba(0,0,0,0.03); }

      .so-slot.is-empty { border-color: var(--so-bad); background: var(--so-bad-bg); }
      .so-slot.is-filled { border-color: var(--so-ok); background: var(--so-ok-bg); }

      .so-slot__empty { font-size:12px; opacity:.75; }

      .so-rowlabel { border:1px solid var(--border-color); border-radius:10px; padding:8px; background: var(--card-bg); }
      .so-rowlabel--desig { background: var(--control-bg); cursor:pointer; font-size:12px; font-weight:800; }

      .so-rowdrag { border:1px dashed var(--border-color); border-radius:12px; }
      .so-rowdrag.so-over { background: rgba(0,0,0,0.02); }

      .so-asset-badge { border-radius:999px; padding:2px 8px; font-size:11px; font-weight:800; border:1px solid var(--border-color); }
      .so-badge-ok { border-color: var(--so-ok); background: var(--so-ok-bg); }
      .so-badge-warn { border-color: var(--so-warn); background: var(--so-warn-bg); }
      .so-badge-bad { border-color: var(--so-bad); background: var(--so-bad-bg); }
    </style>
  `);
}

function escape_html(s) {
  return String(s || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function active_shift_labels(frm) {
  const n = parseInt(frm.doc.shifts || "0", 10) || 0;
  const shift_letters = ["A", "B", "C", "D", "E"].slice(0, Math.max(0, Math.min(5, n)));
  return shift_letters.map((x) => `Shift ${x}`);
}

function group_shifts(frm, group_row) {
  const mode = (group_row.shifts || "").trim();
  if (mode === "Day Shift Only") return ["Day Shift"];
  if (mode === "Night Shift Only") return ["Night Shift"];
  return active_shift_labels(frm);
}

// ------------ row ordering (localStorage per group) ------------
function rows_store_key(frm, group) {
  return key(frm, `rows:${group || ""}`);
}

function load_group_rows(frm, group) {
  try {
    const raw = localStorage.getItem(rows_store_key(frm, group));
    const arr = raw ? JSON.parse(raw) : [];
    return Array.isArray(arr) ? arr : [];
  } catch {
    return [];
  }
}

function save_group_rows(frm, group, rows) {
  try {
    localStorage.setItem(rows_store_key(frm, group), JSON.stringify(rows || []));
  } catch {}
}

function remove_asset_from_all_group_orders(frm, asset) {
  for (const g of frm.doc.group_headings || []) {
    const rows = load_group_rows(frm, g.group).filter((rk) => rk !== row_key_asset(asset));
    save_group_rows(frm, g.group, rows);
  }
}

// ------------- mapping helpers (row_key-driven) -------------
function find_mapping(frm, { group, shift, row_key }) {
  return (frm.doc.shift_mappings || []).find(
    (r) => (r.group || "") === (group || "") && (r.shift || "") === (shift || "") && (r.row_key || "") === (row_key || "")
  );
}

function remove_mapping_rows(frm, predicate) {
  const rows = (frm.doc.shift_mappings || []).slice();
  for (const r of rows) {
    if (predicate(r)) {
      frappe.model.clear_doc(r.doctype, r.name);
    }
  }
}

function get_or_create_mapping_row(frm, { group, shift, row_key, asset }) {
  const existing = find_mapping(frm, { group, shift, row_key });
  if (existing) return existing;

  const child = frm.add_child("shift_mappings");
  child.group = group;
  child.shift = shift;
  child.asset = asset || "";
  child.row_key = row_key;
  child.employee = "";
  return child;
}

// ---------------- cards ----------------
function employee_card_html(e, dragType = "employee", extra = {}) {
  const title = `${e.employee_name || e.employee || ""} (${e.employee || ""})`;
  const meta = e.designation || "";
  const payload = extra.payload ? escape_html(JSON.stringify(extra.payload)) : "";

  return `
    <div class="tm-card so-card" draggable="true"
         data-so-type="${escape_html(dragType)}"
         data-employee="${escape_html(e.employee)}"
         ${payload ? `data-payload='${payload}'` : ""}>
      <div class="tm-card__top">
        <div class="tm-card__left" style="min-width:0;">
          <div class="so-card__title" title="${escape_html(title)}">${escape_html(title)}</div>
        </div>
      </div>
      <div class="so-card__meta" title="${escape_html(meta)}">${escape_html(meta) || "&nbsp;"}</div>
    </div>
  `;
}

function designation_card_html(desig) {
  const title = desig || "Designation";
  return `
    <div class="tm-card so-card" draggable="true"
         data-so-type="designation"
         data-designation="${escape_html(desig)}">
      <div class="tm-card__top">
        <div class="tm-card__left" style="min-width:0;">
          <div class="so-card__title" title="${escape_html(title)}">${escape_html(title)}</div>
        </div>
      </div>
      <div class="so-card__meta">&nbsp;</div>
    </div>
  `;
}

function asset_card_html(a, status) {
  const title = a.asset || "";
  const meta = a.asset_name || "";

  let badge = "";
  if (status) {
    const cls = status.level === "ok" ? "so-badge-ok" : status.level === "warn" ? "so-badge-warn" : "so-badge-bad";
    badge = `<span class="so-asset-badge ${cls}">${escape_html(status.label)}</span>`;
  }

  return `
    <div class="tm-card so-card" draggable="true"
         data-so-type="asset"
         data-asset="${escape_html(a.asset)}">
      <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;">
        <div style="min-width:0;">
          <div class="so-card__title" title="${escape_html(title)}">${escape_html(title)}</div>
          <div class="so-card__meta" title="${escape_html(meta)}">${escape_html(meta) || "&nbsp;"}</div>
        </div>
        ${badge}
      </div>
    </div>
  `;
}

// ---------------- render ----------------
function unique_designations_from_employees(frm) {
  const set = new Set();
  for (const e of frm.doc.employees || []) {
    if (e.designation) set.add(e.designation);
  }
  return [...set].sort();
}

function ensure_group_rows_from_state(frm, group, mappings) {
  let rows = load_group_rows(frm, group);

  const rowkeys_in_group = new Set(
    mappings
      .filter((m) => (m.group || "") === (group || "") && m.row_key)
      .map((m) => m.row_key)
      .filter(Boolean)
  );

  for (const rk of rowkeys_in_group) {
    if (!rows.includes(rk)) rows.push(rk);
  }

  save_group_rows(frm, group, rows);
  return rows;
}

function compute_asset_row_status(frm, group, row_key, shifts) {
  const total = shifts.length;
  let filled = 0;

  for (const s of shifts) {
    const slot = find_mapping(frm, { group, shift: s, row_key });
    if (slot && slot.employee) filled += 1;
  }

  let level = "bad";
  if (filled === 0) level = "bad";
  else if (filled === total) level = "ok";
  else level = "warn";

  return { level, label: `${filled}/${total}` };
}

function render_slot_cell(frm, { group, shift, row_key, asset, emp_by_id }) {
  const row = get_or_create_mapping_row(frm, { group, shift, row_key, asset });
  const emp = row && row.employee ? emp_by_id.get(row.employee) : null;

  const isFilled = !!emp;
  const cls = isFilled ? "so-slot is-filled" : "so-slot is-empty";
  const payload = { group, shift, row_key, rowname: row.name };

  return `
    <div class="${cls}"
         data-so-drop="cell"
         data-group="${escape_html(group)}"
         data-shift="${escape_html(shift)}"
         data-rowkey="${escape_html(row_key)}"
         data-asset="${escape_html(asset || "")}">
      ${emp ? employee_card_html(emp, "assigned", { payload }) : `<div class="so-slot__empty">Drop employee</div>`}
    </div>
  `;
}

function render_site_organogram(frm) {
  const field = frm.get_field("html");
  if (!field || !field.$wrapper) return;

  const $w = field.$wrapper;
  $w.empty();
  ensure_org_styles($w);

  frm._so = frm._so || { pool_mode: "employees", q: "", des: "", _clone_asked: false };

  const employees = (frm.doc.employees || []).filter((e) => e.employee);
  const assets = (frm.doc.assets || []).filter((a) => a.asset);
  const groups = (frm.doc.group_headings || []).filter((g) => g.group);
  const mappings = (frm.doc.shift_mappings || []).slice();

  const emp_by_id = new Map(employees.map((e) => [e.employee, e]));
  const asset_by_id = new Map(assets.map((a) => [a.asset, a]));

  const assigned_employees = new Set(mappings.filter((m) => m.employee).map((m) => m.employee));

  const q = frm._so.q || "";
  const des = frm._so.des || "";
  const pool_mode = frm._so.pool_mode || "employees";

  const employee_desigs = unique_designations_from_employees(frm);
  const all_designations = (frm._so.all_designations || []).slice();

  const pool_employees = employees
    .filter((e) => !assigned_employees.has(e.employee))
    .filter((e) => !des || e.designation === des)
    .filter((e) => {
      if (!q) return true;
      const hay = `${e.employee} ${e.employee_name || ""} ${e.designation || ""}`.toLowerCase();
      return hay.includes(q.toLowerCase());
    });

  const pool_assets = assets.filter((a) => {
    if (!q) return true;
    const hay = `${a.asset} ${a.asset_name || ""} ${a.asset_category || ""}`.toLowerCase();
    return hay.includes(q.toLowerCase());
  });

  const pool_designations = all_designations.filter((d) => {
    if (!q) return true;
    return String(d).toLowerCase().includes(q.toLowerCase());
  });

  const pool_controls_html = `
    <div class="so-tabs">
      <button class="so-tab ${pool_mode === "employees" ? "is-active" : ""}" data-so-tab="employees">Employees</button>
      <button class="so-tab ${pool_mode === "assets" ? "is-active" : ""}" data-so-tab="assets">Assets</button>
      <button class="so-tab ${pool_mode === "designations" ? "is-active" : ""}" data-so-tab="designations">Designations</button>
    </div>
  `;

  const pool_filters_html =
    pool_mode === "employees"
      ? `
        <div class="so-filters">
          <input class="form-control so-input" type="text" placeholder="Search employee…" value="${escape_html(q)}" data-so="pool-search">
        </div>
        <div class="so-filters">
          <select class="form-control so-select" data-so="des-filter">
            <option value="">All designations</option>
            ${employee_desigs
              .map((d) => `<option value="${escape_html(d)}" ${d === des ? "selected" : ""}>${escape_html(d)}</option>`)
              .join("")}
          </select>
        </div>
      `
      : `
        <div class="so-filters">
          <input class="form-control so-input" type="text" placeholder="Search…" value="${escape_html(q)}" data-so="pool-search">
        </div>
      `;

  const pool_list_html =
    pool_mode === "employees"
      ? pool_employees.map((e) => employee_card_html(e, "employee")).join("") ||
        `<div style="opacity:0.7;font-size:12px;">No unallocated employees match filters.</div>`
      : pool_mode === "assets"
      ? pool_assets.map((a) => asset_card_html(a)).join("") ||
        `<div style="opacity:0.7;font-size:12px;">No assets match search.</div>`
      : pool_designations.map((d) => designation_card_html(d)).join("") ||
        `<div style="opacity:0.7;font-size:12px;">No designations match search.</div>`;

  const pool_title =
    pool_mode === "employees" ? "Unallocated Employees" : pool_mode === "assets" ? "Assets Pool" : "Designations Pool";

  const pool_html = `
    <div class="so-panel so-right">
      <div class="so-panel__hd">
        <div class="so-panel__title">${pool_title}</div>
        ${pool_controls_html}
      </div>
      <div class="so-panel__bd">
        ${pool_filters_html}
        <div class="so-pool-drop" data-so-drop="pool">Drop here to unassign / remove row label</div>
        <div class="so-pool">${pool_list_html}</div>
      </div>
    </div>
  `;

  const groups_html = `
    <div class="so-left">
      ${(groups.length ? groups : [{ group: "No Groups Configured", shifts: "Shift Pattern" }])
        .map((g) => {
          const shifts = group_shifts(frm, g);
          const rows = ensure_group_rows_from_state(frm, g.group, mappings);

          const header = `
            <div class="so-grid__hdr">
              <div class="so-hcell so-h-left">Asset / Designation</div>
              ${shifts.map((s) => `<div class="so-hcell so-h-slot">${escape_html(s)}</div>`).join("")}
            </div>
          `;

          const row_html = rows
            .map((rk) => {
              const info = parse_row_key(rk);

              if (info.kind === "asset") {
                const asset = info.asset;
                const a = asset_by_id.get(asset);
                if (!a) return "";

                const status = compute_asset_row_status(frm, g.group, rk, shifts);
                return `
                  <div class="so-grid__row so-rowdrag"
                       draggable="true"
                       data-so-drop="row"
                       data-so-rowkey="${escape_html(rk)}"
                       data-group="${escape_html(g.group)}">
                    <div class="so-leftcell">
                      ${asset_card_html(a, status)}
                    </div>
                    ${shifts
                      .map((s) =>
                        render_slot_cell(frm, {
                          group: g.group,
                          shift: s,
                          row_key: rk,
                          asset: asset,
                          emp_by_id,
                        })
                      )
                      .join("")}
                  </div>
                `;
              }

              if (info.kind === "desig") {
                const desig = info.desig || "Designation";
                return `
                  <div class="so-grid__row so-rowdrag"
                       draggable="true"
                       data-so-drop="row"
                       data-so-rowkey="${escape_html(rk)}"
                       data-group="${escape_html(g.group)}">
                    <div class="so-leftcell">
                      <div class="so-rowlabel so-rowlabel--desig"
                           data-so-desig-label="1"
                           data-group="${escape_html(g.group)}"
                           data-rowkey="${escape_html(rk)}"
                           data-desig="${escape_html(desig)}"
                           title="Click to change designation row">
                        ${escape_html(desig)}
                      </div>
                    </div>
                    ${shifts
                      .map((s) =>
                        render_slot_cell(frm, {
                          group: g.group,
                          shift: s,
                          row_key: rk,
                          asset: "",
                          emp_by_id,
                        })
                      )
                      .join("")}
                  </div>
                `;
              }

              return "";
            })
            .join("");

          return `
            <div class="so-group">
              <div class="so-group__hd">
                <div class="so-group__name">${escape_html(g.group)}</div>
                <div style="opacity:0.75;font-size:12px;">${escape_html(g.shifts || "")}</div>
              </div>

              <div class="so-gridwrap">
                <div class="so-grid" data-group="${escape_html(g.group)}" data-so-drop="grid">
                  ${header}
                  ${row_html || `<div style="padding:10px;opacity:.75;">Drop an Asset or Designation into this group to create rows.</div>`}
                </div>
              </div>
            </div>
          `;
        })
        .join("")}
    </div>
  `;

  $w.append(`
    <div class="so-wrap">
      ${groups_html}
      ${pool_html}
    </div>
  `);

  bind_events(frm, $w);

  // restore focus after rerender
  restore_pool_focus_state(frm, $w);
}

// ---------------- drag/drop + actions ----------------
function bind_events(frm, $w) {
  $w.find("[data-so-tab]")
    .off("click")
    .on("click", async (ev) => {
      const mode = ev.currentTarget.getAttribute("data-so-tab");
      frm._so = frm._so || { pool_mode: "employees", q: "", des: "", _clone_asked: false };
      frm._so.pool_mode = mode;

      if (mode === "designations") {
        await ensure_designations_loaded(frm);
      }
      render_site_organogram(frm);
    });

  $w.find('[data-so="pool-search"]')
    .off("input")
    .on(
      "input",
      debounce((ev) => {
        frm._so = frm._so || { pool_mode: "employees", q: "", des: "", _clone_asked: false };
        frm._so.q = ev.target.value || "";

        capture_pool_focus_state(frm, ev.target);
        render_site_organogram(frm);
      }, 150)
    );

  $w.find('[data-so="des-filter"]')
    .off("change")
    .on("change", (ev) => {
      frm._so = frm._so || { pool_mode: "employees", q: "", des: "", _clone_asked: false };
      frm._so.des = ev.target.value || "";
      render_site_organogram(frm);
    });

  // Change designation row label
  $w.find("[data-so-desig-label='1']")
    .off("click")
    .on("click", async (ev) => {
      const group = ev.currentTarget.getAttribute("data-group");
      const old_rk = ev.currentTarget.getAttribute("data-rowkey");
      const old_desig = ev.currentTarget.getAttribute("data-desig") || "";

      await ensure_designations_loaded(frm);
      const options = (frm._so.all_designations || []).slice();

            const d = await so_select_dialog({
        title: "Change Designation Row",
        label: "Designation Row",
        options,
        default_value: old_desig,
        primary_label: "Set",
      });


      if (!d) return;

      const new_rk = row_key_desig(d.choice);

      const rows = load_group_rows(frm, group);
      save_group_rows(
        frm,
        group,
        rows.map((rk) => (rk === old_rk ? new_rk : rk))
      );

      for (const m of frm.doc.shift_mappings || []) {
        if ((m.group || "") === (group || "") && (m.row_key || "") === (old_rk || "")) {
          frappe.model.set_value(m.doctype, m.name, "row_key", new_rk);
          frappe.model.set_value(m.doctype, m.name, "asset", "");
        }
      }

      frm.refresh_field("shift_mappings");
      render_site_organogram(frm);
    });

  // dragstart for cards + rows
  $w.find("[draggable='true']")
    .off("dragstart")
    .on("dragstart", (ev) => {
      const el = ev.currentTarget;

      if (el.classList.contains("so-rowdrag")) {
        const payload = {
          type: "row",
          group: el.getAttribute("data-group"),
          row_key: el.getAttribute("data-so-rowkey"),
        };
        ev.originalEvent.dataTransfer.setData("application/json", JSON.stringify(payload));
        ev.originalEvent.dataTransfer.effectAllowed = "move";
        return;
      }

      const t = el.getAttribute("data-so-type");

      if (t === "employee" || t === "assigned") {
        const payload = {
          type: "employee",
          employee: el.getAttribute("data-employee"),
        };
        const raw = el.getAttribute("data-payload");
        if (raw) {
          try {
            payload.from = JSON.parse(raw);
          } catch {}
        }
        ev.originalEvent.dataTransfer.setData("application/json", JSON.stringify(payload));
        ev.originalEvent.dataTransfer.effectAllowed = "move";
        return;
      }

      if (t === "asset") {
        const payload = { type: "asset", asset: el.getAttribute("data-asset") };
        ev.originalEvent.dataTransfer.setData("application/json", JSON.stringify(payload));
        ev.originalEvent.dataTransfer.effectAllowed = "move";
        return;
      }

      if (t === "designation") {
        const payload = { type: "designation", designation: el.getAttribute("data-designation") };
        ev.originalEvent.dataTransfer.setData("application/json", JSON.stringify(payload));
        ev.originalEvent.dataTransfer.effectAllowed = "move";
        return;
      }
    });

  const addOver = (el) => el.classList.add("so-over");
  const rmOver = (el) => el.classList.remove("so-over");

  $w.find("[data-so-drop]")
    .off("dragover")
    .on("dragover", (ev) => {
      ev.preventDefault();
      addOver(ev.currentTarget);
    })
    .off("dragleave")
    .on("dragleave", (ev) => rmOver(ev.currentTarget))
    .off("drop")
    .on("drop", async (ev) => {
      ev.preventDefault();
      rmOver(ev.currentTarget);

      const raw = ev.originalEvent.dataTransfer.getData("application/json");
      if (!raw) return;

      let data;
      try {
        data = JSON.parse(raw);
      } catch {
        return;
      }

      const dropType = ev.currentTarget.getAttribute("data-so-drop");

      if (dropType === "pool") {
        if (data.type === "employee" && data.from) {
          await unassign_from_origin(frm, data.from);
        } else if (data.type === "row" && data.row_key) {
          await remove_row_from_group(frm, data.group, data.row_key);
        }
        return;
      }

      if (dropType === "grid") {
        const group = ev.currentTarget.getAttribute("data-group");
        if (data.type === "asset" && data.asset) {
          await add_asset_row(frm, group, data.asset);
        } else if (data.type === "designation" && data.designation) {
          await add_designation_row(frm, group, data.designation);
        }
        return;
      }

      if (dropType === "row" && data.type === "row") {
        const targetKey = ev.currentTarget.getAttribute("data-so-rowkey");
        await reorder_rows(frm, data.group, data.row_key, targetKey);
        return;
      }

      if (dropType === "cell" && data.type === "employee" && data.employee) {
        const group = ev.currentTarget.getAttribute("data-group");
        const shift = ev.currentTarget.getAttribute("data-shift");
        const row_key = ev.currentTarget.getAttribute("data-rowkey");
        const asset = ev.currentTarget.getAttribute("data-asset") || "";
        await assign_employee_to_cell(frm, { group, shift, row_key, asset, employee: data.employee });
        return;
      }
    });
}

async function add_asset_row(frm, group, asset) {
  if (!group || !asset) return;

  const rk = row_key_asset(asset);

  const rows = load_group_rows(frm, group);
  if (!rows.includes(rk)) {
    rows.push(rk);
    save_group_rows(frm, group, rows);
  }

  const grp = (frm.doc.group_headings || []).find((g) => g.group === group);
  if (grp) {
    const shifts = group_shifts(frm, grp);
    for (const s of shifts) {
      get_or_create_mapping_row(frm, { group, shift: s, row_key: rk, asset });
    }
  }

  frm.refresh_field("shift_mappings");
  render_site_organogram(frm);
}

async function add_designation_row(frm, group, designation) {
  if (!group || !designation) return;

  const rk = row_key_desig(designation);

  const rows = load_group_rows(frm, group);
  if (!rows.includes(rk)) {
    rows.push(rk);
    save_group_rows(frm, group, rows);
  }

  const grp = (frm.doc.group_headings || []).find((g) => g.group === group);
  if (grp) {
    const shifts = group_shifts(frm, grp);
    for (const s of shifts) {
      get_or_create_mapping_row(frm, { group, shift: s, row_key: rk, asset: "" });
    }
  }

  frm.refresh_field("shift_mappings");
  render_site_organogram(frm);
}

async function reorder_rows(frm, group, movingKey, targetKey) {
  if (!group || !movingKey || !targetKey || movingKey === targetKey) return;

  const rows = load_group_rows(frm, group);
  const filtered = rows.filter((rk) => rk !== movingKey);

  const idx = filtered.indexOf(targetKey);
  if (idx === -1) filtered.push(movingKey);
  else filtered.splice(idx, 0, movingKey);

  save_group_rows(frm, group, filtered);
  render_site_organogram(frm);
}

async function remove_row_from_group(frm, group, row_key) {
  if (!group || !row_key) return;

  const rows = load_group_rows(frm, group).filter((rk) => rk !== row_key);
  save_group_rows(frm, group, rows);

  remove_mapping_rows(frm, (r) => (r.group || "") === (group || "") && (r.row_key || "") === (row_key || ""));

  frm.refresh_field("shift_mappings");
  render_site_organogram(frm);
}

async function unassign_from_origin(frm, from) {
  if (!from || !from.rowname) return;

  const row = (frm.doc.shift_mappings || []).find((r) => r.name === from.rowname);
  if (!row) return;

  frappe.model.set_value(row.doctype, row.name, "employee", "");
  frm.refresh_field("shift_mappings");
  render_site_organogram(frm);
}

async function assign_employee_to_cell(frm, { group, shift, row_key, asset, employee }) {
  if (!group || !shift || !row_key || !employee) return;

  // prevent duplicates in exact slot
  remove_mapping_rows(frm, (r) => {
    return (
      (r.employee || "") === employee &&
      (r.group || "") === (group || "") &&
      (r.shift || "") === (shift || "") &&
      (r.row_key || "") === (row_key || "")
    );
  });

  const row = get_or_create_mapping_row(frm, { group, shift, row_key, asset });

  const info = parse_row_key(row_key);
  if (info.kind === "desig") {
    frappe.model.set_value(row.doctype, row.name, "asset", "");
  }

  frappe.model.set_value(row.doctype, row.name, "employee", employee);

  if (!row.row_key) {
    frappe.model.set_value(row.doctype, row.name, "row_key", row_key);
  }

  frm.refresh_field("shift_mappings");
  render_site_organogram(frm);
}
