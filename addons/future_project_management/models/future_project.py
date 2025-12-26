from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import date
from dateutil.relativedelta import relativedelta
class FutureProject(models.Model):
    _name = "future.project"
    _description = "Future Project"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "expected_bid_date asc, id desc"

    name = fields.Char("Tên dự án", required=True, tracking=True)
    code = fields.Char("Mã nội bộ")

    stage_id = fields.Many2one(
        "future.project.stage",
        string="Trạng thái",
        default=lambda self: self.env["future.project.stage"].search([], limit=1),
        tracking=True,
        group_expand="_group_expand_stages",
    )

    customer_id = fields.Many2one(
        "res.partner",
        string="Chủ đầu tư",
        tracking=True,
    )
    address = fields.Char("Địa chỉ")
    # 🔥 THÊM FIELD NÀY
    location_id = fields.Many2one(
        "future.project.location",
        string="Khu vực",
        required=True,
        index=True,
        tracking=True,
    )
    hospital_type = fields.Selection(
        [
            ("public", "Public Hospital"),
            ("private", "Private Hospital"),
            ("clinic", "Clinic"),
            ("other", "Other"),
        ],
        string="Project Type",
    )

    contact_person = fields.Char("Người tiếp cận")
    contact_phone = fields.Char("Số điện thoại")
    contact_email = fields.Char("Email")

    assigned_user_id = fields.Many2one(
        "res.users",
        string="Responsible",
        default=lambda self: self.env.user,
        tracking=True,
    )

    expected_start_date = fields.Date("Thời gian dự kiến bắt đầu")
    expected_bid_date = fields.Date("Ngày dự kiến ​​đấu thầu")
    expected_end_date = fields.Date("Thời gian dự kiến kết thúc")

    expected_value = fields.Monetary("Giá trị dự kiến")
    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id,
    )

    probability = fields.Float(
        "Xác suất (%)",
        compute="_compute_probability",
        store=True,
    )

    priority = fields.Selection(
        [("0", "Thấp"), ("1", "Trung bình"), ("2", "Cao")],
        default="1",
        string="Mức độ ưu tiên",
    )

    description = fields.Text("Ghi chú")
    active = fields.Boolean(default=True)
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "future_project_ir_attachment_rel",
        "future_project_id",
        "attachment_id",
        string="Tài liệu đính kèm",
    )
    is_stage_locked = fields.Boolean(
        string="Đã chốt",
        default=False,
        tracking=True,
    )

    @api.depends("stage_id")
    def _compute_probability(self):
        for rec in self:
            rec.probability = rec.stage_id.probability if rec.stage_id else 0.0

    def _group_expand_stages(self, stages, domain, order):
        return self.env["future.project.stage"].search([], order="sequence")
    def write(self, vals):
        # Không cho đổi stage nếu đã lock
        if "stage_id" in vals:
            for rec in self:
                if rec.is_stage_locked:
                    raise UserError("Dự án đã trúng thầu, không thể thay đổi trạng thái.")

        res = super().write(vals)

        if "stage_id" in vals:
            for rec in self:
                stage = rec.stage_id

                # Trúng thầu → lock
                if stage and stage.is_won:
                    rec.is_stage_locked = True
                    rec.active = True

                # # Không khả thi → archive
                # elif stage and stage.is_lost:
                #     rec.active = False

                # # Trường hợp khác → mở lại
                # else:
                #     rec.is_stage_locked = False
                #     rec.active = True

        return res
    # ======================
    # UI BUTTON VISIBILITY
    # ======================
    show_btn_researching = fields.Boolean(compute="_compute_button_visibility")
    show_btn_contacting = fields.Boolean(compute="_compute_button_visibility")
    show_btn_proposal = fields.Boolean(compute="_compute_button_visibility")
    show_btn_bidding = fields.Boolean(compute="_compute_button_visibility")
    show_btn_won = fields.Boolean(compute="_compute_button_visibility")
    show_btn_lost = fields.Boolean(compute="_compute_button_visibility")

    @api.depends("stage_id", "active")
    def _compute_button_visibility(self):
        for rec in self:
            # default ẩn hết
            rec.show_btn_researching = False
            rec.show_btn_contacting = False
            rec.show_btn_proposal = False
            rec.show_btn_bidding = False
            rec.show_btn_won = False
            rec.show_btn_lost = False

            # record không active → ẩn hết
            if not rec.active or not rec.stage_id:
                continue

            stage = rec.stage_id

            # LOST hoặc WON → kết thúc
            if stage.is_won or stage.is_lost:
                continue

            # PIPELINE 1 CHIỀU
            if stage.sequence == 1:
                rec.show_btn_researching = True

            elif stage.sequence == 2:
                rec.show_btn_contacting = True

            elif stage.sequence == 3:
                rec.show_btn_proposal = True

            elif stage.sequence == 4:
                rec.show_btn_bidding = True

            elif stage.sequence == 5:
                rec.show_btn_won = True

            # luôn cho phép Không khả thi
            rec.show_btn_lost = True
    # ======================
    # CORE SET STAGE
    # ======================
    def _set_stage(self, xmlid):
        stage = self.env.ref(xmlid, raise_if_not_found=False)
        if not stage:
            raise UserError(_("Stage chưa được cấu hình đúng."))

        for rec in self:
            # Nếu đã trúng thầu thì không cho đổi lung tung
            if rec.is_stage_locked and not stage.is_lost:
                raise UserError(
                    _("Dự án đã trúng thầu, không thể chuyển trạng thái khác.")
                )

            rec.stage_id = stage.id

            if stage.is_won:
                rec.is_stage_locked = True
                rec.active = True
            elif stage.is_lost:
                rec.active = False
            else:
                rec.is_stage_locked = False
                rec.active = True

    # ======================
    # STAGE ACTIONS (BẮT BUỘC PHẢI CÓ)
    # ======================
    def action_stage_draft(self):
        self._set_stage("future_project_management.stage_draft")

    def action_stage_researching(self):
        self._set_stage("future_project_management.stage_researching")

    def action_stage_contacting(self):
        self._set_stage("future_project_management.stage_contacting")

    def action_stage_proposal(self):
        self._set_stage("future_project_management.stage_proposal")

    def action_stage_bidding(self):
        self._set_stage("future_project_management.stage_bidding")

    def action_stage_won(self):
        self._set_stage("future_project_management.stage_won")

    def action_stage_lost(self):
        self._set_stage("future_project_management.stage_lost")

    # ----------------------------
    # DASHBOARD HELPERS
    # ----------------------------
    @api.model
    def _get_range_from_filters(self, filters):
        filters = filters or {}
        period_type = filters.get("period_type") or "all"

        # ✅ “Tất cả” -> không lọc theo ngày
        if period_type == "all":
            return False, False

        year = int(filters.get("year") or date.today().year)
        month = filters.get("month") or str(date.today().month)
        quarter = filters.get("quarter") or str(((date.today().month - 1) // 3) + 1)

        if period_type == "month":
            start = date(year, int(month), 1)
            end = start + relativedelta(months=1, days=-1)
        elif period_type == "quarter":
            q = int(quarter)
            start = date(year, (q - 1) * 3 + 1, 1)
            end = start + relativedelta(months=3, days=-1)
        else:  # year
            start = date(year, 1, 1)
            end = date(year, 12, 31)

        return start, end

    @api.model
    def _is_won(self, p):
        return bool(getattr(p.stage_id, "is_won", False)) if p.stage_id else False

    @api.model
    def _is_lost(self, p):
        if not p.stage_id:
            return False
        if getattr(p.stage_id, "is_lost", False):
            return True
        name = (p.stage_id.name or "").strip().lower()
        return name in ["không khả thi", "lost", "fail", "failed"]

    @api.model
    def get_dashboard_data(self, filters=None):
        """
        filters góc trên:
            period_type: all|month|quarter|year
            year, month, quarter
            location_id (optional)
        filters riêng list:
            list_stage_id (optional)  # ✅ chỉ lọc list
        """
        filters = filters or {}
        start_date, end_date = self._get_range_from_filters(filters)

        # ✅ FILTER GÓC (áp dụng KPI + summary)
        base_domain = []
        if start_date and end_date:
            base_domain += [
                ("expected_bid_date", ">=", start_date),
                ("expected_bid_date", "<=", end_date),
            ]
        if filters.get("location_id"):
            base_domain.append(("location_id", "=", int(filters["location_id"])))

        Project = self.with_context(active_test=False)

        # ✅ DATA KPI + SUMMARY
        projects_all = Project.search(base_domain)

        won_projects = projects_all.filtered(lambda p: self._is_won(p))
        lost_projects = projects_all.filtered(lambda p: self._is_lost(p))

        total_value = sum(projects_all.mapped("expected_value") or [0.0])
        won_value = sum(won_projects.mapped("expected_value") or [0.0])
        lost_value = sum(lost_projects.mapped("expected_value") or [0.0])
        win_rate = round((len(won_projects) / len(projects_all) * 100), 2) if projects_all else 0.0
        total_value_non_lost = total_value - lost_value
        # ---- stage_summary theo projects_all
        stage_map = {}
        for p in projects_all:
            sid = p.stage_id.id if p.stage_id else 0
            if sid not in stage_map:
                stage_map[sid] = {
                    "id": sid,
                    "name": p.stage_id.name if p.stage_id else "Chưa có trạng thái",
                    "count": 0,
                    "value": 0.0,
                    "is_won": self._is_won(p),
                }
            stage_map[sid]["count"] += 1
            stage_map[sid]["value"] += (p.expected_value or 0.0)

        stage_summary = sorted(stage_map.values(), key=lambda x: (not x["is_won"], x["name"]))

        # ---- location_summary theo projects_all
        loc_map = {}
        for p in projects_all:
            lid = p.location_id.id if p.location_id else 0
            if lid not in loc_map:
                loc_map[lid] = {
                    "id": lid,
                    "name": p.location_id.name if p.location_id else "Chưa có khu vực",
                    "count": 0,
                    "won_count": 0,
                    "value": 0.0,
                }
            loc_map[lid]["count"] += 1
            loc_map[lid]["value"] += (p.expected_value or 0.0)
            if self._is_won(p):
                loc_map[lid]["won_count"] += 1

        location_summary = sorted(loc_map.values(), key=lambda x: (-x["count"], x["name"]))

        # ✅ FILTER RIÊNG CHO LIST (chip stage)
        # ✅ FILTER RIÊNG CHO LIST (CHỈ dự án đang theo dõi, KHÔNG lấy không khả thi)
        list_domain = list(base_domain)
        domain_non_lost = list(base_domain)

        # chỉ lấy đang theo dõi
        list_domain.append(("active", "=", True))

        # loại stage "không khả thi" (lost)
        lost_stage_ids = self.env["future.project.stage"].search([
            "|",
            ("is_lost", "=", True),
            ("name", "ilike", "không khả thi"),
        ]).ids
        if lost_stage_ids:
            list_domain.append(("stage_id", "not in", lost_stage_ids))
            domain_non_lost.append(("stage_id", "not in", lost_stage_ids))

        # chip stage chỉ áp dụng cho list
        if filters.get("list_stage_id"):
            list_domain.append(("stage_id", "=", int(filters["list_stage_id"])))

        projects_list = self.search(list_domain)  # active_test=True mặc định là OK vì ta đã lọc active=True


        def _sort_key(p):
            return ((p.expected_bid_date or date.max), p.id)

        projects_show = projects_list.sorted(key=_sort_key)[:30]

        projects_rows = [{
            "id": p.id,
            "name": p.name,
            "code": p.code or "",
            "customer": p.customer_id.name or "",
            "location": p.location_id.name or "",
            "stage_id": p.stage_id.id if p.stage_id else False,
            "stage": p.stage_id.name or "",
            "expected_bid_date": p.expected_bid_date,
            "expected_value": p.expected_value or 0.0,
            "currency_id": (p.currency_id.id or self.env.company.currency_id.id),
            "active": bool(p.active),
        } for p in projects_show]

        # options
        locations = self.env["future.project.location"].search([])
        location_options = [{"id": l.id, "name": l.name} for l in locations]

        stages = self.env["future.project.stage"].search([], order="sequence, id")

        stage_options = []
        for s in stages:
            # ✅ ẨN stage "Không khả thi" khỏi stageOptions (chip filter)
            name_low = (s.name or "").strip().lower()
            is_lost = bool(getattr(s, "is_lost", False))  # nếu chưa có field thì sẽ False

            if is_lost or name_low == "không khả thi":
                continue

            stage_options.append({
                "id": s.id,
                "name": s.name,
                "is_won": bool(getattr(s, "is_won", False)),
                # optional: để debug
                "is_lost": is_lost,
            })

        return {
            "meta": {
                "start_date": start_date,
                "end_date": end_date,
                "period_type": filters.get("period_type") or "all",
            },
            "kpi": {
                "total_projects": len(projects_all),
                "won_projects": len(won_projects),
                "lost_projects": len(lost_projects),
                "win_rate": win_rate,
                "total_value": total_value_non_lost,
                "won_value": won_value,
                "currency_id": self.env.company.currency_id.id,
            },
            "stage_summary": stage_summary,
            "location_summary": location_summary,
            "projects": projects_rows,          # ✅ list theo list_domain
            "location_options": location_options,
            "stage_options": stage_options,     # ✅ chip dùng options này
        }