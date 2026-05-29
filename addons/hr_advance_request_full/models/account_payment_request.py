# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from markupsafe import Markup, escape
from lxml import etree


class AccountingPaymentRequest(models.Model):
    _inherit = 'account.payment.request'

    advance_request_id = fields.Many2one(
        'somed.advance.request',
        string='Phiếu tạm ứng',
        ondelete='set null',
        index=True,
        copy=False,
    )

    advance_request_count = fields.Integer(
        string='Số phiếu tạm ứng',
        compute='_compute_advance_request_count',
        store=False,
    )

    def _get_related_advance_request(self):
        self.ensure_one()
        if self.advance_request_id:
            return self.advance_request_id
        advance_line = self.line_ids.filtered(lambda l: l.line_type == 'advance' and l.advance_request_id)[:1]
        return advance_line.advance_request_id if advance_line else self.env['somed.advance.request']

    def _compute_advance_request_count(self):
        for rec in self:
            rec.advance_request_count = 1 if rec._get_related_advance_request() else 0

    def action_view_advance_request(self):
        self.ensure_one()
        advance = self._get_related_advance_request()
        if not advance:
            return False
        return {
            'type': 'ir.actions.act_window',
            'name': _('Phiếu tạm ứng'),
            'res_model': 'somed.advance.request',
            'view_mode': 'form',
            'res_id': advance.id,
            'target': 'current',
        }

    @api.model
    def get_view(self, view_id=None, view_type='form', **options):
        res = super().get_view(view_id=view_id, view_type=view_type, **options)

        if view_type != 'form' or not res.get('arch'):
            return res

        try:
            doc = etree.XML(res['arch'])
        except Exception:
            return res

        # Tránh chèn trùng nếu view đã có smart button phiếu tạm ứng.
        if doc.xpath("//button[@name='action_view_advance_request']"):
            res['arch'] = etree.tostring(doc, encoding='unicode')
            return res

        button_xml = etree.fromstring('''
            <button name="action_view_advance_request"
                    type="object"
                    class="oe_stat_button"
                    icon="fa-file-text-o"
                    invisible="not advance_request_id">
                <field name="advance_request_count" widget="statinfo" string="Phiếu tạm ứng"/>
            </button>
        ''')

        boxes = doc.xpath("//div[contains(concat(' ', normalize-space(@class), ' '), ' oe_button_box ')]")
        if boxes:
            boxes[0].insert(0, button_xml)
        else:
            sheets = doc.xpath('//sheet')
            if sheets:
                box = etree.Element('div', {'class': 'oe_button_box', 'name': 'button_box'})
                box.append(button_xml)
                sheets[0].insert(0, box)

        # Field dùng trong invisible cần có mặt trong view để web client đánh giá ổn định.
        if not doc.xpath("//field[@name='advance_request_id']"):
            sheets = doc.xpath('//sheet')
            hidden = etree.Element('field', {'name': 'advance_request_id', 'invisible': '1'})
            if sheets:
                sheets[0].insert(0, hidden)

        res['arch'] = etree.tostring(doc, encoding='unicode')
        return res


    def _get_header_vals_from_lines(self):
        vals = super()._get_header_vals_from_lines()
        self.ensure_one()
        proposal_lines = self.line_ids.filtered(lambda l: l.line_type == 'proposal' and l.proposal_sheet_id)
        if proposal_lines:
            return vals

        advance_lines = self.line_ids.filtered(lambda l: l.line_type == 'advance' and l.advance_request_id)
        if advance_lines:
            advance = advance_lines[0].advance_request_id
            vals.update({
                'proposal_sheet_id': False,
                'proposal_person_id': advance.user_id.id if 'proposal_person_id' in self._fields and advance.user_id else False,
                'date': advance.request_date,
            })
            if 'advance_request_id' in self._fields:
                vals['advance_request_id'] = advance.id
        return vals

    def action_payment_request(self):
        res = super().action_payment_request()
        for rec in self:
            advance = rec.advance_request_id or rec.line_ids.filtered(lambda l: l.line_type == 'advance' and l.advance_request_id)[:1].advance_request_id
            if advance:
                if not advance.payment_request_id:
                    advance.payment_request_id = rec.id
                advance.message_post(
                    body=Markup('<p>Phiếu chi <strong>%s</strong> đã được kế toán xác nhận chi tiền.</p>') % escape(rec.name or ''),
                    subtype_xmlid='mail.mt_comment',
                )
                if advance.user_id and advance.user_id.partner_id:
                    advance.message_post(
                        body=Markup('<p>Phiếu tạm ứng <strong>%s</strong> đã được chi tiền theo phiếu chi <strong>%s</strong>.</p>') % (
                            escape(advance.name or ''),
                            escape(rec.name or ''),
                        ),
                        partner_ids=[advance.user_id.partner_id.id],
                        subtype_xmlid='mail.mt_comment',
                    )
        return res


class AccountPaymentRequestLine(models.Model):
    _inherit = 'account.payment.request.line'

    line_type = fields.Selection(
        selection_add=[('advance', 'Theo phiếu tạm ứng')],
        ondelete={'advance': 'cascade'},
    )

    advance_request_id = fields.Many2one(
        'somed.advance.request',
        string='Phiếu tạm ứng',
        ondelete='set null',
        index=True,
    )

    @api.depends('line_type', 'proposal_sheet_id', 'advance_request_id', 'manual_name', 'interpretation')
    def _compute_display_name_line(self):
        for rec in self:
            if rec.line_type == 'proposal' and rec.proposal_sheet_id:
                rec.display_name_line = rec.proposal_sheet_id.name
            elif rec.line_type == 'advance' and rec.advance_request_id:
                rec.display_name_line = rec.advance_request_id.name
            else:
                rec.display_name_line = rec.manual_name or rec.interpretation or 'Chi thủ công'

    @api.onchange('line_type')
    def _onchange_line_type(self):
        res = super()._onchange_line_type()
        for rec in self:
            if rec.line_type != 'advance':
                rec.advance_request_id = False
            if rec.line_type == 'advance':
                rec.proposal_sheet_id = False
                rec.manual_name = False
        return res

    @api.onchange('advance_request_id')
    def _onchange_advance_request_id(self):
        for rec in self:
            if rec.advance_request_id:
                rec.line_type = 'advance'
                rec.amount = rec.advance_request_id.amount or 0.0
                rec.interpretation = 'Tạm ứng %s - %s' % (
                    rec.advance_request_id.name or '',
                    (rec.advance_request_id.reason or '')[:120],
                )

    @api.constrains('line_type', 'advance_request_id')
    def _check_advance_required(self):
        for rec in self:
            if rec.line_type == 'advance' and not rec.advance_request_id:
                raise ValidationError(_('Dòng theo phiếu tạm ứng bắt buộc phải chọn phiếu tạm ứng.'))

    @api.constrains('advance_request_id', 'payment_request_id', 'line_type')
    def _check_unique_advance_in_payment(self):
        for rec in self:
            if rec.line_type != 'advance' or not rec.payment_request_id or not rec.advance_request_id:
                continue
            dup = self.search_count([
                ('id', '!=', rec.id),
                ('payment_request_id', '=', rec.payment_request_id.id),
                ('advance_request_id', '=', rec.advance_request_id.id),
                ('line_type', '=', 'advance'),
            ])
            if dup:
                raise ValidationError(_('Một phiếu tạm ứng chỉ nên xuất hiện 1 lần trong cùng 1 phiếu chi.'))
