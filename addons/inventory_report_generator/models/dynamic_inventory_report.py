# -*- coding: utf-8 -*-
import io
import json
import calendar
from datetime import date, datetime, time

from odoo import api, fields, models

try:
    from odoo.tools.misc import xlsxwriter
except ImportError:
    import xlsxwriter


class DynamicInventoryReport(models.Model):
    _name = "dynamic.inventory.report"
    _description = "Inventory Movement Summary (by period & location)"

    period_type = fields.Selection(
        [
            ("custom", "Custom Range"),
            ("month", "Month"),
            ("quarter", "Quarter"),
            ("year", "Year"),
        ],
        string="Period Type",
        default="custom",
        required=True,
    )

    date_from = fields.Date(string="Date From")
    date_to = fields.Date(string="Date To")
    month = fields.Selection([(str(i), str(i)) for i in range(1, 13)], string="Month")
    quarter = fields.Selection([("1", "Q1"), ("2", "Q2"), ("3", "Q3"), ("4", "Q4")], string="Quarter")
    year = fields.Integer(string="Year", default=lambda self: fields.Date.context_today(self).year)

    location_id = fields.Many2one("stock.location", string="Location")
    company_id = fields.Many2one("res.company", string="Company", default=lambda self: self.env.company)

    # -----------------
    # Helpers
    # -----------------

    def _compute_date_range(self, rec):
        """Return (start_date, end_date) as python date objects."""
        today = fields.Date.context_today(self)
        y = int(rec.year or today.year)

        if rec.period_type == "custom":
            dfrom = rec.date_from or today
            dto = rec.date_to or today
            if dto < dfrom:
                dfrom, dto = dto, dfrom
            return dfrom, dto

        if rec.period_type == "month":
            m = int(rec.month or today.month)
            last_day = calendar.monthrange(y, m)[1]
            return date(y, m, 1), date(y, m, last_day)

        if rec.period_type == "quarter":
            q = int(rec.quarter or 1)
            q = 1 if q < 1 else (4 if q > 4 else q)
            start_m = (q - 1) * 3 + 1
            end_m = start_m + 2
            last_day = calendar.monthrange(y, end_m)[1]
            return date(y, start_m, 1), date(y, end_m, last_day)

        # year
        return date(y, 1, 1), date(y, 12, 31)

    def _dt_range(self, start_d, end_d):
        start_dt = datetime.combine(start_d, time.min)
        end_dt = datetime.combine(end_d, time.max).replace(microsecond=0)
        return start_dt, end_dt

    def _get_location_ids(self, rec):
        Location = self.env["stock.location"]
        company_id = rec.company_id.id if rec.company_id else self.env.company.id

        if rec.location_id:
            # gồm cả location con
            return Location.search([("id", "child_of", rec.location_id.id)]).ids

        # all internal locations of this company (or shared locations)
        return Location.search([
            ("usage", "=", "internal"),
            "|", ("company_id", "=", False), ("company_id", "=", company_id),
        ]).ids

    def _ml_qty_field(self):
        """
        Auto-detect qty field on stock.move.line.
        - Odoo 17 chuẩn là qty_done
        - Một số DB/custom có thể là quantity_done hoặc quantity
        """
        SML = self.env["stock.move.line"].sudo()
        for f in ("qty_done", "quantity_done", "quantity", "product_uom_qty"):
            if f in SML._fields:
                return f
        raise ValueError(
            "Không tìm thấy field số lượng trên stock.move.line "
            "(qty_done/quantity_done/quantity/product_uom_qty)."
        )

    def _ml_date_field(self):
        """Prefer done date for accurate period filter."""
        SML = self.env["stock.move.line"].sudo()

        # 1) nếu move line có date thì dùng
        if "date" in SML._fields:
            return "date"

        # 2) ưu tiên done date của picking nếu có
        Move = self.env["stock.move"].sudo()
        Picking = self.env["stock.picking"].sudo()
        if "picking_id" in Move._fields and "date_done" in Picking._fields:
            return "move_id.picking_id.date_done"

        # 3) fallback
        return "move_id.date"

    def _rg_qty_by_product(self, domain):
        """Return dict {product_id: qty_sum} on stock.move.line."""
        SML = self.env["stock.move.line"].sudo()
        qty_field = self._ml_qty_field()

        # ✅ read_group sẽ SUM field numeric
        res = SML.read_group(domain, [qty_field], ["product_id"])
        out = {}
        for r in res:
            pid = r.get("product_id") and r["product_id"][0]
            if pid:
                out[pid] = float(r.get(qty_field, 0.0) or 0.0)
        return out

    # -----------------
    # RPC
    # -----------------

    @api.model
    def inventory_report(self, option):
        wizard_id = option[0] if isinstance(option, (list, tuple)) and option else option
        rec = self.browse(wizard_id).exists()
        if not rec:
            return {"name": "Inventory Movement Summary", "orders": {}, "filters": {}, "report_lines": []}

        start_d, end_d = self._compute_date_range(rec)
        start_dt, end_dt = self._dt_range(start_d, end_d)

        loc_ids = self._get_location_ids(rec)
        if not loc_ids:
            return {
                "name": "Inventory Movement Summary",
                "type": "ir.actions.client",
                "tag": "inv_r",
                "orders": {},
                "filters": {},
                "report_lines": [],
            }

        company_id = rec.company_id.id if rec.company_id else self.env.company.id
        date_field = self._ml_date_field()

        # Base domain on MOVE LINE
        base = [
            ("move_id.state", "=", "done"),
            ("product_id.detailed_type", "=", "product"),
            ("move_id.company_id", "=", company_id),
        ]

        # ✅ Giữ như bạn: không loại internal transfer
        exclude_internal_transfers = False

        if exclude_internal_transfers:
            in_extra = [("location_dest_id", "in", loc_ids), ("location_id", "not in", loc_ids)]
            out_extra = [("location_id", "in", loc_ids), ("location_dest_id", "not in", loc_ids)]
        else:
            in_extra = [("location_dest_id", "in", loc_ids)]
            out_extra = [("location_id", "in", loc_ids)]

        start_dt_s = fields.Datetime.to_string(start_dt)
        end_dt_s = fields.Datetime.to_string(end_dt)

        # Opening (< start_dt)
        opening_in = self._rg_qty_by_product(base + in_extra + [(date_field, "<", start_dt_s)])
        opening_out = self._rg_qty_by_product(base + out_extra + [(date_field, "<", start_dt_s)])

        # Period (between)
        in_map = self._rg_qty_by_product(base + in_extra + [(date_field, ">=", start_dt_s), (date_field, "<=", end_dt_s)])
        out_map = self._rg_qty_by_product(base + out_extra + [(date_field, ">=", start_dt_s), (date_field, "<=", end_dt_s)])

        product_ids = sorted(set(opening_in) | set(opening_out) | set(in_map) | set(out_map))
        products = self.env["product.product"].sudo().browse(product_ids).exists()

        lines = []
        for p in products:
            opening_qty = float(opening_in.get(p.id, 0.0)) - float(opening_out.get(p.id, 0.0))
            in_qty = float(in_map.get(p.id, 0.0))
            out_qty = float(out_map.get(p.id, 0.0))
            closing_qty = opening_qty + in_qty - out_qty

            # nếu muốn show cả dòng 0 thì bỏ đoạn này
            if not opening_qty and not in_qty and not out_qty and not closing_qty:
                continue

            lines.append({
                "product_id": p.id,
                "product_name": p.display_name,
                "uom": p.uom_id.name,
                "opening_qty": opening_qty,
                "in_qty": in_qty,
                "out_qty": out_qty,
                "closing_qty": closing_qty,
            })

        lines.sort(key=lambda x: (x.get("product_name") or ""))

        period_label = {
            "custom": "Custom",
            "month": "Month",
            "quarter": "Quarter",
            "year": "Year"
        }.get(rec.period_type, "Custom")

        filters = {
            "period_type": period_label,
            "date_from": fields.Date.to_string(start_d),
            "date_to": fields.Date.to_string(end_d),
            "location": rec.location_id.complete_name if rec.location_id else "All internal locations",
        }

        # orders = dữ liệu thô wizard, để JS sync state
        orders = {
            "period_type": rec.period_type,
            "date_from": fields.Date.to_string(rec.date_from) if rec.date_from else False,
            "date_to": fields.Date.to_string(rec.date_to) if rec.date_to else False,
            "month": rec.month,
            "quarter": rec.quarter,
            "year": rec.year,
            "location_id": rec.location_id.id if rec.location_id else False,
            "computed_date_from": fields.Date.to_string(start_d),
            "computed_date_to": fields.Date.to_string(end_d),
            "company_id": company_id,
        }

        return {
            "name": "Inventory Movement Summary",
            "type": "ir.actions.client",
            "tag": "inv_r",
            "orders": orders,
            "filters": filters,
            "report_lines": lines,
        }

    # -----------------
    # XLSX
    # -----------------

    def get_inventory_xlsx_report(self, data, response, report_data, dfr_data):
        orders = json.loads(data or "{}")
        report_lines = json.loads(report_data or "[]")

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        sheet = workbook.add_worksheet("Inventory")

        head = workbook.add_format({"align": "center", "bold": True, "font_size": 16})
        th = workbook.add_format({"align": "center", "bold": True, "border": 1})
        td = workbook.add_format({"border": 1})
        num = workbook.add_format({"border": 1, "align": "right"})

        sheet.merge_range("A1:F1", "Inventory Movement Summary", head)

        sheet.write("A3", "Period:", th)
        sheet.write(
            "B3",
            f"{orders.get('period_type','')}  {orders.get('computed_date_from','')} -> {orders.get('computed_date_to','')}",
            td,
        )

        loc_name = "All internal locations"
        loc_id = orders.get("location_id")
        if loc_id:
            loc = self.env["stock.location"].browse(int(loc_id)).exists()
            if loc:
                loc_name = loc.complete_name

        sheet.write("A4", "Location:", th)
        sheet.write("B4", loc_name, td)

        row = 5
        sheet.write(row, 0, "Product", th)
        sheet.write(row, 1, "UoM", th)
        sheet.write(row, 2, "Opening", th)
        sheet.write(row, 3, "In", th)
        sheet.write(row, 4, "Out", th)
        sheet.write(row, 5, "Closing", th)

        sheet.set_column(0, 0, 40)
        sheet.set_column(1, 1, 12)
        sheet.set_column(2, 5, 14)

        for line in report_lines:
            row += 1
            sheet.write(row, 0, line.get("product_name", ""), td)
            sheet.write(row, 1, line.get("uom", ""), td)
            sheet.write_number(row, 2, float(line.get("opening_qty") or 0.0), num)
            sheet.write_number(row, 3, float(line.get("in_qty") or 0.0), num)
            sheet.write_number(row, 4, float(line.get("out_qty") or 0.0), num)
            sheet.write_number(row, 5, float(line.get("closing_qty") or 0.0), num)

        workbook.close()
        output.seek(0)
        response.stream.write(output.read())
        output.close()
