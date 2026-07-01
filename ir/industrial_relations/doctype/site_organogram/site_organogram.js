// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

const PY = "ir.industrial_relations.doctype.site_organogram.site_organogram";

// ---------------------------------------------------------------------
// Basic helpers
// ---------------------------------------------------------------------

function so_force_full_width(frm) {
  try {
    const $main = frm && frm.page && frm.page.main ? $(frm.page.main) : null;
    if ($main && $main.length) {
      $main.css({ "max-width": "100%", width: "100%", margin: "0" });
    }

    const $layout = $main ? $main.closest(".layout-main-section") : null;
    if ($layout && $layout.length) {
      $layout.css({ "max-width": "100%", width: "100%" });
    }

    const $container = $main ? $main.closest(".container") : null;
    if ($container && $container.length) {
      $container.css({ "max-width": "100%", width: "100%" });
    }
  } catch (e) {}
}

function escape_html(s) {
  return String(s || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function debounce(fn, wait = 250) {
  let t = null;
  return function (...args) {
    clearTimeout(t);
    t = setTimeout(() => fn.apply(this, args), wait);
  };
}

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
          default: default_value || opts[0] || "",
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
      if (!resolved) {
        resolve(null);
      }
    };

    d.show();
  });
}

function row_key_asset(asset) {
  return `ASSET::${asset}`;
}

function row_key_designation(label, token) {
  const t = token || frappe.utils.get_random(6);
  return `DESIG::${label || "Unlinked Role"}::${t}`;
}

function parse_row_key(row_key) {
  if (!row_key) {
    return { kind: "Unknown" };
  }

  if (row_key.startsWith("ASSET::")) {
    return {
      kind: "Asset",
      asset: row_key.slice("ASSET::".length),
    };
  }

  if (row_key.startsWith("DESIG::")) {
    const rest = row_key.slice("DESIG::".length);
    const parts = rest.split("::");

    return {
      kind: "Designation",
      label: parts[0] || "Unlinked Role",
      token: parts[1] || "",
    };
  }

  return { kind: "Unknown" };
}

function row_label_for_asset(asset_row) {
  if (!asset_row) {
    return "Missing";
  }

  const parts = [asset_row.asset];

  if (asset_row.item_name) {
    parts.push(asset_row.item_name);
  } else if (asset_row.asset_category) {
    parts.push(asset_row.asset_category);
  }

  return parts.filter(Boolean).join(" — ");
}

function active_shift_labels(frm) {
  const n = parseInt(frm.doc.shifts || "0", 10) || 0;
  const letters = ["A", "B", "C", "D", "E"].slice(0, Math.max(0, Math.min(5, n)));
  return letters.map((x) => `Shift ${x}`);
}

function group_shifts(frm, group_row) {
  const mode = (group_row.shifts || "").trim();

  if (mode === "Day Shift Only") {
    return ["Day Shift"];
  }

  if (mode === "Night Shift Only") {
    return ["Night Shift"];
  }

  return active_shift_labels(frm);
}

// ---------------------------------------------------------------------
// localStorage helpers
// ---------------------------------------------------------------------

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

function rows_store_key(frm, group) {
  return key(frm, `rows:${group || ""}`);
}

function save_group_rows(frm, group, rows) {
  try {
    localStorage.setItem(rows_store_key(frm, group), JSON.stringify(rows || []));
  } catch {}
}

function load_group_rows(frm, group) {
  try {
    const raw = localStorage.getItem(rows_store_key(frm, group));
    const arr = raw ? JSON.parse(raw) : [];
    if (Array.isArray(arr) && arr.length) {
      return arr;
    }
  } catch {}

  return [];
}

// ---------------------------------------------------------------------
// Asset category helpers
// ---------------------------------------------------------------------

function get_asset_category_rows_live(frm) {
  const grid = frm.fields_dict.asset_categories && frm.fields_dict.asset_categories.grid;

  if (grid && typeof grid.get_data === "function") {
    return grid.get_data() || [];
  }

  return frm.doc.asset_categories || [];
}

function get_selected_asset_categories(frm) {
  const rows = get_asset_category_rows_live(frm);
  return [...new Set(rows.map((r) => r.asset_cateogories).filter(Boolean))];
}

function categories_signature(frm) {
  return JSON.stringify(get_selected_asset_categories(frm).slice().sort());
}

const maybe_sync_assets_after_categories_change = debounce(async (frm) => {
  if (frm._so_suppress) {
    return;
  }

  ensureAuto(frm);

  const sig = categories_signature(frm);

  if (frm._asset_cat_sig === undefined) {
    frm._asset_cat_sig = sig;
    return;
  }

  if (sig === frm._asset_cat_sig) {
    return;
  }

  frm._asset_cat_sig = sig;

  await sync_assets(frm);
  reconcile_mappings_against_current_pools(frm);

  persistAuto(frm);
  frm.refresh_field("assets");
  frm.refresh_field("shift_mappings");
  render_site_organogram(frm);
}, 200);

function start_category_poll(frm) {
  if (frm._asset_cat_poll) {
    return;
  }

  frm._asset_cat_poll = setInterval(() => {
    if (!frm.doc || !frm.doc.location || frm.doc.docstatus === 1) {
      return;
    }
    maybe_sync_assets_after_categories_change(frm);
  }, 600);
}

function stop_category_poll(frm) {
  if (frm._asset_cat_poll) {
    clearInterval(frm._asset_cat_poll);
    frm._asset_cat_poll = null;
  }
}

// ---------------------------------------------------------------------
// Designation loading
// ---------------------------------------------------------------------

async function ensure_designations_loaded(frm) {
  frm._so = frm._so || {};

  if (Array.isArray(frm._so.all_designations) && frm._so.all_designations.length) {
    return;
  }

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

// ---------------------------------------------------------------------
// Form events
// ---------------------------------------------------------------------

frappe.ui.form.on("Site Organogram", {
  onload(frm) {
    ensureAuto(frm);
    frm._so = frm._so || {
      pool_mode: "employees",
      q: "",
      des: "",
      _clone_asked: false,
    };
  },

  async refresh(frm) {
    ensureAuto(frm);
    start_category_poll(frm);

    frm._so = frm._so || {
      pool_mode: "employees",
      q: "",
      des: "",
      _clone_asked: false,
    };

    await ensure_designations_loaded(frm);

    frm._asset_cat_sig = categories_signature(frm);

    add_export_button(frm);
    render_site_organogram(frm);
  },

  before_save(frm) {
    normalize_mapping_rows(frm);
    sync_all_row_orders(frm, false);
  },

  onhide(frm) {
    stop_category_poll(frm);
  },

  async branch(frm) {
    if (frm._so_suppress) {
      return;
    }

    ensureAuto(frm);

    const cloned = await maybe_offer_clone_previous(frm);

    if (cloned) {
      frm._asset_cat_sig = categories_signature(frm);
      persistAuto(frm);
      return;
    }

    await sync_employees(frm);
    await set_location_from_branch_if_exists(frm);
    await sync_assets(frm);

    reconcile_mappings_against_current_pools(frm);
    persistAuto(frm);

    frm._asset_cat_sig = categories_signature(frm);

    frm.refresh_fields(["employees", "assets", "shift_mappings"]);
    render_site_organogram(frm);
  },

  async location(frm) {
    if (frm._so_suppress) {
      return;
    }

    ensureAuto(frm);

    await sync_assets(frm);
    reconcile_mappings_against_current_pools(frm);
    persistAuto(frm);

    frm._asset_cat_sig = categories_signature(frm);

    frm.refresh_fields(["assets", "shift_mappings"]);
    render_site_organogram(frm);
  },

  shifts(frm) {
    if (frm._so_suppress) {
      return;
    }

    render_site_organogram(frm);
  },

  group_headings(frm) {
    if (frm._so_suppress) {
      return;
    }

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

    if (!row.employee) {
      return;
    }

    frm._auto.employees.delete(row.employee);
    persistAuto(frm);

    frm.call({
      method: `${PY}.get_employee_details`,
      args: { employee: row.employee },
    }).then((r) => {
      const d = r.message || {};
      frappe.model.set_value(cdt, cdn, "employee_name", d.employee_name || "");
      frappe.model.set_value(cdt, cdn, "designation", d.designation || "");
      reconcile_mappings_against_current_pools(frm);
      render_site_organogram(frm);
    });
  },
});

frappe.ui.form.on("Site Organogram Assets", {
  asset(frm, cdt, cdn) {
    ensureAuto(frm);

    const row = locals[cdt][cdn];

    if (!row.asset) {
      return;
    }

    frm._auto.assets.delete(row.asset);
    persistAuto(frm);

    frm.call({
      method: `${PY}.get_asset_details`,
      args: { asset: row.asset },
    }).then((r) => {
      const d = r.message || {};
      frappe.model.set_value(cdt, cdn, "item_name", d.item_name || "");
      frappe.model.set_value(cdt, cdn, "asset_category", d.asset_category || "");
      reconcile_mappings_against_current_pools(frm);
      render_site_organogram(frm);
    });
  },
});

// ---------------------------------------------------------------------
// Export
// ---------------------------------------------------------------------

function add_export_button(frm) {
  try {
    frm.remove_custom_button("Export Excel");
  } catch (e) {}

  frm.add_custom_button("Export Excel", () => {
    if (frm.is_new()) {
      frappe.msgprint("Please save the Site Organogram before exporting.");
      return;
    }

    if (frm.is_dirty()) {
      frappe.msgprint("Please save the Site Organogram before exporting so the export includes the latest mapping changes.");
      return;
    }

    const url = `/api/method/${PY}.export_site_organogram_excel?name=${encodeURIComponent(frm.doc.name)}`;
    window.open(url, "_blank");
  });
}

// ---------------------------------------------------------------------
// Sync employees/assets
// ---------------------------------------------------------------------

async function set_location_from_branch_if_exists(frm) {
  if (!frm.doc.branch) {
    return;
  }

  const r = await frm.call({
    method: `${PY}.get_matching_location_for_branch`,
    args: {
      branch: frm.doc.branch,
    },
  });

  const loc = r.message || "";

  if ((frm.doc.location || "") !== loc) {
    await frm.set_value("location", loc);
  }
}

async function sync_employees(frm) {
  if (!frm.doc.branch) {
    return;
  }

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

  const plan = r.message || {
    to_add: [],
    to_remove: [],
  };

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
  if (!frm.doc.location) {
    return;
  }

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

  const plan = r.message || {
    to_add: [],
    to_remove: [],
  };

  for (const asset_id of plan.to_remove || []) {
    const rows = (frm.doc.assets || []).filter((x) => x.asset === asset_id);
    rows.forEach((row) => frappe.model.clear_doc(row.doctype, row.name));
    frm._auto.assets.delete(asset_id);
  }

  for (const row of plan.to_add || []) {
    const child = frm.add_child("assets");
    child.asset = row.asset;
    child.item_name = row.item_name || "";
    child.asset_category = row.asset_category || "";
    frm._auto.assets.add(row.asset);
  }

  frm.refresh_field("assets");
}

// ---------------------------------------------------------------------
// Clone
// ---------------------------------------------------------------------

async function maybe_offer_clone_previous(frm) {
  if (!frm.is_new() || !frm.doc.branch) {
    return false;
  }

  frm._so = frm._so || {
    pool_mode: "employees",
    q: "",
    des: "",
    _clone_asked: false,
  };

  if (frm._so._clone_asked) {
    return false;
  }

  frm._so._clone_asked = true;

  const hasMeaningfulMappings = (frm.doc.shift_mappings || []).some((r) => {
    return (
      (r.employee && String(r.employee).trim()) ||
      (r.asset && String(r.asset).trim()) ||
      (r.row_key && String(r.row_key).trim())
    );
  });

  if (hasMeaningfulMappings) {
    return false;
  }

  const resp = await frm.call({
    method: `${PY}.list_recent_site_organograms_for_branch`,
    args: {
      branch: frm.doc.branch,
      exclude_name: frm.doc.name,
      limit: 5,
    },
  });

  const rows = resp.message || [];

  if (!rows.length) {
    return false;
  }

  const use_previous = await new Promise((resolve) => {
    frappe.confirm(
      `A previous Site Organogram exists for Branch "${frm.doc.branch}".\n\nDo you want to clone one as a starting point?`,
      () => resolve(true),
      () => resolve(false),
      "Clone Previous Organogram"
    );
  });

  if (!use_previous) {
    return false;
  }

  const labels = rows.map((r) => {
    const dt = r.modified ? frappe.datetime.str_to_user(r.modified) : "";
    return dt ? `${r.name}  —  ${dt}` : r.name;
  });

  const labelToName = new Map(labels.map((label, i) => [label, rows[i].name]));

  const d = await so_select_dialog({
    title: "Select Organogram to Clone",
    label: "Previous Organogram",
    options: labels,
    default_value: labels[0],
    primary_label: "Clone",
  });

  if (!d || !d.choice) {
    return false;
  }

  const source = labelToName.get(d.choice);

  if (!source) {
    return false;
  }

  const tpl = await frm.call({
    method: `${PY}.get_site_organogram_template`,
    args: {
      source_name: source,
    },
  });

  await apply_template_to_form(frm, tpl.message || {});
  return true;
}

async function apply_template_to_form(frm, tpl) {
  frm._so_suppress = true;

  try {
    if (tpl.shifts != null) {
      await frm.set_value("shifts", tpl.shifts);
    }

    if (tpl.location) {
      await frm.set_value("location", tpl.location);
    }

    frm.clear_table("group_headings");
    (tpl.group_headings || []).forEach((r) => {
      const row = frm.add_child("group_headings");
      row.group = r.group || "";
      row.shifts = r.shifts || "";
    });

    frm.clear_table("asset_categories");
    (tpl.asset_categories || []).forEach((r) => {
      const row = frm.add_child("asset_categories");
      row.asset_cateogories = r.asset_cateogories || "";
    });

    frm.clear_table("employees");
    (tpl.employees || []).forEach((r) => {
      const row = frm.add_child("employees");
      row.employee = r.employee || "";
      row.employee_name = r.employee_name || "";
      row.designation = r.designation || "";
      if (row.employee) {
        frm._auto.employees.add(row.employee);
      }
    });

    frm.clear_table("assets");
    (tpl.assets || []).forEach((r) => {
      const row = frm.add_child("assets");
      row.asset = r.asset || "";
      row.item_name = r.item_name || "";
      row.asset_category = r.asset_category || "";
      if (row.asset) {
        frm._auto.assets.add(row.asset);
      }
    });

    frm.clear_table("shift_mappings");

    (tpl.shift_mappings || []).forEach((r) => {
      const row = frm.add_child("shift_mappings");

      row.group = r.group || "";
      row.shift = r.shift || "";
      row.employee = r.employee || "";
      row.asset = r.asset || "";
      row.row_key = r.row_key || "";
      row.row_order = r.row_order || 0;
      row.row_label = r.row_label || "";
      row.row_type = r.row_type || "";
      row.missing_asset = r.missing_asset ? 1 : 0;
      row.missing_employee = r.missing_employee ? 1 : 0;
    });

    normalize_mapping_rows(frm);

    // The clone copies structure exactly first, then reconciles against the
    // current Branch/Location lists without deleting organogram rows.
    await sync_employees(frm);
    await sync_assets(frm);

    reconcile_mappings_against_current_pools(frm);
    seed_group_row_order_from_mappings(frm);
    sync_all_row_orders(frm, false);

    persistAuto(frm);
    frm._asset_cat_sig = categories_signature(frm);

    frm.refresh_fields(["group_headings", "asset_categories", "employees", "assets", "shift_mappings"]);
    render_site_organogram(frm);
  } finally {
    frm._so_suppress = false;
  }
}

// ---------------------------------------------------------------------
// Mapping normalization and reconciliation
// ---------------------------------------------------------------------

function get_employee_set(frm) {
  return new Set((frm.doc.employees || []).map((r) => r.employee).filter(Boolean));
}

function get_asset_set(frm) {
  return new Set((frm.doc.assets || []).map((r) => r.asset).filter(Boolean));
}

function get_asset_by_id(frm) {
  return new Map((frm.doc.assets || []).filter((r) => r.asset).map((r) => [r.asset, r]));
}

function get_employee_by_id(frm) {
  return new Map((frm.doc.employees || []).filter((r) => r.employee).map((r) => [r.employee, r]));
}

function normalize_mapping_rows(frm) {
  const assetById = get_asset_by_id(frm);

  for (const row of frm.doc.shift_mappings || []) {
    if (!row.row_key) {
      if (row.asset) {
        row.row_key = row_key_asset(row.asset);
      } else if (row.row_label) {
        row.row_key = row_key_designation(row.row_label);
      } else {
        row.row_key = row_key_designation("Unlinked Role");
      }
    }

    const info = parse_row_key(row.row_key);

    if (!row.row_type) {
      row.row_type = info.kind === "Asset" ? "Asset" : "Designation";
    }

    if (row.row_type === "Asset") {
      const asset_from_key = info.kind === "Asset" ? info.asset : row.asset;

      if (!row.row_label) {
        const asset_row = assetById.get(row.asset || asset_from_key);
        row.row_label = asset_row ? row_label_for_asset(asset_row) : asset_from_key || "Missing";
      }
    } else {
      row.asset = "";
      row.missing_asset = 0;

      if (!row.row_label) {
        row.row_label = info.kind === "Designation" ? info.label : "Unlinked Role";
      }
    }
  }
}

function reconcile_mappings_against_current_pools(frm) {
  const employeeSet = get_employee_set(frm);
  const assetSet = get_asset_set(frm);
  const assetById = get_asset_by_id(frm);

  for (const row of frm.doc.shift_mappings || []) {
    const info = parse_row_key(row.row_key);

    if (row.row_type === "Asset" || info.kind === "Asset") {
      row.row_type = "Asset";

      const asset_from_key = info.kind === "Asset" ? info.asset : row.asset;

      if (asset_from_key && assetSet.has(asset_from_key)) {
        row.asset = asset_from_key;
        row.missing_asset = 0;

        const asset_row = assetById.get(asset_from_key);
        row.row_label = row_label_for_asset(asset_row);
      } else {
        row.asset = "";
        row.missing_asset = 1;

        if (!row.row_label) {
          row.row_label = "Missing";
        }
      }
    } else {
      row.row_type = "Designation";
      row.asset = "";
      row.missing_asset = 0;

      if (!row.row_label) {
        row.row_label = info.kind === "Designation" ? info.label : "Unlinked Role";
      }
    }

    if (row.employee && employeeSet.has(row.employee)) {
      row.missing_employee = 0;
    } else if (row.employee) {
      row.employee = "";
      row.missing_employee = 1;
    }
  }

  frm.refresh_field("shift_mappings");
}

function find_mapping(frm, { group, shift, row_key }) {
  return (frm.doc.shift_mappings || []).find((r) => {
    return (
      (r.group || "") === (group || "") &&
      (r.shift || "") === (shift || "") &&
      (r.row_key || "") === (row_key || "")
    );
  });
}

function remove_mapping_rows(frm, predicate) {
  const rows = (frm.doc.shift_mappings || []).slice();

  for (const r of rows) {
    if (predicate(r)) {
      frappe.model.clear_doc(r.doctype, r.name);
    }
  }
}

function get_or_create_mapping_row(frm, { group, shift, row_key, row_type, row_label, asset }) {
  const existing = find_mapping(frm, {
    group,
    shift,
    row_key,
  });

  if (existing) {
    return existing;
  }

  const child = frm.add_child("shift_mappings");
  child.group = group;
  child.shift = shift;
  child.row_key = row_key;
  child.row_type = row_type || "Designation";
  child.row_label = row_label || "";
  child.asset = asset || "";
  child.employee = "";
  child.missing_asset = 0;
  child.missing_employee = 0;

  return child;
}

// ---------------------------------------------------------------------
// Row order
// ---------------------------------------------------------------------

function mapping_row_keys_for_group(frm, group) {
  const byKey = new Map();

  (frm.doc.shift_mappings || [])
    .filter((m) => (m.group || "") === (group || "") && m.row_key)
    .sort((a, b) => {
      const ao = Number(a.row_order || 999999);
      const bo = Number(b.row_order || 999999);

      if (ao !== bo) {
        return ao - bo;
      }

      return Number(a.idx || 999999) - Number(b.idx || 999999);
    })
    .forEach((m) => {
      if (!byKey.has(m.row_key)) {
        byKey.set(m.row_key, m);
      }
    });

  return [...byKey.keys()];
}

function ensure_group_rows_from_state(frm, group) {
  const actual = mapping_row_keys_for_group(frm, group);
  let stored = load_group_rows(frm, group);

  stored = stored.filter((rk) => actual.includes(rk));

  for (const rk of actual) {
    if (!stored.includes(rk)) {
      stored.push(rk);
    }
  }

  save_group_rows(frm, group, stored);
  return stored;
}

function seed_group_row_order_from_mappings(frm) {
  const groups = new Set((frm.doc.shift_mappings || []).map((m) => m.group).filter(Boolean));

  for (const group of groups) {
    save_group_rows(frm, group, mapping_row_keys_for_group(frm, group));
  }
}

function sync_row_order_for_group(frm, group, mark_dirty) {
  const rows = ensure_group_rows_from_state(frm, group);
  let changed = false;

  rows.forEach((row_key, index) => {
    const order = index + 1;

    for (const m of frm.doc.shift_mappings || []) {
      if ((m.group || "") !== (group || "")) {
        continue;
      }

      if ((m.row_key || "") !== row_key) {
        continue;
      }

      const current = Number(m.row_order || 0);

      if (current !== order) {
        m.row_order = order;
        changed = true;
      }
    }
  });

  if (changed) {
    frm.refresh_field("shift_mappings");

    if (mark_dirty) {
      frm.dirty();
    }
  }
}

function sync_all_row_orders(frm, mark_dirty) {
  const groups = new Set();

  (frm.doc.group_headings || []).forEach((g) => {
    if (g.group) {
      groups.add(g.group);
    }
  });

  (frm.doc.shift_mappings || []).forEach((m) => {
    if (m.group) {
      groups.add(m.group);
    }
  });

  for (const group of groups) {
    sync_row_order_for_group(frm, group, mark_dirty);
  }
}

// ---------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------

function ensure_org_styles(wrapper) {
  if (wrapper.find("style[data-so-style]").length) {
    return;
  }

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
      .so-right { flex:0 0 310px; max-width:330px; position:sticky; top:12px; }

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
      .so-h-left { width:190px; flex:0 0 190px; }
      .so-h-slot { width:240px; flex:0 0 240px; }

      .so-leftcell { width:190px; flex:0 0 190px; }
      .so-slot { width:240px; flex:0 0 240px; border:1px dashed var(--border-color); border-radius:10px; padding:8px; display:flex; align-items:center; gap:8px; }
      .so-slot.so-over { background: rgba(0,0,0,0.03); }

      .so-slot.is-empty { border-color: var(--so-bad); background: var(--so-bad-bg); }
      .so-slot.is-filled { border-color: var(--so-ok); background: var(--so-ok-bg); }
      .so-slot.is-missing { border-color: var(--so-warn); background: var(--so-warn-bg); }

      .so-slot__empty { font-size:12px; opacity:.75; }

      .so-rowlabel { border:1px solid var(--border-color); border-radius:10px; padding:8px; background: var(--card-bg); min-height:48px; }
      .so-rowlabel--desig { background: var(--control-bg); cursor:pointer; }
      .so-rowlabel--missing { border-color: var(--so-warn); background: var(--so-warn-bg); }

      .so-rowlabel__title { font-size:12px; font-weight:900; }
      .so-rowlabel__meta { font-size:11px; opacity:.78; }

      .so-rowdrag { border:1px dashed var(--border-color); border-radius:12px; }
      .so-rowdrag.so-over { background: rgba(0,0,0,0.02); }

      .so-asset-badge { border-radius:999px; padding:2px 8px; font-size:11px; font-weight:800; border:1px solid var(--border-color); }
      .so-badge-ok { border-color: var(--so-ok); background: var(--so-ok-bg); }
      .so-badge-warn { border-color: var(--so-warn); background: var(--so-warn-bg); }
      .so-badge-bad { border-color: var(--so-bad); background: var(--so-bad-bg); }
    </style>
  `);
}

function unique_designations_from_employees(frm) {
  const set = new Set();

  for (const e of frm.doc.employees || []) {
    if (e.designation) {
      set.add(e.designation);
    }
  }

  return [...set].sort();
}

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
  const meta = a.item_name || a.asset_category || "";

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

function row_identity_for_key(frm, group, row_key) {
  const rows = (frm.doc.shift_mappings || []).filter((m) => {
    return (m.group || "") === (group || "") && (m.row_key || "") === row_key;
  });

  return rows[0] || null;
}

function compute_asset_row_status(frm, group, row_key, shifts) {
  const total = shifts.length;
  let filled = 0;
  let missing = 0;

  for (const s of shifts) {
    const slot = find_mapping(frm, {
      group,
      shift: s,
      row_key,
    });

    if (slot && slot.employee) {
      filled += 1;
    }

    if (slot && slot.missing_employee) {
      missing += 1;
    }
  }

  if (missing) {
    return {
      level: "warn",
      label: "Missing",
    };
  }

  if (filled === total) {
    return {
      level: "ok",
      label: `${filled}/${total}`,
    };
  }

  if (filled > 0) {
    return {
      level: "warn",
      label: `${filled}/${total}`,
    };
  }

  return {
    level: "bad",
    label: `${filled}/${total}`,
  };
}

function render_row_label(frm, row_identity, assetById) {
  if (!row_identity) {
    return `<div class="so-rowlabel so-rowlabel--missing"><div class="so-rowlabel__title">Missing</div></div>`;
  }

  const rowType = row_identity.row_type || "Designation";

  if (rowType === "Asset") {
    if (row_identity.missing_asset) {
      return `
        <div class="so-rowlabel so-rowlabel--missing">
          <div class="so-rowlabel__title">Missing</div>
          <div class="so-rowlabel__meta">${escape_html(row_identity.row_label || "")}</div>
        </div>
      `;
    }

    const asset = assetById.get(row_identity.asset);
    const title = asset ? asset.asset : row_identity.asset || "Missing";
    const meta = asset ? asset.item_name || asset.asset_category || "" : row_identity.row_label || "";

    return `
      <div class="so-rowlabel">
        <div class="so-rowlabel__title">${escape_html(title)}</div>
        <div class="so-rowlabel__meta">${escape_html(meta)}</div>
      </div>
    `;
  }

  return `
    <div class="so-rowlabel so-rowlabel--desig"
         data-so-desig-label="1"
         data-group="${escape_html(row_identity.group || "")}"
         data-rowkey="${escape_html(row_identity.row_key || "")}"
         data-desig="${escape_html(row_identity.row_label || "")}">
      <div class="so-rowlabel__title">${escape_html(row_identity.row_label || "Designation")}</div>
    </div>
  `;
}

function render_slot_cell(frm, { group, shift, row_key, empById }) {
  const row = find_mapping(frm, {
    group,
    shift,
    row_key,
  });

  const emp = row && row.employee ? empById.get(row.employee) : null;

  if (row && row.missing_employee) {
    return `
      <div class="so-slot is-missing"
           data-so-drop="cell"
           data-group="${escape_html(group)}"
           data-shift="${escape_html(shift)}"
           data-rowkey="${escape_html(row_key)}">
        <div class="so-slot__empty">Missing</div>
      </div>
    `;
  }

  const isFilled = !!emp;
  const cls = isFilled ? "so-slot is-filled" : "so-slot is-empty";
  const payload = row
    ? {
        group,
        shift,
        row_key,
        rowname: row.name,
      }
    : {
        group,
        shift,
        row_key,
        rowname: "",
      };

  return `
    <div class="${cls}"
         data-so-drop="cell"
         data-group="${escape_html(group)}"
         data-shift="${escape_html(shift)}"
         data-rowkey="${escape_html(row_key)}">
      ${
        emp
          ? employee_card_html(emp, "assigned", { payload })
          : `<div class="so-slot__empty">Vacant</div>`
      }
    </div>
  `;
}

function render_site_organogram(frm) {
  so_force_full_width(frm);

  const field = frm.get_field("html");

  if (!field || !field.$wrapper) {
    return;
  }

  const $w = field.$wrapper;
  $w.empty();
  ensure_org_styles($w);

  frm._so = frm._so || {
    pool_mode: "employees",
    q: "",
    des: "",
    _clone_asked: false,
  };

  const employees = (frm.doc.employees || []).filter((e) => e.employee);
  const assets = (frm.doc.assets || []).filter((a) => a.asset);
  const groups = (frm.doc.group_headings || []).filter((g) => g.group);
  const mappings = frm.doc.shift_mappings || [];

  const empById = get_employee_by_id(frm);
  const assetById = get_asset_by_id(frm);

  const assignedEmployees = new Set(mappings.filter((m) => m.employee).map((m) => m.employee));
  const assignedAssets = new Set(
    mappings
      .filter((m) => m.row_type === "Asset" && m.asset && !m.missing_asset)
      .map((m) => m.asset)
  );

  const q = frm._so.q || "";
  const des = frm._so.des || "";
  const poolMode = frm._so.pool_mode || "employees";

  const employeeDesigs = unique_designations_from_employees(frm);
  const allDesignations = frm._so.all_designations || [];

  const poolEmployees = employees
    .filter((e) => !assignedEmployees.has(e.employee))
    .filter((e) => !des || e.designation === des)
    .filter((e) => {
      if (!q) {
        return true;
      }

      const hay = `${e.employee} ${e.employee_name || ""} ${e.designation || ""}`.toLowerCase();
      return hay.includes(q.toLowerCase());
    });

  const poolAssets = assets.filter((a) => {
    if (assignedAssets.has(a.asset)) {
      return false;
    }

    if (!q) {
      return true;
    }

    const hay = `${a.asset} ${a.item_name || ""} ${a.asset_category || ""}`.toLowerCase();
    return hay.includes(q.toLowerCase());
  });

  const poolDesignations = allDesignations.filter((d) => {
    if (!q) {
      return true;
    }

    return String(d).toLowerCase().includes(q.toLowerCase());
  });

  const poolControls = `
    <div class="so-tabs">
      <button class="so-tab ${poolMode === "employees" ? "is-active" : ""}" data-so-tab="employees">Employees</button>
      <button class="so-tab ${poolMode === "assets" ? "is-active" : ""}" data-so-tab="assets">Assets</button>
      <button class="so-tab ${poolMode === "designations" ? "is-active" : ""}" data-so-tab="designations">Designations</button>
    </div>
  `;

  const poolFilters =
    poolMode === "employees"
      ? `
        <div class="so-filters">
          <input class="form-control so-input" type="text" placeholder="Search employee…" value="${escape_html(q)}" data-so="pool-search">
        </div>
        <div class="so-filters">
          <select class="form-control so-select" data-so="des-filter">
            <option value="">All designations</option>
            ${employeeDesigs
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

  const poolList =
    poolMode === "employees"
      ? poolEmployees.map((e) => employee_card_html(e, "employee")).join("") ||
        `<div style="opacity:0.7;font-size:12px;">No unallocated employees match filters.</div>`
      : poolMode === "assets"
      ? poolAssets.map((a) => asset_card_html(a)).join("") ||
        `<div style="opacity:0.7;font-size:12px;">No assets match search.</div>`
      : poolDesignations.map((d) => designation_card_html(d)).join("") ||
        `<div style="opacity:0.7;font-size:12px;">No designations match search.</div>`;

  const poolTitle =
    poolMode === "employees"
      ? "Unallocated Employees"
      : poolMode === "assets"
      ? "Assets Pool"
      : "Designations Pool";

  const poolHtml = `
    <div class="so-panel so-right">
      <div class="so-panel__hd">
        <div class="so-panel__title">${poolTitle}</div>
        ${poolControls}
      </div>
      <div class="so-panel__bd">
        ${poolFilters}
        <div class="so-pool-drop" data-so-drop="pool">Drop here to unassign / remove row</div>
        <div class="so-pool">${poolList}</div>
      </div>
    </div>
  `;

  const groupsHtml = `
    <div class="so-left">
      ${
        (groups.length ? groups : [{ group: "No Groups Configured", shifts: "Shift Pattern" }])
          .map((g) => {
            const shifts = group_shifts(frm, g);
            const rows = ensure_group_rows_from_state(frm, g.group);

            const header = `
              <div class="so-grid__hdr">
                <div class="so-hcell so-h-left">Asset / Designation</div>
                ${shifts.map((s) => `<div class="so-hcell so-h-slot">${escape_html(s)}</div>`).join("")}
              </div>
            `;

            const rowHtml = rows
              .map((rowKey) => {
                const rowIdentity = row_identity_for_key(frm, g.group, rowKey);
                if (!rowIdentity) {
                  return "";
                }

                const status = rowIdentity.row_type === "Asset"
                  ? compute_asset_row_status(frm, g.group, rowKey, shifts)
                  : null;

                return `
                  <div class="so-grid__row so-rowdrag"
                       draggable="true"
                       data-so-drop="row"
                       data-group="${escape_html(g.group)}"
                       data-so-rowkey="${escape_html(rowKey)}">
                    <div class="so-leftcell">
                      ${render_row_label(frm, rowIdentity, assetById)}
                    </div>
                    ${
                      shifts
                        .map((shift) =>
                          render_slot_cell(frm, {
                            group: g.group,
                            shift,
                            row_key: rowKey,
                            empById,
                          })
                        )
                        .join("")
                    }
                  </div>
                `;
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
                    ${rowHtml || `<div style="padding:10px;opacity:.75;">Drop an Asset or Designation into this group to create rows.</div>`}
                  </div>
                </div>
              </div>
            `;
          })
          .join("")
      }
    </div>
  `;

  $w.append(`
    <div class="so-wrap">
      ${groupsHtml}
      ${poolHtml}
    </div>
  `);

  bind_events(frm, $w);
  restore_pool_focus_state(frm, $w);
}

// ---------------------------------------------------------------------
// UI events
// ---------------------------------------------------------------------

function bind_events(frm, $w) {
  $w.find("[data-so-tab]")
    .off("click")
    .on("click", async (ev) => {
      const mode = ev.currentTarget.getAttribute("data-so-tab");

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
        frm._so.q = ev.target.value || "";
        capture_pool_focus_state(frm, ev.target);
        render_site_organogram(frm);
      }, 150)
    );

  $w.find('[data-so="des-filter"]')
    .off("change")
    .on("change", (ev) => {
      frm._so.des = ev.target.value || "";
      frm._so._focus = null;
      render_site_organogram(frm);
    });

  $w.find("[data-so-desig-label='1']")
    .off("click")
    .on("click", async (ev) => {
      const group = ev.currentTarget.getAttribute("data-group");
      const oldRowKey = ev.currentTarget.getAttribute("data-rowkey");
      const oldLabel = ev.currentTarget.getAttribute("data-desig") || "";

      await ensure_designations_loaded(frm);

      const d = await so_select_dialog({
        title: "Change Designation Row",
        label: "Designation Row",
        options: frm._so.all_designations || [],
        default_value: oldLabel,
        primary_label: "Set",
      });

      if (!d || !d.choice) {
        return;
      }

      const info = parse_row_key(oldRowKey);
      const newRowKey = row_key_designation(d.choice, info.token || "");

      const rows = ensure_group_rows_from_state(frm, group).map((rk) => {
        return rk === oldRowKey ? newRowKey : rk;
      });

      save_group_rows(frm, group, rows);

      for (const m of frm.doc.shift_mappings || []) {
        if ((m.group || "") === group && (m.row_key || "") === oldRowKey) {
          frappe.model.set_value(m.doctype, m.name, "row_key", newRowKey);
          frappe.model.set_value(m.doctype, m.name, "row_label", d.choice);
          frappe.model.set_value(m.doctype, m.name, "row_type", "Designation");
          frappe.model.set_value(m.doctype, m.name, "asset", "");
          frappe.model.set_value(m.doctype, m.name, "missing_asset", 0);
        }
      }

      sync_row_order_for_group(frm, group, true);
      frm.refresh_field("shift_mappings");
      render_site_organogram(frm);
    });

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
        const payload = {
          type: "asset",
          asset: el.getAttribute("data-asset"),
        };

        ev.originalEvent.dataTransfer.setData("application/json", JSON.stringify(payload));
        ev.originalEvent.dataTransfer.effectAllowed = "move";
        return;
      }

      if (t === "designation") {
        const payload = {
          type: "designation",
          designation: el.getAttribute("data-designation"),
        };

        ev.originalEvent.dataTransfer.setData("application/json", JSON.stringify(payload));
        ev.originalEvent.dataTransfer.effectAllowed = "move";
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
    .on("dragleave", (ev) => {
      rmOver(ev.currentTarget);
    })
    .off("drop")
    .on("drop", async (ev) => {
      ev.preventDefault();
      rmOver(ev.currentTarget);

      const raw = ev.originalEvent.dataTransfer.getData("application/json");

      if (!raw) {
        return;
      }

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
        const rowKey = ev.currentTarget.getAttribute("data-rowkey");

        await assign_employee_to_cell(frm, {
          group,
          shift,
          row_key: rowKey,
          employee: data.employee,
        });
      }
    });
}

// ---------------------------------------------------------------------
// Drag/drop actions
// ---------------------------------------------------------------------

async function add_asset_row(frm, group, assetId) {
  if (!group || !assetId) {
    return;
  }

  const assetById = get_asset_by_id(frm);
  const asset = assetById.get(assetId);

  const rowKey = row_key_asset(assetId);
  const rowLabel = row_label_for_asset(asset);

  const rows = ensure_group_rows_from_state(frm, group);

  if (!rows.includes(rowKey)) {
    rows.push(rowKey);
    save_group_rows(frm, group, rows);
  }

  const grp = (frm.doc.group_headings || []).find((g) => g.group === group);

  if (grp) {
    const shifts = group_shifts(frm, grp);

    for (const shift of shifts) {
      const row = get_or_create_mapping_row(frm, {
        group,
        shift,
        row_key: rowKey,
        row_type: "Asset",
        row_label: rowLabel,
        asset: assetId,
      });

      row.row_type = "Asset";
      row.row_label = rowLabel;
      row.asset = assetId;
      row.missing_asset = 0;
    }
  }

  sync_row_order_for_group(frm, group, true);
  frm.refresh_field("shift_mappings");
  render_site_organogram(frm);
}

async function add_designation_row(frm, group, designation) {
  if (!group || !designation) {
    return;
  }

  const rowKey = row_key_designation(designation);

  const rows = ensure_group_rows_from_state(frm, group);

  if (!rows.includes(rowKey)) {
    rows.push(rowKey);
    save_group_rows(frm, group, rows);
  }

  const grp = (frm.doc.group_headings || []).find((g) => g.group === group);

  if (grp) {
    const shifts = group_shifts(frm, grp);

    for (const shift of shifts) {
      const row = get_or_create_mapping_row(frm, {
        group,
        shift,
        row_key: rowKey,
        row_type: "Designation",
        row_label: designation,
        asset: "",
      });

      row.row_type = "Designation";
      row.row_label = designation;
      row.asset = "";
      row.missing_asset = 0;
    }
  }

  sync_row_order_for_group(frm, group, true);
  frm.refresh_field("shift_mappings");
  render_site_organogram(frm);
}

async function reorder_rows(frm, group, movingKey, targetKey) {
  if (!group || !movingKey || !targetKey || movingKey === targetKey) {
    return;
  }

  const rows = ensure_group_rows_from_state(frm, group);
  const filtered = rows.filter((rk) => rk !== movingKey);
  const idx = filtered.indexOf(targetKey);

  if (idx === -1) {
    filtered.push(movingKey);
  } else {
    filtered.splice(idx, 0, movingKey);
  }

  save_group_rows(frm, group, filtered);
  sync_row_order_for_group(frm, group, true);

  frm.refresh_field("shift_mappings");
  render_site_organogram(frm);
}

async function remove_row_from_group(frm, group, rowKey) {
  if (!group || !rowKey) {
    return;
  }

  const rows = ensure_group_rows_from_state(frm, group).filter((rk) => rk !== rowKey);
  save_group_rows(frm, group, rows);

  remove_mapping_rows(frm, (r) => {
    return (r.group || "") === group && (r.row_key || "") === rowKey;
  });

  sync_row_order_for_group(frm, group, true);

  frm.refresh_field("shift_mappings");
  render_site_organogram(frm);
}

async function unassign_from_origin(frm, from) {
  if (!from || !from.rowname) {
    return;
  }

  const row = (frm.doc.shift_mappings || []).find((r) => r.name === from.rowname);

  if (!row) {
    return;
  }

  frappe.model.set_value(row.doctype, row.name, "employee", "");
  frappe.model.set_value(row.doctype, row.name, "missing_employee", 0);

  frm.refresh_field("shift_mappings");
  render_site_organogram(frm);
}

async function assign_employee_to_cell(frm, { group, shift, row_key, employee }) {
  if (!group || !shift || !row_key || !employee) {
    return;
  }

  const rowIdentity = row_identity_for_key(frm, group, row_key);

  if (!rowIdentity) {
    return;
  }

  remove_mapping_rows(frm, (r) => {
    return (
      (r.employee || "") === employee &&
      (r.group || "") === group &&
      (r.shift || "") === shift &&
      (r.row_key || "") === row_key
    );
  });

  const row = get_or_create_mapping_row(frm, {
    group,
    shift,
    row_key,
    row_type: rowIdentity.row_type || "Designation",
    row_label: rowIdentity.row_label || "",
    asset: rowIdentity.row_type === "Asset" ? rowIdentity.asset || "" : "",
  });

  row.row_type = rowIdentity.row_type || "Designation";
  row.row_label = rowIdentity.row_label || "";
  row.asset = rowIdentity.row_type === "Asset" ? rowIdentity.asset || "" : "";
  row.missing_asset = rowIdentity.missing_asset ? 1 : 0;

  frappe.model.set_value(row.doctype, row.name, "employee", employee);
  frappe.model.set_value(row.doctype, row.name, "missing_employee", 0);

  sync_row_order_for_group(frm, group, true);

  frm.refresh_field("shift_mappings");
  render_site_organogram(frm);
}

function capture_pool_focus_state(frm, inputEl) {
  frm._so = frm._so || {};

  frm._so._focus = {
    caretStart: inputEl && typeof inputEl.selectionStart === "number" ? inputEl.selectionStart : null,
    caretEnd: inputEl && typeof inputEl.selectionEnd === "number" ? inputEl.selectionEnd : null,
    shouldRestore: true,
  };
}

function restore_pool_focus_state(frm, $wrapper) {
  const st = frm._so && frm._so._focus;

  if (!st || !st.shouldRestore) {
    return;
  }

  const $input = $wrapper.find('[data-so="pool-search"]');

  if (!$input.length) {
    return;
  }

  const el = $input.get(0);
  el.focus();

  try {
    if (typeof st.caretStart === "number" && typeof st.caretEnd === "number") {
      el.setSelectionRange(st.caretStart, st.caretEnd);
    }
  } catch (e) {}

  st.shouldRestore = false;
}