# -*- coding: utf-8 -*-
import base64
import hashlib
import logging
import mimetypes
import os
import uuid
from datetime import datetime
from urllib.parse import quote as urlquote

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    import boto3
    from botocore.client import Config
    from botocore.exceptions import ClientError
except Exception:  # pragma: no cover
    boto3 = None
    ClientError = Exception

PARAMS = {
    "enabled": "somed_s3.enabled",
    "bucket": "somed_s3.bucket",
    "region": "somed_s3.region",
    "access_key": "somed_s3.access_key",
    "secret_key": "somed_s3.secret_key",
    "endpoint_url": "somed_s3.endpoint_url",
    "prefix": "somed_s3.prefix",
    "acl": "somed_s3.acl",
    "use_presigned": "somed_s3.use_presigned",
    "presigned_exp": "somed_s3.presigned_exp",
}

# ====== Mixin cấu hình S3 ======
class S3ConfigMixin(models.AbstractModel):
    _name = "s3.config.mixin"
    _description = "S3 Config Mixin (read-only ICP)"

    def _s3_params(self):
        p = self.env["ir.config_parameter"].sudo()
        return {
            "enabled": p.get_param(PARAMS["enabled"]) == "1",
            "bucket": p.get_param(PARAMS["bucket"]) or "",
            "region": p.get_param(PARAMS["region"]) or None,
            "access_key": p.get_param(PARAMS["access_key"]) or None,
            "secret_key": p.get_param(PARAMS["secret_key"]) or None,
            "endpoint_url": p.get_param(PARAMS["endpoint_url"]) or None,
            "prefix": (p.get_param(PARAMS["prefix"]) or "odoo/attachments").strip("/"),
            "acl": p.get_param(PARAMS["acl"]) or "private",
            "use_presigned": p.get_param(PARAMS["use_presigned"]) == "1",
            "presigned_exp": int(p.get_param(PARAMS["presigned_exp"]) or "300"),
        }

    def _s3_client(self):
        if not boto3:
            raise UserError(_("Thiếu thư viện boto3. Hãy cài: pip install boto3"))
        prm = self._s3_params()
        if not (prm["bucket"] and prm["access_key"] and prm["secret_key"]):
            raise UserError(_("Chưa cấu hình S3 (bucket, access/secret key)."))

        session = boto3.session.Session(
            aws_access_key_id=prm["access_key"],
            aws_secret_access_key=prm["secret_key"],
            region_name=prm["region"],
        )
        return session.client(
            "s3",
            endpoint_url=prm["endpoint_url"],
            config=Config(s3={"addressing_style": "auto"}),
        )

# ====== Model chính ======
class ManagementDocumentS3(models.Model):
    _name = "management.document.s3"
    _description = "S3 Document (Standalone)"
    _inherit = "s3.config.mixin"

    # Hiển thị & metadata
    name = fields.Char("Tên hiển thị", required=True)
    s3_key = fields.Char("S3 Key", readonly=True,
                         help="VD: odoo/attachments/2025/10/22/file.png")
    content_type = fields.Char("MIME type", compute="_compute_head", store=False, readonly=True)
    size = fields.Integer("Kích thước (bytes)", compute="_compute_head", store=False, readonly=True)
    preview = fields.Binary("Xem nhanh (<= 2MB)", compute="_compute_preview", store=False, readonly=True)
    preview_filename = fields.Char(default=lambda self: "preview")

    # Trường upload
    file_upload = fields.Binary("Tệp đính kèm", attachment=False)
    file_upload_fname = fields.Char("Tên tệp")

    # ========= Utilities =========
    def _safe_filename(self, filename: str) -> str:
        name = os.path.basename(filename or "file")
        name = name.replace("\\", "_").replace("/", "_")
        name = "".join(ch if ch.isprintable() else "_" for ch in name)
        if not name or name in (".", ".."):
            name = "file"
        root, ext = os.path.splitext(name)
        if not ext:
            guessed = mimetypes.guess_extension(mimetypes.guess_type(name)[0] or "")
            if guessed:
                ext = guessed
        if len(root) > 160:
            root = root[:160]
        return (root or "file") + (ext or "")

    def _build_key_from_filename(self, filename: str) -> str:
        prm = self._s3_params()
        today = datetime.utcnow().strftime("%Y/%m/%d")
        safe_name = self._safe_filename(filename)
        return f"{prm['prefix']}/{today}/{safe_name}".strip("/")

    def _ensure_unique_key(self, client, bucket: str, key: str) -> str:
        try:
            client.head_object(Bucket=bucket, Key=key)
            root, ext = os.path.splitext(key)
            return f"{root}-{uuid.uuid4().hex[:8]}{ext}"
        except ClientError as e:
            code = getattr(e, "response", {}).get("Error", {}).get("Code")
            if code in ("404", "NoSuchKey", "NotFound"):
                return key
            return key

    def _decode_bin_data(self, bin_data):
        if bin_data is None:
            return b""
        if isinstance(bin_data, str) and bin_data.startswith("data:"):
            b64 = bin_data.split(",", 1)[1]
            try:
                return base64.b64decode(b64, validate=True)
            except Exception:
                return base64.b64decode(b64)
        if isinstance(bin_data, str):
            try:
                return base64.b64decode(bin_data, validate=True)
            except Exception:
                return bin_data.encode("utf-8", errors="ignore")
        if isinstance(bin_data, (bytes, bytearray, memoryview)):
            bts = bytes(bin_data)
            try:
                return base64.b64decode(bts, validate=True)
            except Exception:
                return bts
        return bytes(bin_data)

    # ========= HEAD & Preview =========
    @api.depends("s3_key")
    def _compute_head(self):
        for rec in self:
            rec.content_type = False
            rec.size = 0
            if not rec.s3_key:
                continue
            try:
                client = rec._s3_client()
                head = client.head_object(Bucket=rec._s3_params()["bucket"], Key=rec.s3_key)
                rec.size = int(head.get("ContentLength", 0))
                rec.content_type = head.get("ContentType") or mimetypes.guess_type(rec.s3_key)[0] or "application/octet-stream"
            except Exception as e:
                _logger.error("HEAD S3 fail key=%s: %s", rec.s3_key, e)

    @api.depends("s3_key")
    def _compute_preview(self):
        MAX_PREVIEW = 2 * 1024 * 1024
        for rec in self:
            rec.preview = False
            if not rec.s3_key:
                continue
            try:
                size = rec.size or 0
                if not size:
                    client = rec._s3_client()
                    head = client.head_object(Bucket=rec._s3_params()["bucket"], Key=rec.s3_key)
                    size = int(head.get("ContentLength", 0))
                if size and size > MAX_PREVIEW:
                    continue
                client = rec._s3_client()
                obj = client.get_object(Bucket=rec._s3_params()["bucket"], Key=rec.s3_key)
                rec.preview = base64.b64encode(obj["Body"].read())
            except Exception as e:
                _logger.error("Preview S3 fail key=%s: %s", rec.s3_key, e)
                rec.preview = False

    # ========= Upload =========
    def action_upload_to_s3(self):
        """Đẩy `file_upload` lên S3, set s3_key + metadata, xoá dữ liệu upload tạm."""
        self.ensure_one()
        if not self.file_upload:
            raise UserError(_("Chưa chọn tệp để tải lên."))

        raw = self._decode_bin_data(self.file_upload)
        if not isinstance(raw, (bytes, bytearray)) or len(raw) == 0:
            raise UserError(_("Dữ liệu tệp không hợp lệ."))

        filename = self.file_upload_fname or self.name or "file"
        filename = self._safe_filename(filename)
        ctype = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        disp = f'inline; filename="{filename}"; filename*=UTF-8\'\'{urlquote(filename)}'
        md5_b64 = base64.b64encode(hashlib.md5(raw).digest()).decode("ascii")

        prm = self._s3_params()
        client = self._s3_client()
        key = self._ensure_unique_key(client, prm["bucket"], self._build_key_from_filename(filename))

        put_args = dict(
            Bucket=prm["bucket"],
            Key=key,
            Body=raw,
            ACL=prm["acl"],
            ContentType=ctype,
            ContentDisposition=disp,
            ContentMD5=md5_b64,
        )

        _logger.warning("📤 Upload DocumentS3 → bucket=%s key=%s filename=%s size=%s",
                        prm["bucket"], key, filename, len(raw))
        try:
            client.put_object(**put_args)
        except ClientError as e:
            msg = getattr(e, "response", {}).get("Error", {}).get("Message", str(e))
            raise UserError(_("Lỗi S3: %s") % msg)

        # cập nhật record
        self.write({
            "name": filename if not self.name else self.name,
            "s3_key": key,
            "file_upload": False,
            "file_upload_fname": False,
        })
        # force recompute metadata
        self._compute_head()
        self._compute_preview()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Đã tải lên S3"),
                "message": key,
                "type": "success",
                "sticky": False,
            },
        }

    # (Tùy chọn) Tự upload ngay khi tạo nếu người dùng đã gắn file
    @api.model
    def create(self, vals):
        rec = super().create(vals)
        if vals.get("file_upload"):
            rec.action_upload_to_s3()
        return rec

    # ========= Actions xem/tải =========
    def action_open_inline(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": f"/s3doc/content/{self.id}?disposition=inline",
            "target": "new",
        }

    def action_download(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": f"/s3doc/content/{self.id}?disposition=attachment",
            "target": "self",
        }
