/** @odoo-module **/

import { ListRenderer } from "@web/views/list/list_renderer";
import { patch } from "@web/core/utils/patch";

patch(ListRenderer.prototype, {
  renderHeader() {
    const thead = super.renderHeader();

    if (this.props.list.resModel === "project.profit.lost") {
      // kiểm tra nếu chưa chèn header thì thêm vào
      if (!thead.querySelector(".custom-parent-header")) {
        const parentRow = document.createElement("tr");
        parentRow.classList.add("custom-parent-header");
        parentRow.innerHTML = `
                    <th rowspan="2">STT</th>
                    <th rowspan="2">Dự án</th>
                    <th colspan="2" class="text-center">Hợp đồng</th>
                    <th rowspan="2">Số tiền đã thanh toán</th>
                    <th colspan="4" class="text-center">Chi phí</th>
                    <th rowspan="2">Lãi / Lỗ</th>
                `;
        // chèn lên đầu trước dòng header gốc
        thead.prepend(parentRow);
      }
    }

    return thead;
  },
});
