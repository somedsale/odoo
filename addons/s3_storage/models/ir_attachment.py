# -*- coding: utf-8 -*-
import base64
import mimetypes
import uuid
from datetime import datetime
import logging
import os
from pathlib import Path
from urllib.parse import quote as urlquote
import hashlib

from odoo import models, api, fields, _
from odoo.exceptions import UserError
from odoo.http import request
from werkzeug.utils import redirect  # ✅ dùng redirect đúng chuẩn Odoo 17
from urllib.parse import quote_plus

_logger = logging.getLogger(__name__)

try:
    import boto3
    from botocore.client import Config
    from botocore.exceptions import ClientError
except Exception:
    boto3 = None
    ClientError = Exception


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    s3_url = fields.Char("S3 URL", compute="_compute_s3_url", store=False)

    # ======================================================
    # CONFIG
    # ======================================================
    def _s3_enabled(self):
        val = self.env["ir.config_parameter"].sudo().get_param("somed_s3.enabled")
        return str(val or "").strip() == "1"

    def _s3_params(self):
        p = self.env["ir.config_parameter"].sudo()
        return {
            "bucket": p.get_param("somed_s3.bucket") or "",
            "region": p.get_param("somed_s3.region") or None,
            "access_key": p.get_param("somed_s3.access_key") or None,
            "secret_key": p.get_param("somed_s3.secret_key") or None,
            "endpoint_url": p.get_param("somed_s3.endpoint_url") or None,
            "prefix": (p.get_param("somed_s3.prefix") or "odoo/attachments").strip("/"),
            "acl": p.get_param("somed_s3.acl") or "private",
        }

    def _s3_client(self):
        if not boto3:
            raise UserError(_("Thiếu thư viện boto3."))
        prm = self._s3_params()
        if not (prm["bucket"] and prm["access_key"] and prm["secret_key"]):
            raise UserError(_("Chưa cấu hình đầy đủ thông tin S3."))
        session = boto3.session.Session(
            aws_access_key_id=prm["access_key"],
            aws_secret_access_key=prm["secret_key"],
            region_name=prm["region"],
        )
        return session.client(
            "s3", endpoint_url=prm["endpoint_url"], config=Config(s3={"addressing_style": "auto"})
        )

    # ======================================================
    # HELPERS
    # ======================================================
    def _safe_filename(self, filename):
        name = os.path.basename(filename or "file")
        name = name.replace("\\", "_").replace("/", "_")
        root, ext = os.path.splitext(name)
        if not ext:
            guessed = mimetypes.guess_extension(mimetypes.guess_type(name)[0] or "")
            if guessed:
                ext = guessed
        if len(root) > 160:
            root = root[:160]
        return (root or "file") + (ext or "")

    def _normalize_store_key(self, fname):
        """Bỏ schema, filestore local path → key S3"""
        key = str(fname or "").strip()
        if key.startswith("s3://"):
            key = key[5:]
        try:
            fsroot = self._filestore()
            db = self.env.cr.dbname
            for prefix in (fsroot, f"{fsroot}/{db}", f"filestore/{db}", db):
                if key.startswith(prefix):
                    key = key[len(prefix):].lstrip("/")
        except Exception:
            pass
        return key.lstrip("/")

    def _is_s3_key(self, fname):
        """Chỉ coi là S3 key nếu có prefix hợp lệ, tránh web assets."""
        if not fname:
            return False
        fname_low = fname.lower()
        # Loại trừ assets, JS, CSS, font, favicon, svg, xml, theme
        skip_exts = ('.js', '.css', '.xml', '.svg', '.woff', '.ttf', '.less', '.scss')
        if any(fname_low.endswith(ext) for ext in skip_exts):
            return False
        if 'web.assets' in fname_low or 'web/' in fname_low or 'theme_' in fname_low:
            return False
        prefix = (self._s3_params().get("prefix") or "odoo/attachments").strip("/")
        key = self._normalize_store_key(fname)
        return key.startswith(prefix)

    def _build_key_from_filename(self, filename):
        prm = self._s3_params()
        today = datetime.utcnow().strftime("%Y/%m/%d")
        safe_name = self._safe_filename(filename)
        return f"{prm['prefix']}/{today}/{safe_name}".strip("/")

    def _decode_bin_data(self, data):
        if data is None:
            return b""
        if isinstance(data, str):
            try:
                return base64.b64decode(data.split(",")[-1])
            except Exception:
                return data.encode("utf-8", errors="ignore")
        if isinstance(data, (bytes, bytearray, memoryview)):
            return bytes(data)
        return bytes(data)

    # ======================================================
    # PRESIGNED URL
    # ======================================================
    def _get_s3_url(self, key: str, expires_in=3600):
        """Trả về presigned URL hợp lệ cho S3."""
        prm = self._s3_params()
        client = self._s3_client()
        try:
            url = client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": prm["bucket"],
                    "Key": key,
                    "ResponseContentDisposition": f"inline; filename*=UTF-8''{quote_plus(self.name)}",
                    "ResponseContentType": self.mimetype or "application/octet-stream",
                },
                ExpiresIn=expires_in,
            )
            return url
        except Exception as e:
            _logger.error("❌ _get_s3_url failed for %s: %s", key, e)
            return None

    @api.depends("store_fname")
    def _compute_s3_url(self):
        for rec in self:
            if rec._is_s3_key(rec.store_fname):
                key = rec._normalize_store_key(rec.store_fname)
                rec.s3_url = rec._get_s3_url(key)
            else:
                rec.s3_url = False

    # ======================================================
    # ORM CREATE/WRITE
    # ======================================================
    @api.model
    def create(self, vals):
        base = vals.get("name") or "file"
        if "." not in base:
            ext = mimetypes.guess_extension(vals.get("mimetype") or "") or ""
            base = f"{base}{ext}" if ext else base
        vals["name"] = base
        ctx = dict(self._context or {})
        ctx.setdefault("filename", vals["name"])
        return super(IrAttachment, self.with_context(ctx)).create(vals)

    def write(self, vals):
        if "datas" not in vals:
            return super().write(vals)
        ctx = dict(self._context or {})
        if not ctx.get("filename"):
            fname = vals.get("name") or (self.name if len(self) == 1 else "file")
            if "." not in (fname or ""):
                mt = vals.get("mimetype") or (self.mimetype if len(self) == 1 else "")
                ext = mimetypes.guess_extension(mt) or ""
                fname = f"{fname}{ext}" if ext else fname
            ctx["filename"] = fname
            vals.setdefault("name", fname)
        return super(IrAttachment, self.with_context(ctx)).write(vals)

    # ======================================================
    # FILE WRITE → S3
    # ======================================================
    def _file_write(self, bin_data, checksum):
        """Upload file lên S3, tránh ghi đè khi trùng tên."""
        fname = self.env.context.get("filename") or self._safe_filename(self.name)
        fname_low = fname.lower()
        skip_exts = ('.js', '.css', '.xml', '.svg', '.woff', '.ttf', '.less', '.scss')
        if any(fname_low.endswith(ext) for ext in skip_exts) or 'web.assets' in fname_low:
            return super()._file_write(bin_data, checksum)

        if not self._s3_enabled():
            return super()._file_write(bin_data, checksum)

        raw = self._decode_bin_data(bin_data)
        prm = self._s3_params()
        base_key = self._build_key_from_filename(fname)

        try:
            client = self._s3_client()

            # === kiểm tra tồn tại, nếu có → thêm hậu tố ngẫu nhiên ===
            unique_key = base_key
            try:
                client.head_object(Bucket=prm["bucket"], Key=base_key)
                root, ext = os.path.splitext(base_key)
                unique_key = f"{root}-{uuid.uuid4().hex[:8]}{ext}"
                _logger.info("⚠️ S3 key existed, renamed to %s", unique_key)
            except ClientError as e:
                # Nếu file chưa tồn tại → ok
                code = e.response.get("Error", {}).get("Code")
                if code not in ("404", "NoSuchKey", "NotFound"):
                    raise

            ctype = mimetypes.guess_type(fname)[0] or "application/octet-stream"
            disp = f'inline; filename="{self._safe_filename(fname)}"; filename*=UTF-8\'\'{urlquote(fname)}'

            client.put_object(
                Bucket=prm["bucket"],
                Key=unique_key,
                Body=raw,
                ACL=prm["acl"],
                ContentType=ctype,
                ContentDisposition=disp,
            )

            _logger.info("📤 Uploaded to S3: %s", unique_key)
            return unique_key

        except Exception as e:
            _logger.error("❌ Upload S3 failed: %s", e)
            raise UserError(_("Lỗi upload S3: %s") % e)
    # ======================================================
    # READ (LOG)
    # ======================================================
    def _file_read(self, fname):
        if not self._is_s3_key(fname):
            return super()._file_read(fname)
        key = self._normalize_store_key(fname)
        _logger.info("🌐 [S3 READ redirect candidate] key=%s", key)
        return base64.b64encode(b"")

    # ======================================================
    # FULL PATH → REDIRECT
    # ======================================================
    def _full_path(self, store_fname):
        """Chỉ redirect nếu là file S3 (tránh lỗi assets local)."""
        if not self._is_s3_key(store_fname):
            return super()._full_path(store_fname)
        key = self._normalize_store_key(store_fname)
        url = self._get_s3_url(key)
        if url:
            _logger.info("➡️ [S3 REDIRECT] %s", url)
            return f"s3redirect::{url}"
        return super()._full_path(store_fname)

    # ======================================================
    # DELETE
    # ======================================================
    def _file_delete(self, fname):
        if not self._is_s3_key(fname):
            return super()._file_delete(fname)
        prm = self._s3_params()
        key = self._normalize_store_key(fname)
        try:
            self._s3_client().delete_object(Bucket=prm["bucket"], Key=key)
            _logger.info("🗑️ Deleted S3 object %s", key)
        except Exception as e:
            _logger.warning("⚠️ Delete failed: %s", e)
        return True
