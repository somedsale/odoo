# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
import io
import base64
from odoo.tools.misc import xlsxwriter

class ProjectProfitDetailWizard(models.TransientModel):
    _name = "profit.detail.wizard"
    _description = "Wizard chọn công trình in lãi lỗ chi tiết"

    report_scope = fields.Selection([
        ('summary', 'Tổng hợp tất cả công trình'),
        ('detail', 'Chi tiết 1 công trình'),
    ], default='summary', required=True)

    project_id = fields.Many2one(
        "project.project",
        string="Chọn công trình",
        domain=[("active", "=", True)],
    )

    def action_print_report(self):
        self.ensure_one()

        ProfitLost = self.env["project.profit.lost"]

        # ===== CHI TIẾT =====
        if self.report_scope == 'detail':
            if not self.project_id:
                raise UserError("Vui lòng chọn công trình.")

            profit = ProfitLost.search(
                [("project_id", "=", self.project_id.id)],
                limit=1
            )

            if not profit:
                profit = ProfitLost.create({
                    "project_id": self.project_id.id,
                })

            if hasattr(profit, "_recompute_values"):
                profit._recompute_values()

            return self.env.ref(
                "custom_project_profit_report.project_profit_detail_report"
            ).report_action(profit)

        # ===== TỔNG HỢP =====
        else:
            # không cần docids, report summary tự search
            return self.env.ref(
                "custom_project_profit_report.action_report_project_profit"
            ).report_action(self)
        
    def action_export_excel(self):
        self.ensure_one()
        ProfitLost = self.env["project.profit.lost"]
        company = self.env.company

        company_name = company.name or ""
        company_address = ", ".join(filter(None, [
            company.street,
            company.street2,
            company.city,
            company.state_id.name if company.state_id else None,
            company.country_id.name if company.country_id else None,
        ]))
        company_vat = company.vat or ""

        # =====================================================
        # TỔNG HỢP / CHI TIẾT – FORMAT DÙNG CHUNG
        # =====================================================
        def init_common_formats(wb):
            return {
                "fmt_company_name": wb.add_format({"bold": True, "font_size": 11}),
                "fmt_company_info": wb.add_format({"font_size": 10}),
                "fmt_title": wb.add_format({
                    "bold": True, "font_size": 16,
                    "align": "center", "valign": "vcenter"
                }),
                "fmt_group": wb.add_format({
                    "bold": True, "border": 1,
                    "align": "center", "valign": "vcenter",
                    "bg_color": "#E2EFDA"
                }),
                "fmt_head": wb.add_format({
                    "bold": True, "border": 1,
                    "align": "center", "valign": "vcenter",
                    "bg_color": "#C6E0B4",
                    "text_wrap": True
                }),
                "fmt_stt": wb.add_format({
                    "border": 1, "align": "center", "valign": "vcenter"
                }),
                "fmt_text_center": wb.add_format({
                    "border": 1, "align": "center",
                    "valign": "vcenter", "text_wrap": True
                }),
                "fmt_text_left": wb.add_format({
                    "border": 1, "align": "left",
                    "valign": "top", "text_wrap": True
                }),
                "fmt_money": wb.add_format({
                    "border": 1, "num_format": "#,##0",
                    "align": "right", "valign": "vcenter"
                }),
                "fmt_money_bold": wb.add_format({
                    "border": 1, "num_format": "#,##0",
                    "bold": True, "align": "right", "valign": "vcenter"
                }),
            }

        # =====================================================
        # CHI TIẾT
        # =====================================================
        if self.report_scope == "detail":
            if not self.project_id:
                raise UserError("Vui lòng chọn công trình.")

            profit = ProfitLost.search(
                [("project_id", "=", self.project_id.id)], limit=1
            )
            if not profit:
                raise UserError("Chưa có dữ liệu lãi lỗ cho công trình này.")

            if hasattr(profit, "_recompute_values"):
                profit._recompute_values()

            detail_ids = profit.detail_ids.sorted(key=lambda l: l.date or False)
            title = f"CHI TIẾT LÃI LỖ - {profit.project_id.name}"

            output = io.BytesIO()
            wb = xlsxwriter.Workbook(output, {"in_memory": True})
            ws = wb.add_worksheet("Chi tiết")
            F = init_common_formats(wb)

            ws.set_column("A:A", 5)
            ws.set_column("B:O", 16)
            ws.set_column("P:P", 40)

            # LOGO + INFO
            if company.logo:
                ws.insert_image(
                    0, 0, "logo.png",
                    {"image_data": io.BytesIO(base64.b64decode(company.logo)),
                    "x_scale": 1, "y_scale": 1}
                )

            ws.merge_range(0, 2, 0, 8, company_name, F["fmt_company_name"])
            ws.merge_range(1, 2, 1, 8, f"Địa chỉ: {company_address}", F["fmt_company_info"])
            ws.merge_range(2, 2, 2, 8, f"MST: {company_vat}", F["fmt_company_info"])

            ws.merge_range(4, 0, 4, 15, title, F["fmt_title"])
            row = 6

            # HEADER
            ws.merge_range(row, 0, row + 1, 0, "STT", F["fmt_group"])
            ws.merge_range(row, 1, row, 2, "HỢP ĐỒNG", F["fmt_group"])
            ws.merge_range(row, 3, row, 4, "QUYẾT TOÁN", F["fmt_group"])
            ws.merge_range(row, 5, row, 6, "HÓA ĐƠN", F["fmt_group"])
            ws.merge_range(row, 7, row + 1, 7, "Đã TT", F["fmt_group"])
            ws.merge_range(row, 8, row + 1, 8, "Cần thu", F["fmt_group"])
            ws.merge_range(row, 9, row, 13, "CHI PHÍ", F["fmt_group"])
            ws.merge_range(row, 14, row + 1, 14, "Lãi / Lỗ", F["fmt_group"])
            ws.merge_range(row, 15, row + 1, 15, "Ghi chú", F["fmt_group"])

            row += 1
            ws.write_row(row, 1, ["Số HĐ", "Giá trị HĐ"], F["fmt_head"])
            ws.write_row(row, 3, ["Giá trị", "Thuế"], F["fmt_head"])
            ws.write_row(row, 5, ["Giá trị", "Thuế"], F["fmt_head"])
            ws.write_row(row, 9, ["Ngày", "Vật tư", "Nhân công", "SXC", "Tổng CP"], F["fmt_head"])

            ws.freeze_panes(row + 1, 0)
            row += 1

            settlement_tax = sum(profit.settlement_ids.mapped("amount_tax"))
            invoice_tax = sum(profit.invoice_ids.mapped("amount_tax"))

            stt = 1
            for line in detail_ids:
                ws.write(row, 0, stt, F["fmt_stt"])

                if stt == 1:
                    ws.write(row, 1, profit.num_contract or "", F["fmt_text_center"])
                    ws.write(row, 2, profit.contract_value or 0, F["fmt_money"])
                    ws.write(row, 3, profit.settlement_value or 0, F["fmt_money"])
                    ws.write(row, 4, settlement_tax or 0, F["fmt_money"])
                    ws.write(row, 5, profit.invoice_amount or 0, F["fmt_money"])
                    ws.write(row, 6, invoice_tax or 0, F["fmt_money"])
                    ws.write(row, 7, profit.revenue or 0, F["fmt_money"])
                    ws.write(row, 8, profit.receivable_amount or 0, F["fmt_money"])
                else:
                    ws.write_row(row, 1, [""] * 8, F["fmt_text_center"])

                ws.write(row, 9, line.date.strftime("%d/%m/%Y") if line.date else "", F["fmt_text_center"])
                ws.write(row, 10, line.material_amount or 0, F["fmt_money"])
                ws.write(row, 11, line.labor_amount or 0, F["fmt_money"])
                ws.write(row, 12, line.other_amount or 0, F["fmt_money"])
                ws.write(row, 13, line.total_amount or 0, F["fmt_money"])
                ws.write(row, 14, profit.profit or 0, F["fmt_money"])
                ws.write(row, 15, line.description or "", F["fmt_text_left"])

                ws.set_row(row, None, None, {"text_wrap": True})
                row += 1
                stt += 1

            wb.close()
            output.seek(0)
            filename = f"{title}.xlsx"

        # =====================================================
        # TỔNG HỢP
        # =====================================================
        else:
            ProfitLost.load_all_projects()
            pls = ProfitLost.search([
                ("active", "=", True),
                ("project_id.is_internal_project2", "=", False),
                ("project_id", "!=", 4),
            ])

            title = "BÁO CÁO TỔNG HỢP LÃI LỖ CÁC CÔNG TRÌNH"

            output = io.BytesIO()
            wb = xlsxwriter.Workbook(output, {"in_memory": True})
            ws = wb.add_worksheet("Tổng hợp")
            F = init_common_formats(wb)

            ws.set_column("A:A", 5)
            ws.set_column("B:B", 35)
            ws.set_column("C:N", 16)

            if company.logo:
                ws.insert_image(
                    0, 0, "logo.png",
                    {"image_data": io.BytesIO(base64.b64decode(company.logo)),
                    "x_scale": 1, "y_scale": 1}
                )

            ws.merge_range(0, 2, 0, 8, company_name, F["fmt_company_name"])
            ws.merge_range(1, 2, 1, 8, f"Địa chỉ: {company_address}", F["fmt_company_info"])
            ws.merge_range(2, 2, 2, 8, f"MST: {company_vat}", F["fmt_company_info"])

            ws.merge_range(4, 0, 4, 12, title, F["fmt_title"])
            row = 6

            ws.merge_range(row, 0, row + 1, 0, "STT", F["fmt_group"])
            ws.merge_range(row, 1, row + 1, 1, "Dự án", F["fmt_group"])
            ws.merge_range(row, 2, row, 3, "HỢP ĐỒNG", F["fmt_group"])
            ws.merge_range(row, 4, row + 1, 4, "Giá trị quyết toán", F["fmt_group"])
            ws.merge_range(row, 5, row + 1, 5, "Số tiền hóa đơn", F["fmt_group"])
            ws.merge_range(row, 6, row + 1, 6, "Đã thanh toán", F["fmt_group"])
            ws.merge_range(row, 7, row + 1, 7, "Nợ phải thu", F["fmt_group"])
            ws.merge_range(row, 8, row, 11, "CHI PHÍ", F["fmt_group"])
            ws.merge_range(row, 12, row + 1, 12, "Lãi / Lỗ", F["fmt_group"])

            row += 1
            ws.write_row(row, 2, ["Số HĐ", "Giá trị HĐ"], F["fmt_head"])
            ws.write_row(row, 8, ["Nguyên vật liệu", "Nhân công", "SXC", "Tổng chi phí"], F["fmt_head"])

            ws.freeze_panes(row + 1, 0)
            row += 1

            ws.merge_range(row, 0, row, 2, "TỔNG CỘNG", F["fmt_group"])
            ws.write(row, 3, sum(pls.mapped("contract_value")), F["fmt_money_bold"])
            ws.write(row, 4, sum(pls.mapped("settlement_value")), F["fmt_money_bold"])
            ws.write(row, 5, sum(pls.mapped("invoice_amount")), F["fmt_money_bold"])
            ws.write(row, 6, sum(pls.mapped("revenue")), F["fmt_money_bold"])
            ws.write(row, 7, sum(pls.mapped("receivable_amount")), F["fmt_money_bold"])
            ws.write(row, 8, sum(pls.mapped("material_cost")), F["fmt_money_bold"])
            ws.write(row, 9, sum(pls.mapped("labor_cost")), F["fmt_money_bold"])
            ws.write(row, 10, sum(pls.mapped("other_cost")), F["fmt_money_bold"])
            ws.write(row, 11, sum(pls.mapped("expense")), F["fmt_money_bold"])
            ws.write(row, 12, sum(pls.mapped("profit")), F["fmt_money_bold"])

            row += 1
            stt = 1
            for rec in pls:
                ws.write(row, 0, stt, F["fmt_stt"])
                ws.write(row, 1, rec.project_id.name or "", F["fmt_text_left"])
                ws.write(row, 2, rec.num_contract or "", F["fmt_text_center"])
                ws.write(row, 3, rec.contract_value or 0, F["fmt_money"])
                ws.write(row, 4, rec.settlement_value or 0, F["fmt_money"])
                ws.write(row, 5, rec.invoice_amount or 0, F["fmt_money"])
                ws.write(row, 6, rec.revenue or 0, F["fmt_money"])
                ws.write(row, 7, rec.receivable_amount or 0, F["fmt_money"])
                ws.write(row, 8, rec.material_cost or 0, F["fmt_money"])
                ws.write(row, 9, rec.labor_cost or 0, F["fmt_money"])
                ws.write(row, 10, rec.other_cost or 0, F["fmt_money"])
                ws.write(row, 11, rec.expense or 0, F["fmt_money"])
                ws.write(row, 12, rec.profit or 0, F["fmt_money"])
                ws.set_row(row, None, None, {"text_wrap": True})
                row += 1
                stt += 1

            wb.close()
            output.seek(0)
            filename = f"{title}.xlsx"

        attachment = self.env["ir.attachment"].create({
            "name": filename,
            "type": "binary",
            "datas": base64.b64encode(output.read()),
            "res_model": self._name,
            "res_id": self.id,
            "mimetype": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "description": "TEMP_EXPORT_EXCEL",
        })

        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{attachment.id}?download=true",
            "target": "self",
        }


