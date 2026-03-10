/* @odoo-module */

import { ListRenderer } from "@web/views/list/list_renderer";
import { patch } from "@web/core/utils/patch";
import { onMounted, onPatched } from "@odoo/owl";

patch(ListRenderer.prototype, {
  setup() {
    super.setup(...arguments);

    const run = () => {
      this._somedEnsureRowNoHeaderFooter();
      this._somedFixAddRowCell(); // ✅ thêm
      this._somedFixColspan();
    };

    onMounted(run);
    onPatched(run);
  },

  _somedGetTable() {
    const root = this.tableRef?.el;
    if (!root) return null;
    if (root.tagName === "TABLE") return root;
    return (
      root.querySelector?.("table.o_list_table") ||
      root.querySelector?.("table") ||
      null
    );
  },

  _somedEnsureRowNoHeaderFooter() {
    const table = this._somedGetTable();
    if (!table) return;

    const theadRow = table.querySelector("thead tr");
    if (theadRow && !theadRow.querySelector("th.o_list_row_count_sheliya")) {
      const th = document.createElement("th");
      th.className = "o_list_row_number_header o_list_row_count_sheliya";
      th.style.textAlign = "center";
      th.style.width = "40px";
      th.textContent = "#";

      const before =
        theadRow.querySelector("th.o_list_record_selector") ||
        theadRow.firstElementChild;
      theadRow.insertBefore(th, before);
    }

    const footerRow = table.querySelector("tfoot tr");
    if (footerRow && !footerRow.querySelector("td.o_list_row_count_sheliya")) {
      const td = document.createElement("td");
      td.className = "o_list_row_count_sheliya";
      footerRow.insertBefore(td, footerRow.firstElementChild);
    }
  },

  // ✅ tách row "Thêm một dòng" để có border giữa cột #
  _somedFixAddRowCell() {
    const table = this._somedGetTable();
    if (!table) return;

    const theadRow = table.querySelector("thead tr");
    const colCount = theadRow?.children?.length || 0;
    if (!colCount) return;

    // ✅ BẮT ĐÚNG CASE ODOO 17: class nằm trên <td>, không phải <a>
    const ADD_LINK_SEL =
      "td.o_field_x2many_list_row_add, a.o_list_button_add, a.o_list_add_row, a.o_field_x2many_add_row";

    table.querySelectorAll("tbody > tr:not([data-id])").forEach((tr) => {
      const addRow = tr.querySelector(ADD_LINK_SEL);
      if (!addRow) return;

      // nếu đã có cell STT thì thôi
      if (tr.querySelector("td.o_list_row_count_sheliya")) return;

      const firstTd = tr.querySelector("td");
      if (!firstTd) return;

      // đa số add-row là 1 td colspan
      if (tr.children.length === 1 && firstTd.hasAttribute("colspan")) {
        const tdNo = document.createElement("td");
        tdNo.className = "o_list_row_count_sheliya";
        tdNo.tabIndex = -1;
        tr.insertBefore(tdNo, firstTd);

        // giảm colspan xuống 1 để tổng cột vẫn khớp
        const span = parseInt(
          firstTd.getAttribute("colspan") || String(colCount),
          10
        );
        firstTd.colSpan = Math.max(1, span - 1);
      }
    });
  },

  _somedFixColspan() {
    const table = this._somedGetTable();
    if (!table) return;

    const theadRow = table.querySelector("thead tr");
    if (!theadRow) return;

    const colCount = theadRow.children.length;

    table
      .querySelectorAll("tbody > tr:not([data-id]) td[colspan]")
      .forEach((td) => {
        const tr = td.closest("tr");
        const hasRowNo = !!tr?.querySelector("td.o_list_row_count_sheliya");
        // nếu đã tách add-row (có td STT) thì colspan phải là colCount-1
        td.colSpan = hasRowNo ? Math.max(1, colCount - 1) : colCount;
      });
  },

  freezeColumnWidths() {
    const res = super.freezeColumnWidths(...arguments);

    this._somedEnsureRowNoHeaderFooter();
    this._somedFixAddRowCell();
    this._somedFixColspan();

    Promise.resolve().then(() => {
      this._somedFixAddRowCell();
      this._somedFixColspan();
    });

    setTimeout(() => {
      this._somedFixAddRowCell();
      this._somedFixColspan();
    }, 0);

    return res;
  },
});
