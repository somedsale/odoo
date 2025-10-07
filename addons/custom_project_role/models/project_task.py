from odoo import api, fields, models

class ProjectTask(models.Model):
    _inherit = "project.task"

    @api.model
    def _get_stage_by_name(self, name):
        return self.env['project.task.type'].search([('name', '=', name)], limit=1)

    # Khi đổi state → cập nhật stage (UI)
    @api.onchange('state')
    def _onchange_state(self):
        if self.state == '1_done':
            done_stage = self._get_stage_by_name('Hoàn thành')
            if done_stage:
                self.stage_id = done_stage.id
        else:
            # ✅ nếu không phải hoàn thành → đưa về "Đang thực hiện"
            progress_stage = self._get_stage_by_name('Đang thực hiện')
            if progress_stage:
                self.stage_id = progress_stage.id

    # Khi đổi stage → cập nhật state (UI)
    @api.onchange('stage_id')
    def _onchange_stage_id(self):
        if self.stage_id.name == 'Hoàn thành':
            self.state = '1_done'
        else:
            # ✅ nếu stage khác hoàn thành → state = đang thực hiện
            self.state = '01_in_progress'

    # Khi lưu (write) → đồng bộ 2 chiều
    def write(self, vals):
        if self.env.context.get('syncing_stage_state'):
            return super().write(vals)

        res = super().write(vals)
        for rec in self:
            # ---------- Khi đổi state ----------
            if 'state' in vals:
                if rec.state == '1_done':
                    done_stage = rec._get_stage_by_name('Hoàn thành')
                    if done_stage and rec.stage_id != done_stage:
                        rec.with_context(syncing_stage_state=True).write({'stage_id': done_stage.id})
                else:
                    progress_stage = rec._get_stage_by_name('Chưa thực hiện')
                    if progress_stage and rec.stage_id != progress_stage:
                        rec.with_context(syncing_stage_state=True).write({'stage_id': progress_stage.id})

            # ---------- Khi đổi stage ----------
            if 'stage_id' in vals:
                if rec.stage_id.name == 'Hoàn thành':
                    if rec.state != '1_done':
                        rec.with_context(syncing_stage_state=True).write({'state': '1_done'})
                else:
                    if rec.state != '01_in_progress':
                        rec.with_context(syncing_stage_state=True).write({'state': '01_in_progress'})

        return res
