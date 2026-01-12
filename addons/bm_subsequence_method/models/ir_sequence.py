# -*- coding: utf-8 -*-
# See LICENSE file for full licensing details.
# See COPYRIGHT file for full copyright details.
# Developed by Bizmate - Unbox Solutions Co., Ltd.

from datetime import datetime, timedelta
import calendar
from odoo import models, fields

class IrSequence(models.Model):
    _inherit = 'ir.sequence'

    date_range_mode = fields.Selection([
        ('yearly', 'Yearly'),
        ('monthly', 'Monthly'),
        ('daily', 'Daily'),
        ('custom', 'Custom'),
        ], 'Date Range Mode', default='yearly')
    
    def _create_date_range_seq(self, date):
        year = fields.Date.from_string(date).strftime('%Y')
        month = fields.Date.from_string(date).strftime('%m')

        if self.date_range_mode == 'yearly':
            date_from = '{year}-01-01'.format(year=year)
            date_to = '{year}-12-31'.format(year=year)

        elif self.date_range_mode == 'monthly':
            max_day = calendar.monthrange(int(year), int(month))[1]
            date_from = '{year}-{month}-01'.format(year=year, month=month)
            date_to = '{year}-{month}-{max_day}'.format(year=year, month=month, max_day=max_day)
            
        elif self.date_range_mode == 'daily':
            date_from = date.strftime('%Y-%m-%d')
            date_to = date.strftime('%Y-%m-%d')
            
        date_range = self.env['ir.sequence.date_range'].search([('sequence_id', '=', self.id), ('date_from', '>=', date), ('date_from', '<=', date_to)], order='date_from desc', limit=1)
        if date_range:
            date_to = date_range.date_from + timedelta(days=-1)
        date_range = self.env['ir.sequence.date_range'].search([('sequence_id', '=', self.id), ('date_to', '>=', date_from), ('date_to', '<=', date)], order='date_to desc', limit=1)
        if date_range:
            date_from = date_range.date_to + timedelta(days=1)
        seq_date_range = self.env['ir.sequence.date_range'].sudo().create({
            'date_from': date_from,
            'date_to': date_to,
            'sequence_id': self.id,
        })
        return seq_date_range