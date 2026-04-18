import json
import logging
from datetime import datetime

import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class HostingContact(models.Model):
    _name = "hosting.contact"
    _description = "Hosting Contact"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "remote_created_at desc, id desc"
    _rec_name = "display_name"

    display_name = fields.Char(
        string="Tên hiển thị",
        compute="_compute_display_name",
        store=True,
    )

    remote_id = fields.Char(
        string="ID bên hosting",
        required=True,
        tracking=True,
        index=True,
    )
    title = fields.Char(string="Tiêu đề", tracking=True)
    contact_name = fields.Char(string="Họ tên", tracking=True)
    phone = fields.Char(string="Điện thoại", tracking=True)
    email = fields.Char(string="Email", tracking=True)
    message = fields.Text(string="Nội dung")
    product = fields.Char(string="Sản phẩm quan tâm", tracking=True)

    partner_id = fields.Many2one(
        "res.partner",
        string="Khách hàng",
        tracking=True,
        copy=False,
    )
    sale_order_id = fields.Many2one(
        "sale.order",
        string="Báo giá",
        tracking=True,
        copy=False,
    )
    user_id = fields.Many2one(
        "res.users",
        string="Phụ trách",
        default=lambda self: self.env.user,
        tracking=True,
    )

    state = fields.Selection(
        [
            ("new", "Mới"),
            ("contacted", "Đã liên hệ"),
            ("quoted", "Đã tạo báo giá"),
            ("done", "Hoàn tất"),
            ("cancel", "Hủy"),
        ],
        string="Trạng thái",
        default="new",
        tracking=True,
        index=True,
    )

    remote_created_at = fields.Datetime(string="Ngày tạo bên hosting", tracking=True)
    last_fetch_at = fields.Datetime(string="Lần lấy gần nhất", tracking=True)

    contact_date = fields.Datetime(string="Ngày liên hệ", tracking=True)
    quotation_date = fields.Datetime(string="Ngày tạo báo giá", tracking=True)
    done_date = fields.Datetime(string="Ngày hoàn tất", tracking=True)
    cancel_date = fields.Datetime(string="Ngày hủy", tracking=True)

    sync_error = fields.Text(string="Lỗi đồng bộ")
    raw_payload = fields.Text(string="Dữ liệu gốc")
    note_internal = fields.Text(string="Ghi chú nội bộ")
    active = fields.Boolean(default=True)

    sale_order_count = fields.Integer(
        string="Số báo giá",
        compute="_compute_sale_order_count",
    )

    _sql_constraints = [
        ("remote_id_unique", "unique(remote_id)", "ID contact từ hosting đã tồn tại."),
    ]

    @api.depends("title", "contact_name", "email", "phone", "remote_id")
    def _compute_display_name(self):
        for rec in self:
            name = rec.contact_name or rec.title or rec.email or rec.phone or rec.remote_id
            if rec.title and rec.contact_name:
                name = "%s - %s" % (rec.title, rec.contact_name)
            rec.display_name = name

    @api.depends("sale_order_id")
    def _compute_sale_order_count(self):
        for rec in self:
            rec.sale_order_count = 1 if rec.sale_order_id else 0

    def _get_config(self):
        icp = self.env["ir.config_parameter"].sudo()
        api_url = (icp.get_param("hosting_contact_sync.api_url") or "").strip()
        api_token = (icp.get_param("hosting_contact_sync.api_token") or "").strip()
        timeout = int(icp.get_param("hosting_contact_sync.api_timeout") or 20)
        verify_ssl = (icp.get_param("hosting_contact_sync.verify_ssl") or "True") == "True"

        if not api_url:
            raise UserError(_("Bạn chưa cấu hình Hosting Contact API URL trong Cài đặt."))

        return {
            "api_url": api_url,
            "api_token": api_token,
            "timeout": timeout,
            "verify_ssl": verify_ssl,
        }

    def _prepare_headers(self, config):
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if config.get("api_token"):
            headers["X-API-KEY"] = config["api_token"]
        return headers

    def _parse_remote_datetime(self, value):
        if not value:
            return False

        if isinstance(value, (int, float)):
            ts = int(value)
            if ts > 9999999999:
                ts = ts // 1000
            if ts <= 0 or ts >= 2147483647:
                return False
            return datetime.utcfromtimestamp(ts)

        value = str(value).strip()

        if value.isdigit():
            ts = int(value)
            if ts > 9999999999:
                ts = ts // 1000
            if ts <= 0 or ts >= 2147483647:
                return False
            return datetime.utcfromtimestamp(ts)

        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(value, fmt)
            except Exception:
                continue

        return False

    def _prepare_vals_from_remote(self, item):
        remote_id = item.get("id") or item.get("remote_id")
        if not remote_id:
            raise UserError(_("Dữ liệu từ hosting thiếu remote_id/id."))

        remote_created_at = self._parse_remote_datetime(
            item.get("created_at")
            or item.get("created_at_local")
            or item.get("ngaytao")
            or item.get("create_date")
            or item.get("created")
        )

        return {
            "remote_id": str(remote_id),
            "title": item.get("tieude") or item.get("title") or item.get("product") or "",
            "contact_name": item.get("ten") or item.get("name") or "",
            "phone": item.get("dienthoai") or item.get("phone") or "",
            "email": item.get("email") or "",
            "message": item.get("noidung") or item.get("message") or "",
            "product": item.get("product") or item.get("tieude") or item.get("title") or "",
            "remote_created_at": remote_created_at,
            "last_fetch_at": fields.Datetime.now(),
            "raw_payload": json.dumps(item, ensure_ascii=False, indent=2),
            "sync_error": False,
        }

    @api.model
    def _fetch_remote_contacts(self):
        config = self._get_config()
        headers = self._prepare_headers(config)

        try:
            response = requests.get(
                config["api_url"],
                headers=headers,
                timeout=config["timeout"],
                verify=config["verify_ssl"],
            )
            response.raise_for_status()
        except Exception as e:
            _logger.exception("Lỗi gọi hosting API")
            raise UserError(_("Không gọi được hosting API:\n%s") % str(e))

        try:
            result = response.json()
        except Exception:
            raise UserError(_("Hosting API không trả về JSON hợp lệ.\nResponse:\n%s") % response.text[:1000])

        if isinstance(result, list):
            data = result
        elif isinstance(result, dict):
            data = result.get("data") or result.get("contacts") or result.get("items") or []
            if result.get("success") is False:
                raise UserError(result.get("message") or _("Hosting API trả về lỗi."))
        else:
            raise UserError(_("Dữ liệu trả về từ hosting không đúng định dạng JSON."))

        if not isinstance(data, list):
            raise UserError(_("Trường data/contacts/items của hosting phải là list."))

        return data

    def action_fetch_from_hosting(self):
        records_created = 0
        records_updated = 0
        row_errors = 0

        items = self._fetch_remote_contacts()

        for item in items:
            try:
                vals = self._prepare_vals_from_remote(item)
                existing = self.search([("remote_id", "=", vals["remote_id"])], limit=1)

                if existing:
                    existing.write(vals)
                    records_updated += 1
                else:
                    self.create(vals)
                    records_created += 1

            except Exception as row_error:
                row_errors += 1
                _logger.exception("Lỗi xử lý contact từ hosting")
                remote_id = item.get("id") or item.get("remote_id") or "unknown"
                existing = self.search([("remote_id", "=", str(remote_id))], limit=1)
                if existing:
                    existing.write({
                        "sync_error": str(row_error),
                        "last_fetch_at": fields.Datetime.now(),
                        "raw_payload": json.dumps(item, ensure_ascii=False, indent=2),
                    })

        message = _(
            "Đã lấy toàn bộ Hosting Contacts.\n"
            "Tổng nhận: %(total)s\n"
            "Tạo mới: %(created)s\n"
            "Cập nhật: %(updated)s\n"
            "Lỗi dòng: %(errors)s"
        ) % {
            "total": len(items),
            "created": records_created,
            "updated": records_updated,
            "errors": row_errors,
        }

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Đồng bộ thành công"),
                "message": message,
                "type": "success" if row_errors == 0 else "warning",
                "sticky": False,
                "next": {"type": "ir.actions.client", "tag": "reload"},
            },
        }

    def _prepare_partner_vals(self):
        self.ensure_one()
        return {
            "name": self.contact_name or self.title or _("Khách từ website"),
            "phone": self.phone or False,
            "email": self.email or False,
            "customer_rank": 1,
        }


    def _prepare_sale_order_vals(self, partner):
        self.ensure_one()
        return {
            "partner_id": partner.id,
            "user_id": self.user_id.id or self.env.user.id,
            "note": self.message or False,
            "origin": "Hosting Contact %s" % (self.remote_id or self.id),
        }

    def _close_notification_activities(self):
        """Kết thúc các activity thông báo contact mới."""
        activity_type = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
        
        if not activity_type:
            return
        
        for rec in self:
            activities = self.env["mail.activity"].sudo().search([
                ("res_model", "=", rec._name),
                ("res_id", "=", rec.id),
                ("activity_type_id", "=", activity_type.id),
                ("summary", "=", "Contact mới từ website"),
                ("date_done", "=", False),
            ])
            
            if activities:
                activities.action_done()

    def action_mark_contacted(self):
        for rec in self:
            if rec.state in ["done", "cancel"]:
                continue
            vals = {
                "state": "contacted",
            }
            if not rec.contact_date:
                vals["contact_date"] = fields.Datetime.now()
            rec.write(vals)
        
        self._close_notification_activities()
        return True

    def action_create_quotation(self):
        self.ensure_one()

        if self.state == "cancel":
            raise UserError(_("Contact này đã bị hủy, không thể tạo báo giá."))

        if self.sale_order_id:
            return {
                "type": "ir.actions.act_window",
                "name": _("Báo giá"),
                "res_model": "sale.order",
                "view_mode": "form",
                "res_id": self.sale_order_id.id,
                "target": "current",
            }

        if not self.partner_id:
            raise UserError(_("Vui lòng chọn Khách hàng trước khi tạo báo giá."))

        sale_order = self.env["sale.order"].sudo().create(
            self._prepare_sale_order_vals(self.partner_id)
        )

        vals = {
            "sale_order_id": sale_order.id,
            "state": "quoted",
        }
        if not self.quotation_date:
            vals["quotation_date"] = fields.Datetime.now()

        self.write(vals)
        self._close_notification_activities()

        return {
            "type": "ir.actions.act_window",
            "name": _("Báo giá"),
            "res_model": "sale.order",
            "view_mode": "form",
            "res_id": sale_order.id,
            "target": "current",
        }

    def action_open_sale_order(self):
        self.ensure_one()
        if not self.sale_order_id:
            raise UserError(_("Contact này chưa có báo giá."))

        return {
            "type": "ir.actions.act_window",
            "name": _("Báo giá"),
            "res_model": "sale.order",
            "view_mode": "form",
            "res_id": self.sale_order_id.id,
            "target": "current",
        }

    def action_done(self):
        for rec in self:
            rec.write({
                "state": "done",
                "done_date": fields.Datetime.now(),
            })
        self._close_notification_activities()
        return True

    def action_cancel(self):
        for rec in self:
            rec.write({
                "state": "cancel",
                "cancel_date": fields.Datetime.now(),
            })
        self._close_notification_activities()
        return True

    def action_reset_to_new(self):
        for rec in self:
            rec.write({
                "state": "new",
                "contact_date": False,
                "quotation_date": False,
                "done_date": False,
                "cancel_date": False,
            })
        return True

    def action_open_partner(self):
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_("Contact này chưa có khách hàng."))

        return {
            "type": "ir.actions.act_window",
            "name": _("Khách hàng"),
            "res_model": "res.partner",
            "view_mode": "form",
            "res_id": self.partner_id.id,
            "target": "current",
        }

    @api.model
    def cron_fetch_contacts(self):
        self.env["hosting.contact"].action_fetch_from_hosting()

    def _notify_sale_users_new_contact(self):
        """Tạo activity cho toàn bộ user thuộc nhóm sale.group_sale_user."""
        activity_type = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
        sale_group = self.env.ref("sales_team.group_sale_salesman", raise_if_not_found=False)

        if not activity_type or not sale_group:
            return

        sale_users = sale_group.users.filtered(lambda u: u.active and u.partner_id)

        for rec in self:
            note = _(
                "Có contact mới từ website.\n"
                "Khách hàng: %(name)s\n"
                "Điện thoại: %(phone)s\n"
                "Email: %(email)s\n"
                "Sản phẩm quan tâm: %(product)s"
            ) % {
                "name": rec.contact_name or "",
                "phone": rec.phone or "",
                "email": rec.email or "",
                "product": rec.product or rec.title or "",
            }

            for user in sale_users:
                existed = self.env["mail.activity"].sudo().search([
                    ("res_model", "=", rec._name),
                    ("res_id", "=", rec.id),
                    ("user_id", "=", user.id),
                    ("activity_type_id", "=", activity_type.id),
                    ("summary", "=", "Contact mới từ website"),
                ], limit=1)

                if not existed:
                    self.env["mail.activity"].sudo().create({
                        "activity_type_id": activity_type.id,
                        "summary": "Contact mới từ website",
                        "note": note,
                        "res_model_id": self.env["ir.model"].sudo()._get_id(rec._name),
                        "res_id": rec.id,
                        "user_id": user.id,
                        "date_deadline": fields.Date.today(),
                    })


    def _post_new_contact_message(self):
        for rec in self:
            body = _(
                "<b>Có contact mới từ website</b><br/>"
                "Khách hàng: %(name)s<br/>"
                "Điện thoại: %(phone)s<br/>"
                "Email: %(email)s<br/>"
                "Sản phẩm quan tâm: %(product)s"
            ) % {
                "name": rec.contact_name or "",
                "phone": rec.phone or "",
                "email": rec.email or "",
                "product": rec.product or rec.title or "",
            }
            rec.message_post(body=body)