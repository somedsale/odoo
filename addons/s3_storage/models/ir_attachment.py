# -*- coding: utf-8 -*-
import base64
import mimetypes
import uuid
from datetime import datetime
import logging
import os
from pathlib import Path

from odoo import models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    import boto3
    from botocore.client import Config
    from botocore.exceptions import ClientError
except Exception:  # pragma: no cover
    boto3 = None
    ClientError = Exception


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    # ----------------------- Helpers -----------------------
    def _s3_enabled(self):
        return self.env["ir.config_parameter"].sudo().get_param("somed_s3.enabled") == "1"

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
            raise UserError(_("Thiếu thư viện boto3, hãy cài đặt boto3."))
        prm = self._s3_params()
        if not (prm["bucket"] and prm["access_key"] and prm["secret_key"]):
            raise UserError(_("Chưa cấu hình đầy đủ thông tin S3."))
        session = boto3.session.Session(
            aws_access_key_id=prm["access_key"],
            aws_secret_access_key=prm["secret_key"],
            region_name=prm["region"],
        )
        return session.client("s3", endpoint_url=prm["endpoint_url"], config=Config(s3={"addressing_style": "auto"}))

    def _s3_make_key(self, *, checksum=None, filename=None):
        prm = self._s3_params()
        name = (filename or "file").lower()
        ext = ""
        if "." in name:
            part = name.rsplit(".", 1)[-1]
            if 0 < len(part) < 10:
                ext = f".{part}"
        today = datetime.utcnow().strftime("%Y/%m/%d")
        tail = checksum or uuid.uuid4().hex
        return f"{prm['prefix']}/{today}/{tail}{ext}".strip("/")

    def _is_s3_key(self, fname):
        if not fname:
            return False
        prm = self._s3_params()
        s3_prefix = prm["prefix"].strip("/")
        key = str(fname).strip("/")
        return key.startswith(s3_prefix + "/")

    # ----------------------- WRITE (UPLOAD) -----------------------
    # Odoo 17: signature (bin_data, checksum)
    def _file_write(self, bin_data, checksum):
        if not self._s3_enabled():
            return super()._file_write(bin_data, checksum)

        try:
            raw = base64.b64decode(bin_data or b"")
        except Exception:
            raise UserError(_("Không thể giải mã dữ liệu file để upload lên S3."))

        prm = self._s3_params()

        filename = (self.env.context.get("default_datas_fname")
                    or self.env.context.get("datas_fname")
                    or self.env.context.get("filename")
                    or self.env.context.get("default_name")
                    or "file")

        key = self._s3_make_key(checksum=checksum, filename=filename)

        _logger.warning("📤 Uploading to S3 bucket=%s key=%s", prm["bucket"], key)
        try:
            client = self._s3_client()
            ctype = mimetypes.guess_type(filename)[0] or "application/octet-stream"
            client.put_object(Bucket=prm["bucket"], Key=key, Body=raw, ACL=prm["acl"], ContentType=ctype)
            _logger.warning("✅ Uploaded successfully to S3: %s", key)
            return key  # store_fname
        except ClientError as e:
            msg = getattr(e, "response", {}).get("Error", {}).get("Message", str(e))
            _logger.error("❌ S3 ClientError (write): %s", msg)
            raise UserError(_("Lỗi S3: %s") % msg)
        except Exception as e:
            _logger.error("❌ Exception (write): %s", e)
            raise UserError(_("Lỗi khác khi upload S3: %s") % str(e))

    # ----------------------- READ (DOWNLOAD) -----------------------
    def _file_read(self, fname):
        if not self._s3_enabled() or not self._is_s3_key(fname):
            return super()._file_read(fname)

        prm = self._s3_params()
        key = str(fname).strip("/")

        _logger.warning("📥 Reading from S3 bucket=%s key=%s", prm["bucket"], key)
        try:
            s3 = self._s3_client()
            obj = s3.get_object(Bucket=prm["bucket"], Key=key)
            return base64.b64encode(obj["Body"].read())
        except ClientError as e:
            msg = getattr(e, "response", {}).get("Error", {}).get("Message", str(e))
            _logger.error("❌ S3 ClientError (read): %s", msg)
            # Fallback local cho file cũ nếu có
            try:
                return super()._file_read(fname)
            except Exception:
                raise UserError(_("Lỗi khi đọc file từ S3: %s") % msg)
        except Exception as e:
            _logger.error("❌ Exception (read): %s", e)
            try:
                return super()._file_read(fname)
            except Exception:
                raise UserError(_("Lỗi khác khi đọc S3: %s") % str(e))

    # ----------------------- SIZE -----------------------
    def _read_file_get_size(self, fname):
        if not self._s3_enabled() or not self._is_s3_key(fname):
            return super()._read_file_get_size(fname)
        try:
            head = self._s3_client().head_object(Bucket=self._s3_params()["bucket"], Key=str(fname).strip("/"))
            return int(head.get("ContentLength", 0))
        except Exception:
            return 0

    # ----------------------- DELETE -----------------------
    def _file_delete(self, fname):
        if not self._s3_enabled() or not self._is_s3_key(fname):
            return super()._file_delete(fname)
        prm = self._s3_params()
        key = str(fname).strip("/")
        try:
            self._s3_client().delete_object(Bucket=prm["bucket"], Key=key)
        except Exception:
            pass
        return True

    # ----------------------- CRITICAL FIX: _full_path -----------------------
    # Một số route (ảnh discuss, web editor, ...) đọc file bằng đường dẫn local:
    # Stream.from_attachment -> os.stat(_full_path(store_fname))
    # => Nếu file nằm trên S3, ta tải về cache local và trả path cache.
    def _full_path(self, store_fname):
        # Nếu chưa bật S3 hoặc key không thuộc S3 -> dùng đường dẫn mặc định
        if not self._s3_enabled() or not self._is_s3_key(store_fname):
            return super()._full_path(store_fname)

        prm = self._s3_params()
        key = str(store_fname).strip("/")

        # Thư mục cache cố định trong home odoo
        base_cache = Path("/var/lib/odoo/.local/share/Odoo/s3cache")
        # Thay "/" trong key thành "__" để làm tên file an toàn
        safe_name = key.replace("/", "__")
        cache_file = base_cache / safe_name

        try:
            base_cache.mkdir(parents=True, exist_ok=True)
            if not cache_file.exists() or cache_file.stat().st_size == 0:
                _logger.warning("⬇️  S3 -> cache: %s", cache_file)
                s3 = self._s3_client()
                obj = s3.get_object(Bucket=prm["bucket"], Key=key)
                with open(cache_file, "wb") as f:
                    f.write(obj["Body"].read())
            return str(cache_file)
        except ClientError as e:
            msg = getattr(e, "response", {}).get("Error", {}).get("Message", str(e))
            _logger.error("❌ S3 ClientError (cache full_path): %s", msg)
            # fallback: để Odoo thử path mặc định (sẽ 404 nếu không có)
            return super()._full_path(store_fname)
        except Exception as e:
            _logger.error("❌ Exception (cache full_path): %s", e)
            return super()._full_path(store_fname)
