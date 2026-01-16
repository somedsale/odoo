# -*- coding: utf-8 -*-
import base64
import mimetypes
import logging

from odoo import http, _
from odoo.http import request
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)


def _attachment_to_dict(a):
    return {
        "id": a.id,
        "name": a.name,
        "mimetype": a.mimetype,
        # url tải về
        "url": f"/web/content/{a.id}?download=true",
        "download_url": f"/web/content/{a.id}?download=true",
        # url xem inline (img src)
        "view_url": f"/web/content/{a.id}",
    }


class CommunityHubAttachmentController(http.Controller):
    """
    Upload file kiểu Teams:
    - FE dùng fetch multipart/form-data
    - BE tạo ir.attachment và "neo" vào channel (res_model/res_id) để người khác trong channel đọc được
    """

    @http.route(
        "/community_hub/api/attachment/upload",
        type="http",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def upload(self, **kw):
        community_id = int(kw.get("community_id") or 0)
        channel_id = int(kw.get("channel_id") or 0)

        if not community_id:
            return request.make_json_response({"error": "community_id is required"}, status=400)

        # chỉ member joined mới upload
        request.env["community.hub.member"].ensure_joined(community_id)

        # cần channel_id để gắn res_model/res_id (đảm bảo /web/content cho người khác xem được)
        if not channel_id:
            ch = request.env["community.hub.channel"].search([("community_id", "=", community_id)], limit=1)
            channel_id = ch.id if ch else 0
        if not channel_id:
            return request.make_json_response({"error": "channel_id is required"}, status=400)

        files = request.httprequest.files.getlist("files") or []
        if not files:
            return request.make_json_response({"items": []})

        Attachment = request.env["ir.attachment"]  # KHÔNG sudo để giữ create_uid đúng user
        created = []
        for f in files:
            try:
                content = f.read()
                if not content:
                    continue

                filename = getattr(f, "filename", None) or "file"
                mimetype = getattr(f, "mimetype", None) or mimetypes.guess_type(filename)[0] or "application/octet-stream"

                att = Attachment.create({
                    "name": filename,
                    "datas": base64.b64encode(content).decode("ascii"),
                    "mimetype": mimetype,
                    # neo vào channel để member khác tải/xem được
                    "res_model": "community.hub.channel",
                    "res_id": channel_id,
                })
                created.append(att)
            except Exception:
                _logger.exception("community_hub upload failed: %s", getattr(f, "filename", "file"))

        return request.make_json_response({"items": [_attachment_to_dict(a) for a in created]})

    @http.route("/community_hub/api/attachment/delete", type="json", auth="user")
    def delete(self, attachmentId=None, **kw):
        """
        Xoá file khi còn đang "draft" (user remove trước khi Post).
        Chỉ cho xoá nếu:
        - create_uid là user hiện tại
        - attachment chưa được gắn vào post/comment relation table
        """
        aid = int(attachmentId or 0)
        if not aid:
            return {"ok": True}

        att = request.env["ir.attachment"].browse(aid)
        if not att.exists():
            return {"ok": True}

        if att.create_uid.id != request.env.user.id:
            raise AccessError(_("You cannot delete this file."))

        # nếu đã được dùng trong post/comment => không xoá
        request.env.cr.execute(
            "SELECT 1 FROM community_hub_post_attachment_rel WHERE attachment_id=%s LIMIT 1", (aid,)
        )
        if request.env.cr.fetchone():
            return {"ok": False, "reason": "in_use"}

        request.env.cr.execute(
            "SELECT 1 FROM community_hub_comment_attachment_rel WHERE attachment_id=%s LIMIT 1", (aid,)
        )
        if request.env.cr.fetchone():
            return {"ok": False, "reason": "in_use"}

        att.unlink()
        return {"ok": True}
