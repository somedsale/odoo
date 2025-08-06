# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

class SaleContractCustom(models.Model):
    _name = 'sale.contract.custom'
    _description = 'Sale Contract Custom'

    name = fields.Char(string='Mô tả', required=True)
    total_amount = fields.Monetary(string='Giá trị trước thuế', required=True)
    note = fields.Text(string='Ghi chú')
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
class SaleContractNegotiate(models.Model):
    _name = 'sale.contract.negotiate'
    _description = 'Sale Contract Negotiate'

    name = fields.Char(string='Mô tả', required=True)
    total_amount = fields.Monetary(string='Giá trị trước thuế', required=True)
    note = fields.Text(string='Ghi chú')
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
class ProjectProsect(models.Model):
    _name = 'project.prosect'
    _description = 'Project Prosect'

    name = fields.Char(string='Mô tả', required=True)
    total_amount = fields.Monetary(string='Giá trị trước thuế', required=True)
    note = fields.Text(string='Ghi chú')
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
class SaleReportWizard(models.TransientModel):
    _name = 'sale.report.wizard'
    _description = 'Sale Report Wizard'

    week_start_date = fields.Date(string='Week Start Date', required=True)
    business_plan = fields.Text(string='Triển khai kế hoạch kinh doanh', help='Enter the business plan for the selected week')
    contract_ids = fields.Many2many(
        'sale.contract.custom',
        relation='sale_report_wizard_contract_rel',
        string='Contracts',
        help='Select contracts to include in the report'
    )
    contract_negotiation_ids = fields.Many2many(
        'sale.contract.negotiate',
        relation='sale_report_wizard_negotiation_rel',
        string='Contracts Negotiation',
        help='Select contracts negotiation to include in the report'
    )
    project_prospect_ids = fields.Many2many(
        'project.prosect',
        relation='sale_report_wizard_project_rel',
        string='Project Prosect',
        help='Select project prosect to include in the report'
    )
    @api.model
    def default_get(self, fields_list):
        res = super(SaleReportWizard, self).default_get(fields_list)
        # Load saved values from config
        config = self.env['ir.config_parameter'].sudo()
        saved_week_start_date = config.get_param('custom_sale_report.week_start_date')
        saved_contract_ids = config.get_param('custom_sale_report.contract_ids')
        saved_contract_negotiation_ids = config.get_param('custom_sale_report.contract_negotiation_ids')
        saved_project_prospect_ids = config.get_param('custom_sale_report.project_prospect_ids')
        saved_business_plan = config.get_param('custom_sale_report.business_plan', default='')
        if saved_week_start_date and 'week_start_date' in fields_list:
            try:
                res['week_start_date'] = fields.Date.from_string(saved_week_start_date)
            except ValueError:
                res['week_start_date'] = fields.Date.today()
        if saved_business_plan and 'business_plan' in fields_list:
            res['business_plan'] = saved_business_plan
        else:
            res['business_plan'] = ''
        if saved_contract_ids and 'contract_ids' in fields_list:
            try:
                contract_ids = [int(cid) for cid in saved_contract_ids.split(',') if cid]
                if contract_ids:
                    res['contract_ids'] = [(6, 0, contract_ids)]
            except ValueError:
                res['contract_ids'] = [(6, 0, [])]
        
        if saved_contract_negotiation_ids and 'contract_negotiation_ids' in fields_list:
            try:
                negotiation_ids = [int(cid) for cid in saved_contract_negotiation_ids.split(',') if cid]                
                if negotiation_ids:
                    res['contract_negotiation_ids'] = [(6, 0, negotiation_ids)]
            except ValueError:
                res['contract_negotiation_ids'] = [(6, 0, [])]
        if saved_project_prospect_ids and 'project_prospect_ids' in fields_list:
            try:
                project_ids = [int(pid) for pid in saved_project_prospect_ids.split(',') if pid]                
                if project_ids:                
                    res['project_prospect_ids'] = [(6, 0, project_ids)]
            except ValueError:
                res['project_prospect_ids'] = [(6, 0, [])]
        if not res.get('week_start_date'):
            res['week_start_date'] = fields.Date.today()
            
        return res

    def _save_wizard_values(self):
        # Save values to config
        config = self.env['ir.config_parameter'].sudo()
        # config.set_param('custom_sale_report.week_start_date', self.week_start_date)
        config.set_param('custom_sale_report.contract_ids', ','.join(str(cid) for cid in self.contract_ids.ids))
        config.set_param('custom_sale_report.contract_negotiation_ids', ','.join(str(cid) for cid in self.contract_negotiation_ids.ids))
        config.set_param('custom_sale_report.project_prospect_ids', ','.join(str(pid) for pid in self.project_prospect_ids.ids))
        config.set_param('custom_sale_report.business_plan', self.business_plan or '')
    def _save_report_history(self, report_data):
        self.env['sale.report.history'].create({
            'week_start_date': self.week_start_date,
            'contract_ids': [(6, 0, self.contract_ids.ids)],
            'contract_negotiation_ids': [(6, 0, self.contract_negotiation_ids.ids)],
            'project_prospect_ids': [(6, 0, self.project_prospect_ids.ids)],
            'business_plan': self.business_plan or '',
            'user_id': self.env.uid,
            'week_count': report_data['week_data']['count'],
            'week_amount': report_data['week_data']['total_amount'],
            'month_count': report_data['month_data']['count'],
            'month_amount': report_data['month_data']['total_amount'],
            'quarter_count': report_data['quarter_data']['count'],
            'quarter_amount': report_data['quarter_data']['total_amount'],
            'year_count': report_data['year_data']['count'],
            'year_amount': report_data['year_data']['total_amount'],
            'create_date': fields.Datetime.now(),
        })
    def generate_report(self):
        self._save_wizard_values()
        report_data = self.env['report.custom_sale_report.sale_report_template']._get_report_values(None, {
            'week_start_date': self.week_start_date,
            'contract_ids': self.contract_ids.ids,
            'contract_negotiation_ids': self.contract_negotiation_ids.ids,
            'project_prospect_ids': self.project_prospect_ids.ids,
            'business_plan': self.business_plan or ''
        })
        self._save_report_history(report_data)
        return self.env.ref('custom_sale_report.action_sale_report_pdf').report_action(self, data={
            'week_start_date': self.week_start_date,
            'contract_ids': self.contract_ids.ids,
            'contract_negotiation_ids': self.contract_negotiation_ids.ids,
            'project_prospect_ids': self.project_prospect_ids.ids,
            'business_plan': self.business_plan or ''
        })

    def preview_report(self):
        self._save_wizard_values()
        report_data = self.env['report.custom_sale_report.sale_report_template']._get_report_values(None, {
            'week_start_date': self.week_start_date,
            'contract_ids': self.contract_ids.ids,
            'contract_negotiation_ids': self.contract_negotiation_ids.ids,
            'project_prospect_ids': self.project_prospect_ids.ids,
            'business_plan': self.business_plan or ''
        })
        self._save_report_history(report_data)
        
        return self.env.ref('custom_sale_report.action_sale_report_html').report_action(self, data={
            'week_start_date': self.week_start_date,
            'contract_ids': self.contract_ids.ids,
            'contract_negotiation_ids': self.contract_negotiation_ids.ids,
            'project_prospect_ids': self.project_prospect_ids.ids,
            'business_plan': self.business_plan or ''
        })

class SaleReport(models.AbstractModel):
    _name = 'report.custom_sale_report.sale_report_template'
    _description = 'Sale Report'

    def _get_report_values(self, docids, data=None):
        week_start_date = fields.Date.from_string(data.get('week_start_date', fields.Date.today()))
        contract_ids = data.get('contract_ids', [])
        contract_negotiation_ids = data.get('contract_negotiation_ids', [])
        project_prospect_ids = data.get('project_prospect_ids', [])
        business_plan = data.get('business_plan', '')
        date_format = '%d-%m-%Y'
        week_number = week_start_date.isocalendar()[1]  # Số tuần trong năm
        start_of_week = week_start_date - timedelta(days=week_start_date.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        week_sales = self.env['sale.order'].search([
            ('date_order', '>=', start_of_week.strftime('%Y-%m-%d')),
            ('date_order', '<=', end_of_week.strftime('%Y-%m-%d')),
            ('state', 'in', ['sale', 'done', 'sent']),
        ])
        week_data = {
            'period': f'Tuần {week_number}: "("{start_of_week.strftime("%d-%m")} - {end_of_week.strftime("%d-%m")}")"',
            'count': len(week_sales),
            'total_amount': sum(sale.amount_total for sale in week_sales),
        }

        start_of_month = week_start_date.replace(day=1)
        end_of_month = (start_of_month + relativedelta(months=1) - timedelta(days=1))
        month_sales = self.env['sale.order'].search([
            ('date_order', '>=', start_of_month.strftime('%Y-%m-%d')),
            ('date_order', '<=', end_of_month.strftime('%Y-%m-%d')),
            ('state', 'in', ['sale', 'done', 'sent']),
        ])
        month_data = {
            'period': f'Tháng {start_of_month.strftime("%m")}',
            'count': len(month_sales),
            'total_amount': sum(sale.amount_total for sale in month_sales),
        }

        quarter = (week_start_date.month - 1) // 3 + 1
        start_of_quarter = week_start_date.replace(month=(quarter-1)*3+1, day=1)
        end_of_quarter = (start_of_quarter + relativedelta(months=3) - timedelta(days=1))
        quarter_sales = self.env['sale.order'].search([
            ('date_order', '>=', start_of_quarter.strftime('%Y-%m-%d')),
            ('date_order', '<=', end_of_quarter.strftime('%Y-%m-%d')),
            ('state', 'in', ['sale', 'done', 'sent']),
        ])
        quarter_data = {
            'period': f'Quý {quarter}: Tháng {start_of_quarter.strftime("%m")} đến Tháng {end_of_quarter.strftime("%m")}',
            'count': len(quarter_sales),
            'total_amount': sum(sale.amount_total for sale in quarter_sales),
        }
        start_of_year = week_start_date.replace(month=1, day=1)
        end_of_year = week_start_date.replace(month=12, day=31)
        year_sales = self.env['sale.order'].search([
            ('date_order', '>=', start_of_year.strftime('%Y-%m-%d')),
            ('date_order', '<=', end_of_year.strftime('%Y-%m-%d')),
            ('state', 'in', ['sale', 'done', 'sent']),
        ])
        year_data = {
            'period': f'Year: {start_of_year.strftime("%Y")}',
            'count': len(year_sales),
            'total_amount': sum(sale.amount_total for sale in year_sales),
        }
        contracts = self.env['sale.contract.custom'].browse(contract_ids)
        contract_negotiations = self.env['sale.contract.negotiate'].browse(contract_negotiation_ids)
        project_prosects = self.env['project.prosect'].browse(project_prospect_ids)

        return {
            'week_data': week_data,
            'month_data': month_data,
            'quarter_data': quarter_data,
            'year_data': year_data,
            'contracts': contracts,
            'contract_negotiations': contract_negotiations,
            'project_prosects': project_prosects,
            'business_plan': business_plan,
            'res_company': self.env.company,
        }
class SaleReportHistory(models.Model):
    _name = 'sale.report.history'
    _description = 'Sale Report History'
    _order = 'create_date desc'

    week_start_date = fields.Date(string='Week Start Date')
    contract_ids = fields.Many2many('sale.contract.custom', string='Contracts')
    contract_negotiation_ids = fields.Many2many('sale.contract.negotiate', string='Contracts Negotiation')
    project_prospect_ids = fields.Many2many('project.prosect', string='Project Prosects')
    week_count = fields.Integer(string='Week Quotations')
    week_amount = fields.Monetary(string='Week Total Amount')
    month_count = fields.Integer(string='Month Quotations')
    month_amount = fields.Monetary(string='Month Total Amount')
    quarter_count = fields.Integer(string='Quarter Quotations')
    quarter_amount = fields.Monetary(string='Quarter Total Amount')
    year_count = fields.Integer(string='Year Quotations')
    year_amount = fields.Monetary(string='Year Total Amount')
    business_plan = fields.Text(string='Business Plan')
    user_id = fields.Many2one('res.users', string='User', default=lambda self: self.env.user)
    create_date = fields.Datetime(string='Created On', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    def action_view_report(self):
        self.ensure_one()
        return self.env.ref('custom_sale_report.action_sale_report_history_html').report_action(self, data={
            'week_start_date': self.week_start_date,
            'contract_ids': self.contract_ids.ids,
            'contract_negotiation_ids': self.contract_negotiation_ids.ids,
            'project_prospect_ids': self.project_prospect_ids.ids,
            'business_plan': self.business_plan or '',
            'week_count': self.week_count,
            'week_amount': self.week_amount,
            'month_count': self.month_count,
            'month_amount': self.month_amount,
            'quarter_count': self.quarter_count,
            'quarter_amount': self.quarter_amount,
            'year_count': self.year_count,
            'year_amount': self.year_amount,
        })