from odoo import models, api, _
from odoo.exceptions import ValidationError

class ResUsers(models.Model):
    _inherit = 'res.users'

    @api.constrains('groups_id')
    def _check_director_unique(self):
        director_group = self.env.ref('custom_director_role.group_director', raise_if_not_found=False)
        if not director_group:
            return

        for user in self:
            if director_group in user.groups_id:
                # Tìm người dùng khác (ngoài user hiện tại) đã có trong group 'Giám Đốc'
                other_users = self.search([
                    ('id', '!=', user.id),
                    ('groups_id', 'in', director_group.id)
                ])
                if other_users:
                    raise ValidationError(_("Chỉ được gán nhóm 'Giám Đốc' cho duy nhất một người dùng."))
