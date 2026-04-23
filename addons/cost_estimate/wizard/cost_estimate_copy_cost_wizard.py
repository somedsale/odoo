# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError


class CostEstimateCopyCostWizard(models.TransientModel):
    _name = 'cost.estimate.copy.cost.wizard'
    _description = 'Wizard sao chép chi phí giữa các hạng mục'

    cost_estimate_id = fields.Many2one(
        'cost.estimate',
        string='Dự toán',
        required=True,
        readonly=True,
    )

    target_line_id = fields.Many2one(
        'cost.estimate.line',
        string='Hạng mục đích',
        required=True,
        domain="[('cost_estimate_id', '=', cost_estimate_id), ('display_type', '=', False)]",
    )

    source_line_id = fields.Many2one(
        'cost.estimate.line',
        string='Hạng mục nguồn',
        required=True,
        domain="[('cost_estimate_id', '=', cost_estimate_id), ('display_type', '=', False), ('id', '!=', target_line_id)]",
    )

    copy_material = fields.Boolean(string='Chi phí nguyên vật liệu', default=True)
    copy_labor = fields.Boolean(string='Chi phí nhân công', default=True)
    copy_other = fields.Boolean(string='Chi phí khác (SXC)', default=True)

    replace_existing = fields.Boolean(
        string='Xóa chi phí hiện tại ở hạng mục đích trước khi sao chép',
        default=True,
    )

    @api.onchange('target_line_id')
    def _onchange_target_line_id(self):
        if self.target_line_id:
            self.cost_estimate_id = self.target_line_id.cost_estimate_id.id

    def action_copy_costs(self):
        self.ensure_one()

        if not self.source_line_id or not self.target_line_id:
            raise UserError("Vui lòng chọn đầy đủ hạng mục nguồn và hạng mục đích.")

        if self.source_line_id.id == self.target_line_id.id:
            raise UserError("Hạng mục nguồn và hạng mục đích không được trùng nhau.")

        if not (self.copy_material or self.copy_labor or self.copy_other):
            raise UserError("Vui lòng chọn ít nhất 1 loại chi phí để sao chép.")

        source = self.source_line_id
        target = self.target_line_id

        if source.cost_estimate_id.id != target.cost_estimate_id.id:
            raise UserError("Chỉ được sao chép giữa các hạng mục trong cùng một dự toán.")

        # Xóa dòng cũ nếu người dùng chọn thay thế
        if self.replace_existing:
            if self.copy_material and target.material_line_ids:
                target.material_line_ids.unlink()
            if self.copy_labor and target.labor_expense_line_ids:
                target.labor_expense_line_ids.unlink()
            if self.copy_other and target.expense_line_ids:
                target.expense_line_ids.unlink()

        # Copy vật tư
        if self.copy_material:
            material_commands = []
            for line in source.material_line_ids:
                material_commands.append((0, 0, {
                    'material_id': line.material_id.id,
                    'factor': line.factor,
                    'quantity': line.quantity,
                    'unit': line.unit.id if line.unit else False,
                    'price_unit': line.price_unit,
                    'vendor_id': line.vendor_id.id if getattr(line, 'vendor_id', False) else False,
                }))
            if material_commands:
                target.write({'material_line_ids': material_commands})

        # Copy nhân công
        if self.copy_labor:
            labor_commands = []
            for line in source.labor_expense_line_ids:
                labor_commands.append((0, 0, {
                    'expense_id': line.expense_id.id,
                    'factor': line.factor,
                    'quantity': line.quantity,
                    'unit': line.unit.id if line.unit else False,
                    'price_unit': line.price_unit,
                    'type': 'labor',
                }))
            if labor_commands:
                target.write({'labor_expense_line_ids': labor_commands})

        # Copy chi phí khác
        if self.copy_other:
            other_commands = []
            for line in source.expense_line_ids:
                other_commands.append((0, 0, {
                    'expense_id': line.expense_id.id,
                    'factor': line.factor,
                    'quantity': line.quantity,
                    'unit': line.unit.id if line.unit else False,
                    'price_unit': line.price_unit,
                    'type': 'other',
                }))
            if other_commands:
                target.write({'expense_line_ids': other_commands})

        return {'type': 'ir.actions.act_window_close'}