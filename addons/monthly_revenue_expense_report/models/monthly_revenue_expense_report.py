# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from datetime import date
from dateutil.relativedelta import relativedelta
from collections import defaultdict
from odoo.exceptions import UserError
import io
import base64
from odoo.exceptions import UserError
from odoo.tools.misc import xlsxwriter



class MonthlyRevenueExpenseReport(models.TransientModel):
    _name = 'monthly.revenue.expense.report'
    _description = 'Báo cáo doanh thu - chi phí hàng tháng'
    period_type = fields.Selection(
    [
        ('month', 'Theo tháng'),
        ('quarter', 'Theo quý'),
        ('year', 'Theo năm'),
    ],
    string='Kỳ báo cáo',
    required=True,
    default='month'
)
    quarter = fields.Selection(
    [
        ('1', 'Quý I'),
        ('2', 'Quý II'),
        ('3', 'Quý III'),
        ('4', 'Quý IV'),
    ],
    string='Quý'
)

    month = fields.Selection(
        [(str(m), f'Tháng {m}') for m in range(1, 13)],
        string='Tháng', required=True, default=lambda self: str(date.today().month)
    )
    year = fields.Integer(
        string='Năm', required=True, default=lambda self: date.today().year
    )
    def _get_date_range(self):
        self.ensure_one()
        year = int(self.year)

        if self.period_type == 'month':
            month = int(self.month)
            date_from = date(year, month, 1)
            date_to = date_from + relativedelta(months=1, days=-1)

        elif self.period_type == 'quarter':
            if not self.quarter:
                raise UserError(_("Vui lòng chọn Quý"))
            q = int(self.quarter)
            month_from = (q - 1) * 3 + 1
            date_from = date(year, month_from, 1)
            date_to = date_from + relativedelta(months=3, days=-1)

        else:  # year
            date_from = date(year, 1, 1)
            date_to = date(year, 12, 31)
        return date_from, date_to

    def action_view_report(self):
        self.ensure_one()
        date_from, date_to = self._get_date_range()

        data = {
            'period_type': self.period_type,
            'month': self.month,
            'quarter': self.quarter,
            'year': self.year,
            'date_from': date_from,
            'date_to': date_to,
        }

        return self.env.ref(
            'monthly_revenue_expense_report.report_monthly_revenue_expense_action_html'
        ).report_action(self, data=data)
    def action_export_excel(self):
        self.ensure_one()

        # Lấy data y như report HTML
        report_model = self.env['report.monthly_revenue_expense_report.report_template']
        date_from, date_to = self._get_date_range()

        vals = report_model._get_report_values([], data={
            'period_type': self.period_type,
            'month': self.month,
            'quarter': self.quarter,
            'year': self.year,
            'date_from': date_from,
            'date_to': date_to,
        })

        month = int(vals['month'])
        year = int(vals['year'])
        period_type = vals.get('period_type')
        year = int(vals.get('year'))

        if period_type == 'month':
            month = int(vals.get('month'))
            period_label = f"THÁNG {month} NĂM {year}"
            period_code = f"T{month}-{year}"

        elif period_type == 'quarter':
            quarter = vals.get('quarter')
            period_label = f"QUÝ {quarter} NĂM {year}"
            period_code = f"Q{quarter}-{year}"

        else:  # year
            period_label = f"NĂM {year}"
            period_code = f"Y{year}"

        revenue_data = vals.get("revenue_data") or []
        expense_data = vals.get("expense_data") or []

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
        # FORMAT (GIỐNG THẰNG LÃI LỖ)
        # =====================================================
        def init_formats(wb):
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
        # BUILD FILE
        # =====================================================
        output = io.BytesIO()
        wb = xlsxwriter.Workbook(output, {"in_memory": True})
        ws = wb.add_worksheet(period_code)
        F = init_formats(wb)

        ws.set_column("A:A", 6)      # STT
        ws.set_column("B:B", 70)     # Nội dung (RỘNG hơn nhiều)
        ws.set_column("C:C", 20)     # Doanh thu
        ws.set_column("D:D", 20)     # Chi phí
        ws.set_column("E:E", 22) 

        # LOGO + INFO
        if company.logo:
            ws.insert_image(
                0, 0, "logo.png",
                {"image_data": io.BytesIO(base64.b64decode(company.logo))}
            )

        ws.merge_range(0, 2, 0, 6, company_name, F["fmt_company_name"])
        ws.merge_range(1, 2, 1, 6, f"Địa chỉ: {company_address}", F["fmt_company_info"])
        ws.merge_range(2, 2, 2, 6, f"MST: {company_vat}", F["fmt_company_info"])

        ws.merge_range(4, 0, 4, 6,
            f"BÁO CÁO DOANH THU - CHI PHÍ {period_label}",
            F["fmt_title"]
        )
        ws.set_row(4, 36)

        row = 6
        # HEADER TABLE
        ws.write_row(row, 0, ["STT", "Nội dung", "Doanh thu", "Chi phí", "Chênh lệch"], F["fmt_head"])
        ws.set_row(row, 26)
        ws.freeze_panes(row + 1, 0)
        row += 1
        total_revenue = vals.get("total_revenue", 0.0) or 0.0
        total_expense = vals.get("total_expense", 0.0) or 0.0
        net_profit = total_revenue - total_expense

        ws.merge_range(row, 0, row, 1, "TỔNG CỘNG", F["fmt_group"])
        ws.write(row, 2, total_revenue, F["fmt_money_bold"])
        ws.write(row, 3, total_expense, F["fmt_money_bold"])
        ws.write(row, 4, net_profit, F["fmt_money_bold"])

        # cho dòng tổng nổi bật hơn
        ws.set_row(row, 28)

        row += 1

        # =====================================================
        # I. DOANH THU
        # =====================================================
        total_revenue = vals.get("total_revenue", 0.0) or 0.0

        ws.merge_range(row, 0, row, 1, "I. DOANH THU", F["fmt_group"])
        ws.write(row, 2, total_revenue, F["fmt_money_bold"])
        ws.write(row, 3, 0, F["fmt_money_bold"])
        ws.write(row, 4, total_revenue, F["fmt_money_bold"])
        row += 1

        stt = 1
        for grp in revenue_data:
            ws.merge_range(row, 0, row, 1, grp["type_label"], F["fmt_group"])
            ws.write(row, 2, grp["subtotal"], F["fmt_money_bold"])
            ws.write(row, 3, 0, F["fmt_money_bold"])
            ws.write(row, 4, grp["subtotal"], F["fmt_money_bold"])
            row += 1

            for line in grp.get("projects", []):
                ws.write(row, 0, stt, F["fmt_stt"])
                ws.write(row, 1, line["name"], F["fmt_text_left"])
                ws.write(row, 2, line["revenue"], F["fmt_money"])
                ws.write(row, 3, 0, F["fmt_money"])
                ws.write(row, 4, line["revenue"], F["fmt_money"])
                row += 1
                stt += 1

        row += 1

        # =====================================================
        # II. CHI PHÍ
        # =====================================================
        total_expense = vals.get("total_expense", 0.0) or 0.0

        ws.merge_range(row, 0, row, 1, "II. CHI PHÍ", F["fmt_group"])
        ws.write(row, 2, 0, F["fmt_money_bold"])
        ws.write(row, 3, total_expense, F["fmt_money_bold"])
        ws.write(row, 4, -total_expense, F["fmt_money_bold"])
        row += 1

        stt = 1
        for grp in expense_data:
            ws.merge_range(row, 0, row, 1, grp["type_label"], F["fmt_group"])
            ws.write(row, 2, 0, F["fmt_money_bold"])
            ws.write(row, 3, grp["subtotal"], F["fmt_money_bold"])
            ws.write(row, 4, -grp["subtotal"], F["fmt_money_bold"])
            row += 1

            if grp.get("subgroups"):
                for sub in grp["subgroups"]:
                    ws.merge_range(row, 0, row, 1, sub["sub_label"], F["fmt_group"])
                    ws.write(row, 2, 0, F["fmt_money_bold"])
                    ws.write(row, 3, sub["subtotal"], F["fmt_money_bold"])
                    ws.write(row, 4, -sub["subtotal"], F["fmt_money_bold"])
                    row += 1

                    for line in sub["lines"]:
                        ws.write(row, 0, stt, F["fmt_stt"])
                        ws.write(row, 1, line["name"], F["fmt_text_left"])
                        ws.write(row, 2, 0, F["fmt_money"])
                        ws.write(row, 3, line["expense"], F["fmt_money"])
                        ws.write(row, 4, -line["expense"], F["fmt_money"])
                        row += 1
                        stt += 1
            else:
                for line in grp["lines"]:
                    ws.write(row, 0, stt, F["fmt_stt"])
                    ws.write(row, 1, line["name"], F["fmt_text_left"])
                    ws.write(row, 2, 0, F["fmt_money"])
                    ws.write(row, 3, line["expense"], F["fmt_money"])
                    ws.write(row, 4, -line["expense"], F["fmt_money"])
                    row += 1
                    stt += 1

            row += 1

        wb.close()
        output.seek(0)

        filename = f"BAO_CAO_DOANH_THU_CHI_PHI_{period_code}.xlsx"
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


class AccountReceiptReport(models.AbstractModel):
    _name = 'report.monthly_revenue_expense_report.report_template'
    _description = 'Render báo cáo doanh thu - chi phí hàng tháng'

    @api.model
    def _get_report_values(self, docids, data=None):
        data = data or {}
        start_date = data.get('date_from')
        end_date = data.get('date_to')

        if not start_date or not end_date:
            raise UserError(_("Thiếu khoảng thời gian báo cáo"))

        month = data.get('month')
        year = data.get('year')
        quarter = data.get('quarter')
        period_type = data.get('period_type')

        receipts = self.env['account.receipt'].search([
            ('date', '>=', start_date),
            ('date', '<=', end_date),
            ('state', '=', 'posted'),
        ])

        rev_grouped = defaultdict(lambda: defaultdict(float))
        for r in receipts:
            tkey = r.type_revenue or 'unknown'
            if tkey in ('done_revenue', 'advance'):
                if not r.project_id:
                    continue
                key_name = r.project_id.name
            elif tkey in ('loan', 'other'):
                key_name = r.project_id.name if r.project_id else (r.note or _('(Không có nội dung)'))
            else:
                continue
            rev_grouped[tkey][key_name] += r.amount

        rev_order = [
            ('done_revenue', 'A. Doanh thu đã thực hiện'),
            ('advance', 'B. Doanh thu chưa thực hiện (Tạm ứng)'),
            ('other', 'C. Các khoản thu khác'),
            ('loan', 'D. Các khoản vay'),
        ]

        revenue_data = []
        for key, label in rev_order:
            project_lines = rev_grouped.get(key, {})
            total = sum(project_lines.values())
            revenue_data.append({
                'type_key': key,
                'type_label': label,
                'projects': [{'name': k, 'revenue': v} for k, v in project_lines.items()],
                'subtotal': total,
            })

        # ==============================
        # 🔹 Chi phí (A/B GÁN CỨNG theo expense_bucket)
        # ==============================

        FIXED_A = [
            ("rent_office_factory", "Chi phí thuê văn phòng + xưởng"),
        ]

        FIXED_B_COMPANY = [
            ("loan_principal", "Trả gốc vay (Ngân hàng + cá nhân)"),
            ("loan_interest", "Lãi vay (Ngân hàng, Cá nhân)"),
            ("bank_fee", "Phí ngân hàng (CK, Phí số dư, mua SEC,...)"),
            ("salary_board", "Chi phí lương ban Giám Đốc"),
            ("salary_sales", "Chi phí lương Kinh Doanh"),
            ("salary_accounting", "Chi phí lương Kế Toán"),
            ("salary_planning_tech_production", "Chi phí lương bộ phận kế hoạch kỹ thuật và sản xuất"),
            ("insurance_215", "Chi phí BHXH, BHYT, BHTN 21,5%"),
            ("electric_water", "Chi phí điện, Nước sinh hoạt"),
            ("phone_fee", "Chi phí Cước điện thoại (di động, cố định, số hotline...)"),
            ("internet_fee", "Cước Internet văn phòng"),
            ("stationery_hygiene_shipping", "Văn phòng phẩm + vật dụng vệ sinh + cước vận chuyển"),
            ("garbage_fee", "Chi phí đổ rác"),
            ("reception", "Chi phí Tiếp khách"),
            ("drinking_water", "Chi phí nước uống bình nhân viên"),
            ("badminton", "Chi phí cầu lông (đặt sân, mua cầu..)"),
            ("worship", "Chi phí cúng (mùng 1,15, ....)"),
        ]

        A_KEYS = [k for k, _ in FIXED_A]
        B_KEYS = [k for k, _ in FIXED_B_COMPANY]

        payments = self.env['account.payment.request'].search([
            ('date_payment', '>=', start_date),
            ('date_payment', '<=', end_date),
            ('state', 'in', ['post', 'done']),
        ])

        def _sum_fixed(records, keys):
            sums = {k: 0.0 for k in keys}
            unknown = 0.0
            for p in records:
                k = p.expense_bucket
                amt = p.total or 0.0
                if k in sums:
                    sums[k] += amt
                else:
                    unknown += amt
            return sums, unknown

        # ✅ A: CHỈ theo bucket rent_office_factory
        A_recs = payments.filtered(lambda x: x.expense_bucket in A_KEYS)
        A_SUMS, A_UNKNOWN = _sum_fixed(A_recs, A_KEYS)

        # ✅ B/a: theo 17 bucket còn lại
        B_recs = payments.filtered(lambda x: x.expense_bucket in B_KEYS)
        B_SUMS, B_UNKNOWN = _sum_fixed(B_recs, B_KEYS)

        # b. Chi phí công trình (GIỮ NGUYÊN)
        project_costs = defaultdict(float)
        for p in payments.filtered(lambda x: x.cost_classification == 'project'):
            key = p.project_id.name or _('(Không có dự án)')
            project_costs[key] += (p.total or 0.0)

        # C. Biến phí không thường xuyên (GIỮ NGUYÊN)
        irregular_costs = defaultdict(float)
        for p in payments.filtered(lambda x: x.cost_classification == 'irregular_expenses'):
            key = p.expense_category_id.name or _('(Không có khoản mục)')
            irregular_costs[key] += (p.total or 0.0)

        # Luôn đủ dòng
        A_LINES = [{'key': k, 'name': label, 'expense': A_SUMS.get(k, 0.0)} for k, label in FIXED_A]
        B_LINES = [{'key': k, 'name': label, 'expense': B_SUMS.get(k, 0.0)} for k, label in FIXED_B_COMPANY]

        # Nếu muốn bắt lỗi phiếu chi chọn bucket ngoài list / không chọn bucket thì bật dòng dưới
        # if A_UNKNOWN:
        #     A_LINES.append({'key': 'unclassified', 'name': 'Chưa phân loại (A)', 'expense': A_UNKNOWN})
        # if B_UNKNOWN:
        #     B_LINES.append({'key': 'unclassified', 'name': 'Chưa phân loại (B/a)', 'expense': B_UNKNOWN})

        expense_data = [
            {
                'type_label': 'A. TỔNG ĐỊNH PHÍ',
                'lines': A_LINES,
                'subtotal': sum(x['expense'] for x in A_LINES),
            },
            {
                'type_label': 'B. TỔNG BIẾN PHÍ THƯỜNG XUYÊN',
                'subgroups': [
                    {
                        'sub_label': 'a. Chi phí công ty',
                        'lines': B_LINES,
                        'subtotal': sum(x['expense'] for x in B_LINES),
                    },
                    {
                        'sub_label': 'b. Chi phí công trình',
                        'lines': [{'name': k, 'expense': v} for k, v in project_costs.items()],
                        'subtotal': sum(project_costs.values()),
                    },
                ],
                'subtotal': sum(x['expense'] for x in B_LINES) + sum(project_costs.values()),
            },
            {
                'type_label': 'C. TỔNG BIẾN PHÍ KHÔNG THƯỜNG XUYÊN',
                'lines': [{'name': k, 'expense': v} for k, v in irregular_costs.items()],
                'subtotal': sum(irregular_costs.values()),
            },
        ]

        # ==============================
        # 🔹 Tổng hợp cuối (GIỮ NGUYÊN)
        # ==============================
        total_revenue = sum(r.amount for r in receipts if r.type_revenue not in ('explain',))
        total_expense = sum(p.total for p in payments)
        net_profit = total_revenue - total_expense

        return {
            'doc_ids': docids,
            'doc_model': 'account.receipt',
            'period_type': period_type,
            'quarter': quarter,
            'month': month,
            'year': year,
            'start_date': start_date,
            'end_date': end_date,
            'revenue_data': revenue_data,
            'expense_data': expense_data,
            'total_revenue': total_revenue,
            'total_expense': total_expense,
            'net_profit': net_profit,
        }
