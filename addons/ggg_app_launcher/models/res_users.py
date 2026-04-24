from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    ggg_app_layout = fields.Text(string='GGG App Layout')

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ['ggg_app_layout']

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + ['ggg_app_layout']
