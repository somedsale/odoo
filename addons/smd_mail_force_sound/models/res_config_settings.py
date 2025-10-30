# -*- coding: utf-8 -*-
from odoo import api, fields, models

_PARAM = "smd_mail_force_sound.enabled"

class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    smd_force_sound = fields.Boolean(
        string="Luôn phát âm thanh khi có tin nhắn",
        config_parameter=_PARAM,
        help="Khi bật, Odoo sẽ phát âm thanh mặc định ngay cả khi trình duyệt đã bật Desktop Notifications.",
        default=True,
    )

    @api.model
    def is_force_sound_enabled(self):
        """Cho JS gọi nhanh qua RPC."""
        icp = self.env["ir.config_parameter"].sudo()
        return icp.get_param(_PARAM, default="True").lower() == "true"
