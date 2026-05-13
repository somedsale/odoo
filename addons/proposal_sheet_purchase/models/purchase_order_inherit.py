# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, float_is_zero
from markupsafe import Markup

# XMLID các stage
XID_STAGE_DELIVERY     = "contract_management.task_type_delivery"      # Giao hàng
XID_STAGE_PRODUCTION   = "contract_management.task_type_production"    # Sản xuất
XID_STAGE_INSTALLATION = "contract_management.task_type_installation"  # Thi công
XID_STAGE_ACCEPTANCE   = "contract_management.task_type_acceptance"    # Nghiệm thu

class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    # --- LIÊN KẾT PHIẾU ĐỀ XUẤT ---
    # Giữ M2O cũ cho backward compatibility / hiển thị nhanh 1 phiếu chính
    proposal_sheet_id = fields.Many2one(
        "proposal.sheet",
        string="Phiếu Đề Xuất (cũ)",
        index=True,
        ondelete="set null",
        help="Dùng cho tương thích cũ. Với PO gộp nhiều phiếu, hãy xem tab 'Phiếu Đề Xuất'.",
    )

    # Mới: Nhiều Phiếu Đề Xuất có thể gom chung thành 1 PO
    proposal_sheet_ids = fields.Many2many(
        "proposal.sheet",
        "proposal_sheet_purchase_rel",
        "purchase_id",
        "proposal_sheet_id",
        string="Phiếu Đề Xuất",
    )

    # Trạng thái hàng hóa
    shipping_status = fields.Selection([
        ('not_shipped', 'Chưa giao'),
        ('in_progress', 'Đang giao'),
        ('done', 'Đã giao'),
        ('cancelled', 'Đã hủy'),     # <-- NEW
    ], string="Trạng thái hàng hóa", default='not_shipped', tracking=True)

    # Project / Task: Không còn compute thuần từ proposal_sheet_id nữa,
    # mà từ toàn bộ proposal_sheet_ids. Ưu tiên sheet đầu tiên nếu nhiều.
    project_id = fields.Many2one(
        "project.project",
        string="Dự án",
        compute="_compute_project_task",
        inverse="_inverse_project_task",
        store=True,
    )
    task_id = fields.Many2one(
        "project.task",
        string="Nhiệm vụ",
        compute="_compute_project_task",
        inverse="_inverse_project_task",
        store=True,
    )
    main_proposal_sheet_id = fields.Many2one(
        "proposal.sheet",
        string="Phiếu đề xuất (cũ)",
        compute="_compute_main_proposal_sheet_id",
        store=False,
    )

    def _compute_main_proposal_sheet_id(self):
        for po in self:
            # Ưu tiên field cũ proposal_sheet_id (M2O),
            # nếu rỗng thì lấy cái đầu tiên trong proposal_sheet_ids (M2M)
            ps = po.proposal_sheet_id or (po.proposal_sheet_ids[:1] if hasattr(po, "proposal_sheet_ids") else False)
            po.main_proposal_sheet_id = ps and ps.id or False
    supplier_invoice_ids = fields.One2many(
        "supplier.invoice", "purchase_id", string="Hóa đơn NCC"
    )
    supplier_invoice_count = fields.Integer(
        string="Số hóa đơn NCC",
        compute="_compute_supplier_invoice_count"
    )

    payment_request_ids = fields.One2many(
        "account.payment.request", "purchase_id", string="Phiếu chi"
    )
    payment_request_count = fields.Integer(
        compute="_compute_payment_request_count", string="Số phiếu chi"
    )

    amount_paid = fields.Monetary(
        string="Đã thanh toán",
        currency_field="currency_id",
        compute="_compute_payment_progress", store=True)
    amount_to_pay = fields.Monetary(
        string="Còn lại",
        currency_field="currency_id",
        compute="_compute_payment_progress", store=True)
    payment_progress = fields.Float(
        string="Tiến độ thanh toán (%)",
        compute="_compute_payment_progress", store=True)
    payment_status = fields.Selection([
        ("no", "Chưa thanh toán"),
        ("partial", "Thanh toán một phần"),
        ("paid", "Đã thanh toán hết"),
    ], string="Trạng thái thanh toán",
       compute="_compute_payment_progress", store=True)
    is_paid = fields.Boolean(
        string="Đã thanh toán hết",
        compute="_compute_payment_progress", store=True)

    amount_requested = fields.Monetary(
        string="Đã yêu cầu chi",
        currency_field="currency_id",
        compute="_compute_request_locks", store=True)
    has_full_request = fields.Boolean(
        string="Đã có phiếu chi toàn bộ",
        compute="_compute_request_locks", store=True)
    is_fully_requested = fields.Boolean(
        string="Đã yêu cầu đủ",
        compute="_compute_request_locks", store=True)

    auto_payment_on_confirm = fields.Boolean(
        string="Tạo phiếu chi khi xác nhận", default=False)
    payment_on_confirm_type = fields.Selection(
        [("advance", "Tạm ứng"), ("full", "Thanh toán toàn bộ")],
        string="Kiểu thanh toán khi xác nhận", default="full")
    advance_amount_type = fields.Selection(
        [("percent", "Theo % tổng PO"), ("fixed", "Theo số tiền")],
        string="Cách tính tạm ứng", default="percent")
    advance_percent = fields.Float(string="Tạm ứng (%)", default=30.0)
    advance_amount = fields.Monetary(
        string="Tạm ứng (số tiền)", currency_field="currency_id")

    supplier_contract_id = fields.Many2one(
        "supplier.contract", string="Hợp đồng NCC", index=True)

    note = fields.Text(string="Ghi chú", translate=True)
    # Tổng quan: chưa nhập / nhập một phần / đã nhập đủ
    receiving_status = fields.Selection([
        ('none', 'Chưa nhập'),
        ('partial', 'Nhập một phần'),
        ('done', 'Đã nhập đủ'),
    ], string="Trạng thái nhập kho", compute="_compute_receiving_status", store=True)

    # Cờ nhanh: đã có bất kỳ lượng nào được nhập (đã có picking done) chưa
    has_inventory_receipt = fields.Boolean(
        string="Đã xác nhận nhập kho",
        compute="_compute_receiving_status",
        store=True,
        help="Bật khi có bất kỳ số lượng nào của PO đã được nhập kho (qty_received > 0)."
    )

    @api.depends('order_line.product_qty', 'order_line.qty_received', 'order_line.product_uom')
    def _compute_receiving_status(self):
        """
        Đánh giá theo qty_received của các dòng PO:
          - none: tất cả dòng đều qty_received == 0
          - done: tất cả dòng qty_received >= product_qty (tính theo rounding UoM riêng của dòng)
          - partial: còn lại
        Đồng thời đặt cờ has_inventory_receipt = (tổng qty_received > 0)
        """
        for po in self:
            lines = po.order_line.filtered(lambda l: l.display_type is False)
            if not lines:
                po.receiving_status = 'none'
                po.has_inventory_receipt = False
                continue

            any_received = False
            all_done = True
            all_zero = True

            for l in lines:
                qty = l.product_qty or 0.0
                rcv = l.qty_received or 0.0
                uom_round = l.product_uom.rounding or 0.01

                if float_compare(rcv, 0.0, precision_rounding=uom_round) > 0:
                    any_received = True
                    all_zero = False

                # nếu rcv < qty thì chưa “đủ”
                if float_compare(rcv, qty, precision_rounding=uom_round) < 0:
                    all_done = False

                # nếu rcv > 0 thì chắc chắn không còn là all_zero
                # (đã set ở trên)

            po.has_inventory_receipt = any_received
            if all_zero:
                po.receiving_status = 'none'
            elif all_done:
                po.receiving_status = 'done'
            else:
                po.receiving_status = 'partial'
    # ============================================================
    #  COMPUTES / HELPERS
    # ============================================================

    @api.depends("proposal_sheet_ids", "proposal_sheet_id")
    def _compute_project_task(self):
        """
        Ưu tiên lấy project/task chung từ danh sách proposal_sheet_ids (multi).
        Nếu rỗng thì fallback proposal_sheet_id (legacy).
        Nếu vẫn rỗng => giữ nguyên giá trị người dùng đã gán thủ công.
        """
        for po in self:
            sheets = po.proposal_sheet_ids
            if not sheets and po.proposal_sheet_id:
                sheets = po.proposal_sheet_id

            # Nếu nhiều sheet, giả định chúng cùng project/task (điều kiện đã check khi tạo).
            sheet_first = sheets[0] if sheets else False

            if sheet_first:
                po.project_id = sheet_first.project_id.id if sheet_first.project_id else po.project_id
                po.task_id = sheet_first.task_id.id if sheet_first.task_id else po.task_id
            else:
                # không overwrite thủ công
                po.project_id = po.project_id
                po.task_id = po.task_id

    def _inverse_project_task(self):
        """
        Cho phép user sửa thủ công trong form PO.
        Không cần đồng bộ ngược lại proposal_sheet.
        """
        for po in self:
            # intentionally empty
            pass

    def _compute_payment_request_count(self):
        for po in self:
            po.payment_request_count = len(po.payment_request_ids)

    @api.depends(
        "amount_total", "currency_id",
        "payment_request_ids.total", "payment_request_ids.state"
    )
    def _compute_payment_progress(self):
        states_paid = ("done", "post")  # coi done & post là đã chi
        for po in self:
            currency = po.currency_id or po.company_id.currency_id
            paid = sum(pr.total for pr in po.payment_request_ids if pr.state in states_paid)
            po.amount_paid = paid
            remaining = (po.amount_total or 0.0) - paid
            cmp = float_compare(
                remaining, 0.0,
                precision_rounding=(currency.rounding if currency else 0.01)
            )
            po.is_paid = (cmp <= 0)
            po.amount_to_pay = 0.0 if po.is_paid else max(remaining, 0.0)
            po.payment_progress = (
                min(100.0, max(0.0, paid * 100.0 / po.amount_total))
                if (po.amount_total or 0.0) > 0 else 0.0
            )
            po.payment_status = "paid" if po.is_paid else ("partial" if paid > 0 else "no")

    @api.depends(
        "amount_total", "currency_id",
        "payment_request_ids.total", "payment_request_ids.state", "payment_request_ids.payment_kind"
    )
    def _compute_request_locks(self):
        not_cancel_states = ("draft", "confirmed", "post", "done")
        for po in self:
            currency = po.currency_id or po.company_id.currency_id
            reqs = po.payment_request_ids.filtered(lambda r: r.state in not_cancel_states)
            amount_req = sum(reqs.mapped("total")) or 0.0
            po.amount_requested = amount_req
            po.has_full_request = any(req.payment_kind == "full" for req in reqs)
            remaining = (po.amount_total or 0.0) - amount_req
            cmp = float_compare(
                remaining, 0.0,
                precision_rounding=(currency.rounding if currency else 0.01)
            )
            po.is_fully_requested = (cmp <= 0)

    def _requested_total(self):
        self.ensure_one()
        not_cancel_states = ("draft", "confirmed", "post", "done")
        return sum(
            self.payment_request_ids.filtered(lambda r: r.state in not_cancel_states).mapped("total")
        ) or 0.0

    # ============================================================
    #  ACTIONS / WIZARDS
    # ============================================================

    def action_view_payment_requests(self):
        self.ensure_one()
        # chọn 1 phiếu đề xuất đại diện để fill ngữ cảnh (nếu có)
        first_sheet = self.proposal_sheet_ids[:1] or self.proposal_sheet_id
        return {
            "type": "ir.actions.act_window",
            "name": _("Phiếu chi"),
            "res_model": "account.payment.request",
            "view_mode": "tree,form",
            "domain": [("purchase_id", "=", self.id)],
            "context": {
                "default_purchase_id": self.id,
                "default_proposal_sheet_id": first_sheet.id if first_sheet else False,
                "default_project_id": self.project_id.id if self.project_id else False,
                "default_task_id": self.task_id.id if self.task_id else False,
            },
        }

    def action_view_supplier_contract(self):
        self.ensure_one()
        if not self.supplier_contract_id:
            raise UserError(_("Không có hợp đồng gắn với đơn hàng này."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Hợp đồng NCC"),
            "res_model": "supplier.contract",
            "view_mode": "form",
            "res_id": self.supplier_contract_id.id,
            "target": "current",
        }

    def _check_can_create_payment_request(self, kind, amount_to_create=None):
        self.ensure_one()
        if self.has_full_request:
            raise UserError(_("Đơn hàng đã có Phiếu chi 'Thanh toán toàn bộ'."))
        if self.is_fully_requested:
            raise UserError(_("Các Phiếu chi hiện có đã đủ tổng giá trị đơn hàng."))
        if amount_to_create:
            currency = self.currency_id or self.company_id.currency_id
            leftover = (self.amount_total or 0.0) - self._requested_total()
            cmp = float_compare(
                leftover - amount_to_create, 0.0,
                precision_rounding=(currency.rounding if currency else 0.01)
            )
            if cmp < 0:
                raise UserError(
                    _("Số tiền tạo thêm (%.2f) vượt quá số còn lại phải chi (%.2f).")
                    % (amount_to_create, leftover)
                )

    def _create_payment_request(self, kind, amount_override=None,
                                payment_type="bank", journal_id=False, note=None):
        """
        kind: 'advance' | 'full'
        """
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

        # lấy toàn bộ phiếu đề xuất từ PO
        sheets = self.proposal_sheet_ids
        if not sheets and self.proposal_sheet_id:
            sheets = self.proposal_sheet_id

        first_sheet = sheets[:1] if sheets else False

        project = self.project_id
        task = self.task_id
        contract = self.supplier_contract_id or self._get_or_create_supplier_contract()
        cost_classification = "project" if project else "office"

        # chuẩn bị line_ids cho phiếu chi
        line_vals = []
        if sheets:
            total_sheet_amount = sum((sheet.amount_total or 0.0) for sheet in sheets)

            # nếu tổng proposal > 0 => chia theo tỷ lệ
            if total_sheet_amount > 0:
                remaining = pay_amount
                for index, sheet in enumerate(sheets):
                    if index == len(sheets) - 1:
                        line_amount = remaining
                    else:
                        line_amount = pay_amount * ((sheet.amount_total or 0.0) / total_sheet_amount)
                        remaining -= line_amount

                    line_vals.append((0, 0, {
                        "line_type": "proposal",
                        "proposal_sheet_id": sheet.id,
                        "amount": line_amount,
                        "interpretation": sheet.name or _("Chi theo phiếu đề xuất"),
                    }))
            else:
                # nếu proposal không có amount_total thì chia đều
                count_sheet = len(sheets)
                if count_sheet:
                    base_amount = pay_amount / count_sheet
                    remaining = pay_amount
                    for index, sheet in enumerate(sheets):
                        if index == count_sheet - 1:
                            line_amount = remaining
                        else:
                            line_amount = base_amount
                            remaining -= line_amount

                        line_vals.append((0, 0, {
                            "line_type": "proposal",
                            "proposal_sheet_id": sheet.id,
                            "amount": line_amount,
                            "interpretation": sheet.name or _("Chi theo phiếu đề xuất"),
                        }))

        vals = {
            "name": "/",
            "purchase_id": self.id,
            "proposal_sheet_id": first_sheet.id if first_sheet else False,
            "supplier_contract_id": contract.id,
            "project_id": project.id if project else False,
            "task_id": task.id if task else False,
            "proposal_person_id": first_sheet.requested_by.id if first_sheet and first_sheet.requested_by else False,
            "date": first_sheet.date_proposal if first_sheet and first_sheet.date_proposal else fields.Date.context_today(self),
            "currency_id": self.currency_id.id,
            "receive_person": self.partner_id.id,
            "payment_person": self.env.user.partner_id.id,
            "supplier_id": self.partner_id.id,
            "payment_type": payment_type,
            "journal_id": journal_id or False,
            "cost_classification": cost_classification,
            "expense_type": "material",
            "note": note or _("{} PO {} - NCC {}").format(
                "Tạm ứng" if kind == "advance" else "Thanh toán toàn bộ",
                self.name, self.partner_id.display_name
            ),
            "payment_kind": kind,
            "state": "draft",
        }

        # Nếu PO có phiếu đề xuất thì tạo dòng chi tiết theo proposal
        if line_vals:
            vals["line_ids"] = line_vals

        # Nếu PO không có phiếu đề xuất thì gán tiền vào manual_total
        else:
            vals["manual_total"] = pay_amount

        pr = self.env["account.payment.request"].create(vals)

        if self.state in ("purchase", "done") and self.shipping_status == "not_shipped":
            pass
        return pr

    def create_advance_payment_from_wizard(self, amount,
                                           payment_type="bank",
                                           journal_id=False,
                                           note=None):
        self.ensure_one()
        self._create_payment_request(
            "advance",
            amount_override=amount,
            payment_type=payment_type,
            journal_id=journal_id,
            note=note,
        )

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
        cmp = float_compare(
            leftover, 0.0,
            precision_rounding=(currency.rounding if currency else 0.01)
        )
        if cmp <= 0:
            raise UserError(_("Đơn hàng không còn số tiền phải chi."))
        self._create_payment_request("full", amount_override=leftover)
        return self.action_view_payment_requests()

    # ============================================================
    #  SHIPPING / TASK STAGE FLOW
    # ============================================================

    def action_mark_shipping_in_progress(self):
        """
        'Đang giao'
        """
        for po in self:
            if po.state not in ('purchase', 'done'):
                raise UserError(_("Chỉ PO đã xác nhận mới chuyển sang 'Đang giao'."))
            if po.shipping_status != 'not_shipped':
                raise UserError(_("PO không ở trạng thái 'Chưa giao'."))
            po.shipping_status = 'in_progress'
            po.message_post(body=Markup("Trạng thái hàng hóa ➜ <b>Đang giao</b>."))
        self._auto_move_task_by_shipping()
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_mark_shipping_done(self):
        """
        'Nhận hàng'
        """
        for po in self:
            if po.state not in ('purchase', 'done'):
                raise UserError(_("Chỉ PO đã xác nhận mới được 'Nhận hàng'."))
            if po.shipping_status != 'in_progress':
                raise UserError(_("Chỉ có thể 'Nhận hàng' khi trạng thái đang là 'Đang giao'."))
            po.shipping_status = 'done'
            po.message_post(body=Markup("Trạng thái hàng hóa ➜ <b>Đã giao</b>."))
        self._auto_move_task_by_shipping()

        # Khi đã giao xong: đánh dấu tất cả phiếu đề xuất liên quan là done
        for po in self:
            for sheet in po.proposal_sheet_ids:
                sheet.action_done()
            if po.proposal_sheet_id:
                po.proposal_sheet_id.action_done()
        return {'type': 'ir.actions.client', 'tag': 'reload'}
    def _validate_single_receipt(self, picking, create_backorder=True):
        """Xác nhận 1 phiếu nhập (stock.picking) theo chuẩn Odoo 17:
        - Không tự set qty_done; để wizard Immediate Transfer xử lý.
        - Tự confirm/assign trước khi validate.
        """
        self.ensure_one()
        if picking.picking_type_code != 'incoming':
            return False

        # B1: đưa về trạng thái sẵn sàng
        if picking.state == 'draft':
            picking.action_confirm()
        if picking.state in ('confirmed', 'waiting'):
            picking.action_assign()

        # B2: validate & xử lý wizard phát sinh
        res = picking.button_validate()
        if isinstance(res, dict):
            # Immediate transfer wizard -> sẽ tự set số lượng done
            if res.get('res_model') == 'stock.immediate.transfer':
                wiz = self.env['stock.immediate.transfer'].browse(res.get('res_id'))
                wiz.process()
            # Backorder wizard
            elif res.get('res_model') == 'stock.backorder.confirmation':
                wiz = self.env['stock.backorder.confirmation'].browse(res.get('res_id'))
                if create_backorder:
                    wiz.process()
                else:
                    wiz.process_cancel()
            # Overprocessed wizard
            elif res.get('res_model') == 'stock.overprocessed.transfer':
                wiz = self.env['stock.overprocessed.transfer'].browse(res.get('res_id'))
                wiz.action_confirm()  # hoặc wiz.action_cancel() tùy nghiệp vụ

        return True


    def action_validate_existing_receipts(self):
        """
        Xác nhận tất cả phiếu nhập kho (incoming pickings) đã được tạo cho PO này.
        - Tự confirm/assign nếu cần
        - Tự điền quantity_done nếu chưa có
        - Tự xử lý immediate/backorder wizard
        """
        validated = 0
        for po in self:
            # Tìm pickings "incoming" gắn với PO:
            # liên kết vững nhất là qua move -> purchase_line_id -> order_id
            pickings = self.env['stock.picking'].search([
                ('picking_type_code', '=', 'incoming'),
                ('move_ids_without_package.purchase_line_id.order_id', '=', po.id),
                ('state', 'in', ['draft', 'confirmed', 'waiting', 'assigned'])
            ])
            for p in pickings:
                ok = po._validate_single_receipt(p)
                if ok:
                    validated += 1

        # Thông báo ngắn gọn
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Nhập kho"),
                'message': _("Đã xác nhận %s phiếu nhập.") % validated,
                'sticky': False,
                'type': 'success' if validated else 'warning',
            }
        }

    def button_confirm(self):
        res = super().button_confirm()
        for po in self:
            # tạo / gắn hợp đồng NCC
            contract = po._get_or_create_supplier_contract()
            # link chứng từ vào contract
            po._link_po_documents_to_contract(contract)
            # reset shipping_status nếu cần
            if po.state in ('purchase', 'done') and po.shipping_status == 'done':
                po.shipping_status = 'not_shipped'
        return res
    # NEW: Khi HỦY PO => chuyển shipping_status sang 'cancelled'
    def button_cancel(self):
        res = super().button_cancel()
        for po in self:
            if po.shipping_status != 'cancelled':
                po.shipping_status = 'cancelled'
                po.message_post(body=Markup("Trạng thái hàng hóa ➜ <b>Đã hủy</b> (PO bị hủy)."))
        # Hủy thì không tự động đẩy stage task
        return res

    # Khôi phục về Nháp => trả shipping_status về 'not_shipped' (tiện để người dùng làm lại luồng)
    def button_draft(self):
        res = super().button_draft()
        for po in self:
            # chỉ reset khi đang ở 'Đã hủy' để tránh đụng các trạng thái hợp lệ khác
            if po.shipping_status == 'cancelled':
                po.shipping_status = 'not_shipped'
                po.message_post(body=Markup("Trạng thái hàng hóa ➜ <b>Chưa giao</b> (Khôi phục về Nháp)."))
        return res
# 1) CHẶN Ở write: nếu state đổi thì cập nhật shipping_status + log
    def write(self, vals):
        prev_states = {po.id: po.state for po in self}
        res = super().write(vals)

        # Khi user/logic đổi state -> đồng bộ shipping_status
        if 'state' in vals:
            for po in self:
                old = prev_states.get(po.id)
                new = po.state
                # vào cancel
                if new == 'cancel' and po.shipping_status != 'cancelled':
                    po.shipping_status = 'cancelled'
                    po.message_post(body=Markup("Trạng thái hàng hóa ➜ <b>Đã hủy</b> (PO bị hủy)."))
                # quay về draft từ cancel
                if old == 'cancel' and new == 'draft' and po.shipping_status == 'cancelled':
                    po.shipping_status = 'not_shipped'
                    po.message_post(body=Markup("Trạng thái hàng hóa ➜ <b>Chưa giao</b> (Khôi phục về Nháp)."))

        # Nếu shipping_status đổi (bởi ai đó), vẫn đẩy stage task
        if 'shipping_status' in vals:
            self._auto_move_task_by_shipping()

        # Nếu thay đổi proposal_sheet_ids / proposal_sheet_id -> đảm bảo follower
        if 'proposal_sheet_ids' in vals or 'proposal_sheet_id' in vals:
            self._ensure_proposal_requester_follower()
        return res


    def _auto_move_task_by_shipping(self):
        """
        Stage Task tự động dựa trên shipping_status.
        Lưu ý: Giờ PO có thể link nhiều phiếu => sẽ xử lý tất cả task liên quan.
        Quy tắc như cũ:
          - in_progress  -> "Giao hàng" (nếu không cần sản xuất)
          - done         -> "Sản xuất" hoặc "Thi công"/"Nghiệm thu" tùy flag task
        """
        for po in self:
            # Lấy tất cả task từ tất cả phiếu
            tasks = po.proposal_sheet_ids.mapped("task_id")
            if po.proposal_sheet_id and po.proposal_sheet_id.task_id:
                tasks |= po.proposal_sheet_id.task_id

            for task in tasks:
                project = task.project_id

                def _get_stage(xid):
                    st = self.env.ref(xid, raise_if_not_found=False)
                    if st and project and project.id not in st.project_ids.ids:
                        st.sudo().write({'project_ids': [(4, project.id)]})
                    return st

                need_prod = bool(getattr(task, 'add_stage_production', False))
                need_inst = bool(getattr(task, 'add_stage_installation', False))

                if po.shipping_status == 'in_progress':
                    if not need_prod:
                        st = _get_stage(XID_STAGE_DELIVERY)
                        if st and task.stage_id != st:
                            task.sudo().write({'stage_id': st.id})
                            task.message_post(
                                body=Markup("Chuyển stage tự động ➜ <b>Giao hàng</b> (PO đang giao).")
                            )

                elif po.shipping_status == 'done':
                    if need_prod:
                        st = _get_stage(XID_STAGE_PRODUCTION)
                        if st and task.stage_id != st:
                            task.sudo().write({'stage_id': st.id})
                            task.message_post(
                                body=Markup("Chuyển stage tự động ➜ <b>Sản xuất</b> (vật tư đã về).")
                            )
                    else:
                        target_xid = XID_STAGE_INSTALLATION if need_inst else XID_STAGE_ACCEPTANCE
                        st = _get_stage(target_xid)
                        if st and task.stage_id != st:
                            task.sudo().write({'stage_id': st.id})
                            task.message_post(
                                body=Markup("Chuyển stage tự động ➜ <b>%s</b>." % (st.name,))
                            )

    def _compute_supplier_invoice_count(self):
        for po in self:
            po.supplier_invoice_count = len(po.supplier_invoice_ids)

    def action_open_create_supplier_invoice_wizard(self):
        self.ensure_one()
        view_ref = "proposal_sheet_purchase.view_purchase_create_supplier_invoice_wizard_form"
        view = self.env.ref(view_ref, raise_if_not_found=False)
        return {
            "type": "ir.actions.act_window",
            "name": _("Tạo hóa đơn NCC"),
            "res_model": "purchase.create.supplier.invoice.wizard",
            "view_mode": "form",
            "views": [(view.id, "form")] if view else [(False, "form")],
            "target": "new",
            "context": {"active_id": self.id},
        }

    def action_view_supplier_invoices(self):
        self.ensure_one()
        domain = [("purchase_id", "=", self.id)]
        invoices = self.env["supplier.invoice"].search(domain, limit=2)

        first_sheet = self.proposal_sheet_ids[:1] or self.proposal_sheet_id

        action = {
            "type": "ir.actions.act_window",
            "name": "Hóa đơn NCC",
            "res_model": "supplier.invoice",
            "view_mode": "tree,form",
            "domain": domain,
            "context": {
                "default_purchase_id": self.id,
                "default_contract_id": self.supplier_contract_id.id if self.supplier_contract_id else False,
                "default_partner_id": self.partner_id.id,
                "default_project_id": first_sheet.project_id.id if first_sheet and first_sheet.project_id else False,
            },
            "target": "current",
        }
        if len(invoices) == 1:
            action.update({"view_mode": "form", "res_id": invoices.id})
        return action

    # ============================================================
    #  HỢP ĐỒNG NCC + FOLLOWER
    # ============================================================

    def _get_or_create_supplier_contract(self):
        """
        Tìm / tạo Hợp đồng NCC theo (partner, project)
        """
        self.ensure_one()
        partner = self.partner_id
        project = self.project_id

        domain = [("partner_id", "=", partner.id)]
        if project:
            domain.append(("project_id", "=", project.id))

        contract = self.env["supplier.contract"].search(domain, limit=1)
        if not contract:
            seq = self.env["ir.sequence"].next_by_code("supplier.contract") or "SC/00000"
            contract = self.env["supplier.contract"].create({
                "name": seq,
                "partner_id": partner.id,
                "project_id": project.id if project else False,
                "interpretation": f"HĐ từ PO {self.name}",
                "contract_date": fields.Date.context_today(self),
                "amount": self.amount_total,
                "currency_id": self.currency_id.id,
            })
        if not self.supplier_contract_id:
            self.supplier_contract_id = contract.id
        return contract

    def _link_po_documents_to_contract(self, contract):
        """
        Gán APR & Invoice của PO vào contract nếu chưa gán.
        """
        self.ensure_one()
        aprs = self.env["account.payment.request"].search([
            ("purchase_id", "=", self.id),
            ("supplier_contract_id", "=", False),
        ])
        aprs.write({"supplier_contract_id": contract.id})

        invoices = self.env["supplier.invoice"].sudo().search([
            ("purchase_id", "=", self.id),
            ("contract_id", "=", False),
        ])
        invoices.write({"contract_id": contract.id})

    def _ensure_proposal_requester_follower(self):
        """
        Đảm bảo người đề xuất (requested_by) của TẤT CẢ phiếu đề xuất
        đều được subscribe vào PO.
        """
        for po in self:
            partners_to_add = self.env['res.partner']
            for sheet in po.proposal_sheet_ids | (po.proposal_sheet_id and po.proposal_sheet_id or self.env["proposal.sheet"]):
                proposer_user = sheet.requested_by
                partner = proposer_user and proposer_user.partner_id
                if partner and partner.id not in po.message_partner_ids.ids:
                    partners_to_add |= partner
            if partners_to_add:
                po.message_subscribe(partner_ids=partners_to_add.ids)

    @api.model
    def create(self, vals):
        po = super().create(vals)
        po._ensure_proposal_requester_follower()
        return po

    @api.ondelete(at_uninstall=False)
    def _unlink_if_cancelled(self):
        """Cho phép xóa PO nếu state = draft/cancel"""
        for order in self:
            if order.state not in ('draft', 'cancel'):
                raise UserError(_("Chỉ có thể xóa đơn hàng ở trạng thái Nháp hoặc Đã hủy."))


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    goods_status = fields.Selection([
        ('not_shipped', 'Chưa giao'),
        ('partial', 'Đang giao'),
        ('done', 'Đã giao'),
    ], string="Trạng thái hàng", compute="_compute_goods_status", store=True)

    qty_remaining = fields.Float(
        string="Còn lại", compute="_compute_qty_remaining", store=True)
    proposal_line_note = fields.Text(
        string="Ghi chú phiếu đề xuất",
        copy=False,
        help="Ghi chú lấy từ dòng Phiếu đề xuất khi tạo Đơn mua hàng.",
    )
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
