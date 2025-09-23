from odoo import models, fields, api
from datetime import date, timedelta


class SupplierInvoiceReportWizard(models.TransientModel):
    _name = "supplier.invoice.wizard"
    _description = "Wizard Báo cáo Hóa đơn NCC"

    filter_type = fields.Selection(
        [
            ('day', 'Theo ngày'),
            ('month', 'Theo tháng'),
            ('quarter', 'Theo quý'),
            ('year', 'Theo năm'),
            ('view_all', 'Xem tất cả'),
        ],
        string="Kiểu lọc",
        required=True,
        default="month"
    )

    date_from = fields.Date(string="Từ ngày")
    date_to = fields.Date(string="Đến ngày")
    month = fields.Selection(
        [(str(m), 'Tháng %s' % m) for m in range(1, 13)],
        string="Tháng"
    )
    quarter = fields.Selection(
        [
            ('1', 'Quý 1 (01-03)'),
            ('2', 'Quý 2 (04-06)'),
            ('3', 'Quý 3 (07-09)'),
            ('4', 'Quý 4 (10-12)'),
        ],
        string="Quý"
    )
    year = fields.Char(
        string="Năm",
        required=True,
        default=lambda self: fields.Date.today().year
    )

    def _get_date_range(self):
        """Xác định date_from, date_to dựa trên filter_type"""
        year = int(self.year) if self.year else date.today().year

        if self.filter_type == 'day':
            return self.date_from, self.date_to

        if self.filter_type == 'month':
            month = int(self.month)
            date_from = date(year, month, 1)
            if month == 12:
                date_to = date(year, 12, 31)
            else:
                date_to = date(year, month + 1, 1) - timedelta(days=1)
            return date_from, date_to

        if self.filter_type == 'quarter':
            q = int(self.quarter)
            start_month = (q - 1) * 3 + 1
            date_from = date(year, start_month, 1)
            if q == 4:
                date_to = date(year, 12, 31)
            else:
                date_to = date(year, start_month + 3, 1) - timedelta(days=1)
            return date_from, date_to

        if self.filter_type == 'year':
            date_from = date(year, 1, 1)
            date_to = date(year, 12, 31)
            return date_from, date_to

        return None, None

    def action_print_report(self):
        date_from, date_to = self._get_date_range()
        domain = [
            ('date', '>=', date_from),
            ('date', '<=', date_to),
        ]
        invoices = self.env['supplier.invoice'].search(domain, order="date asc")
        data = {
            'filter_type': self.filter_type,
            'date_from': str(date_from),
            'date_to': str(date_to),
            'year': self.year,
            'month': self.month,
            'quarter': self.quarter,
        }
        return self.env.ref(
            'vendor_debt_management.action_supplier_invoice_report_pdf'
        ).report_action(invoices, data=data)

    def action_view_report(self):
        date_from, date_to = self._get_date_range()
        domain = [
            ('date', '>=', date_from),
            ('date', '<=', date_to),
        ]
        invoices = self.env['supplier.invoice'].search(domain, order="date asc")
        data = {
            'filter_type': self.filter_type,
            'date_from': str(date_from),
            'date_to': str(date_to),
            'year': self.year,
            'month': self.month,
            'quarter': self.quarter,
        }
        return self.env.ref(
            'vendor_debt_management.action_supplier_invoice_report'
        ).report_action(invoices, data=data)
    def action_view_all(self):
        """Xem tất cả hóa đơn NCC mà không lọc theo ngày"""
        invoices = self.env['supplier.invoice'].search([], order="date asc")
        data = {
            'date_from': None,
            'date_to': None,
            'year': self.year,
            'month': self.month,
            'quarter': self.quarter,
        }
        return self.env.ref(
            'vendor_debt_management.action_supplier_invoice_report'
        ).report_action(invoices, data=data)
