# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
from markupsafe import Markup
from datetime import timedelta


class CostEstimate(models.Model):
    _name = 'cost.estimate'
    _description = 'Dự toán chi phí Dự án'
    _order = "create_date desc"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    code = fields.Char(
        'Mã dự toán',
        required=True, copy=False, readonly=True,
        help='Mã định danh duy nhất của dự toán chi phí',
        default='New'
    )
    name = fields.Char('Tên dự toán', required=True, default='New')

    requested_by = fields.Many2one(
        'res.users',
        string='Người tạo dự toán',
        default=lambda self: self.env.user,
        readonly=True
    )

    project_id = fields.Many2one('project.project', string='Dự án', ondelete='restrict')
    sale_order_id = fields.Many2one('sale.order', string='Đơn hàng', ondelete='restrict')

    line_ids = fields.One2many('cost.estimate.line', 'cost_estimate_id', string='Chi tiết dự toán')

    director_user_id = fields.Many2one(
        'res.users',
        string="Giám Đốc",
        default=lambda self: self._default_director_user(),
        readonly=True
    )

    show_button_submit = fields.Boolean(compute='_compute_show_button')
    show_button_approve = fields.Boolean(compute='_compute_show_button')
    show_button_cancel = fields.Boolean(compute='_compute_show_button')
    show_button_draft = fields.Boolean(compute='_compute_show_button')

    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    total_cost = fields.Float(
        string='Tổng dự toán sản phẩm (Trước thuế)',
        compute='_compute_total_cost',
        store=True,
        digits=(16, 0)
    )

    state = fields.Selection([
        ('draft', 'Nháp'),
        ('submitted', 'Gủi duyệt'),
        ('approved', 'Đã phê duyệt'),
        ('rejected', 'Bị từ chối'),
        ('cancel', 'Hủy bỏ')
    ], string='Trạng thái', default='draft', required=True, copy=False)

    additional_expense_line_ids = fields.One2many(
        'cost.additional.expense.line',
        'cost_estimate_id',
        string='Chi phí bổ sung'
    )

    amount_additional_expense = fields.Float(
        string='Tổng dự toán khác (Trước thuế)',
        compute='_compute_amount_additional_expense',
        store=True
    )

    total_final_non_tax = fields.Float(
        string='Tổng dự toán (Trước thuế)',
        compute='_compute_total_final_non_tax',
        store=True,
    )

    total_cost_with_tax = fields.Float(
        string='Tổng dự toán sản phẩm (Có thuế)',
        compute='_compute_total_cost_with_tax',
        store=True,
    )

    amount_additional_expense_with_tax = fields.Float(
        string='Tổng dự toán khác (Có thuế)',
        compute='_compute_amount_additional_expense_with_tax',
        store=True
    )

    total_final_tax = fields.Float(
        string='Tổng dự toán (Có thuế)',
        compute='_compute_total_final_tax',
        store=True,
    )

    # ===== popup SO info =====
    sale_order_partner = fields.Many2one(
        related="sale_order_id.partner_id",
        string="Khách hàng",
        store=False,
        readonly=True,
    )
    sale_order_date = fields.Datetime(
        related="sale_order_id.date_order",
        string="Ngày đơn hàng",
        store=False,
        readonly=True,
    )
    sale_order_amount_total = fields.Monetary(
        related="sale_order_id.amount_total",
        string="Tổng tiền",
        store=False,
        readonly=True,
        currency_field="currency_id",
    )

    contract_id = fields.Many2one(
        "contract.management",
        string="Hợp đồng",
        compute="_compute_contract_id",
        store=False,
    )
    contract_value = fields.Monetary(
        string="Giá trị hợp đồng",
        compute="_compute_contract_value",
        currency_field="currency_id",
        store=False,
    )

    activity_ids = fields.One2many(
        'mail.activity',
        'res_id',
        domain=[('res_model', '=', 'cost.estimate')],
        string='Hoạt động',
    )
   
    # =========================
    # COMPUTES
    # =========================
    @api.depends("sale_order_id")
    def _compute_contract_id(self):
        for rec in self:
            contract = self.env["contract.management"].search(
                [("sale_order_id", "=", rec.sale_order_id.id)],
                limit=1
            )
            rec.contract_id = contract.id if contract else False

    @api.depends("contract_id")
    def _compute_contract_value(self):
        for rec in self:
            rec.contract_value = rec.contract_id.contract_value if rec.contract_id else 0.0

    @api.depends('total_cost_with_tax', 'amount_additional_expense_with_tax')
    def _compute_total_final_tax(self):
        for rec in self:
            rec.total_final_tax = (rec.total_cost_with_tax or 0.0) + (rec.amount_additional_expense_with_tax or 0.0)

    @api.depends('additional_expense_line_ids.price_total')
    def _compute_amount_additional_expense_with_tax(self):
        for rec in self:
            rec.amount_additional_expense_with_tax = sum(rec.additional_expense_line_ids.mapped('price_total'))

    @api.depends('line_ids.price_total', 'line_ids.display_type')
    def _compute_total_cost_with_tax(self):
        for rec in self:
            lines = rec.line_ids.filtered(lambda l: not l.display_type)
            rec.total_cost_with_tax = sum(lines.mapped('price_total'))

    @api.depends('total_cost', 'amount_additional_expense')
    def _compute_total_final_non_tax(self):
        for rec in self:
            rec.total_final_non_tax = (rec.total_cost or 0.0) + (rec.amount_additional_expense or 0.0)

    @api.depends('additional_expense_line_ids.price_subtotal')
    def _compute_amount_additional_expense(self):
        for rec in self:
            rec.amount_additional_expense = sum(rec.additional_expense_line_ids.mapped('price_subtotal'))

    @api.depends('state')
    def _compute_show_button(self):
        for rec in self:
            is_creator = rec.requested_by == self.env.user
            is_director = rec.director_user_id == self.env.user
            rec.show_button_submit = rec.state == 'draft'
            rec.show_button_draft = rec.state == 'approved' and is_director
            rec.show_button_approve = rec.state == 'submitted' and is_director
            rec.show_button_cancel = rec.state in ['draft', 'submitted'] and is_creator

    @api.depends('line_ids.price_subtotal', 'line_ids.display_type')
    def _compute_total_cost(self):
        for rec in self:
            lines = rec.line_ids.filtered(lambda l: not l.display_type)
            rec.total_cost = sum(lines.mapped('price_subtotal'))

    # =========================
    # DEFAULTS / ACTIONS
    # =========================
    @api.model
    def _default_director_user(self):
        group = self.env.ref('custom_director_role.group_director', raise_if_not_found=False)
        if not group:
            return False
        users = self.env['res.users'].search([('groups_id', 'in', group.id)], limit=1)
        return users.id if users else False

    def action_submit(self):
        for rec in self:
            rec.state = 'submitted'
            if rec.director_user_id:
                rec.message_subscribe(partner_ids=[rec.director_user_id.partner_id.id])

            rec.message_post(
                body=Markup('<p>Dự toán chi phí <strong>{}</strong> đã được gửi duyệt.</p>').format(rec.name),
                subtype_xmlid='mail.mt_comment',
                message_type='comment'
            )

            if rec.director_user_id:
                rec.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=rec.director_user_id.id,
                    summary=f"Duyệt dự toán {rec.name}",
                    note=Markup(f"📌 Dự toán chi phí <b>{rec.name}</b> đang chờ duyệt."),
                    date_deadline=fields.Date.today() + timedelta(days=3),
                )

    def _close_activity(self, user, xmlid='mail.mail_activity_data_todo', feedback="Đã xử lý"):
        self.ensure_one()
        act_type = self.env.ref(xmlid, raise_if_not_found=False)
        if not act_type:
            return
        acts = self.env['mail.activity'].search([
            ('res_model', '=', self._name),
            ('res_id', '=', self.id),
            ('activity_type_id', '=', act_type.id),
            ('user_id', '=', user.id),
        ])
        if acts:
            acts.action_feedback(feedback=feedback)

    def action_approve(self):
        for rec in self:
            rec.state = 'approved'
            self.env['project.expense.dashboard'].create({
                'project_id': rec.project_id.id,
                'cost_estimate_id': rec.id,
            })
            rec.message_post(
                body=Markup('<p>Dự toán chi phí <strong>{}</strong> đã được phê duyệt.</p>').format(rec.name),
                subtype_xmlid='mail.mt_comment',
                message_type='comment'
            )
            if rec.director_user_id:
                rec._close_activity(user=rec.director_user_id, feedback="Đã duyệt")

    def action_cancel(self):
        for rec in self:
            rec.state = 'cancel'

    def action_draft(self):
        for rec in self:
            rec.state = 'draft'

    @api.model
    def create(self, vals):
        if not vals.get('code') or vals.get('code') == 'New':
            vals['code'] = self.env['ir.sequence'].next_by_code('cost.estimate.code') or '/'
        return super().create(vals)