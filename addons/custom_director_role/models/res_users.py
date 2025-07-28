from odoo import models, api, _
from odoo.exceptions import ValidationError

class ResUsers(models.Model):
    _inherit = 'res.users'

    @api.constrains('groups_id')
    def _check_director_unique(self):
        director_group = self.env.ref('custom_director_role.group_director', raise_if_not_found=False)
        if director_group:
            users_in_group = self.search([
                ('groups_id', 'in', director_group.id),
                ('id', '!=', self.id)
            ])
            for user in self:
                if director_group in user.groups_id and users_in_group:
                    raise ValidationError(_("Chỉ được gán nhóm 'Giám Đốc' cho duy nhất một người dùng."))
