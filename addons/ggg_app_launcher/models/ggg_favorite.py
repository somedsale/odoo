from odoo import fields, models


class GggFavorite(models.Model):
    _name = 'ggg.favorite'
    _description = 'App Launcher Favorite'
    _order = 'sequence, id'

    name = fields.Char(required=True)
    url = fields.Char(required=True)
    user_id = fields.Many2one(
        'res.users', required=True,
        default=lambda self: self.env.user,
        ondelete='cascade',
    )
    sequence = fields.Integer(default=10)
