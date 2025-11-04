# -*- coding: utf-8 -*-
from odoo import models, api, fields
from datetime import datetime, timedelta

class AccountingDashboard(models.AbstractModel):
    _name = "wt.account.dashboard"
    _description = "Accounting Dashboard Data Provider"

    @api.model
    def get_dashboard_data(self, date_from=None, date_to=None, company_id=None, currency_id=None):
        """Trả dữ liệu KPI/Chart cho dashboard kế toán qua RPC orm.call()"""

        # ---- Chuẩn hoá khoảng ngày (giống sale) ----
        now = fields.Datetime.now()
        # date_to
        if date_to:
            try:
                dt_to = datetime.fromisoformat(str(date_to)[:19])
            except Exception:
                dt_to = now
        else:
            dt_to = now
        dt_to = dt_to.replace(hour=23, minute=59, second=59, microsecond=999999)
        # date_from
        if date_from:
            try:
                dt_from = datetime.fromisoformat(str(date_from)[:19])
            except Exception:
                dt_from = dt_to - timedelta(days=30)
        else:
            dt_from = dt_to - timedelta(days=30)
        dt_from = dt_from.replace(hour=0, minute=0, second=0, microsecond=0)

        # ---- Ngữ cảnh công ty & tiền tệ (tuỳ chọn) ----
        env = self.env
        if company_id:
            env = env(context=dict(env.context, allowed_company_ids=[company_id]))
        company = env.company
        currency = env['res.currency'].browse(currency_id) if currency_id else company.currency_id

        # ---- KPI ví dụ (giữ API giống controller cũ) ----
        SaleOrder = env['sale.order']
        quotations = SaleOrder.search_count([
            ('date_order', '>=', dt_from),
            ('date_order', '<=', dt_to),
            ('state', 'in', ['draft', 'sent']),
        ])
        orders = SaleOrder.search_count([
            ('date_order', '>=', dt_from),
            ('date_order', '<=', dt_to),
            ('state', '=', 'sale'),
        ])

        # Doanh thu = tổng amount_total của hóa đơn bán đã post trong kỳ
        Move = env['account.move']
        posted_out = Move.search([
            ('state', '=', 'posted'),
            ('move_type', '=', 'out_invoice'),
            ('invoice_date', '>=', dt_from.date()),
            ('invoice_date', '<=', dt_to.date()),
        ])
        # quy về currency hiển thị (nếu khác)
        revenues = sum(m.amount_total_signed if m.currency_id == currency else m.currency_id._convert(
            m.amount_total, currency, m.company_id, m.invoice_date or fields.Date.today()
        ) for m in posted_out)

        avg_order = revenues / orders if orders else 0.0

        # (Bạn có thể bổ sung các phần khác: AR/AP, aging, cashflow… tuỳ dashboard)
        return {
            "quotations": quotations,
            "orders": orders,
            "revenues": revenues,
            "avg_order": avg_order,
            # có thể trả thêm kpis/charts nếu UI cần
        }
