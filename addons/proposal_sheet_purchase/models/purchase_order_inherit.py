# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, float_is_zero


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    # Trạng thái hàng hóa: điều khiển bằng nút + tự set "Đã giao" khi nhận hàng
    shipping_status = fields.Selection([
        ('not_shipped', 'Chưa giao'),
        ('in_progress', 'Đang giao'),
        ('done', 'Đã giao'),
    ], string="Trạng thái hàng hóa", default='not_shipped', tracking=True)

    # Liên kết để hiển thị (nếu bạn đã có thì giữ nguyên)
    proposal_sheet_id = fields.Many2one("proposal.sheet", string="Phiếu Đề Xuất", index=True, ondelete="set null")
    project_id = fields.Many2one("project.project", string="Dự án", compute="_compute_project_task", store=False, readonly=True)
    task_id = fields.Many2one("project.task", string="Nhiệm vụ", compute="_compute_project_task", store=False, readonly=True)

    # Theo dõi phiếu chi (giữ nguyên nếu bạn đã có)
    payment_request_ids = fields.One2many("account.payment.request", "purchase_id", string="Phiếu chi")
    payment_request_count = fields.Integer(compute="_compute_payment_request_count", string="Số phiếu chi")

    # Theo dõi thanh toán (giữ nguyên nếu bạn đã có)
    amount_paid = fields.Monetary(string="Đã thanh toán", currency_field="currency_id",
                                  compute="_compute_payment_progress", store=True)
    amount_to_pay = fields.Monetary(string="Còn lại", currency_field="currency_id",
                                    compute="_compute_payment_progress", store=True)
    payment_progress = fields.Float(string="Tiến độ thanh toán (%)",
                                    compute="_compute_payment_progress", store=True)
    payment_status = fields.Selection([
        ("no", "Chưa thanh toán"),
        ("partial", "Thanh toán một phần"),
        ("paid", "Đã thanh toán hết"),
    ], string="Trạng thái thanh toán", compute="_compute_payment_progress", store=True)
    is_paid = fields.Boolean(string="Đã thanh toán hết", compute="_compute_payment_progress", store=True)

    # Khóa tạo phiếu chi (giữ nguyên nếu bạn đã có)
    amount_requested = fields.Monetary(string="Đã yêu cầu chi", currency_field="currency_id",
                                       compute="_compute_request_locks", store=True)
    has_full_request = fields.Boolean(string="Đã có phiếu chi toàn bộ", compute="_compute_request_locks", store=True)
    is_fully_requested = fields.Boolean(string="Đã yêu cầu đủ", compute="_compute_request_locks", store=True)

    # Cấu hình auto-pay khi xác nhận (giữ nguyên nếu bạn đã có)
    auto_payment_on_confirm = fields.Boolean(string="Tạo phiếu chi khi xác nhận", default=False)
    payment_on_confirm_type = fields.Selection([("advance", "Tạm ứng"), ("full", "Thanh toán toàn bộ")],
                                               string="Kiểu thanh toán khi xác nhận", default="full")
    advance_amount_type = fields.Selection([("percent", "Theo % tổng PO"), ("fixed", "Theo số tiền")],
                                           string="Cách tính tạm ứng", default="percent")
    advance_percent = fields.Float(string="Tạm ứng (%)", default=30.0)
    advance_amount = fields.Monetary(string="Tạm ứng (số tiền)", currency_field="currency_id")

    # ==== Computes ngắn gọn (bạn có thể giữ code cũ của mình nếu đã có) ====
    @api.depends("proposal_sheet_id")
    def _compute_project_task(self):
        for po in self:
            po.project_id = po.proposal_sheet_id.project_id if po.proposal_sheet_id else False
            po.task_id = po.proposal_sheet_id.task_id if po.proposal_sheet_id else False

    def _compute_payment_request_count(self):
        for po in self:
            po.payment_request_count = len(po.payment_request_ids)

    @api.depends("amount_total", "currency_id", "payment_request_ids.total", "payment_request_ids.state")
    def _compute_payment_progress(self):
        states_paid = ("done", "post")  # coi done & post là đã chi
        for po in self:
            currency = po.currency_id or po.company_id.currency_id
            paid = sum(pr.total for pr in po.payment_request_ids if pr.state in states_paid)
            po.amount_paid = paid
            remaining = (po.amount_total or 0.0) - paid
            cmp = float_compare(remaining, 0.0, precision_rounding=(currency.rounding if currency else 0.01))
            po.is_paid = (cmp <= 0)
            po.amount_to_pay = 0.0 if po.is_paid else max(remaining, 0.0)
            po.payment_progress = (min(100.0, max(0.0, paid * 100.0 / po.amount_total))
                                   if (po.amount_total or 0.0) > 0 else 0.0)
            po.payment_status = "paid" if po.is_paid else ("partial" if paid > 0 else "no")

    @api.depends("amount_total", "currency_id",
                 "payment_request_ids.total", "payment_request_ids.state", "payment_request_ids.payment_kind")
    def _compute_request_locks(self):
        not_cancel_states = ("draft", "confirmed", "post", "done")
        for po in self:
            currency = po.currency_id or po.company_id.currency_id
            reqs = po.payment_request_ids.filtered(lambda r: r.state in not_cancel_states)
            amount_req = sum(reqs.mapped("total")) or 0.0
            po.amount_requested = amount_req
            po.has_full_request = any(req.payment_kind == "full" for req in reqs)
            remaining = (po.amount_total or 0.0) - amount_req
            cmp = float_compare(remaining, 0.0, precision_rounding=(currency.rounding if currency else 0.01))
            po.is_fully_requested = (cmp <= 0)

    def _requested_total(self):
        self.ensure_one()
        not_cancel_states = ("draft", "confirmed", "post", "done")
        return sum(self.payment_request_ids.filtered(lambda r: r.state in not_cancel_states).mapped("total")) or 0.0

    def _check_can_create_payment_request(self, kind, amount_to_create=None):
        self.ensure_one()
        if self.has_full_request:
            raise UserError(_("Đơn hàng đã có Phiếu chi 'Thanh toán toàn bộ'."))
        if self.is_fully_requested:
            raise UserError(_("Các Phiếu chi hiện có đã đủ tổng giá trị đơn hàng."))
        if amount_to_create:
            currency = self.currency_id or self.company_id.currency_id
            leftover = (self.amount_total or 0.0) - self._requested_total()
            cmp = float_compare(leftover - amount_to_create, 0.0,
                                precision_rounding=(currency.rounding if currency else 0.01))
            if cmp < 0:
                raise UserError(_("Số tiền tạo thêm (%.2f) vượt quá số còn lại phải chi (%.2f).")
                                % (amount_to_create, leftover))

    # ==== Luồng tạo phiếu chi ====
    def action_view_payment_requests(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Phiếu chi"),
            "res_model": "account.payment.request",
            "view_mode": "tree,form",
            "domain": [("purchase_id", "=", self.id)],
            "context": {
                "default_purchase_id": self.id,
                "default_proposal_sheet_id": self.proposal_sheet_id.id if self.proposal_sheet_id else False,
                "default_project_id": self.project_id.id if self.project_id else False,
                "default_task_id": self.task_id.id if self.task_id else False,
            },
        }

    def _create_payment_request(self, kind, amount_override=None, payment_type="bank", journal_id=False, note=None):
        """kind: 'advance' | 'full'"""
        self.ensure_one()
        if kind not in ("advance", "full"):
            raise UserError(_("Kiểu thanh toán không hợp lệ."))

        amount_total = self.amount_total or 0.0
        if amount_override and amount_override > 0:
            pay_amount = amount_override
        else:
            if kind == "full":
                pay_amount = amount_total
            else:
                if self.advance_amount_type == "percent":
                    if self.advance_percent <= 0 or self.advance_percent > 100:
                        raise ValidationError(_("Phần trăm tạm ứng phải trong khoảng 0-100."))
                    pay_amount = amount_total * (self.advance_percent / 100.0)
                else:
                    if self.advance_amount <= 0:
                        raise ValidationError(_("Số tiền tạm ứng phải > 0."))
                    pay_amount = self.advance_amount

        self._check_can_create_payment_request(kind, pay_amount)

        proposal = self.proposal_sheet_id
        project = self.project_id
        task = self.task_id
        cost_classification = "project" if project else "office"

        vals = {
            "name": "/",
            "purchase_id": self.id,
            "proposal_sheet_id": proposal.id if proposal else False,
            "project_id": project.id if project else False,
            "task_id": task.id if task else False,
            "proposal_person_id": self.env.user.id,
            "total": pay_amount,
            "date": fields.Date.context_today(self),
            "currency_id": self.currency_id.id,
            "receive_person": self.partner_id.id,
            "payment_person": self.env.user.partner_id.id,
            "payment_type": payment_type,
            "journal_id": journal_id or False,
            "cost_classification": cost_classification,
            "expense_type": "material",
            "note": note or _("{} PO {} - NCC {}").format(
                "Tạm ứng" if kind == "advance" else "Thanh toán toàn bộ",
                self.name, self.partner_id.display_name
            ),
            "payment_kind": kind,
            "state": "confirmed",
        }
        pr = self.env["account.payment.request"].create(vals)

        # Theo flow: sau khi có tạm ứng/thanh toán, trạng thái mặc định là "Chưa giao"
        if self.state in ('purchase', 'done') and self.shipping_status == 'not_shipped':
            # Giữ nguyên 'not_shipped' (không đổi nếu đã chuyển 'in_progress')
            pass
        return pr

    def create_advance_payment_from_wizard(self, amount, payment_type="bank", journal_id=False, note=None):
        self.ensure_one()
        self._create_payment_request("advance", amount_override=amount,
                                     payment_type=payment_type, journal_id=journal_id, note=note)

    def action_create_payment_request_full(self):
        self.ensure_one()
        self._create_payment_request("full")
        return self.action_view_payment_requests()

    def action_open_advance_wizard(self):
        self.ensure_one()
        view_ref = "proposal_sheet_purchase.view_purchase_advance_payment_wizard_form"
        try:
            view_id = self.env.ref(view_ref).id
            views = [(view_id, "form")]
        except ValueError:
            views = [(False, "form")]
        return {
            "type": "ir.actions.act_window",
            "name": _("Tạo phiếu chi tạm ứng"),
            "res_model": "purchase.advance.payment.wizard",
            "view_mode": "form",
            "views": views,
            "target": "new",
            "context": {"active_id": self.id},
        }

    def action_create_payment_request_remaining(self):
        self.ensure_one()
        currency = self.currency_id or self.company_id.currency_id
        leftover = (self.amount_total or 0.0) - self._requested_total()
        cmp = float_compare(leftover, 0.0, precision_rounding=(currency.rounding if currency else 0.01))
        if cmp <= 0:
            raise UserError(_("Đơn hàng không còn số tiền phải chi."))
        self._create_payment_request("full", amount_override=leftover)
        return self.action_view_payment_requests()

    # ====== FLOW TRẠNG THÁI HÀNG HÓA ======
    def action_mark_shipping_in_progress(self):
        """
        Bấm 'Đang giao': chỉ khi PO đã xác nhận (purchase/done)
        và đã có tạm ứng/thanh toán (payment_status != 'no' hoặc amount_requested > 0),
        và trạng thái hiện tại là 'Chưa giao'.
        """
        for po in self:
            if po.state not in ('purchase', 'done'):
                raise UserError(_("Chỉ PO đã xác nhận mới chuyển sang 'Đang giao'."))
            if (po.payment_status == 'no') and (po.amount_requested <= 0):
                raise UserError(_("Cần có tạm ứng/ thanh toán trước khi chuyển 'Đang giao'."))
            if po.shipping_status != 'not_shipped':
                raise UserError(_("PO không ở trạng thái 'Chưa giao'."))
            po.shipping_status = 'in_progress'
            po.message_post(body=_("Trạng thái hàng hóa chuyển sang <b>Đang giao</b>."))
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    # Khi xác nhận PO, reset shipping_status về 'Chưa giao' (nếu trước đó là done do lặp)
    def button_confirm(self):
        res = super().button_confirm()
        for po in self:
            if po.state in ('purchase', 'done') and po.shipping_status == 'done':
                po.shipping_status = 'not_shipped'
        return res

    def action_mark_shipping_done(self):
        """
        Nút 'Nhận hàng' để kết thúc luồng giao hàng (đặt trạng thái 'Đã giao').
        Chỉ cho phép khi:
          - PO đã xác nhận (purchase/done)
          - Trạng thái hiện tại là 'Đang giao'
        Không tạo/ảnh hưởng tới kho; chỉ cập nhật cờ trạng thái hiển thị trên PO.
        """
        for po in self:
            if po.state not in ('purchase', 'done'):
                raise UserError(_("Chỉ PO đã xác nhận mới được 'Nhận hàng'."))
            if po.shipping_status != 'in_progress':
                raise UserError(_("Chỉ có thể 'Nhận hàng' khi trạng thái đang là 'Đang giao'."))
            po.shipping_status = 'done'
            po.message_post(body=_("Trạng thái hàng hóa chuyển sang <b>Đã giao</b> (cập nhật thủ công)."))
        return {'type': 'ir.actions.client', 'tag': 'reload'}
class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    goods_status = fields.Selection([
        ('not_shipped', 'Chưa giao'),
        ('partial', 'Đang giao'),
        ('done', 'Đã giao'),
    ], string="Trạng thái hàng", compute="_compute_goods_status", store=True)

    qty_remaining = fields.Float(string="Còn lại", compute="_compute_qty_remaining", store=True)

    @api.depends('product_qty', 'qty_received', 'state')
    def _compute_goods_status(self):
        for line in self:
            qty_total = line.product_qty or 0.0
            qty_recv = line.qty_received or 0.0
            if float_is_zero(qty_total, precision_rounding=1e-6):
                line.goods_status = 'not_shipped'
            elif float_is_zero(qty_recv, precision_rounding=1e-6):
                line.goods_status = 'not_shipped'
            else:
                cmp_full = float_compare(qty_recv, qty_total, precision_rounding=1e-6)
                line.goods_status = 'done' if cmp_full >= 0 else 'partial'

    @api.depends('product_qty', 'qty_received')
    def _compute_qty_remaining(self):
        for line in self:
            qty_total = line.product_qty or 0.0
            qty_recv = line.qty_received or 0.0
            remaining = qty_total - qty_recv
            line.qty_remaining = remaining if remaining > 0 else 0.0
