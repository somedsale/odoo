# -*- coding: utf-8 -*-
import logging
from urllib.parse import quote as urlquote

from odoo import http, _
from odoo.http import request
from odoo.exceptions import AccessError, MissingError

_logger = logging.getLogger(__name__)

try:
    from botocore.exceptions import ClientError
except Exception:  # pragma: no cover
    ClientError = Exception


class S3DocController(http.Controller):

    @http.route("/s3doc/content/<int:doc_id>", type="http", auth="user", methods=["GET"], csrf=False)
    def s3doc_content(self, doc_id, disposition="inline", **kwargs):
        """
        - Nếu cấu hình 'use_presigned' => redirect sang presigned URL (tự hết hạn).
        - Ngược lại => stream bytes từ S3 về client.
        """
        try:
            doc = request.env["management.document.s3"].browse(doc_id)
            if not doc.exists():
                raise MissingError(_("Không tìm thấy tài liệu"))
            doc.check_access_rights("read")
            doc.check_access_rule("read")

            prm = doc._s3_params()
            s3 = doc._s3_client()
            key = doc.s3_key
            filename = doc.name or "file"

            if prm.get("use_presigned"):
                # Tạo presigned URL (GET) với Content-Disposition đúng tên Unicode
                response_params = {
                    "ResponseContentDisposition": f'{disposition}; filename="{filename}"; filename*=UTF-8\'\'{urlquote(filename)}'
                }
                # Có thể gán luôn type để inline đúng loại
                if doc.content_type:
                    response_params["ResponseContentType"] = doc.content_type

                url = s3.generate_presigned_url(
                    ClientMethod="get_object",
                    Params={
                        "Bucket": prm["bucket"],
                        "Key": key,
                        **response_params,
                    },
                    ExpiresIn=prm.get("presigned_exp", 300),
                )
                # Redirect 302 sang URL presigned (trình duyệt tải/xem trực tiếp từ S3)
                from werkzeug.utils import redirect
                return redirect(url)

            # --- Stream thẳng nếu không dùng presigned ---
            head = s3.head_object(Bucket=prm["bucket"], Key=key)
            content_type = head.get("ContentType") or doc.content_type or "application/octet-stream"
            size = int(head.get("ContentLength", 0))

            obj = s3.get_object(Bucket=prm["bucket"], Key=key)
            data = obj["Body"].read()

            headers = [
                ("Content-Type", content_type),
                ("Content-Disposition", f'{disposition}; filename="{filename}"; filename*=UTF-8\'\'{urlquote(filename)}'),
                ("Content-Length", str(len(data) if data else size)),
                ("Cache-Control", "private, max-age=0, no-cache"),
            ]
            return request.make_response(data, headers)

        except (AccessError, MissingError):
            return request.not_found()
        except ClientError as e:
            msg = getattr(e, "response", {}).get("Error", {}).get("Message", str(e))
            _logger.error("S3 client error (doc_id=%s): %s", doc_id, msg)
            return request.make_response(("S3 error: " + msg).encode("utf-8"), [("Content-Type", "text/plain")], 500)
        except Exception as e:
            _logger.error("Unhandled error (doc_id=%s): %s", doc_id, e)
            return request.make_response(str(e).encode("utf-8"), [("Content-Type", "text/plain")], 500)
