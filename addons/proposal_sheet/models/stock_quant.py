from odoo import models, _, SUPERUSER_ID
from odoo.exceptions import UserError


class StockQuant(models.Model):
    _inherit = "stock.quant"

    def action_apply_inventory(self):
        # Chỉ bypass khi đi từ phiếu đề xuất
        if self.env.context.get("from_proposal_sheet_actual_stock"):
            records = self.sudo().with_user(SUPERUSER_ID)

            # đoạn này mô phỏng đúng flow apply tồn của stock.quant
            valid_records = records.filtered(
                lambda quant: quant.inventory_diff_quantity != 0 or quant.inventory_quantity_set
            )
            if not valid_records:
                return True

            return valid_records._apply_inventory_from_proposal()

        return super().action_apply_inventory()

    def _apply_inventory_from_proposal(self):
        self.ensure_one() if len(self) == 1 else None

        # dùng method lõi của Odoo nếu có
        if hasattr(super(StockQuant, self), "_apply_inventory"):
            return super(StockQuant, self)._apply_inventory()

        # fallback cho các bản khác nhau của stock
        if hasattr(self, "_apply_inventory"):
            return self._apply_inventory()

        raise UserError(_("Không tìm thấy method apply inventory phù hợp để override."))