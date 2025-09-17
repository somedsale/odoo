# -*- coding: utf-8 -*-
from odoo import models, fields, api

MODULE_XML = "contract_management"

BASE_STAGE_XMLIDS = [
    f"{MODULE_XML}.task_type_new_order",
    f"{MODULE_XML}.task_type_purchase",
    f"{MODULE_XML}.task_type_delivery",
    f"{MODULE_XML}.task_type_acceptance",
    f"{MODULE_XML}.task_type_completed",
]
PROD_XMLID = f"{MODULE_XML}.task_type_production"
INSTALL_XMLID = f"{MODULE_XML}.task_type_installation"


class ProjectTask(models.Model):
    _inherit = "project.task"

    add_stage_production = fields.Boolean(string="Sản xuất")
    add_stage_installation = fields.Boolean(string="Thi công")

    @api.model
    def create(self, vals):
        task = super().create(vals)
        task._ensure_project_uses_specific_stages()
        task._apply_optional_stage_links()
        # không cần reload; stage_id domain sẽ được cập nhật bằng onchange khi người dùng thay đổi checkbox
        task.project_id._prune_optional_stages()
        return task

    def write(self, vals):
        old_projects = {t.id: t.project_id for t in self}
        res = super().write(vals)
        affected = set(old_projects.values()) | set(self.mapped("project_id"))
        for t in self:
            t._ensure_project_uses_specific_stages()
            t._apply_optional_stage_links()
        for p in affected - {False}:
            p._prune_optional_stages()
        return res

    # ---------- REFRESH NGAY TRÊN FORM (không cần reload) ----------
    @api.onchange('add_stage_production', 'add_stage_installation', 'project_id')
    def _onchange_optional_stages(self):
        """Khi tick/bỏ tick, liên kết stage và trả về domain stage_id tức thì."""
        self._ensure_project_uses_specific_stages()
        self._apply_optional_stage_links()
        return self._return_stage_domain()

    def _return_stage_domain(self):
        """Trả về domain cho field stage_id dựa trên type_ids của project hiện tại."""
        self.ensure_one()
        if self.project_id:
            stage_ids = self.project_id.type_ids.ids
            return {'domain': {'stage_id': [('id', 'in', stage_ids)]}}
        return {'domain': {'stage_id': []}}

    # ---------- Button (tuỳ chọn) để force reload ----------
    def action_refresh_view(self):
        """Nút 'Làm mới stage' -> reload view."""
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    # ---------- Helpers ----------
    def _ensure_project_uses_specific_stages(self):
        for t in self:
            p = t.project_id
            if not p or p.type_ids:
                continue
            stages = [self.env.ref(xid, raise_if_not_found=False) for xid in BASE_STAGE_XMLIDS]
            for st in filter(None, stages):
                if p.id not in st.project_ids.ids:
                    st.write({'project_ids': [(4, p.id)]})

    def _apply_optional_stage_links(self):
        for t in self:
            p = t.project_id
            if not p:
                continue
            if t.add_stage_production:
                st = self.env.ref(PROD_XMLID, raise_if_not_found=False)
                if st and p.id not in st.project_ids.ids:
                    st.write({'project_ids': [(4, p.id)]})
            if t.add_stage_installation:
                st = self.env.ref(INSTALL_XMLID, raise_if_not_found=False)
                if st and p.id not in st.project_ids.ids:
                    st.write({'project_ids': [(4, p.id)]})


class Project(models.Model):
    _inherit = "project.project"

    def _prune_optional_stages(self):
        Task = self.env['project.task'].sudo()

        def _maybe_unlink(xid, need_field, proj):
            st = self.env.ref(xid, raise_if_not_found=False)
            if not st or proj.id not in st.project_ids.ids:
                return
            still_needed = Task.search_count([('project_id', '=', proj.id), (need_field, '=', True)]) > 0
            if still_needed:
                return
            in_use = Task.search_count([('project_id', '=', proj.id), ('stage_id', '=', st.id)]) > 0
            if in_use:
                return
            st.write({'project_ids': [(3, proj.id)]})

        for p in self:
            _maybe_unlink(PROD_XMLID, 'add_stage_production', p)
            _maybe_unlink(INSTALL_XMLID, 'add_stage_installation', p)
