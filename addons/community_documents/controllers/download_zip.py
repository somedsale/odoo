# -*- coding: utf-8 -*-
import base64
import io
import mimetypes
import os
import zipfile

from odoo import http
from odoo.http import request
from werkzeug.utils import secure_filename


class CommunityDocumentsZipController(http.Controller):

    @http.route("/community_documents/download_zip", type="http", auth="user", website=False)
    def download_zip(self, ids="", **kw):
        # ids: "1,2,3"
        id_list = []
        for part in (ids or "").split(","):
            part = part.strip()
            if part.isdigit():
                id_list.append(int(part))

        if not id_list:
            return request.not_found()

        # Không sudo -> tôn trọng ACL hiện tại của user
        docs = request.env["document.document"].browse(id_list).exists()

        # đảm bảo quyền read
        docs.check_access_rights("read")
        docs.check_access_rule("read")

        buf = io.BytesIO()
        used = set()

        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for doc in docs:
                att = doc.attachment_id
                if not att:
                    continue

                # File name
                base_name = att.name or doc.name or f"doc_{doc.id}"
                base_name = secure_filename(base_name) or f"doc_{doc.id}"

                # URL attachment -> tạo file .url
                if att.type == "url":
                    fn = base_name
                    if not fn.lower().endswith(".url"):
                        fn += ".url"
                    fn = self._unique_name(fn, used)
                    content = f"[InternetShortcut]\nURL={att.url or ''}\n"
                    zf.writestr(fn, content)
                    continue

                # Binary attachment
                data = base64.b64decode(att.datas or b"")
                fn = base_name

                # gắn extension nếu thiếu
                root, ext = os.path.splitext(fn)
                if not ext and att.mimetype:
                    guess = mimetypes.guess_extension(att.mimetype) or ""
                    fn = root + guess

                fn = self._unique_name(fn, used)
                zf.writestr(fn, data)

        buf.seek(0)
        zip_bytes = buf.getvalue()

        headers = [
            ("Content-Type", "application/zip"),
            ("Content-Disposition", 'attachment; filename="documents.zip"'),
        ]
        return request.make_response(zip_bytes, headers)

    def _unique_name(self, filename, used_set):
        filename = filename or "file"
        name, ext = os.path.splitext(filename)
        candidate = filename
        i = 1
        while candidate in used_set:
            candidate = f"{name}_{i}{ext}"
            i += 1
        used_set.add(candidate)
        return candidate
