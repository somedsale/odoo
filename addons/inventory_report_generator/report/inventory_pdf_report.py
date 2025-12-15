from odoo import api, models

class InventoryPDFReport(models.AbstractModel):
    _name = "report.inventory_report_generator.inventory_pdf_report"
    def _fmt_vn(self, val, digits=0, strip_zeros=False):
        v = float(val or 0.0)
        s = f"{v:,.{digits}f}"  # 1,234.50
        s = s.replace(",", "X").replace(".", ",").replace("X", ".")  # 1.234,50
        if strip_zeros and digits:
            s = s.rstrip("0").rstrip(",")
        if digits == 0:
            s = s.split(",")[0]
        return s

    @api.model
    def _get_report_values(self, docids, data=None):
        data = data or {}

        if self.env.context.get("inventory_pdf_report") and data:
            report_data = data.get("report_data") or {}

            data.update({
                "report_main_line_data": report_data.get("report_lines", []),
                "Filters": report_data.get("filters", {}),
                "Dates": report_data.get("orders", {}),
                # ✅ thêm Totals để template dùng được
                "Totals": report_data.get("totals", {}),
                "company": self.env.company,
                "fmt_qty": lambda v: self._fmt_vn(v, digits=2, strip_zeros=True),
            "fmt_val": lambda v: self._fmt_vn(v, digits=0),
            })

        return data
