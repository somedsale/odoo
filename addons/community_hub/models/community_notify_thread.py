# -*- coding: utf-8 -*-
from odoo import models, fields

class CommunityHubNotifyThread(models.Model):
    _name = "community.hub.notify.thread"
    _description = "Community Hub Notify Thread"
    _inherit = ["mail.thread"]

    name = fields.Char(required=True, default="Community Hub Notifications")
