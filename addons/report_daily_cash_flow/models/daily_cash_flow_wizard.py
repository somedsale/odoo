from odoo import models, fields, api
from datetime import timedelta
from odoo.exceptions import UserError

class DailyCashFlowWizard(models.TransientModel):
    _name = 'daily.cash.flow.wizard'
    _description = 'Daily Cash Flow Report Wizard'

    date_report = fields.Date(
        string='Report Date',
        required=True,
        default=fields.Date.today()
    )
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    opening_bank = fields.Monetary(string='Tồn đầu kỳ - Ngân hàng', currency_field='currency_id', default=0.0)
    opening_cash = fields.Monetary(string='Tồn đầu kỳ - Tiền mặt', currency_field='currency_id', default=0.0)
    # --- Gợi ý tồn đầu từ tồn cuối ngày trước ---
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        date_report = res.get('date_report') or fields.Date.today()
        prev_date = fields.Date.to_date(date_report) - timedelta(days=1)
        prev = self.env['cash.daily.balance'].search([
            ('date', '=', prev_date),
        ], limit=1)
        if prev:
            res.setdefault('opening_bank', prev.closing_bank)
            res.setdefault('opening_cash', prev.closing_cash)
        # nếu không có prev -> giữ mặc định 0.0 cho 2 trường
        return res

    @api.onchange('date_report')
    def _onchange_suggest_opening(self):
        if not self.date_report:
            return
        prev = self.env['cash.daily.balance'].search([
            ('date', '=', self.date_report - timedelta(days=1)),
        ], limit=1)
        if prev:
            self.opening_bank = prev.closing_bank
            self.opening_cash = prev.closing_cash
        # else: KHÔNG làm gì -> giữ giá trị hiện tại (thường là 0 hoặc do user đã gõ)


    def _sum_receipts(self, date_report):
        """Tính tổng THU (theo kênh) trong ngày."""
        receipts = self.env['account.receipt'].search([
            ('date', '=', date_report),
        ])
        bank = sum(r.amount for r in receipts.filtered(lambda r: r.payment_method == 'bank'))
        cash = sum(r.amount for r in receipts.filtered(lambda r: r.payment_method != 'bank'))
        return bank, cash

    def _sum_payments(self, date_report):
        """Tính tổng CHI (theo kênh) trong ngày."""
        pays = self.env['account.payment.request'].search([
            ('date_payment', '=', date_report),
        ])
        bank = sum(p.total for p in pays.filtered(lambda p: p.payment_type == 'bank'))
        cash = sum(p.total for p in pays.filtered(lambda p: p.payment_type != 'bank'))
        return bank, cash

    def action_generate_report(self):
        self.ensure_one()
        report_date = self.date_report

        # Lấy bản ghi (để render chi tiết như cũ)
        payments = self.env['account.payment.request'].search([
            ('date_payment', '=', report_date),
        ])
        receipts = self.env['account.receipt'].search([
            ('date', '=', report_date),
        ])

        # Tính tổng/ tồn cuối -> lưu để hôm sau gợi ý
        r_bank, r_cash = self._sum_receipts(report_date)     # tổng thu
        p_bank, p_cash = self._sum_payments(report_date)     # tổng chi

        closing_bank = (self.opening_bank or 0.0) + r_bank - p_bank
        closing_cash = (self.opening_cash or 0.0) + r_cash - p_cash

        # upsert vào cash.daily.balance cho ngày hiện tại
        Balance = self.env['cash.daily.balance']
        today_balance = Balance.search([
            ('date', '=', report_date),
        ], limit=1)
        vals = {'closing_bank': closing_bank, 'closing_cash': closing_cash, 'date': report_date}
        if today_balance:
            today_balance.write(vals)
        else:
            Balance.create(vals)

        data = {
            'doc_ids': self.ids,
            'date_report': str(report_date.strftime('%d/%m/%Y')),
            'account_payment_ids': payments.ids,
            'account_receipt_ids': receipts.ids,
            'opening_bank': self.opening_bank or 0.0,
            'opening_cash': self.opening_cash or 0.0,
            'currency_id': self.currency_id.id,
            # gửi thêm tổng & tồn cuối để bạn muốn hiển thị ở cuối bảng
            'sum_receipt_bank': r_bank,
            'sum_receipt_cash': r_cash,
            'sum_payment_bank': p_bank,
            'sum_payment_cash': p_cash,
            'closing_bank': closing_bank,
            'closing_cash': closing_cash,
        }
        return self.env.ref('report_daily_cash_flow.daily_cash_flow_report').report_action(self, data=data)