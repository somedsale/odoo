# -*- coding: utf-8 -*-
from odoo import api, models


class DiscussChannel(models.Model):
    _inherit = "discuss.channel"

    def sidebar_assign_section(self, section_id):
        self.ensure_one()
        self.env["discuss.sidebar.section.line"].assign_channel_to_section(
            self.id, section_id
        )
        return True

    def sidebar_unassign_section(self):
        self.ensure_one()
        self.env["discuss.sidebar.section.line"].unassign_channel(self.id)
        return True

    @api.model
    def sidebar_assign_section_multi(self, channel_ids, section_id):
        line_model = self.env["discuss.sidebar.section.line"]
        for channel_id in channel_ids or []:
            line_model.assign_channel_to_section(channel_id, section_id)
        return True

    @api.model
    def sidebar_drag_to_section(self, channel_ids, section_id):
        self.env["discuss.sidebar.section.line"].move_channels_to_section(
            channel_ids=channel_ids,
            section_id=section_id,
        )
        return True

    @api.model
    def sidebar_drag_before_channel(self, channel_ids, target_channel_id):
        self.env["discuss.sidebar.section.line"].move_channels_before_channel(
            channel_ids=channel_ids,
            target_channel_id=target_channel_id,
        )
        return True

    @api.model
    def sidebar_drag_after_channel(self, channel_ids, target_channel_id):
        self.env["discuss.sidebar.section.line"].move_channels_after_channel(
            channel_ids=channel_ids,
            target_channel_id=target_channel_id,
        )
        return True