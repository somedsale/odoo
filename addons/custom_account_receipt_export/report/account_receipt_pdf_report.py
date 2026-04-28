# -*- coding: utf-8 -*-

from odoo import api, fields, models


class AccountReceiptPdfReport(models.AbstractModel):
    _name = 'report.custom_account_receipt_export.receipt_pdf'
    _description = 'PDF Phiếu Thu'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['account.receipt'].browse(docids)

        company = self.env.company
        if docs and 'company_id' in docs._fields and docs[0].company_id:
            company = docs[0].company_id

        def format_vn_date(date_value):
            if not date_value:
                date_value = fields.Date.context_today(self)

            date_value = fields.Date.to_date(date_value)
            return 'Ngày %02d tháng %02d năm %04d' % (
                date_value.day,
                date_value.month,
                date_value.year,
            )

        def format_money(amount):
            return '{:,.0f}'.format(amount or 0).replace(',', '.')

        def get_payer_name(receipt):
            if receipt.partner_type == 'employee' and receipt.employee_id:
                return receipt.employee_id.name or ''

            if receipt.partner_id:
                return receipt.partner_id.name or ''

            return ''

        def get_employee_address(employee):
            if not employee:
                return ''

            # Odoo bản có private address
            if 'address_home_id' in employee._fields and employee.address_home_id:
                return employee.address_home_id.contact_address or employee.address_home_id.name or ''

            # Một số bản/hr custom dùng address_id
            if 'address_id' in employee._fields and employee.address_id:
                return employee.address_id.contact_address or employee.address_id.name or ''

            # Một số bản có work_location_id
            if 'work_location_id' in employee._fields and employee.work_location_id:
                return employee.work_location_id.name or ''

            # Một số bản có work_email/work_phone thì không phải địa chỉ, nên không dùng
            return ''

        def get_payer_address(receipt):
            if receipt.partner_type == 'employee' and receipt.employee_id:
                return get_employee_address(receipt.employee_id)

            if receipt.partner_id:
                return receipt.partner_id.contact_address or ''

            return ''

        return {
            'doc_ids': docids,
            'doc_model': 'account.receipt',
            'docs': docs,
            'data': data or {},
            'company': company,
            'company_id': company,
            'format_vn_date': format_vn_date,
            'format_money': format_money,
            'get_payer_name': get_payer_name,
            'get_payer_address': get_payer_address,
        }