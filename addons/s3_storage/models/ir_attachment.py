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

from odoo import models, _, api
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

    # ======================================================
    # CONFIG / CLIENT
    # ======================================================
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

    # ======================================================
    # FILENAME
    # ======================================================
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

    def _pick_filename(self):
        candidates = [
            getattr(self, "name", None),
            self.env.context.get("filename"),
            self.env.context.get("default_name"),
            self.env.context.get("datas_fname"),
        ]
        for c in candidates:
            if c:
                return c
        return "file"

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

    # ======================================================
    # KEY NORMALIZE (handle ABSOLUTE PATHS)
    # ======================================================
    def _normalize_store_key(self, fname: str) -> str:
        """
        Chuẩn hoá về key S3 tương đối, xử lý được:
        - s3://...
        - absolute path: /.../filestore[/<dbname>]/...
        - 'filestore/<dbname>/...'
        - còn dư '<dbname>/' ở đầu
        """
        key = str(fname or "").strip()
        # strip schema
        if key.startswith("s3://"):
            key = key[5:]
        # try cut absolute filestore root
        filestore_root = ""
        try:
            filestore_root = self._filestore()  # e.g. /var/lib/odoo/.local/share/Odoo/filestore or .../filestore/<db>
        except Exception:
            pass
        if filestore_root:
            fs_root = filestore_root.rstrip("/")
            # TH1: has /filestore/<db> in absolute
            dbname = self.env.cr.dbname
            fs_root_with_db = f"{fs_root}/{dbname}"
            for candidate in (fs_root_with_db, fs_root):
                c = candidate.lstrip("/")
                if key.startswith(c + "/"):
                    key = key[len(c) + 1 :]
                    break
        # strip leading slash
        key = key.lstrip("/")
        # remove 'filestore/<db>/' if still present
        fs_prefix = f"filestore/{self.env.cr.dbname}/"
        if key.startswith(fs_prefix):
            key = key[len(fs_prefix):]
        # remove '<db>/' if still present
        db_prefix = f"{self.env.cr.dbname}/"
        if key.startswith(db_prefix):
            key = key[len(db_prefix):]
        # final trim
        return key.lstrip("/")

    def _is_s3_key(self, fname) -> bool:
        if not fname:
            return False
        prm = self._s3_params()
        s3_prefix = (prm.get("prefix") or "odoo/attachments").strip("/")
        key = self._normalize_store_key(fname)
        return key.startswith(s3_prefix) or key == s3_prefix

    # ======================================================
    # DECODE
    # ======================================================
    def _decode_bin_data(self, bin_data):
        if bin_data is None:
            return b""
        if isinstance(bin_data, str) and bin_data.startswith("data:"):
            try:
                b64 = bin_data.split(",", 1)[1]
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

    # ======================================================
    # ORM HOOKS
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
            if vals.get("name"):
                fname = vals["name"]
            elif len(self) == 1:
                fname = self.name or "file"
            else:
                fname = "file"
            if "." not in (fname or ""):
                mt = vals.get("mimetype") or (self.mimetype if len(self) == 1 else "")
                ext = mimetypes.guess_extension(mt) or ""
                fname = f"{fname}{ext}" if ext else fname
            ctx["filename"] = fname
            if not vals.get("name"):
                vals["name"] = fname
        return super(IrAttachment, self.with_context(ctx)).write(vals)

    # ======================================================
    # WRITE (UPLOAD)
    # ======================================================
    def _file_write(self, bin_data, checksum):
        if not self._s3_enabled():
            return super()._file_write(bin_data, checksum)
        raw = self._decode_bin_data(bin_data)
        if not isinstance(raw, (bytes, bytearray)):
            raise UserError(_("Dữ liệu file không hợp lệ."))

        prm = self._s3_params()
        filename = self._pick_filename()
        key = self._build_key_from_filename(filename)

        _logger.warning("📤 Uploading to S3 bucket=%s key=%s (original=%s size=%s)", prm["bucket"], key, filename, len(raw))
        try:
            client = self._s3_client()
            key = self._ensure_unique_key(client, prm["bucket"], key)
            ctype = mimetypes.guess_type(filename)[0] or "application/octet-stream"
            disp = f'inline; filename="{self._safe_filename(filename)}"; filename*=UTF-8\'\'{urlquote(filename)}'
            md5_b64 = base64.b64encode(hashlib.md5(raw).digest()).decode("ascii")
            client.put_object(
                Bucket=prm["bucket"],
                Key=key,
                Body=raw,
                ACL=prm["acl"],
                ContentType=ctype,
                ContentDisposition=disp,
                ContentMD5=md5_b64,
            )
            _logger.warning("✅ Uploaded to S3: %s (md5=%s)", key, md5_b64)
            return key
        except ClientError as e:
            msg = getattr(e, "response", {}).get("Error", {}).get("Message", str(e))
            _logger.error("❌ S3 ClientError (write): %s", msg)
            raise UserError(_("Lỗi S3: %s") % msg)
        except Exception as e:
            _logger.error("❌ Exception (write): %s", e)
            raise UserError(_("Lỗi khác khi upload S3: %s") % str(e))

    # ======================================================
    # READ (DOWNLOAD) – base64 cho Odoo
    # ======================================================
    def _file_read(self, fname):
        # đọc từ S3 nếu là S3 key (không phụ thuộc enabled)
        if not self._is_s3_key(fname):
            return super()._file_read(fname)
        prm = self._s3_params()
        key = self._normalize_store_key(fname)
        _logger.warning("📥 Reading from S3 bucket=%s key=%s", prm["bucket"], key)
        try:
            s3 = self._s3_client()
            obj = s3.get_object(Bucket=prm["bucket"], Key=key)
            return base64.b64encode(obj["Body"].read())
        except ClientError as e:
            msg = getattr(e, "response", {}).get("Error", {}).get("Message", str(e))
            _logger.error("❌ S3 ClientError (read): %s", msg)
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

    # ======================================================
    # SIZE
    # ======================================================
    def _read_file_get_size(self, fname):
        if not self._is_s3_key(fname):
            return super()._read_file_get_size(fname)
        try:
            head = self._s3_client().head_object(
                Bucket=self._s3_params()["bucket"],
                Key=self._normalize_store_key(fname),
            )
            return int(head.get("ContentLength", 0))
        except Exception as e:
            _logger.warning("⚠️ head_object failed for %s: %s", fname, e)
            return 0

    # ======================================================
    # DELETE (S3 + dọn cache)
    # ======================================================
    def _file_delete(self, fname):
        if not self._is_s3_key(fname):
            return super()._file_delete(fname)

        prm = self._s3_params()
        key = self._normalize_store_key(fname)
        _logger.warning("🗑️ Deleting S3 object bucket=%s key=%s", prm["bucket"], key)

        try:
            self._s3_client().delete_object(Bucket=prm["bucket"], Key=key)
        except Exception as e:
            _logger.warning("⚠️ Cannot delete S3 object %s: %s", key, e)

        cache_path = self._s3_cache_root() / key
        try:
            if cache_path.exists():
                cache_path.unlink()
        except Exception as e:
            _logger.warning("⚠️ Cannot remove cache file %s: %s", cache_path, e)

        return True

    # ======================================================
    # FULL PATH (CACHE LOCAL CHO /web/image)
    # ======================================================
    def _s3_cache_root(self) -> Path:
        return Path(os.getenv("ODOO_S3_CACHE_DIR", "/var/lib/odoo/.local/share/Odoo/s3cache"))

    def _download_s3_to_cache(self, key: str) -> str:
        prm = self._s3_params()
        client = self._s3_client()
        cache_root = self._s3_cache_root()
        local_path = cache_root / key  # GIỮ NGUYÊN cấu trúc thư mục theo key
        local_path.parent.mkdir(parents=True, exist_ok=True)

        if not local_path.exists() or local_path.stat().st_size == 0:
            _logger.warning("⬇️  Download S3 to cache: s3://%s/%s -> %s", prm["bucket"], key, local_path)
            client.download_file(prm["bucket"], key, str(local_path))
        return str(local_path)

    def _full_path(self, store_fname):
        # Log chẩn đoán (có thể giữ lại vài ngày đầu để chắc chắn)
        # key_dbg = self._normalize_store_key(store_fname)
        # _logger.warning("🔎 _full_path input=%s | normalized=%s | is_s3=%s",
        #                 store_fname, key_dbg, self._is_s3_key(store_fname))

        if not self._is_s3_key(store_fname):
            return super()._full_path(store_fname)

        key = self._normalize_store_key(store_fname)
        try:
            return self._download_s3_to_cache(key)
        except ClientError as e:
            err = getattr(e, "response", {}).get("Error", {}) or {}
            msg = err.get("Message", str(e))
            _logger.error("❌ S3 download failed (full_path): %s | key=%s", msg, key)
            return super()._full_path(store_fname)
        except Exception as e:
            _logger.error("❌ Exception (cache full_path): %s", e)
            return super()._full_path(store_fname)
