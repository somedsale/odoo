from odoo import fields, models, api, exceptions

class ProjectConfig(models.Model):
    _name = 'project.config'
    _description = 'Project Configuration'

    default_project_manager_id = fields.Many2one(
        comodel_name='res.users',
        string='Default Project Manager',
    )
    default_boss_id = fields.Many2one(
        comodel_name='res.users',
        string='Default Boss',  # Boss mặc định
        required=True
    )

    @api.constrains('id')
    def _check_one_record(self):
        if self.search_count([]) > 1:
            raise exceptions.ValidationError('Only one Project Configuration record is allowed.')

    @api.model
    def action_open_config(self):
        config = self.search([], limit=1)
        if not config:
            config = self.create({})
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'project.config',
            'view_mode': 'form',
            'res_id': config.id,
            'target': 'current',
            'view_id': self.env.ref('custom_sale_project.project_config_view_form').id,
        }
    @api.model
    def get_default_boss(self):
        config = self.search([], limit=1)
        return config.default_boss_id.id if config else False