# community_hub/models/mail_message.py
from odoo import models, fields

class MailMessage(models.Model):
    _inherit = "mail.message"

    # URL để mở đúng community/channel/post
    community_hub_open_url = fields.Char(index=True)

    # Flag để mail (Discuss) KHÔNG tạo desktop notification kiểu cũ
    community_hub_skip_desktop = fields.Boolean(default=False, index=True)

    def _message_format(self, *args, **kwargs):
        """Expose custom fields to JS payload (Discuss/bus)."""
        res = super()._message_format(*args, **kwargs)  # list[dict]
        by_id = {d.get("id"): d for d in res if d.get("id")}
        for msg in self:
            d = by_id.get(msg.id)
            if d is not None:
                d["community_hub_open_url"] = msg.community_hub_open_url or False
                d["community_hub_skip_desktop"] = bool(msg.community_hub_skip_desktop)
        return res
