# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

class SaleReportWizard(models.TransientModel):
    _name = 'sale.report.wizard'
    _description = 'Sale Report Wizard'

    sale_order_ids = fields.Many2many(
        comodel_name='sale.order',
        string='Sale Orders',
        domain="[('state', 'in', ['sale', 'done'])]",
        help='Select sale orders to include in the report.'
    )

    def generate_report(self):
        data = {
            'sale_order_ids': self.sale_order_ids.ids,
        }
        return self.env.ref('custom_sale_report.action_sale_report_pdf').report_action(self, data=data)

    def preview_report(self):
        data = {
            'sale_order_ids': self.sale_order_ids.ids,
        }
        return self.env.ref('custom_sale_report.action_sale_report_html').report_action(self, data=data)

class SaleReport(models.AbstractModel):
    _name = 'report.custom_sale_report.sale_report_template'
    _description = 'Sale Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        today = fields.Date.today()
        date_format = '%Y-%m-%d'

        # Week: Monday to Sunday of current week
        start_of_week = today - timedelta(days=today.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        week_sales = self.env['sale.order'].search([
            ('date_order', '>=', start_of_week.strftime(date_format)),
            ('date_order', '<=', end_of_week.strftime(date_format)),
            ('state', 'in', ['sale', 'done', 'sent']),
        ])
        week_data = {
            'period': f'Week: {start_of_week.strftime(date_format)} to {end_of_week.strftime(date_format)}',
            'count': len(week_sales),
            'total_amount': sum(sale.amount_total for sale in week_sales),
        }

        # Month: First to last day of current month
        start_of_month = today.replace(day=1)
        end_of_month = (start_of_month + relativedelta(months=1) - timedelta(days=1))
        month_sales = self.env['sale.order'].search([
            ('date_order', '>=', start_of_month.strftime(date_format)),
            ('date_order', '<=', end_of_month.strftime(date_format)),
            ('state', 'in', ['sale', 'done', 'sent']),
        ])
        month_data = {
            'period': f'Month: {start_of_month.strftime("%Y-%m")}',
            'count': len(month_sales),
            'total_amount': sum(sale.amount_total for sale in month_sales),
        }

        # Quarter: First to last day of current quarter
        quarter = (today.month - 1) // 3 + 1
        start_of_quarter = today.replace(month=(quarter-1)*3+1, day=1)
        end_of_quarter = (start_of_quarter + relativedelta(months=3) - timedelta(days=1))
        quarter_sales = self.env['sale.order'].search([
            ('date_order', '>=', start_of_quarter.strftime(date_format)),
            ('date_order', '<=', end_of_quarter.strftime(date_format)),
            ('state', 'in', ['sale', 'done', 'sent']),
        ])
        quarter_data = {
            'period': f'Quarter {quarter}: {start_of_quarter.strftime("%Y-%m-%d")} to {end_of_quarter.strftime(date_format)}',
            'count': len(quarter_sales),
            'total_amount': sum(sale.amount_total for sale in quarter_sales),
        }

        # Selected Sale Orders
        sale_order_ids = data.get('sale_order_ids', [])
        selected_orders = self.env['sale.order'].browse(sale_order_ids).filtered(lambda so: so.state in ['sale', 'done'])
        selected_orders_data = [
            {
                'name': order.name,
                'partner_name': order.partner_id.name,
                'date_order': order.date_order.strftime(date_format),
                'amount_total': order.amount_total,
            } for order in selected_orders
        ]

        return {
            'week_data': week_data,
            'month_data': month_data,
            'quarter_data': quarter_data,
            'selected_orders_data': selected_orders_data,
            'res_company': self.env.company,
        }