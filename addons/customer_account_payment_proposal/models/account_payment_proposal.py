from odoo import models, fields, api, _
from odoo.exceptions import UserError
from markupsafe import Markup
from datetime import timedelta
from num2words import num2words
import logging

_logger = logging.getLogger(__name__)


class AccountPaymentProposal(models.Model):
    _name = "account.payment.proposal"
    _description = "Giấy đề nghị giải chi"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"

    # ========== THÔNG TIN CƠ BẢN ==========
    name = fields.Char(string="Số chứng từ", readonly=True, copy=False, default="/")
    date_request = fields.Date(string="Ngày đề nghị", default=fields.Date.context_today)
    user_id = fields.Many2one("res.users", string="Người tạo", default=lambda self: self.env.user, readonly=True)
    department_id = fields.Many2one(
        "hr.department",
        string="Phòng ban",
        required=True,
        default=lambda self: self.env.user.employee_id.department_id.id,
    )
    manager_id = fields.Many2one(
        "hr.employee",
        string="Người quản lý",
        compute="_compute_manager_id",
        store=True,
    )
    director_user_id = fields.Many2one(
        "res.users",
        string="Giám đốc duyệt",
        default=lambda self: self._default_director_user(),
        readonly=True,
    )
    project_id = fields.Many2one(
        "project.project",
        string="Dự án liên quan",
        help="Chọn dự án hoặc công trình liên quan đến khoản chi này"
    )

    # ========== TIỀN TỆ ==========
    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id, string="Loại tiền"
    )
    total_amount = fields.Monetary(
        string="Tổng chi thực tế", currency_field="currency_id", compute="_compute_totals", store=True
    )
    amount_advance = fields.Monetary(string="Số tiền tạm ứng", currency_field="currency_id")
    amount_refund = fields.Monetary(
        string="Số tiền hoàn ứng", currency_field="currency_id", compute="_compute_totals", store=True
    )
    amount_remain = fields.Monetary(
        string="Số tiền còn lại thanh toán", currency_field="currency_id", compute="_compute_totals", store=True
    )
    amount_in_words = fields.Char(
        string="Số tiền còn lại bằng chữ", compute="_compute_amount_in_words", store=True
    )
    note = fields.Text(string="Ghi chú")
    line_ids = fields.One2many("account.payment.proposal.line", "proposal_id", string="Chi tiết chứng từ")

    # ========== TRẠNG THÁI DUYỆT ==========
    state = fields.Selection(
        [
            ("draft", "Nháp"),
            ("submitted", "Chờ trưởng phòng duyệt"),
            ("dept_approved", "Chờ kế toán duyệt"),
            ("account_approved", "Chờ giám đốc duyệt"),
            ("director_approved", "Chờ kế toán chi"),
            ("paid", "Đã chi tiền"),
            ("rejected", "Từ chối"),
        ],
        default="draft",
        string="Trạng thái",
    )
    manager_approved_at   = fields.Datetime(string="TG trưởng phòng duyệt", tracking=True)
    accountant_approved_at = fields.Datetime(string="TG kế toán duyệt", tracking=True)
    director_approved_at   = fields.Datetime(string="TG giám đốc duyệt", tracking=True)
    # ========== TÍNH TOÁN ==========
    @api.depends("line_ids.amount", "amount_advance")
    def _compute_totals(self):
        for rec in self:
            total = sum(rec.line_ids.mapped("amount"))
            rec.total_amount = total
            if rec.amount_advance:
                if total < rec.amount_advance:
                    rec.amount_refund = rec.amount_advance - total
                    rec.amount_remain = 0
                else:
                    rec.amount_refund = 0
                    rec.amount_remain = total - rec.amount_advance
            else:
                rec.amount_refund = 0
                rec.amount_remain = total

    @api.depends("department_id")
    def _compute_manager_id(self):
        for record in self:
            record.manager_id = record.department_id.manager_id if record.department_id else False

    @api.depends("amount_remain")
    def _compute_amount_in_words(self):
        for rec in self:
            if rec.amount_remain:
                try:
                    rec.amount_in_words = num2words(rec.amount_remain, lang="vi").capitalize() + " đồng"
                except Exception:
                    rec.amount_in_words = ""
            else:
                rec.amount_in_words = ""
    can_submit = fields.Boolean(compute="_compute_permissions", string="Có thể gửi duyệt")
    can_approve_manager = fields.Boolean(compute="_compute_permissions", string="Trưởng phòng duyệt được")
    can_approve_accountant = fields.Boolean(compute="_compute_permissions", string="Kế toán duyệt được")
    can_approve_director = fields.Boolean(compute="_compute_permissions", string="Giám đốc duyệt được")
    can_paid = fields.Boolean(compute="_compute_permissions", string="Kế toán chi được")
    can_reset_draft = fields.Boolean(compute="_compute_permissions", string="Có thể hóa nháp")
    can_reject = fields.Boolean(compute="_compute_permissions", string="Có thể từ chối")
    @api.depends("state", "user_id", "manager_id", "director_user_id")
    def _compute_permissions(self):
        """Xác định ai được thấy nút nào"""
        for rec in self:
            current_user = self.env.user
            rec.can_submit = (
                rec.state == "draft" and current_user == rec.user_id
            )
            rec.can_approve_manager = (
                rec.state == "submitted"
                and rec.manager_id
                and rec.manager_id.user_id == current_user
            )

            # Kiểm tra nếu user thuộc nhóm kế toán
            accountant_group = self.env.ref("account.group_account_manager", raise_if_not_found=False)
            is_accountant = accountant_group and current_user in accountant_group.users

            rec.can_approve_accountant = (
                rec.state == "dept_approved" and is_accountant
            )

            rec.can_approve_director = (
                rec.state == "account_approved"
                and rec.director_user_id == current_user
            )

            rec.can_paid = (
                rec.state in ["director_approved", "account_approved"] and is_accountant and current_user != rec.director_user_id
            )
            rec.can_reset_draft = (
                rec.state == "rejected"
            )
            rec.can_reject = (
            (rec.state == "submitted" and rec.manager_id and rec.manager_id.user_id == current_user)
            or (rec.state == "dept_approved" and is_accountant)
            or (rec.state == "account_approved" and rec.director_user_id == current_user)
        )

    @api.model
    def _default_director_user(self):
        """Tự động lấy người thuộc nhóm Giám đốc"""
        try:
            group = self.env.ref("custom_director_role.group_director", raise_if_not_found=False)
            if group:
                user = self.env["res.users"].search([("groups_id", "in", group.id)], limit=1)
                return user.id or False
        except Exception:
            return False
        return False

    # ========== TẠO RECORD ==========
    @api.model
    def create(self, vals):
        if vals.get("name", "/") == "/":
            vals["name"] = self.env["ir.sequence"].next_by_code("account.payment.proposal")
        return super().create(vals)
    # ========== HÀNH ĐỘNG ==========
    def action_submit(self):
        accountant_group = self.env.ref("account.group_account_manager", raise_if_not_found=False)
        current_user = self.env.user

        for rec in self:
            if not rec.line_ids:
                raise UserError(_("Phải có ít nhất một dòng chi tiết trước khi gửi duyệt."))

            # ===== 1) Nếu người gửi là KẾ TOÁN → nhảy thẳng tới account_approved =====
            if accountant_group and current_user in accountant_group.users:
                rec.state = "account_approved"
                rec.accountant_approved_at = fields.Datetime.now()

                director_partner = rec.director_user_id.partner_id.id if rec.director_user_id else None

                rec._send_notification(
                    "💰 Phiếu giải chi do kế toán gửi, chuyển trực tiếp cho giám đốc duyệt.",
                    [director_partner] if director_partner else []
                )

                if rec.director_user_id:
                    rec.activity_schedule(
                        activity_type_id=self.env.ref("mail.mail_activity_data_todo").id,
                        user_id=rec.director_user_id.id,
                        summary=f"Duyệt phiếu giải chi {rec.name}",
                        note=f"📌 Phiếu giải chi <b>{rec.name}</b> đang chờ giám đốc duyệt.",
                        date_deadline=fields.Date.today() + timedelta(days=2),
                    )
                continue

            # ===== 2) Nếu người gửi là TRƯỞNG PHÒNG → bỏ qua bước 'submitted' =====
            if rec.manager_id and rec.manager_id.user_id == current_user:
                rec.state = "dept_approved"
                rec.manager_approved_at = fields.Datetime.now()

                rec._send_notification(
                    "👨‍💼 Trưởng phòng đã gửi và tự duyệt, chuyển cho kế toán kiểm tra.",
                    rec._get_accountant_partners()
                )
                continue

            # ===== 3) Người gửi KHÔNG phải kế toán / trưởng phòng → Luồng cũ =====
            rec.state = "submitted"
            rec._send_notification(
                "📤 Phiếu giải chi đã được gửi cho trưởng phòng duyệt.",
                [rec.manager_id.user_id.partner_id.id] if rec.manager_id and rec.manager_id.user_id else [],
            )

    def action_approve_manager(self):
        for rec in self:
            if rec.state != "submitted":
                raise UserError(_("Chỉ trưởng phòng có thể duyệt bước này."))
            rec.state = "dept_approved"
            rec.manager_approved_at = fields.Datetime.now()
            rec._send_notification("✅ Trưởng phòng đã duyệt, chuyển cho kế toán kiểm tra.", rec._get_accountant_partners())

    def action_approve_accountant(self):
        for rec in self:
            if rec.state != "dept_approved":
                raise UserError(_("Chỉ kế toán được duyệt bước này."))
            rec.state = "account_approved"
            rec.accountant_approved_at = fields.Datetime.now()

            director_partner = rec.director_user_id.partner_id.id if rec.director_user_id else None
            rec._send_notification("💰 Kế toán đã duyệt, chờ giám đốc xác nhận.", [director_partner] if director_partner else [])

            if rec.director_user_id:
                rec.activity_schedule(
                    activity_type_id=self.env.ref("mail.mail_activity_data_todo").id,
                    user_id=rec.director_user_id.id,
                    summary=f"Duyệt phiếu giải chi {rec.name}",
                    note=f"📌 Phiếu giải chi <b>{rec.name}</b> đang chờ duyệt.",
                    date_deadline=fields.Date.today() + timedelta(days=2),
                )

    def action_approve_director(self):
        for rec in self:
            if rec.state != "account_approved":
                raise UserError(_("Chỉ giám đốc được duyệt bước này."))
            rec.state = "director_approved"
            rec.director_approved_at = fields.Datetime.now()
            rec._send_notification("🏁 Giám đốc đã duyệt, chuyển lại cho kế toán xử lý chi.", rec._get_accountant_partners())
            rec._close_activity(rec.director_user_id)

    def action_paid(self):
        self.ensure_one()
        if self.state not in ["director_approved","account_approved"]:
            raise UserError(_("Chỉ được tạo chứng từ sau khi giám đốc duyệt."))
        return {
        "type": "ir.actions.act_window",
        "res_model": "account.payment.proposal.wizard",
        "view_mode": "form",
        "target": "new",
        "context": {
            "default_payment_proposal_id": self.id,
        },
    }
    def action_done (self):
        self.ensure_one()
        for rec in self:
            if rec.state not in ["account_approved", "director_approved"]:
                raise UserError(_("Chỉ xong khi giám đốc duyệt bước này."))
            rec.state = "paid"
    def action_reset_draft (self):
        self.ensure_one()
        for rec in self:
            if rec.state != "rejected":
                raise UserError(_("Chỉ reset lại những phiếu bị từ chối "))
            rec.state = "draft"



    def action_reject(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Nhập lý do từ chối",
            "res_model": "account.payment.proposal.reject.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_proposal_id": self.id},
        }

    # ========== THÔNG BÁO & CÔNG CỤ ==========
    def _send_notification(self, message, partner_ids=None):
        """Gửi thông báo Chatter + Discuss (auto subscribe nếu chưa)"""
        partner_ids = [pid for pid in (partner_ids or []) if pid]
        if not partner_ids:
            return

        # Đảm bảo các đối tượng được theo dõi
        new_partners = [p for p in partner_ids if p not in self.message_partner_ids.ids]
        if new_partners:
            self.message_subscribe(partner_ids=new_partners)

        self.message_post(
            body=Markup(message),
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
            partner_ids=partner_ids,
        )

    def _get_accountant_partners(self):
        """Trả về partner_id của tất cả kế toán viên (loại giám đốc ra nếu có)"""
        accounting_group = self.env.ref("account.group_account_manager", raise_if_not_found=False)
        if not accounting_group:
            return []

        # Lấy tất cả user kế toán
        accountant_users = accounting_group.users

        # Loại user giám đốc nếu có
        if self.director_user_id:
            accountant_users = accountant_users - self.director_user_id

        # Trả về danh sách partner_id duy nhất
        return list({u.partner_id.id for u in accountant_users if u.partner_id})

    def _close_activity(self, user, xmlid="mail.mail_activity_data_todo"):
        """Tự đóng nhắc việc khi đã duyệt"""
        if not user:
            return
        act_type = self.env.ref(xmlid)
        acts = self.env["mail.activity"].search([
            ("res_model", "=", self._name),
            ("res_id", "=", self.id),
            ("activity_type_id", "=", act_type.id),
            ("user_id", "=", user.id),
        ])
        acts.action_feedback("Đã duyệt")

    receipt_ids = fields.One2many(
        "account.receipt", "payment_proposal_id", string="Phiếu thu liên quan"
    )
    payment_request_ids = fields.One2many(
        "account.payment.request", "payment_proposal_id", string="Phiếu chi liên quan"
    )

    # 🧮 Trường thống kê
    receipt_count = fields.Integer(string="Số phiếu thu", compute="_compute_related_counts", store=True)
    receipt_total = fields.Monetary(string="Tổng tiền thu", compute="_compute_related_counts", store=True, currency_field="currency_id")

    payment_count = fields.Integer(string="Số phiếu chi", compute="_compute_related_counts", store=True)
    payment_total = fields.Monetary(string="Tổng tiền chi", compute="_compute_related_counts", store=True, currency_field="currency_id")

    @api.depends("receipt_ids.amount", "payment_request_ids.total")
    def _compute_related_counts(self):
        for rec in self:
            rec.receipt_count = len(rec.receipt_ids)
            rec.receipt_total = sum(rec.receipt_ids.mapped("amount"))
            rec.payment_count = len(rec.payment_request_ids)
            rec.payment_total = sum(rec.payment_request_ids.mapped("total"))

    def action_view_receipts(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Phiếu thu liên quan",
            "res_model": "account.receipt",
            "view_mode": "tree,form",
            "domain": [("payment_proposal_id", "=", self.id)],
            "context": {"default_payment_proposal_id": self.id},
        }

    def action_view_payments(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Phiếu chi liên quan",
            "res_model": "account.payment.request",
            "view_mode": "tree,form",
            "domain": [("payment_proposal_id", "=", self.id)],
            "context": {"default_payment_proposal_id": self.id},
        }
