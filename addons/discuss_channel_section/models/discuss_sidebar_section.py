# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class DiscussSidebarSection(models.Model):
    _name = "discuss.sidebar.section"
    _description = "Discuss Sidebar Section"
    _order = "sequence, id"

    name = fields.Char(required=True)
    user_id = fields.Many2one(
        "res.users",
        required=True,
        default=lambda self: self.env.user,
        index=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(default=10)
    is_folded = fields.Boolean(string="Collapsed", default=False)

    line_ids = fields.One2many(
        "discuss.sidebar.section.line",
        "section_id",
        string="Channels",
    )

    _sql_constraints = [
        (
            "uniq_section_name_per_user",
            "unique(name, user_id)",
            "Tên section đã tồn tại cho user này.",
        )
    ]

    @api.constrains("name")
    def _check_name(self):
        for rec in self:
            if not rec.name or not rec.name.strip():
                raise ValidationError(_("Tên section không được để trống."))

    @api.model
    def get_my_sections(self):
        sections = self.search(
            [("user_id", "=", self.env.user.id)],
            order="sequence, id",
        )
        result = []
        for sec in sections:
            lines = sec.line_ids.sorted(key=lambda l: (l.sequence, l.id))
            result.append({
                "id": sec.id,
                "name": sec.name,
                "sequence": sec.sequence,
                "is_folded": sec.is_folded,
                "channel_ids": lines.mapped("channel_id").ids,
            })
        return result

    @api.model
    def create_section(self, name):
        name = (name or "").strip()
        if not name:
            raise UserError(_("Tên section không được để trống."))

        last = self.search(
            [("user_id", "=", self.env.user.id)],
            order="sequence desc, id desc",
            limit=1,
        )
        next_seq = (last.sequence + 10) if last else 10

        sec = self.create({
            "name": name,
            "user_id": self.env.user.id,
            "sequence": next_seq,
        })
        return {
            "id": sec.id,
            "name": sec.name,
            "sequence": sec.sequence,
            "is_folded": sec.is_folded,
            "channel_ids": [],
        }

    def rename_section(self, name):
        self.ensure_one()
        if self.user_id.id != self.env.user.id:
            raise UserError(_("Bạn không có quyền sửa section này."))

        name = (name or "").strip()
        if not name:
            raise UserError(_("Tên section không được để trống."))

        self.write({"name": name})
        return True

    def delete_section(self):
        self.ensure_one()
        if self.user_id.id != self.env.user.id:
            raise UserError(_("Bạn không có quyền xoá section này."))

        self.unlink()
        return True

    def toggle_fold(self):
        self.ensure_one()
        if self.user_id.id != self.env.user.id:
            raise UserError(_("Bạn không có quyền thao tác section này."))

        self.is_folded = not self.is_folded
        return self.is_folded

    def create_channel_in_section(self, channel_name):
        self.ensure_one()

        if self.user_id.id != self.env.user.id:
            raise UserError(_("Bạn không có quyền thao tác section này."))

        channel_name = (channel_name or "").strip()
        if not channel_name:
            raise UserError(_("Tên kênh không được để trống."))

        channel_vals = {
            "name": channel_name,
            "channel_type": "channel",
        }

        # Một số bản Odoo/discuss có field channel_member_ids,
        # một số logic membership sẽ tự xử lý sau khi create.
        channel = self.env["discuss.channel"].create(channel_vals)

        # Cố gắng add current user vào channel nếu field tồn tại
        if "channel_partner_ids" in channel._fields:
            channel.write({
                "channel_partner_ids": [(4, self.env.user.partner_id.id)]
            })
        elif "channel_member_ids" in channel._fields:
            member_model = self.env["discuss.channel.member"]
            existing_member = member_model.search([
                ("channel_id", "=", channel.id),
                ("partner_id", "=", self.env.user.partner_id.id),
            ], limit=1)
            if not existing_member:
                member_model.create({
                    "channel_id": channel.id,
                    "partner_id": self.env.user.partner_id.id,
                })

        self.env["discuss.sidebar.section.line"].assign_channel_to_section(
            channel.id, self.id
        )

        return {
            "id": channel.id,
            "name": channel.name,
        }


class DiscussSidebarSectionLine(models.Model):
    _name = "discuss.sidebar.section.line"
    _description = "Discuss Sidebar Section Line"
    _order = "sequence, id"

    section_id = fields.Many2one(
        "discuss.sidebar.section",
        required=True,
        ondelete="cascade",
        index=True,
    )
    user_id = fields.Many2one(
        "res.users",
        related="section_id.user_id",
        store=True,
        index=True,
    )
    channel_id = fields.Many2one(
        "discuss.channel",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)

    _sql_constraints = [
        (
            "uniq_channel_per_section",
            "unique(section_id, channel_id)",
            "Kênh này đã nằm trong section.",
        ),
        (
            "uniq_channel_per_user",
            "unique(user_id, channel_id)",
            "Mỗi kênh chỉ được nằm trong một section cho mỗi user.",
        ),
    ]

    @api.model
    def assign_channel_to_section(self, channel_id, section_id):
        section = self.env["discuss.sidebar.section"].browse(section_id).exists()
        if not section:
            raise UserError(_("Section không tồn tại."))
        if section.user_id.id != self.env.user.id:
            raise UserError(_("Bạn không có quyền dùng section này."))

        channel = self.env["discuss.channel"].browse(channel_id).exists()
        if not channel:
            raise UserError(_("Kênh không tồn tại."))

        existing = self.search([
            ("user_id", "=", self.env.user.id),
            ("channel_id", "=", channel.id),
        ], limit=1)

        if existing:
            moved_from_section = existing.section_id
            existing.section_id = section.id

            # nếu line đang chuyển section thì đẩy xuống cuối section mới
            if moved_from_section.id != section.id:
                last = self.search(
                    [("section_id", "=", section.id), ("id", "!=", existing.id)],
                    order="sequence desc, id desc",
                    limit=1,
                )
                existing.sequence = (last.sequence + 10) if last else 10
                if moved_from_section:
                    self._normalize_section_sequences(moved_from_section)
            elif existing.sequence <= 0:
                existing.sequence = 10
        else:
            last = self.search(
                [("section_id", "=", section.id)],
                order="sequence desc, id desc",
                limit=1,
            )
            next_seq = (last.sequence + 10) if last else 10
            self.create({
                "section_id": section.id,
                "channel_id": channel.id,
                "sequence": next_seq,
            })
        return True

    @api.model
    def unassign_channel(self, channel_id):
        line = self.search([
            ("user_id", "=", self.env.user.id),
            ("channel_id", "=", channel_id),
        ], limit=1)
        if line:
            section = line.section_id
            line.unlink()
            if section:
                self._normalize_section_sequences(section)
        return True

    @api.model
    def get_my_channel_section_map(self):
        lines = self.search([("user_id", "=", self.env.user.id)])
        return {line.channel_id.id: line.section_id.id for line in lines}

    @api.model
    def _normalize_section_sequences(self, section):
        lines = self.search(
            [("section_id", "=", section.id)],
            order="sequence, id",
        )
        seq = 10
        for line in lines:
            line.sequence = seq
            seq += 10
        return True

    @api.model
    def _get_or_create_line(self, channel_id, section_id):
        section = self.env["discuss.sidebar.section"].browse(section_id).exists()
        if not section:
            raise UserError(_("Section không tồn tại."))
        if section.user_id.id != self.env.user.id:
            raise UserError(_("Bạn không có quyền dùng section này."))

        channel = self.env["discuss.channel"].browse(channel_id).exists()
        if not channel:
            raise UserError(_("Kênh không tồn tại."))

        line = self.search([
            ("user_id", "=", self.env.user.id),
            ("channel_id", "=", channel.id),
        ], limit=1)

        if not line:
            line = self.create({
                "section_id": section.id,
                "channel_id": channel.id,
                "sequence": 999999,
            })
        else:
            line.section_id = section.id

        return line

    @api.model
    def move_channels_to_section(self, channel_ids, section_id):
        section = self.env["discuss.sidebar.section"].browse(section_id).exists()
        if not section:
            raise UserError(_("Section không tồn tại."))
        if section.user_id.id != self.env.user.id:
            raise UserError(_("Bạn không có quyền dùng section này."))

        moved_lines = self.browse()
        old_sections = self.env["discuss.sidebar.section"]

        for channel_id in channel_ids or []:
            old_line = self.search([
                ("user_id", "=", self.env.user.id),
                ("channel_id", "=", channel_id),
            ], limit=1)
            if old_line:
                old_sections |= old_line.section_id

            line = self._get_or_create_line(channel_id, section.id)
            moved_lines |= line

        existing_lines = self.search([
            ("section_id", "=", section.id),
            ("id", "not in", moved_lines.ids),
        ], order="sequence, id")

        ordered = existing_lines | moved_lines
        seq = 10
        for line in ordered:
            line.sequence = seq
            seq += 10

        for sec in old_sections:
            if sec.id != section.id:
                self._normalize_section_sequences(sec)

        return True

    @api.model
    def move_channels_before_channel(self, channel_ids, target_channel_id):
        target_line = self.search([
            ("user_id", "=", self.env.user.id),
            ("channel_id", "=", target_channel_id),
        ], limit=1)
        if not target_line:
            raise UserError(_("Không tìm thấy kênh đích trong section."))

        target_section = target_line.section_id
        old_sections = self.env["discuss.sidebar.section"]
        moved_lines = self.browse()

        for channel_id in channel_ids or []:
            if channel_id == target_channel_id:
                continue

            old_line = self.search([
                ("user_id", "=", self.env.user.id),
                ("channel_id", "=", channel_id),
            ], limit=1)
            if old_line:
                old_sections |= old_line.section_id

            line = self._get_or_create_line(channel_id, target_section.id)
            moved_lines |= line

        section_lines = self.search([
            ("section_id", "=", target_section.id),
            ("id", "not in", moved_lines.ids),
        ], order="sequence, id")

        ordered = []
        inserted = False
        moved_ids = moved_lines.sorted(key=lambda l: (l.sequence, l.id)).ids

        for line in section_lines:
            if line.id == target_line.id and not inserted:
                ordered.extend(moved_ids)
                inserted = True
            ordered.append(line.id)

        if not inserted:
            ordered.extend(moved_ids)

        seq = 10
        for line in self.browse(ordered):
            line.sequence = seq
            seq += 10

        for sec in old_sections:
            if sec.id != target_section.id:
                self._normalize_section_sequences(sec)

        return True

    @api.model
    def move_channels_after_channel(self, channel_ids, target_channel_id):
        target_line = self.search([
            ("user_id", "=", self.env.user.id),
            ("channel_id", "=", target_channel_id),
        ], limit=1)
        if not target_line:
            raise UserError(_("Không tìm thấy kênh đích trong section."))

        target_section = target_line.section_id
        old_sections = self.env["discuss.sidebar.section"]
        moved_lines = self.browse()

        for channel_id in channel_ids or []:
            if channel_id == target_channel_id:
                continue

            old_line = self.search([
                ("user_id", "=", self.env.user.id),
                ("channel_id", "=", channel_id),
            ], limit=1)
            if old_line:
                old_sections |= old_line.section_id

            line = self._get_or_create_line(channel_id, target_section.id)
            moved_lines |= line

        section_lines = self.search([
            ("section_id", "=", target_section.id),
            ("id", "not in", moved_lines.ids),
        ], order="sequence, id")

        ordered = []
        inserted = False
        moved_ids = moved_lines.sorted(key=lambda l: (l.sequence, l.id)).ids

        for line in section_lines:
            ordered.append(line.id)
            if line.id == target_line.id and not inserted:
                ordered.extend(moved_ids)
                inserted = True

        if not inserted:
            ordered.extend(moved_ids)

        seq = 10
        for line in self.browse(ordered):
            line.sequence = seq
            seq += 10

        for sec in old_sections:
            if sec.id != target_section.id:
                self._normalize_section_sequences(sec)

        return True