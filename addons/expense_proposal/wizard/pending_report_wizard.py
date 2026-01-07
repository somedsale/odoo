# -*- coding: utf-8 -*-
from collections import OrderedDict
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.misc import format_date
from dateutil.relativedelta import relativedelta

_logger = logging.getLogger(__name__)


# =========================================================
# Helpers
# =========================================================
def _to_float(v):
    """Make sure value is a real number for monetary widget."""
    if v in (None, False, ""):
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)

    s = str(v).strip().replace(" ", "")
    # Handle VN/Intl formats: 1.234.567,89 | 1,234,567.89 | 1234567
    if "," in s and "." in s:
        # Assume VN: 1.234.567,89 => 1234567.89
        s = s.replace(".", "").replace(",", ".")
    else:
        # If only comma: treat as decimal separator
        s = s.replace(",", ".")
    try:
        return float(s)
    except Exception:
        return 0.0


# =========================================================
# Wizard
# =========================================================
class PendingReportWizard(models.TransientModel):
    _name = "pending.report.wizard"
    _description = "Wizard - Dự kiến thanh toán (Report riêng)"

    company_id = fields.Many2one(
        "res.company",
        string="Công ty",
        required=True,
        default=lambda self: self.env.company,
    )
    date_from = fields.Date(string="Từ ngày")
    date_to = fields.Date(string="Đến ngày")
    project_id = fields.Many2one("project.project", string="Dự án")

    # Optional: user can pick exact sheets; if empty -> use filters
    sheet_ids = fields.Many2many("proposal.sheet", string="Chọn phiếu đề xuất")

    include_material = fields.Boolean(string="Lấy từ Đề xuất loại 'Vật tư'", default=True)
    include_expense = fields.Boolean(string="Lấy từ Đề xuất loại 'Chi phí công trình'", default=True)
    include_other = fields.Boolean(string="Lấy từ Đề xuất loại 'Chi phí khác'", default=True)

    line_ids = fields.One2many(
        "pending.report.wizard.line", "wizard_id", string="Danh sách mục"
    )

    def _get_chosen_types(self):
        self.ensure_one()
        chosen = []
        if self.include_material:
            chosen.append("material")
        if self.include_expense:
            chosen.append("expense")
        if self.include_other:
            chosen.append("other")
        if not chosen:
            raise UserError(_("Vui lòng chọn ít nhất 1 loại đề xuất để lấy dữ liệu."))
        return chosen

    def _search_sheets(self, chosen_types):
        self.ensure_one()

        allowed_states = ["reviewed_manager", "reviewed_accounting", "approved", "waiting_accounting_paid", "done"]

        # Domain chính
        domain = [
            ("type", "in", chosen_types),
            ("state", "in", allowed_states),
        ]

        if self.project_id:
            domain.append(("project_id", "=", self.project_id.id))

        # ✅ Lọc ngày bằng create_date để tránh date_approved = False làm rỗng
        if self.date_from:
            dt_from = fields.Datetime.to_datetime(self.date_from)  # 00:00
            domain.append(("create_date", ">=", dt_from))
        if self.date_to:
            dt_to = fields.Datetime.to_datetime(self.date_to) + relativedelta(days=1)  # < ngày+1
            domain.append(("create_date", "<", dt_to))

        # company filter nếu có field company_id
        if "company_id" in self.env["proposal.sheet"]._fields:
            domain.append(("company_id", "=", self.company_id.id))

        sheets = self.env["proposal.sheet"].search(domain, order="create_date asc, id asc")
        if sheets:
            return sheets

        # =========================
        # DEBUG: thống kê theo state để biết DB có gì
        # =========================
        debug_domain = [("type", "in", chosen_types)]
        if self.project_id:
            debug_domain.append(("project_id", "=", self.project_id.id))
        if "company_id" in self.env["proposal.sheet"]._fields:
            debug_domain.append(("company_id", "=", self.company_id.id))

        grouped = self.env["proposal.sheet"].read_group(
            debug_domain, ["state"], ["state"], lazy=False
        )

        lines = []
        for g in grouped:
            st = g.get("state") or "False"
            cnt = g.get("__count", 0)
            lines.append(f"- {st}: {cnt}")

        msg = "Không có phiếu phù hợp điều kiện lọc.\n\n"
        msg += f"Domain đang dùng:\n{domain}\n\n"
        msg += "Thống kê phiếu theo trạng thái (bỏ lọc state/date):\n"
        msg += "\n".join(lines) if lines else "- Không có phiếu nào theo project/type/company."

        raise UserError(msg)

    def action_load_lines(self):
        """Load candidates into wizard lines for user to tick."""
        self.ensure_one()
        self.line_ids = [(5, 0, 0)]

        chosen_types = self._get_chosen_types()
        sheets = self._search_sheets(chosen_types)

        if not sheets:
            raise UserError(_("Không có phiếu phù hợp điều kiện lọc."))

        vals_list = []

        for sheet in sheets:
            # ----- OTHER: expense_noproject_line_ids
            if sheet.type == "other":
                for l in sheet.expense_noproject_line_ids:
                    vals_list.append({
                        "wizard_id": self.id,
                        "selected": True,
                        "source": "proposal_other",
                        "source_id": l.id,
                        "sheet_id": sheet.id,
                        "proposal_type": "other",
                        "cost_classification": (getattr(l, "cost_classification", None) or "other"),
                        "object_name": (l.object.name if getattr(l, "object", False) else ""),
                        "content": (l.content or ""),
                        "amount": _to_float(getattr(l, "amount", 0.0)),
                        "project_name": (sheet.project_id.display_name if sheet.project_id else ""),
                        "note": (getattr(l, "note", "") or ""),
                        "date": (getattr(l, "date", False) or sheet.date_approved),
                    })

            # ----- EXPENSE: expense_line_ids
            elif sheet.type == "expense":
                for l in sheet.expense_line_ids:
                    content = ""
                    if getattr(l, "expense_id", False):
                        content = l.expense_id.display_name
                    elif getattr(l, "name", False):
                        content = l.name or ""

                    amount = 0.0
                    if "price_total" in l._fields:
                        amount = _to_float(l.price_total)
                    elif "amount" in l._fields:
                        amount = _to_float(l.amount)

                    object_name = ""
                    for f in ["vendor_id", "partner_id", "object"]:
                        if f in l._fields and getattr(l, f):
                            object_name = getattr(l, f).name
                            break

                    vals_list.append({
                        "wizard_id": self.id,
                        "selected": True,
                        "source": "proposal_expense",
                        "source_id": l.id,
                        "sheet_id": sheet.id,
                        "proposal_type": "expense",
                        "cost_classification": "expense",
                        "object_name": object_name,
                        "content": content,
                        "amount": amount,
                        "project_name": (sheet.project_id.display_name if sheet.project_id else ""),
                        "note": (getattr(l, "note", "") or ""),
                        "date": (getattr(l, "date", False) or sheet.date_approved),
                    })

            # ----- MATERIAL: material_line_ids
            elif sheet.type == "material":
                for l in sheet.material_line_ids:
                    content = ""
                    if getattr(l, "material_id", False):
                        content = l.material_id.display_name
                    elif getattr(l, "name", False):
                        content = l.name or ""

                    amount = 0.0
                    if "price_total_taxed" in l._fields:
                        amount = _to_float(l.price_total_taxed)
                    elif "price_total" in l._fields:
                        amount = _to_float(l.price_total)

                    object_name = ""
                    for f in ["vendor_id", "partner_id"]:
                        if f in l._fields and getattr(l, f):
                            object_name = getattr(l, f).name
                            break

                    vals_list.append({
                        "wizard_id": self.id,
                        "selected": True,
                        "source": "proposal_material",
                        "source_id": l.id,
                        "sheet_id": sheet.id,
                        "proposal_type": "material",
                        "cost_classification": "material",
                        "object_name": object_name,
                        "content": content,
                        "amount": amount,
                        "project_name": (sheet.project_id.display_name if sheet.project_id else ""),
                        "note": (getattr(l, "note", "") or ""),
                        "date": (getattr(l, "date", False) or sheet.date_approved),
                    })

        if not vals_list:
            raise UserError(_("Không có dữ liệu line phù hợp."))

        self.env["pending.report.wizard.line"].create(vals_list)

        return {
            "type": "ir.actions.act_window",
            "res_model": "pending.report.wizard",
            "view_mode": "form",
            "res_id": self.id,
            "target": "new",
        }

    def action_print_html(self):
        self.ensure_one()
        return self.env.ref("expense_proposal.action_pending_payment_wizard_report_html").report_action(self)

    def action_print_pdf(self):
        self.ensure_one()
        return self.env.ref("expense_proposal.action_pending_payment_wizard_report_pdf").report_action(self)


# =========================================================
# Wizard line
# =========================================================
class PendingReportWizardLine(models.TransientModel):
    _name = "pending.report.wizard.line"
    _description = "Wizard line - Dự kiến thanh toán (Report riêng)"
    _order = "date asc, id asc"

    wizard_id = fields.Many2one("pending.report.wizard", required=True, ondelete="cascade")
    selected = fields.Boolean(string="Chọn", default=True)

    source = fields.Selection([
        ("proposal_other", "Proposal - Other line"),
        ("proposal_expense", "Proposal - Expense line"),
        ("proposal_material", "Proposal - Material line"),
    ], required=True)

    source_id = fields.Integer(string="Source ID")
    sheet_id = fields.Many2one("proposal.sheet", string="Phiếu đề xuất")

    proposal_type = fields.Selection([
        ("material", "Vật tư"),
        ("expense", "Chi phí công trình"),
        ("other", "Chi phí khác"),
    ], string="Loại đề xuất")

    cost_classification = fields.Selection([
        ("material", "Vật tư"),
        ("expense", "Chi phí công trình"),
        ("employee", "Khoản vay nhân viên"),
        ("office", "Chi phí tại công ty"),
        ("project", "Chi phí công trình"),
        ("estimated_cost", "Chi phí dự toán"),
        ("fixed_cost", "Chi phí cố định"),
        ("irregular_expenses", "Chi phí không thường xuyên"),
        ("other", "Khác"),
    ], string="Nhóm")

    object_name = fields.Char(string="Đối tượng/NCC")
    content = fields.Char(string="Nội dung")
    amount = fields.Float(string="Giá trị")
    project_name = fields.Char(string="Dự án")
    note = fields.Char(string="Ghi chú")
    date = fields.Date(string="Ngày")


# =========================================================
# Report (AbstractModel)
# =========================================================
class ReportPendingPaymentWizard(models.AbstractModel):
    _name = "report.expense_proposal.report_pending_payment_wizard"
    _description = "QWeb Report: Pending Payment Wizard (Report riêng)"

    @api.model
    def _get_report_values(self, docids, data=None):
        wizards = self.env["pending.report.wizard"].browse(docids).exists()
        today = fields.Date.context_today(self)

        group_titles = OrderedDict([
            ("material", "VẬT TƯ"),
            ("expense", "CHI PHÍ CÔNG TRÌNH"),
            ("employee", "KHOẢN VAY NỘI BỘ NHÂN VIÊN"),
            ("office", "CHI PHÍ TẠI CÔNG TY"),
            ("project", "CHI PHÍ CÁC CÔNG TRÌNH"),
            ("estimated_cost", "CHI PHÍ DỰ TOÁN"),
            ("fixed_cost", "CHI PHÍ CỐ ĐỊNH"),
            ("irregular_expenses", "CHI PHÍ KHÔNG THƯỜNG XUYÊN"),
            ("other", "KHÁC"),
        ])

        payloads = []

        for wiz in wizards:
            currency = (wiz.company_id.currency_id or self.env.company.currency_id)

            selected_lines = wiz.line_ids.filtered(lambda l: l.selected)
            groups_map = {
                k: {"key": k, "title": title, "lines": [], "total": 0.0}
                for k, title in group_titles.items()
            }
            stt_map = {k: 0 for k in group_titles.keys()}

            for l in selected_lines:
                cls = l.cost_classification or l.proposal_type or "other"
                if cls not in groups_map:
                    cls = "other"

                stt_map[cls] += 1

                date_display = ""
                if l.date:
                    try:
                        date_display = format_date(self.env, l.date)
                    except Exception:
                        date_display = fields.Date.to_string(l.date)

                amt = _to_float(l.amount)

                groups_map[cls]["lines"].append({
                    "stt": stt_map[cls],
                    "proposal": l.sheet_id.name if l.sheet_id else "",
                    "date": date_display,
                    "object": l.object_name or "",
                    "name": l.content or "",
                    "amount": amt,
                    "project": l.project_name or "",
                    "note": l.note or "",
                })
                groups_map[cls]["total"] += amt

            groups = [g for g in groups_map.values() if g["total"]]
            total = float(sum(g["total"] for g in groups))

            payloads.append({
                "wizard": wiz,
                "currency": currency,
                "groups": groups,
                "total": total,
            })

        return {
            "doc_model": "pending.report.wizard",
            "docs": wizards,
            "payloads": payloads,
            "today": today,
            "company": self.env.company,
        }
