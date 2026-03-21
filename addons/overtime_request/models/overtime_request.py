# -*- coding: utf-8 -*-
from datetime import timedelta
from markupsafe import Markup

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class OvertimeRequest(models.Model):
    _name = "overtime.request"
    _description = "Phiếu đề xuất tăng ca"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"

    name = fields.Char(
        string="Mã phiếu",
        default="New",
        readonly=True,
        copy=False,
        tracking=True,
    )

    requested_by = fields.Many2one(
        "res.users",
        string="Người đề nghị",
        default=lambda self: self.env.user,
        readonly=True,
        tracking=True,
    )

    department_id = fields.Many2one(
        "hr.department",
        string="Phòng ban",
        required=True,
        default=lambda self: self.env.user.employee_id.department_id.id if self.env.user.employee_id else False,
        tracking=True,
    )

    manager_id = fields.Many2one(
        "hr.employee",
        string="Trưởng phòng",
        compute="_compute_manager_id",
        store=True,
        readonly=True,
    )

    director_user_id = fields.Many2one(
        "res.users",
        string="Giám đốc",
        default=lambda self: self._default_director_user(),
        readonly=True,
    )

    project_id = fields.Many2one(
        "project.project",
        string="Dự án",
        tracking=True,
    )

    contract_num = fields.Char(
        string="Số hợp đồng",
        related="project_id.num_contract",
        store=True,
        readonly=True,
    )

    work_item_ids = fields.Many2many(
        "project.work.item",
        "overtime_request_work_item_rel",
        "request_id",
        "work_item_id",
        string="Hạng mục",
        tracking=True,
        domain="[('project_id', '=', project_id)]",
    )

    work_item_names = fields.Char(
        string="Hạng mục",
        compute="_compute_work_item_names",
        store=True,
    )

    overtime_date = fields.Date(
        string="Ngày tăng ca",
        required=True,
        tracking=True,
    )

    reason = fields.Text(
        string="Lý do tăng ca",
        required=True,
        tracking=True,
    )

    line_ids = fields.One2many(
        "overtime.request.line",
        "request_id",
        string="Danh sách người tăng ca",
        copy=True,
    )

    state = fields.Selection([
        ("draft", "Nháp"),
        ("reviewed_manager", "Trưởng phòng đang duyệt"),
        ("reviewed_hr", "Nhân sự đang duyệt"),
        ("approved", "Giám đốc đang duyệt"),
        ("done", "Đã duyệt"),
        ("rejected", "Từ chối"),
        ("canceled", "Đã hủy"),
    ], string="Trạng thái", default="draft", tracking=True)

    date_submitted = fields.Datetime(string="Ngày gửi duyệt", readonly=True)
    date_reviewed_manager = fields.Datetime(string="Ngày trưởng phòng duyệt", readonly=True)
    date_reviewed_hr = fields.Datetime(string="Ngày nhân sự duyệt", readonly=True)
    date_approved = fields.Datetime(string="Ngày giám đốc duyệt", readonly=True)

    manager_approved_by = fields.Many2one(
        "res.users",
        string="Người duyệt trưởng phòng",
        readonly=True,
    )
    hr_approved_by = fields.Many2one(
        "res.users",
        string="Người duyệt nhân sự",
        readonly=True,
    )
    director_approved_by = fields.Many2one(
        "res.users",
        string="Người duyệt giám đốc",
        readonly=True,
    )

    reject_reason = fields.Text(string="Lý do từ chối", tracking=True)

    show_button_submit = fields.Boolean(compute="_compute_show_buttons")
    show_button_manager_approve = fields.Boolean(compute="_compute_show_buttons")
    show_button_hr_approve = fields.Boolean(compute="_compute_show_buttons")
    show_button_director_approve = fields.Boolean(compute="_compute_show_buttons")
    show_button_reject = fields.Boolean(compute="_compute_show_buttons")
    show_button_cancel = fields.Boolean(compute="_compute_show_buttons")
    show_button_reset_draft = fields.Boolean(compute="_compute_show_buttons")
    show_button_withdraw_submit = fields.Boolean(compute="_compute_show_buttons")

    attachment_ids = fields.Many2many(
        "ir.attachment",
        "overtime_request_ir_attachments_rel",
        "request_id",
        "attachment_id",
        string="Tệp đính kèm",
    )

    @api.model
    def _default_director_user(self):
        group = self.env.ref("custom_director_role.group_director", raise_if_not_found=False)
        if not group:
            return False
        user = self.env["res.users"].search([("groups_id", "in", group.id)], limit=1)
        return user.id if user else False

    @api.depends("department_id")
    def _compute_manager_id(self):
        for rec in self:
            rec.manager_id = rec.department_id.manager_id if rec.department_id else False

    @api.depends("work_item_ids", "work_item_ids.name")
    def _compute_work_item_names(self):
        for rec in self:
            rec.work_item_names = ", ".join(rec.work_item_ids.mapped("name")) if rec.work_item_ids else ""

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        work_item_id = self.env.context.get("default_work_item_id")
        if work_item_id:
            work_item = self.env["project.work.item"].browse(work_item_id)
            if work_item.exists():
                res["work_item_ids"] = [(6, 0, [work_item.id])]
                res["project_id"] = work_item.project_id.id
        return res

    @api.onchange("work_item_ids")
    def _onchange_work_item_ids(self):
        if self.work_item_ids and not self.project_id:
            self.project_id = self.work_item_ids[0].project_id.id

    @api.onchange("project_id")
    def _onchange_project_id(self):
        if self.project_id and self.work_item_ids:
            self.work_item_ids = self.work_item_ids.filtered(
                lambda w: w.project_id == self.project_id
            )
        elif not self.project_id:
            self.work_item_ids = [(5, 0, 0)]

        return {
            "domain": {
                "work_item_ids": [("project_id", "=", self.project_id.id)]
            }
        }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("overtime.request") or "OT/0000"
        return super().create(vals_list)

    def unlink(self):
        for rec in self:
            if rec.state not in ("draft", "canceled", "rejected"):
                raise UserError(_("Chỉ được xóa phiếu ở trạng thái Nháp / Đã hủy / Từ chối."))
        return super().unlink()

    @api.constrains("line_ids")
    def _check_lines(self):
        for rec in self:
            if not rec.line_ids:
                raise ValidationError(_("Phiếu tăng ca phải có ít nhất một dòng nhân sự tăng ca."))

    def _send_notification(self, message, partner_ids=None):
        self.ensure_one()
        partner_ids = partner_ids or []

        existing_followers = self.message_partner_ids.ids
        new_partners = [pid for pid in partner_ids if pid not in existing_followers]
        if new_partners:
            self.message_subscribe(partner_ids=new_partners)

        self.message_post(
            body=Markup(message),
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
            partner_ids=partner_ids,
        )

    def _get_approval_partners(self, include_manager=False, include_hr=False, include_director=False):
        self.ensure_one()
        partner_ids = []

        if self.requested_by.partner_id:
            partner_ids.append(self.requested_by.partner_id.id)

        if include_manager and self.manager_id and self.manager_id.user_id and self.manager_id.user_id.partner_id:
            pid = self.manager_id.user_id.partner_id.id
            if pid not in partner_ids:
                partner_ids.append(pid)

        if include_hr:
            hr_group = self.env.ref("overtime_request.group_overtime_hr", raise_if_not_found=False)
            if hr_group:
                for user in hr_group.users:
                    if user.partner_id and user.partner_id.id not in partner_ids:
                        partner_ids.append(user.partner_id.id)

        if include_director and self.director_user_id and self.director_user_id.partner_id:
            pid = self.director_user_id.partner_id.id
            if pid not in partner_ids:
                partner_ids.append(pid)

        return partner_ids

    def _close_activity(self, user, xmlid="mail.mail_activity_data_todo", feedback="Đã xử lý"):
        self.ensure_one()
        act_type = self.env.ref(xmlid, raise_if_not_found=False)
        if not act_type or not user:
            return

        acts = self.env["mail.activity"].search([
            ("res_model", "=", self._name),
            ("res_id", "=", self.id),
            ("activity_type_id", "=", act_type.id),
            ("user_id", "=", user.id),
        ])
        if acts:
            acts.action_feedback(feedback=feedback)

    def action_submit(self):
        self.ensure_one()

        if self.state != "draft":
            raise UserError(_("Chỉ phiếu ở trạng thái nháp mới được gửi duyệt."))

        if not self.department_id:
            raise ValidationError(_("Vui lòng chọn phòng ban."))
        if not self.manager_id or not self.manager_id.user_id:
            raise ValidationError(_("Phòng ban chưa có Trưởng phòng hoặc Trưởng phòng chưa liên kết user."))
        if not self.line_ids:
            raise ValidationError(_("Vui lòng thêm danh sách người tăng ca."))

        if self.manager_id.user_id == self.env.user:
            self.write({
                "state": "reviewed_hr",
                "date_submitted": fields.Datetime.now(),
                "date_reviewed_manager": fields.Datetime.now(),
                "manager_approved_by": self.env.user.id,
            })
            partner_ids = self._get_approval_partners(include_hr=True)
            self._send_notification(
                f"<p>Phiếu tăng ca <strong>{self.name}</strong> đã được gửi thẳng cho "
                f"<strong>Nhân sự</strong> bởi trưởng phòng <em>{self.env.user.name}</em>.</p>",
                partner_ids,
            )
        else:
            self.write({
                "state": "reviewed_manager",
                "date_submitted": fields.Datetime.now(),
            })
            partner_ids = self._get_approval_partners(include_manager=True)
            self._send_notification(
                f"<p>Phiếu tăng ca <strong>{self.name}</strong> đã được gửi duyệt bởi "
                f"<em>{self.env.user.name}</em>.</p>",
                partner_ids,
            )

        return {"type": "ir.actions.client", "tag": "reload"}

    def action_manager_approve(self):
        self.ensure_one()

        if self.state != "reviewed_manager":
            raise UserError(_("Chỉ phiếu đang chờ Trưởng phòng duyệt mới được thực hiện thao tác này."))
        if self.manager_id.user_id != self.env.user:
            raise UserError(_("Bạn không phải Trưởng phòng của phiếu này."))

        self.write({
            "state": "reviewed_hr",
            "date_reviewed_manager": fields.Datetime.now(),
            "manager_approved_by": self.env.user.id,
        })
        partner_ids = self._get_approval_partners(include_hr=True)
        self._send_notification(
            f"<p>Phiếu tăng ca <strong>{self.name}</strong> đã được Trưởng phòng "
            f"<em>{self.env.user.name}</em> duyệt.</p>",
            partner_ids,
        )
        return {"type": "ir.actions.client", "tag": "reload"}

    def action_hr_approve(self):
        self.ensure_one()

        if self.state != "reviewed_hr":
            raise UserError(_("Chỉ phiếu đang chờ Nhân sự duyệt mới được thực hiện thao tác này."))
        if not self.env.user.has_group("overtime_request.group_overtime_hr"):
            raise UserError(_("Bạn không thuộc nhóm Nhân sự."))

        self.write({
            "state": "approved",
            "date_reviewed_hr": fields.Datetime.now(),
            "hr_approved_by": self.env.user.id,
        })

        partner_ids = self._get_approval_partners(include_director=True)
        self._send_notification(
            f"<p>Phiếu tăng ca <strong>{self.name}</strong> đã được Nhân sự "
            f"<em>{self.env.user.name}</em> duyệt và chuyển Giám đốc.</p>",
            partner_ids,
        )

        if self.director_user_id:
            self.activity_schedule(
                activity_type_id=self.env.ref("mail.mail_activity_data_todo").id,
                user_id=self.director_user_id.id,
                summary=f"Duyệt phiếu tăng ca {self.name}",
                note=f"Phiếu tăng ca <b>{self.name}</b> đang chờ duyệt.",
                date_deadline=fields.Date.today() + timedelta(days=2),
            )

        return {"type": "ir.actions.client", "tag": "reload"}

    def action_director_approve(self):
        self.ensure_one()

        if self.state != "approved":
            raise UserError(_("Chỉ phiếu đang chờ Giám đốc duyệt mới được thực hiện thao tác này."))
        if self.director_user_id != self.env.user:
            raise UserError(_("Bạn không phải Giám đốc được cấu hình duyệt phiếu này."))

        self.write({
            "state": "done",
            "date_approved": fields.Datetime.now(),
            "director_approved_by": self.env.user.id,
        })

        self._send_notification(
            f"<p>Phiếu tăng ca <strong>{self.name}</strong> đã được Giám đốc "
            f"<em>{self.env.user.name}</em> duyệt hoàn tất.</p>",
            self._get_approval_partners(),
        )

        if self.director_user_id:
            self._close_activity(user=self.director_user_id, feedback="Đã duyệt phiếu tăng ca")

        return {"type": "ir.actions.client", "tag": "reload"}

    def action_reject(self):
        self.ensure_one()

        allowed = (
            (self.state == "reviewed_manager" and self.manager_id.user_id == self.env.user)
            or (self.state == "reviewed_hr" and self.env.user.has_group("overtime_request.group_overtime_hr"))
            or (self.state == "approved" and self.director_user_id == self.env.user)
        )
        if not allowed:
            raise UserError(_("Bạn không có quyền từ chối phiếu này."))

        self.write({"state": "rejected"})
        self._send_notification(
            f"<p>Phiếu tăng ca <strong>{self.name}</strong> đã bị từ chối bởi "
            f"<em>{self.env.user.name}</em>.</p>",
            self._get_approval_partners(),
        )
        return {"type": "ir.actions.client", "tag": "reload"}

    def action_cancel(self):
        self.ensure_one()

        if self.requested_by != self.env.user:
            raise UserError(_("Chỉ người đề nghị mới được hủy phiếu."))
        if self.state != "draft":
            raise UserError(_("Chỉ phiếu nháp mới được hủy."))

        self.write({"state": "canceled"})
        self.message_post(body=Markup("<p>Phiếu đã được hủy.</p>"))
        return {"type": "ir.actions.client", "tag": "reload"}

    def action_reset_draft(self):
        self.ensure_one()

        if self.state != "rejected":
            raise UserError(_("Chỉ phiếu bị từ chối mới được đưa về nháp."))
        if self.requested_by != self.env.user:
            raise UserError(_("Chỉ người đề nghị mới được đưa phiếu về nháp."))

        self.write({
            "state": "draft",
            "date_submitted": False,
            "date_reviewed_manager": False,
            "date_reviewed_hr": False,
            "date_approved": False,
            "manager_approved_by": False,
            "hr_approved_by": False,
            "director_approved_by": False,
            "reject_reason": False,
        })
        self.message_post(body=Markup("<p>Phiếu đã được đưa về nháp.</p>"))
        return {"type": "ir.actions.client", "tag": "reload"}

    def action_withdraw_submit(self):
        self.ensure_one()

        if self.requested_by != self.env.user:
            raise UserError(_("Chỉ người đề nghị mới có quyền rút lại phiếu."))

        if self.state not in ("reviewed_manager", "reviewed_hr", "approved"):
            raise UserError(_("Chỉ được rút khi phiếu đang chờ duyệt."))

        old_state = self.state
        self.write({
            "state": "draft",
            "date_submitted": False,
            "date_reviewed_manager": False,
            "date_reviewed_hr": False,
            "date_approved": False,
            "manager_approved_by": False,
            "hr_approved_by": False,
            "director_approved_by": False,
        })

        if old_state == "approved" and self.director_user_id:
            self._close_activity(user=self.director_user_id, feedback="Phiếu đã được rút lại")

        partner_ids = self._get_approval_partners(
            include_manager=(old_state == "reviewed_manager"),
            include_hr=(old_state == "reviewed_hr"),
            include_director=(old_state == "approved"),
        )
        self._send_notification(
            f"<p>Người đề nghị <em>{self.env.user.name}</em> đã rút lại phiếu "
            f"<strong>{self.name}</strong> để chỉnh sửa.</p>",
            partner_ids,
        )

        return {"type": "ir.actions.client", "tag": "reload"}

    @api.depends("state", "requested_by", "manager_id", "director_user_id")
    def _compute_show_buttons(self):
        for rec in self:
            is_creator = rec.requested_by == self.env.user
            is_manager = rec.manager_id.user_id == self.env.user if rec.manager_id and rec.manager_id.user_id else False
            is_hr = self.env.user.has_group("overtime_request.group_overtime_hr")
            is_director = rec.director_user_id == self.env.user

            rec.show_button_submit = rec.state == "draft" and is_creator
            rec.show_button_manager_approve = rec.state == "reviewed_manager" and is_manager
            rec.show_button_hr_approve = rec.state == "reviewed_hr" and is_hr
            rec.show_button_director_approve = rec.state == "approved" and is_director
            rec.show_button_reject = (
                (rec.state == "reviewed_manager" and is_manager)
                or (rec.state == "reviewed_hr" and is_hr)
                or (rec.state == "approved" and is_director)
            )
            rec.show_button_cancel = rec.state == "draft" and is_creator
            rec.show_button_reset_draft = rec.state == "rejected" and is_creator
            rec.show_button_withdraw_submit = rec.state in ("reviewed_manager", "reviewed_hr", "approved") and is_creator


class OvertimeRequestLine(models.Model):
    _name = "overtime.request.line"
    _description = "Chi tiết tăng ca"
    _order = "id"

    request_id = fields.Many2one(
        "overtime.request",
        string="Phiếu tăng ca",
        required=True,
        ondelete="cascade",
    )

    employee_id = fields.Many2one(
        "hr.employee",
        string="Nhân viên",
        required=True,
    )

    time_start = fields.Float(
        string="Bắt đầu",
        required=True,
        help="Nhập theo giờ thập phân. Ví dụ: 17.5 = 17:30",
    )

    time_end = fields.Float(
        string="Kết thúc",
        required=True,
        help="Nhập theo giờ thập phân. Ví dụ: 20.0 = 20:00",
    )

    hours = fields.Float(
        string="Số giờ",
        compute="_compute_hours",
        store=True,
    )

    work_content = fields.Text(
        string="Nội dung công việc",
        required=True,
    )

    note = fields.Char(string="Ghi chú")

    @api.depends("time_start", "time_end")
    def _compute_hours(self):
        for rec in self:
            if rec.time_start is not False and rec.time_end is not False and rec.time_end >= rec.time_start:
                rec.hours = rec.time_end - rec.time_start
            else:
                rec.hours = 0.0

    @api.constrains("time_start", "time_end")
    def _check_time_range(self):
        for rec in self:
            if rec.time_start < 0 or rec.time_start > 24:
                raise ValidationError(_("Giờ bắt đầu phải nằm trong khoảng 0 đến 24."))
            if rec.time_end < 0 or rec.time_end > 24:
                raise ValidationError(_("Giờ kết thúc phải nằm trong khoảng 0 đến 24."))
            if rec.time_end <= rec.time_start:
                raise ValidationError(_("Giờ kết thúc phải lớn hơn giờ bắt đầu."))