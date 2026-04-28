# -*- coding: utf-8 -*-

from odoo import api, fields, models


class PaymentRequestPdfReport(models.AbstractModel):
    _name = 'report.custom_account_payment_request_export.paypdf'
    _description = 'PDF Phieu Chi'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['account.payment.request'].browse(docids)

        company = self.env.company
        if docs and 'company_id' in docs._fields and docs[0].company_id:
            company = docs[0].company_id

        def format_vn_date(date_value):
            """
            Ưu tiên dùng ngày chi/ngày thanh toán.
            Nhận được cả fields.Date hoặc fields.Datetime.
            """
            if not date_value:
                date_value = fields.Date.context_today(self)

            date_value = fields.Date.to_date(date_value)
            return 'Ngày %02d tháng %02d năm %04d' % (
                date_value.day,
                date_value.month,
                date_value.year,
            )

        return {
            'doc_ids': docids,
            'doc_model': 'account.payment.request',
            'docs': docs,
            'data': data or {},
            'company': company,
            'company_id': company,
            'format_vn_date': format_vn_date,
        }