# -*- coding: utf-8 -*-
from odoo import _, http, fields
from odoo.exceptions import AccessError, ValidationError
from odoo.http import request
from markupsafe import Markup, escape
import json
import base64
import logging
from urllib.parse import urlencode
from odoo.tools import html2plaintext

from werkzeug.utils import redirect
_logger = logging.getLogger(__name__)

# =========================================================
# BUS HELPERS (chịu nhiều signature _sendone khác nhau)
# =========================================================
def _bus_send(channel_name: str, channel_id: int, payload: dict):
    """
    Send payload to bus channel used by bus_service.addChannel(name, id).
    """
    bus = request.env["bus.bus"].sudo()
    dbname = request.env.cr.dbname
    channel_id = int(channel_id)
    payload = payload or {}

    full = (dbname, channel_name, channel_id)
    short = (channel_name, channel_id)

    for args in (
        (full, channel_name, payload),   # Odoo 17 hay dùng
        (short, channel_name, payload),  # fallback
        (full, payload),                 # signature cũ
        (short, payload),
    ):
        try:
            bus._sendone(*args)
            return True
        except TypeError:
            continue
        except Exception:
            _logger.exception("bus _sendone failed args=%s", args)
            return False

    _logger.warning("bus _sendone: no compatible signature found")
    return False


def _notify_community(community_id: int, payload: dict):
    _bus_send("community_hub", int(community_id), payload)


def _notify_user(user_id: int, payload: dict):
    _bus_send("community_hub.user", int(user_id), payload)


# =========================================================
# SMALL UTILS
# =========================================================
def _to_int_list(v):
    """Accept [1,2], ('1','2'), '1,2' ..."""
    if not v:
        return []
    if isinstance(v, (list, tuple)):
        out = []
        for x in v:
            try:
                out.append(int(x))
            except Exception:
                pass
        return out
    if isinstance(v, str):
        parts = [p.strip() for p in v.split(",")]
        out = []
        for p in parts:
            try:
                out.append(int(p))
            except Exception:
                pass
        return out
    try:
        return [int(v)]
    except Exception:
        return []


def _dt_to_str(dt):
    """JSON-safe datetime string."""
    if not dt:
        return False
    try:
        return fields.Datetime.to_string(dt)
    except Exception:
        return str(dt)


def _ext_from_name(name):
    name = (name or "").strip()
    if "." in name:
        return name.rsplit(".", 1)[-1].lower()
    return ""


def _is_image_mimetype(m):
    return bool(m) and str(m).startswith("image/")


# =========================================================
# ACCESS HELPERS
# =========================================================
def _get_member(community_id: int, user_id: int):
    Member = request.env["community.hub.member"].sudo()
    return Member.search(
        [("community_id", "=", int(community_id)), ("user_id", "=", int(user_id))],
        limit=1
    )


def _ensure_access_community(community_id: int):
    community_id = int(community_id)
    community = request.env["community.hub"].sudo().browse(community_id)
    if not community.exists():
        raise ValidationError(_("Community not found."))

    m = _get_member(community_id, request.env.user.id)
    if not m or m.state not in ("joined", "invited"):
        raise AccessError(_("You are not allowed to access this community."))
    return community, m


def _ensure_joined(community_id: int):
    community, m = _ensure_access_community(community_id)
    if m.state != "joined":
        raise AccessError(_("You must join this community to do this action."))
    return community, m


def _ensure_manage(community_id: int):
    community, m = _ensure_joined(community_id)
    if m.role not in ("owner", "admin"):
        raise AccessError(_("You are not allowed to manage this community."))
    return community, m


def _ensure_owner(community_id: int):
    community, m = _ensure_joined(community_id)
    if m.role != "owner":
        raise AccessError(_("Only owner can do this action."))
    return community, m


def _is_creator_uid(record_create_uid: int):
    """Chỉ creator (create_uid) mới được sửa/xoá."""
    uid = request.env.user.id
    return bool(record_create_uid) and int(record_create_uid) == int(uid)

def _unread_counts_for_user(user_id: int, community_ids=None):
    """
    Return:
      {
        "community": {community_id: unread_count},
        "channel":   {channel_id: unread_count},
      }

    ✅ IMPORTANT:
    - channel map phải trả FULL (kể cả 0) để FE merge có thể reset badge.
    """
    user_id = int(user_id)
    Member = request.env["community.hub.member"].sudo()
    Channel = request.env["community.hub.channel"].sudo()

    dom_mem = [("user_id", "=", user_id), ("state", "=", "joined")]
    if community_ids:
        dom_mem.append(("community_id", "in", [int(x) for x in community_ids]))

    joined_cids = Member.search(dom_mem).mapped("community_id").ids
    if not joined_cids:
        return {"community": {}, "channel": {}}

    channels = Channel.search([("community_id", "in", joined_cids)])
    if not channels:
        return {"community": {cid: 0 for cid in joined_cids}, "channel": {}}

    ch_ids = channels.ids

    cr = request.env.cr
    cr.execute("""
        SELECT p.channel_id, COUNT(*)::int AS cnt
        FROM community_hub_post p
        LEFT JOIN community_hub_channel_read r
          ON r.channel_id = p.channel_id AND r.user_id = %s
        WHERE p.channel_id IN %s
          AND (r.last_read_post_id IS NULL OR p.id > r.last_read_post_id)
        GROUP BY p.channel_id
    """, (user_id, tuple(ch_ids)))

    rows = cr.fetchall()  # [(channel_id, cnt), ...]
    only_nonzero = {int(chid): int(cnt) for (chid, cnt) in rows}

    # ✅ FULL channel map (missing => 0)
    full_ch_cnt = {int(ch.id): int(only_nonzero.get(ch.id, 0)) for ch in channels}

    # ✅ cộng theo community từ full map
    ch_to_c = {int(ch.id): int(ch.community_id.id) for ch in channels}
    c_cnt = {int(cid): 0 for cid in joined_cids}
    for chid, cnt in full_ch_cnt.items():
        cid = ch_to_c.get(chid)
        if cid:
            c_cnt[cid] = c_cnt.get(cid, 0) + int(cnt)

    return {"community": c_cnt, "channel": full_ch_cnt}
def _set_channel_read(user_id: int, channel_id: int, last_post_id: int):
    Read = request.env["community.hub.channel.read"].sudo()
    ch = request.env["community.hub.channel"].sudo().browse(int(channel_id)).exists()
    if not ch:
        return False

    uid = int(user_id)
    last_post_id = int(last_post_id or 0)

    r = Read.search([("channel_id", "=", ch.id), ("user_id", "=", uid)], limit=1)

    vals = {
        "community_id": ch.community_id.id,
        "channel_id": ch.id,
        "user_id": uid,
        "last_read_post_id": last_post_id or False,
        "last_read_at": fields.Datetime.now(),
    }

    if r:
        # chỉ tăng, không giảm
        if r.last_read_post_id and last_post_id and r.last_read_post_id.id > last_post_id:
            vals["last_read_post_id"] = r.last_read_post_id.id
        r.write(vals)
    else:
        Read.create(vals)

    return True

# =========================================================
# ATTACHMENTS
# =========================================================
def _serialize_attachment(a):
    """
    ✅ FIX "Không rõ ngày": trả create_date dạng string.
    """
    mimetype = a.mimetype or "application/octet-stream"
    name = a.name or ""
    open_url = f"/web/content/{a.id}?download=false"
    download_url = f"/web/content/{a.id}?download=true"

    return {
        "id": a.id,
        "name": name,
        "mimetype": mimetype,
        "size": a.file_size or 0,
        "ext": _ext_from_name(name),
        "create_date": _dt_to_str(a.create_date),  # ✅ timeline
        "open_url": open_url,
        "view_url": open_url,
        "download_url": download_url,
        "thumb_url": open_url if _is_image_mimetype(mimetype) else "",
        "kind": "image" if _is_image_mimetype(mimetype) else "file",
    }


def _attachments_for(res_model, res_id):
    """
    Không sudo để respect rule (nếu bị rule chặn có thể sudo + tự enforce),
    nhưng trong feature timeline sẽ dùng sudo + enforce bằng community membership.
    """
    Att = request.env["ir.attachment"]
    atts = Att.search(
        [("res_model", "=", res_model), ("res_id", "=", int(res_id))],
        order="id asc",
    )
    return [_serialize_attachment(a) for a in atts]


def _relocate_attachments(attachment_ids, res_model, res_id):
    """
    Move only current user's draft attachments onto the record.
    Draft attachments đang gắn tạm vào res.users (res_model='res.users', res_id=user.id)
    """
    ids = _to_int_list(attachment_ids)
    if not ids:
        return []

    uid = request.env.user.id
    Att = request.env["ir.attachment"].sudo()
    atts = Att.browse(ids).exists()

    # Chỉ cho relocate các attachment do chính user tạo
    atts = atts.filtered(lambda a: a.create_uid.id == uid)
    if not atts:
        return []

    atts.write({"res_model": res_model, "res_id": int(res_id)})
    return atts.ids


def _delete_attachment(attachment_id: int):
    """
    Xoá attachment an toàn: chỉ cho xoá nếu create_uid là current user.
    (áp dụng cho draft/pending attachments)
    """
    aid = int(attachment_id or 0)
    if not aid:
        return False
    Att = request.env["ir.attachment"].sudo().browse(aid).exists()
    if not Att:
        return False
    if Att.create_uid.id != request.env.user.id:
        raise AccessError(_("You cannot delete this attachment."))
    Att.unlink()
    return True


def _cleanup_attachments_any(res_model: str, res_ids):
    """
    Cleanup attachments theo record (dùng khi xoá post/comment).
    Ở đây có thể xoá ALL attachments gắn vào record để tránh orphan.
    """
    ids = [int(x) for x in (res_ids or []) if x]
    if not ids:
        return
    Att = request.env["ir.attachment"].sudo()
    atts = Att.search([("res_model", "=", res_model), ("res_id", "in", ids)])
    if atts:
        atts.unlink()


# =========================================================
# DISCUSS INBOX NOTIFY (optional)
# =========================================================
def _hub_dashboard_url(community_id=None, channel_id=None, post_id=None, tab="posts"):
    action = request.env.ref("community_hub.action_community_hub_client", raise_if_not_found=False)
    menu = request.env.ref("community_hub.menu_community_hub_root", raise_if_not_found=False)

    parts = []
    if action:
        parts.append(f"action={action.id}")
    if menu:
        parts.append(f"menu_id={menu.id}")

    if community_id:
        parts.append(f"community_id={int(community_id)}")
    if channel_id:
        parts.append(f"channel_id={int(channel_id)}")
    if post_id:
        parts.append(f"post_id={int(post_id)}")
    if tab:
        parts.append(f"tab={tab}")

    return "/web#" + "&".join(parts) if parts else "/web"


def _notify_discuss_inbox_users(user_ids, *, subject, body_html, community_id=None, channel_id=None, post_id=None):
    user_ids = [int(u) for u in (user_ids or []) if u]
    if not user_ids:
        return

    env = request.env
    Users = env["res.users"].sudo().browse(list(set(user_ids)))
    partner_ids = Users.mapped("partner_id").ids
    if not partner_ids:
        return

    author_pid = env.user.partner_id.id

    # ===== chọn target record để message_post =====
    target = None
    if post_id:
        target = env["community.hub.post"].sudo().browse(int(post_id)).exists() or None
    if not target and channel_id:
        target = env["community.hub.channel"].sudo().browse(int(channel_id)).exists() or None
    if not target and community_id:
        target = env["community.hub"].sudo().browse(int(community_id)).exists() or None
    # --- resolve ids nếu thiếu (post -> channel -> community) ---
    if post_id:
        p = env["community.hub.post"].sudo().browse(int(post_id)).exists()
        if p:
            # tùy field thực tế của bạn: channel_id / community_id
            if not channel_id and hasattr(p, "channel_id"):
                channel_id = p.channel_id.id
            if not community_id and hasattr(p, "community_id"):
                community_id = p.community_id.id
            # nếu post chỉ có channel_id thì suy ra community_id từ channel
            if channel_id and (not community_id) and hasattr(p, "channel_id") and hasattr(p.channel_id, "community_id"):
                community_id = p.channel_id.community_id.id

    if channel_id and not community_id:
        ch = env["community.hub.channel"].sudo().browse(int(channel_id)).exists()
        if ch and hasattr(ch, "community_id"):
            community_id = ch.community_id.id


    # body gốc
    body_main = (body_html or "").strip()

    # placeholder link (sẽ thay sau khi có msg.id)
    PLACEHOLDER = "__CH_OPEN_LINK__"
    body_with_placeholder = (
        Markup("""
            <p style="margin:0 0 8px 0">
              <a href="{url}" style="text-decoration:none;">➡️ Mở Community Hub</a>
            </p>
        """).format(url=PLACEHOLDER)
        + Markup(body_main)
    )

    if target and hasattr(target, "message_post"):
        try:
            # 1) post message để tạo mail.message + mail.notification
            msg = target.message_post(
                subject=subject or False,
                body=str(body_with_placeholder),
                author_id=author_pid,
                partner_ids=partner_ids,
                message_type="notification",
                subtype_xmlid="mail.mt_comment",
                email_layout_xmlid="mail.mail_notification_layout",
            )

            # 2) tạo open-link đi qua controller -> mark read -> redirect /web#...
            open_link = (
                "/community_hub/open"
                f"?message_id={msg.id}"
                f"&community_id={int(community_id or 0)}"
                f"&channel_id={int(channel_id or 0)}"
                f"&post_id={int(post_id or 0)}"
                f"&tab=posts"
            )

            # 3) update body để thay placeholder bằng link thật
            new_body = str(body_with_placeholder).replace(PLACEHOLDER, str(escape(open_link)))
            # msg.sudo().write({"body": new_body})
            msg.sudo().write({
                "body": new_body,
                "community_hub_open_url": open_link,  # <-- quan trọng
                "community_hub_skip_desktop": True,      # ✅ chặn desktop kiểu cũ
            })
            _send_browser_notify_via_bus(
                user_ids,
                title=subject,
                body_html=body_main,     # hoặc body_with_placeholder
                open_url=open_link,
            )
            return

        except Exception:
            _logger.exception("message_post failed, fallback to message_notify")

    # fallback
    env["mail.thread"].sudo().message_notify(
        partner_ids=partner_ids,
        subject=subject or False,
        body=str(body_with_placeholder).replace(PLACEHOLDER, "/web"),
        author_id=author_pid,
        model=False,
        res_id=False,
        email_layout_xmlid="mail.mail_notification_layout",
        mail_auto_delete=False,
    )
def _send_browser_notify_via_bus(user_ids, *, title, body_html, open_url):
    """Send a custom bus notification so frontend can create a Desktop Notification with correct onclick."""
    env = request.env
    Bus = env["bus.bus"].sudo()

    base_url = env["ir.config_parameter"].sudo().get_param("web.base.url", "")
    # dùng absolute URL cho chắc (Windows notification click mở đúng)
    full_url = (base_url.rstrip("/") + "/" + open_url.lstrip("/")) if base_url else open_url

    text = (html2plaintext(body_html or "") or "").strip()
    text = text[:180]  # ngắn thôi cho notification

    Users = env["res.users"].sudo().browse(list(set(int(u) for u in (user_ids or []) if u)))
    for u in Users:
        channel = f"community_hub_notify:{u.id}"
        payload = {
            "type": "community_hub_notify",
            "title": title or "Community Hub",
            "body": text or "Bạn có thông báo mới",
            "url": full_url,
        }
        Bus._sendone(channel, "notification", payload)

def _notify_members(
    community_id: int,
    payload: dict,
    exclude_user_id: int = None,
    inbox_subject: str = None,
    inbox_body_html: str = None,
    inbox_channel_id: int = None,
    inbox_post_id: int = None
):
    """
    exclude_user_id sẽ loại khỏi cả BUS notify lẫn Inbox notify (tránh tự notify).
    """
    Member = request.env["community.hub.member"].sudo()
    members = Member.search([
        ("community_id", "=", int(community_id)),
        ("state", "in", ["joined", "invited"]),
    ])
    uids_all = set(members.mapped("user_id").ids)

    for uid in uids_all:
        if exclude_user_id and int(uid) == int(exclude_user_id):
            continue
        _notify_user(uid, payload)

    uids_inbox = set(uids_all)
    if exclude_user_id:
        uids_inbox.discard(int(exclude_user_id))

    if inbox_subject and inbox_body_html and uids_inbox:
        _notify_discuss_inbox_users(
            list(uids_inbox),
            subject=inbox_subject,
            body_html=inbox_body_html,
            community_id=community_id,
            channel_id=inbox_channel_id,
            post_id=inbox_post_id,
        )


# =========================================================
# SERIALIZERS
# =========================================================
def _community_to_dict(c, my_member=None):
    return {
        "id": c.id,
        "name": c.name,
        "owner_id": c.owner_id.id if c.owner_id else False,
        "join_policy": c.join_policy,
        "is_public": bool(getattr(c, "is_public", False)),
        "description_html": c.description_html or "",
        "my_role": my_member.role if my_member else None,
        "my_state": my_member.state if my_member else None,
    }


def _channel_to_dict(ch):
    return {"id": ch.id, "name": ch.name, "community_id": ch.community_id.id, "sequence": ch.sequence}


def _reaction_summary(post_id=None, comment_id=None, limit_users=20):
    Reaction = request.env["community.hub.reaction"].sudo()

    dom = []
    if post_id:
        dom += [("post_id", "=", int(post_id))]
    else:
        dom += [("post_id", "=", False)]
    if comment_id:
        dom += [("comment_id", "=", int(comment_id))]
    else:
        dom += [("comment_id", "=", False)]

    recs = Reaction.search(dom, order="id asc")
    me_uid = request.env.user.id

    summary = {}
    for r in recs:
        e = (r.emoji or "").strip()
        if not e:
            continue

        d = summary.setdefault(e, {"count": 0, "me": False, "users": [], "more": 0})
        d["count"] += 1

        if r.user_id.id == me_uid:
            d["me"] = True

        # collect names (limit to avoid payload too big)
        if len(d["users"]) < int(limit_users or 20):
            d["users"].append({"id": r.user_id.id, "name": r.user_id.name})
        else:
            d["more"] += 1

    # return stable list
    return [{
        "emoji": emoji,
        "count": d["count"],
        "me": d["me"],
        "users": d["users"],   # [{id,name},...]
        "more": d["more"],     # number of extra users not included
    } for emoji, d in summary.items()]

def _post_to_dict(p):
    if "attachment_ids" in p._fields:
        atts = [_serialize_attachment(a) for a in p.attachment_ids]
    else:
        atts = _attachments_for("community.hub.post", p.id)

    return {
        "id": p.id,
        "community_id": p.community_id.id,
        "channel_id": p.channel_id.id,
        "author_id": p.author_id.id if p.author_id else False,
        "author_name": p.author_id.name if p.author_id else "",
        "create_uid": p.create_uid.id if getattr(p, "create_uid", False) else False,
        "body_html": p.body_html or "",
        "create_date": _dt_to_str(p.create_date),  # ✅ JSON-safe
        "attachments": atts,
        "reactions": _reaction_summary(post_id=p.id),
    }


def _comment_to_dict(c):
    if "attachment_ids" in c._fields:
        atts = [_serialize_attachment(a) for a in c.attachment_ids]
    else:
        atts = _attachments_for("community.hub.comment", c.id)

    community_id = c.community_id.id if "community_id" in c._fields else c.post_id.community_id.id

    return {
        "id": c.id,
        "post_id": c.post_id.id,
        "community_id": community_id,
        "author_id": c.author_id.id if getattr(c, "author_id", False) else False,
        "author_name": c.author_id.name if getattr(c, "author_id", False) else "",
        "create_uid": c.create_uid.id if getattr(c, "create_uid", False) else False,
        "body_html": c.body_html or "",
        "create_date": _dt_to_str(c.create_date),  # ✅ JSON-safe
        "attachments": atts,
        "reactions": _reaction_summary(comment_id=c.id),
    }


# =========================================================
# CONTROLLER
# =========================================================
class CommunityHubController(http.Controller):

    # ---------------- BOOTSTRAP ----------------
    @http.route("/community_hub/api/bootstrap", type="json", auth="user")
    def bootstrap(self):
        user = request.env.user
        Member = request.env["community.hub.member"].sudo()

        my_members = Member.search([
            ("user_id", "=", user.id),
            ("state", "in", ["joined", "invited"]),
        ])

        communities = my_members.mapped("community_id").sorted(key=lambda x: (x.id), reverse=True)
        selected = communities[:1]
        selected = selected[0] if selected else None

        sel_member = my_members.filtered(lambda m: m.community_id.id == selected.id)[:1] if selected else Member.browse([])

        channels = request.env["community.hub.channel"].sudo().search(
            [("community_id", "=", selected.id)] if (selected and sel_member and sel_member.state == "joined") else [],
            order="sequence,id",
        )

        def _my_member_for(c):
            return my_members.filtered(lambda m: m.community_id.id == c.id)[:1]
        unread = _unread_counts_for_user(user.id)
        return {
            "user": {"id": user.id, "name": user.name, "login": user.login},
            "communities": [_community_to_dict(c, _my_member_for(c)) for c in communities],
            "selected": _community_to_dict(selected, _my_member_for(selected)) if selected else None,
            "channels": [_channel_to_dict(ch) for ch in channels],
            "unread":unread,
        }

    # ---------------- COMMUNITY CRUD ----------------
    @http.route("/community_hub/api/community/create", type="json", auth="user")
    def create_community(self, name=None, joinPolicy="invite", isPublic=False, descriptionHtml=None, **kw):
        if isinstance(name, dict):
            data = name
            name = data.get("name")
            joinPolicy = data.get("joinPolicy", joinPolicy)
            isPublic = data.get("isPublic", isPublic)
            descriptionHtml = data.get("descriptionHtml", descriptionHtml)

        name = (name or "").strip()
        if not name:
            raise ValidationError(_("Community name is required."))

        user = request.env.user
        Community = request.env["community.hub"].sudo()
        Member = request.env["community.hub.member"].sudo()
        Channel = request.env["community.hub.channel"].sudo()

        c = Community.create({
            "name": name,
            "owner_id": user.id,
            "join_policy": joinPolicy or "invite",
            "is_public": bool(isPublic),
            "description_html": descriptionHtml or False,
        })

        m = Member.search([("community_id", "=", c.id), ("user_id", "=", user.id)], limit=1)
        vals = {"role": "owner", "state": "joined", "invited_by": user.id}
        if m:
            m.write(vals)
        else:
            Member.create({"community_id": c.id, "user_id": user.id, **vals})

        if not Channel.search([("community_id", "=", c.id)], limit=1):
            Channel.create({"community_id": c.id, "name": "General", "sequence": 10})

        _notify_user(user.id, {"type": "bootstrap_reload"})
        return {"community": _community_to_dict(c, _get_member(c.id, user.id))}

    @http.route("/community_hub/api/community/update", type="json", auth="user")
    def update_community(self, communityId=None, vals=None, **kw):
        if isinstance(communityId, dict):
            data = communityId
            communityId = data.get("communityId") or data.get("community_id")
            vals = data.get("vals") or vals

        communityId = int(communityId or 0)
        if not communityId:
            raise ValidationError(_("communityId is required."))
        _ensure_manage(communityId)

        allowed = {"name", "join_policy", "is_public", "description_html"}
        clean = {k: v for k, v in (vals or {}).items() if k in allowed}

        request.env["community.hub"].sudo().browse(communityId).write(clean)
        _notify_community(communityId, {"type": "community_updated", "community_id": communityId})
        return {"ok": True}

    @http.route("/community_hub/api/community/<int:community_id>/join", type="json", auth="user")
    def join(self, community_id):
        community_id = int(community_id)
        community = request.env["community.hub"].sudo().browse(community_id)
        if not community.exists():
            raise ValidationError(_("Community not found."))

        user = request.env.user
        Member = request.env["community.hub.member"].sudo()

        m = Member.search([("community_id", "=", community_id), ("user_id", "=", user.id)], limit=1)

        if community.join_policy == "invite":
            if not m or m.state != "invited":
                raise AccessError(_("You are not invited to this community."))

        if not m:
            Member.create({
                "community_id": community_id,
                "user_id": user.id,
                "role": "member",
                "state": "joined",
                "invited_by": user.id,
            })
        else:
            m.write({"state": "joined"})

        _notify_user(user.id, {"type": "bootstrap_reload"})
        _notify_community(community_id, {"type": "members_changed", "community_id": community_id})
        return {"ok": True}

    # ---------------- CHANNELS ----------------
    @http.route("/community_hub/api/community/<int:community_id>/channels", type="json", auth="user")
    def channels(self, community_id):
        _ensure_joined(community_id)
        chs = request.env["community.hub.channel"].sudo().search(
            [("community_id", "=", int(community_id))],
            order="sequence,id",
        )
        return {"items": [_channel_to_dict(ch) for ch in chs]}

    @http.route("/community_hub/api/channel/create", type="json", auth="user")
    def create_channel(self, communityId=None, name=None, sequence=10, **kw):
        if isinstance(communityId, dict):
            data = communityId
            communityId = data.get("communityId") or data.get("community_id")
            name = data.get("name") or name
            sequence = data.get("sequence", sequence)
        else:
            if not communityId and ("communityId" in kw or "community_id" in kw):
                communityId = kw.get("communityId") or kw.get("community_id")
            if not name and "name" in kw:
                name = kw.get("name")
            if "sequence" in kw:
                sequence = kw.get("sequence", sequence)

        communityId = int(communityId or 0)
        if not communityId:
            raise ValidationError(_("communityId is required."))
        _ensure_manage(communityId)

        name = (name or "").strip()
        if not name:
            raise ValidationError(_("Channel name is required."))

        ch = request.env["community.hub.channel"].sudo().create({
            "community_id": communityId,
            "name": name,
            "sequence": int(sequence or 10),
        })
        _notify_community(communityId, {"type": "channel_created", "community_id": communityId, "channel_id": ch.id})
        return {"channel": _channel_to_dict(ch)}

    @http.route("/community_hub/api/channel/update", type="json", auth="user")
    def update_channel(self, channelId=None, vals=None, **kw):
        if isinstance(channelId, dict):
            data = channelId
            channelId = data.get("channelId") or data.get("channel_id")
            vals = data.get("vals") or vals

        channelId = int(channelId or 0)
        if not channelId:
            raise ValidationError(_("channelId is required."))

        ch = request.env["community.hub.channel"].sudo().browse(channelId)
        if not ch.exists():
            raise ValidationError(_("Channel not found."))

        _ensure_manage(ch.community_id.id)

        allowed = {"name", "sequence"}
        clean = {k: v for k, v in (vals or {}).items() if k in allowed}
        ch.write(clean)

        _notify_community(ch.community_id.id, {"type": "channel_updated", "community_id": ch.community_id.id, "channel_id": ch.id})
        return {"ok": True}

    @http.route("/community_hub/api/channel/delete", type="json", auth="user")
    def delete_channel(self, channelId=None, **kw):
        if isinstance(channelId, dict):
            data = channelId
            channelId = data.get("channelId") or data.get("channel_id")

        channelId = int(channelId or 0)
        if not channelId:
            return {"ok": True}

        ch = request.env["community.hub.channel"].sudo().browse(channelId)
        if not ch.exists():
            return {"ok": True}

        _ensure_manage(ch.community_id.id)
        cid = ch.community_id.id
        ch.unlink()

        _notify_community(cid, {"type": "channel_deleted", "community_id": cid, "channel_id": channelId})
        return {"ok": True}

    # ---------------- FEED ----------------
    @http.route("/community_hub/api/channel/<int:channel_id>/feed", type="json", auth="user")
    def feed(self, channel_id, limit=20, offset=0):
        channel_id = int(channel_id)
        ch = request.env["community.hub.channel"].sudo().browse(channel_id)
        if not ch.exists():
            raise ValidationError(_("Channel not found."))
        _ensure_joined(ch.community_id.id)

        Post = request.env["community.hub.post"].sudo()
        posts = Post.search(
            [("channel_id", "=", channel_id)],
            order="create_date desc, id desc",
            limit=int(limit or 20),
            offset=int(offset or 0),
        )
        total = Post.search_count([("channel_id", "=", channel_id)])
        has_more = (int(offset or 0) + len(posts)) < total
        return {"items": [_post_to_dict(p) for p in posts], "has_more": has_more}

    @http.route("/community_hub/api/channel/feed", type="json", auth="user")
    def feed_alias(self, channelId=None, limit=20, offset=0, **kw):
        if isinstance(channelId, dict):
            data = channelId
            channelId = data.get("channelId") or data.get("channel_id")
            limit = data.get("limit", limit)
            offset = data.get("offset", offset)
        channelId = int(channelId or 0)
        if not channelId:
            raise ValidationError(_("channelId is required."))
        return self.feed(channelId, limit=limit, offset=offset)

    # ---------------- POSTS ----------------
    @http.route("/community_hub/api/post/create", type="json", auth="user")
    def create_post(self, channelId=None, bodyHtml=None, attachmentIds=None, **kw):
        if isinstance(channelId, dict):
            data = channelId
            channelId = data.get("channelId") or data.get("channel_id")
            bodyHtml = data.get("bodyHtml") or data.get("body_html") or bodyHtml
            attachmentIds = data.get("attachmentIds") or data.get("attachment_ids") or attachmentIds

        channelId = int(channelId or 0)
        if not channelId:
            raise ValidationError(_("channelId is required."))

        ch = request.env["community.hub.channel"].sudo().browse(channelId)
        if not ch.exists():
            raise ValidationError(_("Channel not found."))

        _ensure_joined(ch.community_id.id)

        bodyHtml = (bodyHtml or "").strip()
        if not bodyHtml and not _to_int_list(attachmentIds):
            raise ValidationError(_("Post content is required."))

        # ✅ KHÔNG sudo khi create để create_uid đúng user
        Post = request.env["community.hub.post"]

        vals = {
            "community_id": ch.community_id.id,
            "channel_id": ch.id,
            "author_id": request.env.user.id,
            "body_html": bodyHtml or "<p></p>",
        }
        post = Post.create(vals)

        moved_ids = _relocate_attachments(attachmentIds, "community.hub.post", post.id)
        if moved_ids and "attachment_ids" in Post._fields:
            post.sudo().write({"attachment_ids": [(6, 0, moved_ids)]})

        # ❌ BỎ realtime feed notify community
        _set_channel_read(request.env.user.id, ch.id, post.id)

        # Inbox notify (tuỳ bạn giữ)
        actor = request.env.user
        subject = f"[Community Hub] Bài viết mới • {ch.community_id.name}"
        body = f"""<p><b>{actor.name}</b> vừa đăng bài mới trong <b>{ch.community_id.name}</b> • kênh <b>{ch.name}</b>.</p>"""
        _notify_members(
            ch.community_id.id,
            payload={
                "type": "notify_post",
                "community_id": ch.community_id.id,
                "community_name": ch.community_id.name,
                "channel_id": ch.id,
                "channel_name": ch.name,
                "post_id": post.id,
                "actor_id": actor.id,
                "actor_name": actor.name,
            },
            exclude_user_id=actor.id,
            inbox_subject=subject,
            inbox_body_html=body,
            inbox_channel_id=ch.id,
            inbox_post_id=post.id,
        )

        return {"post": _post_to_dict(post.sudo())}

    # ---------------- COMMENTS LIST ----------------
    @http.route("/community_hub/api/post/<int:post_id>/comments", type="json", auth="user")
    def comments(self, post_id, limit=50, offset=0, **kw):
        post_id = int(post_id)
        post = request.env["community.hub.post"].sudo().browse(post_id)
        if not post.exists():
            raise ValidationError(_("Post not found."))
        _ensure_joined(post.community_id.id)

        Comment = request.env["community.hub.comment"].sudo()
        items = Comment.search(
            [("post_id", "=", post_id)],
            order="create_date asc, id asc",
            limit=int(limit or 50),
            offset=int(offset or 0),
        )
        total = Comment.search_count([("post_id", "=", post_id)])
        has_more = (int(offset or 0) + len(items)) < total

        return {"items": [_comment_to_dict(c) for c in items], "has_more": has_more}

    # =========================================================
    # UPLOAD ATTACHMENTS (multipart)
    #   POST /community_hub/api/attachment/upload   (csrf=False)
    # =========================================================
    @http.route("/community_hub/api/attachment/upload", type="http", auth="user", methods=["POST"], csrf=False)
    def api_upload_attachments(self, **kw):
        """
        Params form:
          - community_id (required)
          - channel_id (optional)  -> upload cho POST
          - post_id (optional)     -> upload cho COMMENT (gắn theo post)
          - files (multiple)
        Return: {"items":[{id,name,mimetype,size,ext,create_date,open_url,download_url,thumb_url}]}
        """
        community_id = int(request.params.get("community_id") or request.params.get("communityId") or 0)
        channel_id = int(request.params.get("channel_id") or request.params.get("channelId") or 0)
        post_id = int(request.params.get("post_id") or request.params.get("postId") or 0)

        if not community_id:
            return request.make_response(
                json.dumps({"error": "Missing community_id"}),
                headers=[("Content-Type", "application/json")],
                status=400,
            )

        # check joined
        Member = request.env["community.hub.member"].sudo()
        me_member = Member.search([
            ("community_id", "=", community_id),
            ("user_id", "=", request.env.user.id),
            ("state", "=", "joined"),
        ], limit=1)
        if not me_member:
            return request.make_response(
                json.dumps({"error": "Not a joined member"}),
                headers=[("Content-Type", "application/json")],
                status=403,
            )

        if channel_id:
            ch = request.env["community.hub.channel"].sudo().browse(channel_id).exists()
            if not ch or ch.community_id.id != community_id:
                return request.make_response(
                    json.dumps({"error": "Invalid channel_id"}),
                    headers=[("Content-Type", "application/json")],
                    status=400,
                )

        if post_id:
            post = request.env["community.hub.post"].sudo().browse(post_id).exists()
            if not post or post.community_id.id != community_id:
                return request.make_response(
                    json.dumps({"error": "Invalid post_id"}),
                    headers=[("Content-Type", "application/json")],
                    status=400,
                )

        files = request.httprequest.files.getlist("files") or request.httprequest.files.getlist("ufile")
        if not files:
            return request.make_response(
                json.dumps({"items": []}),
                headers=[("Content-Type", "application/json")],
                status=200,
            )

        # ✅ không sudo để create_uid là user thật
        Attachment = request.env["ir.attachment"]
        items = []
        user = request.env.user

        for f in files:
            raw = f.read() or b""
            datas = base64.b64encode(raw)

            att = Attachment.create({
                "name": f.filename,
                "datas": datas,
                "mimetype": f.mimetype or "application/octet-stream",
                # draft: gắn tạm vào user
                "res_model": "res.users",
                "res_id": user.id,
            })

            open_url = f"/web/content/{att.id}?download=false"
            download_url = f"/web/content/{att.id}?download=true"

            items.append({
                "id": att.id,
                "name": f.filename,
                "mimetype": att.mimetype,
                "size": len(raw),
                "ext": _ext_from_name(f.filename),
                "create_date": _dt_to_str(att.create_date),  # ✅ timeline
                "open_url": open_url,
                "download_url": download_url,
                "thumb_url": open_url if _is_image_mimetype(att.mimetype) else "",
                "kind": "image" if _is_image_mimetype(att.mimetype) else "file",
            })

        return request.make_response(
            json.dumps({"items": items}),
            headers=[("Content-Type", "application/json")],
            status=200,
        )

    @http.route("/community_hub/upload_attachments", type="http", auth="user", methods=["POST"], csrf=False)
    def upload_attachments_compat(self, **kw):
        return self.api_upload_attachments(**kw)

    # =========================================================
    # DELETE ATTACHMENT
    # =========================================================
    @http.route("/community_hub/api/attachment/delete", type="json", auth="user", methods=["POST"])
    def api_delete_attachment(self, attachmentId=None, attachment_id=None, **kw):
        aid = attachmentId or attachment_id or (kw.get("attachmentId") or kw.get("attachment_id"))
        _delete_attachment(aid)
        return {"ok": True}

    # =========================================================
    # CREATE COMMENT
    # =========================================================
    @http.route("/community_hub/api/comment/create", type="json", auth="user", methods=["POST"])
    def create_comment(self, **kw):
        post_id = int(kw.get("postId") or kw.get("post_id") or 0)
        body_html = (kw.get("bodyHtml") or kw.get("body_html") or "").strip()
        attachment_ids = kw.get("attachmentIds") or kw.get("attachment_ids") or []

        if not post_id:
            raise ValidationError(_("Missing postId"))

        post = request.env["community.hub.post"].sudo().browse(post_id).exists()
        if not post:
            raise ValidationError(_("Post not found."))

        _ensure_joined(post.community_id.id)

        if not body_html and not _to_int_list(attachment_ids):
            raise ValidationError(_("Empty comment"))

        # ✅ KHÔNG sudo khi create để create_uid đúng user
        Comment = request.env["community.hub.comment"]

        vals = {"post_id": post.id, "body_html": body_html or "<p></p>"}
        if "author_id" in Comment._fields:
            vals["author_id"] = request.env.user.id
        if "community_id" in Comment._fields:
            vals["community_id"] = post.community_id.id
        if "channel_id" in Comment._fields:
            vals["channel_id"] = post.channel_id.id

        comment = Comment.create(vals)

        moved_ids = _relocate_attachments(attachment_ids, "community.hub.comment", comment.id)
        if moved_ids and "attachment_ids" in Comment._fields:
            comment.sudo().write({"attachment_ids": [(6, 0, moved_ids)]})

        # ❌ BỎ realtime feed notify community

        actor = request.env.user
        _notify_members(
            post.community_id.id,
            payload={
                "type": "notify_comment",
                "community_id": post.community_id.id,
                "community_name": post.community_id.name,
                "channel_id": post.channel_id.id,
                "channel_name": post.channel_id.name,
                "post_id": post.id,
                "comment_id": comment.id,
                "actor_id": actor.id,
                "actor_name": actor.name,
            },
            exclude_user_id=actor.id,
            inbox_subject=f"[Community Hub] Bình luận mới • {post.community_id.name}",
            inbox_body_html=f"<p><b>{actor.name}</b> vừa bình luận trong <b>{post.community_id.name}</b>.</p>",
            inbox_channel_id=post.channel_id.id,
            inbox_post_id=post.id,
        )

        return {"ok": True, "comment": _comment_to_dict(comment.sudo())}

    # ---------------- REACTIONS ----------------
    @http.route("/community_hub/api/reaction/toggle", type="json", auth="user")
    def toggle_reaction(self, communityId=None, emoji=None, postId=None, commentId=None, **kw):
        if isinstance(communityId, dict):
            data = communityId
            communityId = data.get("communityId") or data.get("community_id") or communityId
            emoji = data.get("emoji") or emoji
            postId = data.get("postId") or data.get("post_id") or postId
            commentId = data.get("commentId") or data.get("comment_id") or commentId
        else:
            # fallback nếu FE gửi qua kw
            if not communityId:
                communityId = kw.get("communityId") or kw.get("community_id")
            if not postId:
                postId = kw.get("postId") or kw.get("post_id")
            if not commentId:
                commentId = kw.get("commentId") or kw.get("comment_id")
            if not emoji:
                emoji = kw.get("emoji")

        communityId = int(communityId or 0)
        if not communityId:
            raise ValidationError(_("communityId is required."))

        _ensure_joined(communityId)

        emoji = (emoji or "").strip()
        if not emoji:
            raise ValidationError(_("Emoji is required."))

        postId = int(postId) if postId else False
        commentId = int(commentId) if commentId else False
        if not postId and not commentId:
            raise ValidationError(_("postId or commentId is required."))

        # (khuyến nghị) validate post/comment thuộc đúng community
        if postId:
            post = request.env["community.hub.post"].sudo().browse(postId).exists()
            if not post or post.community_id.id != communityId:
                raise ValidationError(_("Invalid postId"))
        if commentId:
            c = request.env["community.hub.comment"].sudo().browse(commentId).exists()
            cid = c.community_id.id if (c and "community_id" in c._fields) else (c.post_id.community_id.id if c else 0)
            if not c or cid != communityId:
                raise ValidationError(_("Invalid commentId"))

        Reaction = request.env["community.hub.reaction"].sudo()
        dom = [
            ("community_id", "=", communityId),
            ("user_id", "=", request.env.user.id),
            ("emoji", "=", emoji),
            ("post_id", "=", postId or False),
            ("comment_id", "=", commentId or False),
        ]
        r = Reaction.search(dom, limit=1)
        if r:
            r.unlink()
        else:
            Reaction.create({
                "community_id": communityId,
                "user_id": request.env.user.id,
                "emoji": emoji,
                "post_id": postId or False,
                "comment_id": commentId or False,
            })

        # ✅ trả về summary để FE update ngay
        # cuối toggle_reaction (sau create/unlink)
        return {
            "ok": True,
            "post_id": postId or False,
            "comment_id": commentId or False,
            "reactions": _reaction_summary(post_id=postId) if postId else _reaction_summary(comment_id=commentId),
        }


    # ---------------- MEMBERS ----------------
    @http.route("/community_hub/api/community/<int:community_id>/members", type="json", auth="user")
    def members(self, community_id):
        _ensure_access_community(community_id)

        members = request.env["community.hub.member"].sudo().search([
            ("community_id", "=", int(community_id)),
            ("state", "in", ["joined", "invited"]),
        ], order="role desc, id asc")

        return {
            "items": [{
                "id": m.id,
                "user_id": m.user_id.id,
                "name": m.user_id.name,
                "login": m.user_id.login,
                "role": m.role,
                "state": m.state,
            } for m in members]
        }

    @http.route("/community_hub/api/community/<int:community_id>/users/search", type="json", auth="user")
    def search_users(self, community_id, q=None, limit=10):
        _ensure_manage(community_id)

        q = (q or "").strip()
        if not q:
            return {"items": []}

        existing = request.env["community.hub.member"].sudo().search([
            ("community_id", "=", int(community_id)),
            ("state", "in", ["joined", "invited"]),
        ]).mapped("user_id").ids

        Users = request.env["res.users"].sudo()
        dom = ["|", ("name", "ilike", q), ("login", "ilike", q)]
        if existing:
            dom = ["&", ("id", "not in", existing)] + dom

        users = Users.search(dom, limit=int(limit or 10))
        return {"items": [{"id": u.id, "name": u.name, "login": u.login} for u in users]}

    @http.route("/community_hub/api/community/<int:community_id>/members/invite", type="json", auth="user")
    def invite(self, community_id, userIds=None):
        _ensure_manage(community_id)
        community_id = int(community_id)

        userIds = [int(x) for x in (userIds or [])]
        if not userIds:
            return {"ok": True}

        Community = request.env["community.hub"].sudo().browse(community_id)
        community_name = Community.name

        Member = request.env["community.hub.member"].sudo()
        for uid in userIds:
            m = Member.search([("community_id", "=", community_id), ("user_id", "=", uid)], limit=1)
            if m:
                m.write({"state": "invited", "role": "member", "invited_by": request.env.user.id})
            else:
                Member.create({
                    "community_id": community_id,
                    "user_id": uid,
                    "role": "member",
                    "state": "invited",
                    "invited_by": request.env.user.id,
                })

            _notify_user(uid, {
                "type": "invited",
                "community_id": community_id,
                "community_name": community_name,
                "invited_by": request.env.user.id,
                "invited_by_name": request.env.user.name,
            })

            subject = f"[Community Hub] Bạn được mời vào: {community_name}"
            body = f"<p>Bạn được <b>{request.env.user.name}</b> mời vào community <b>{community_name}</b>.</p>"
            _notify_discuss_inbox_users([uid], subject=subject, body_html=body, community_id=community_id)

        _notify_community(community_id, {"type": "members_changed", "community_id": community_id})
        return {"ok": True}

    @http.route("/community_hub/api/community/<int:community_id>/members/kick", type="json", auth="user")
    def kick(self, community_id, userId=None, **kw):
        _ensure_manage(community_id)
        community_id = int(community_id)
        userId = int(userId or 0)
        if not userId:
            raise ValidationError(_("userId is required."))

        Member = request.env["community.hub.member"].sudo()
        m = Member.search([("community_id", "=", community_id), ("user_id", "=", userId)], limit=1)
        if not m:
            return {"ok": True}

        if m.role == "owner":
            raise AccessError(_("Cannot kick owner."))

        m.unlink()

        _notify_user(userId, {"type": "kicked", "community_id": community_id})
        _notify_community(community_id, {"type": "members_changed", "community_id": community_id})
        return {"ok": True}

    @http.route("/community_hub/api/community/<int:community_id>/members/role", type="json", auth="user")
    def set_role(self, community_id, userId=None, role=None, **kw):
        _ensure_owner(community_id)
        community_id = int(community_id)
        userId = int(userId or 0)
        role = (role or "").strip()

        if role not in ("owner", "admin", "member"):
            raise ValidationError(_("Invalid role."))

        Member = request.env["community.hub.member"].sudo()
        m = Member.search([("community_id", "=", community_id), ("user_id", "=", userId)], limit=1)
        if not m or m.state != "joined":
            raise AccessError(_("User is not a joined member."))

        if m.role == "owner" and role != "owner":
            owners = Member.search_count([
                ("community_id", "=", community_id),
                ("role", "=", "owner"),
                ("state", "=", "joined")
            ])
            if owners <= 1:
                raise AccessError(_("You must keep at least one owner."))

        m.write({"role": role})
        _notify_community(community_id, {"type": "members_changed", "community_id": community_id})
        return {"ok": True}

    # ---------------- POSTS: UPDATE / DELETE ----------------
    @http.route("/community_hub/api/post/update", type="json", auth="user", methods=["POST"])
    def update_post(self, postId=None, bodyHtml=None, attachmentIds=None, **kw):
        if isinstance(postId, dict):
            data = postId
            postId = data.get("postId") or data.get("post_id")
            bodyHtml = data.get("bodyHtml") or data.get("body_html") or bodyHtml
            attachmentIds = data.get("attachmentIds") or data.get("attachment_ids") or attachmentIds

        postId = int(postId or 0)
        if not postId:
            raise ValidationError(_("postId is required."))

        Post = request.env["community.hub.post"].sudo()
        post = Post.browse(postId).exists()
        if not post:
            raise ValidationError(_("Post not found."))

        _ensure_joined(post.community_id.id)

        if not _is_creator_uid(post.create_uid.id):
            raise AccessError(_("You cannot edit this post."))

        bodyHtml = (bodyHtml or "").strip()
        moved_ids = _relocate_attachments(attachmentIds, "community.hub.post", post.id)

        has_old_atts = bool(_attachments_for("community.hub.post", post.id))
        if not bodyHtml and not moved_ids and not has_old_atts:
            raise ValidationError(_("Post content is required."))

        post.write({"body_html": bodyHtml or "<p></p>"})
        if moved_ids and "attachment_ids" in Post._fields:
            post.write({"attachment_ids": [(6, 0, list(set(post.attachment_ids.ids + moved_ids)))]})

        # ❌ bỏ realtime
        return {"ok": True, "post": _post_to_dict(post)}

    @http.route("/community_hub/api/post/delete", type="json", auth="user", methods=["POST"])
    def delete_post(self, postId=None, **kw):
        if isinstance(postId, dict):
            data = postId
            postId = data.get("postId") or data.get("post_id")

        postId = int(postId or 0)
        if not postId:
            return {"ok": True}

        Post = request.env["community.hub.post"].sudo()
        post = Post.browse(postId).exists()
        if not post:
            return {"ok": True}

        _ensure_joined(post.community_id.id)

        if not _is_creator_uid(post.create_uid.id):
            raise AccessError(_("You cannot delete this post."))

        # delete comments + reactions
        Comment = request.env["community.hub.comment"].sudo()
        comments = Comment.search([("post_id", "=", post.id)])
        comment_ids = comments.ids

        # delete reactions for post + comments
        Reaction = request.env["community.hub.reaction"].sudo()
        dom = ["|", ("post_id", "=", post.id), ("comment_id", "in", comment_ids)] if comment_ids else [("post_id", "=", post.id)]
        Reaction.search(dom).unlink()

        # cleanup attachments: post + comments (xoá hết để tránh orphan)
        _cleanup_attachments_any("community.hub.post", [post.id])
        if comment_ids:
            _cleanup_attachments_any("community.hub.comment", comment_ids)

        comments.unlink()
        post.unlink()

        # ❌ bỏ realtime
        return {"ok": True}

    # ---------------- COMMENTS: UPDATE / DELETE ----------------
    @http.route("/community_hub/api/comment/update", type="json", auth="user", methods=["POST"])
    def update_comment(self, commentId=None, bodyHtml=None, attachmentIds=None, **kw):
        if isinstance(commentId, dict):
            data = commentId
            commentId = data.get("commentId") or data.get("comment_id")
            bodyHtml = data.get("bodyHtml") or data.get("body_html") or bodyHtml
            attachmentIds = data.get("attachmentIds") or data.get("attachment_ids") or attachmentIds

        commentId = int(commentId or 0)
        if not commentId:
            raise ValidationError(_("commentId is required."))

        Comment = request.env["community.hub.comment"].sudo()
        c = Comment.browse(commentId).exists()
        if not c:
            raise ValidationError(_("Comment not found."))

        community_id = c.community_id.id if "community_id" in c._fields else c.post_id.community_id.id
        _ensure_joined(community_id)

        if not _is_creator_uid(c.create_uid.id):
            raise AccessError(_("You cannot edit this comment."))

        bodyHtml = (bodyHtml or "").strip()
        moved_ids = _relocate_attachments(attachmentIds, "community.hub.comment", c.id)

        has_old_atts = bool(_attachments_for("community.hub.comment", c.id))
        if not bodyHtml and not moved_ids and not has_old_atts:
            raise ValidationError(_("Empty comment"))

        c.write({"body_html": bodyHtml or "<p></p>"})
        if moved_ids and "attachment_ids" in Comment._fields:
            c.write({"attachment_ids": [(6, 0, list(set(c.attachment_ids.ids + moved_ids)))]})

        # ❌ bỏ realtime
        return {"ok": True, "comment": _comment_to_dict(c)}

    @http.route("/community_hub/api/comment/delete", type="json", auth="user", methods=["POST"])
    def delete_comment(self, commentId=None, **kw):
        if isinstance(commentId, dict):
            data = commentId
            commentId = data.get("commentId") or data.get("comment_id")

        commentId = int(commentId or 0)
        if not commentId:
            return {"ok": True}

        Comment = request.env["community.hub.comment"].sudo()
        c = Comment.browse(commentId).exists()
        if not c:
            return {"ok": True}

        community_id = c.community_id.id if "community_id" in c._fields else c.post_id.community_id.id
        _ensure_joined(community_id)

        if not _is_creator_uid(c.create_uid.id):
            raise AccessError(_("You cannot delete this comment."))

        request.env["community.hub.reaction"].sudo().search([("comment_id", "=", c.id)]).unlink()

        # cleanup attachments comment (xoá hết để tránh orphan)
        _cleanup_attachments_any("community.hub.comment", [c.id])

        c.unlink()

        # ❌ bỏ realtime
        return {"ok": True}

    # =========================================================
    # MEDIA / FILES / PHOTOS (for timeline)
    #   Frontend sẽ group theo create_date -> "Ngày dd Tháng mm"
    # =========================================================
    def _media_collect_for_channel(self, channel_id: int, limit=500):
        channel_id = int(channel_id)
        ch = request.env["community.hub.channel"].sudo().browse(channel_id).exists()
        if not ch:
            raise ValidationError(_("Channel not found."))
        _ensure_joined(ch.community_id.id)

        # lấy posts trong channel
        Post = request.env["community.hub.post"].sudo()
        post_ids = Post.search([("channel_id", "=", channel_id)], order="id desc", limit=int(limit or 500)).ids

        # lấy comments thuộc các post đó
        Comment = request.env["community.hub.comment"].sudo()
        comment_ids = Comment.search([("post_id", "in", post_ids)], order="id desc", limit=int(limit or 2000)).ids if post_ids else []

        # lấy attachments theo res_model/res_id
        Att = request.env["ir.attachment"].sudo()
        dom = []
        if post_ids:
            dom = ["|", "&", ("res_model", "=", "community.hub.post"), ("res_id", "in", post_ids),
                        "&", ("res_model", "=", "community.hub.comment"), ("res_id", "in", comment_ids)]
        elif comment_ids:
            dom = [("res_model", "=", "community.hub.comment"), ("res_id", "in", comment_ids)]
        else:
            return {"items": [], "photos": [], "files": []}

        atts = Att.search(dom, order="create_date desc, id desc")
        items = [_serialize_attachment(a) for a in atts]

        photos = [x for x in items if x.get("kind") == "image"]
        files = [x for x in items if x.get("kind") != "image"]

        return {"items": items, "photos": photos, "files": files}

    @http.route("/community_hub/api/channel/<int:channel_id>/media", type="json", auth="user")
    def channel_media(self, channel_id, limit=500):
        return self._media_collect_for_channel(channel_id, limit=limit)

    @http.route("/community_hub/api/community/<int:community_id>/media", type="json", auth="user")
    def community_media(self, community_id, limit=800):
        # gom tất cả channel trong community
        community_id = int(community_id)
        _ensure_joined(community_id)

        Channel = request.env["community.hub.channel"].sudo()
        ch_ids = Channel.search([("community_id", "=", community_id)], order="sequence,id").ids

        Post = request.env["community.hub.post"].sudo()
        post_ids = Post.search([("community_id", "=", community_id)], order="id desc", limit=int(limit or 800)).ids
        Comment = request.env["community.hub.comment"].sudo()
        comment_ids = Comment.search([("post_id", "in", post_ids)], order="id desc", limit=4000).ids if post_ids else []

        Att = request.env["ir.attachment"].sudo()
        dom = []
        if post_ids:
            dom = ["|", "&", ("res_model", "=", "community.hub.post"), ("res_id", "in", post_ids),
                        "&", ("res_model", "=", "community.hub.comment"), ("res_id", "in", comment_ids)]
        elif comment_ids:
            dom = [("res_model", "=", "community.hub.comment"), ("res_id", "in", comment_ids)]
        else:
            return {"items": [], "photos": [], "files": []}

        atts = Att.search(dom, order="create_date desc, id desc")
        items = [_serialize_attachment(a) for a in atts]

        photos = [x for x in items if x.get("kind") == "image"]
        files = [x for x in items if x.get("kind") != "image"]

        return {"items": items, "photos": photos, "files": files}
    @http.route("/community_hub/api/unread", type="json", auth="user")
    def unread(self, communityId=None, communityIds=None, **kw):
        if isinstance(communityId, dict):
            data = communityId
            communityId = data.get("communityId") or data.get("community_id")
            communityIds = data.get("communityIds") or data.get("community_ids")

        if communityId:
            cids = [int(communityId)]
        else:
            cids = _to_int_list(communityIds)

        data = _unread_counts_for_user(request.env.user.id, community_ids=cids or None)
        return {"unread": data}
    @http.route("/community_hub/api/channel/mark_read", type="json", auth="user", methods=["POST"])
    def mark_channel_read(self, channelId=None, lastPostId=None, **kw):
        if isinstance(channelId, dict):
            data = channelId
            channelId = data.get("channelId") or data.get("channel_id")
            lastPostId = data.get("lastPostId") or data.get("last_post_id") or lastPostId

        channelId = int(channelId or 0)
        if not channelId:
            raise ValidationError(_("channelId is required."))

        ch = request.env["community.hub.channel"].sudo().browse(channelId).exists()
        if not ch:
            raise ValidationError(_("Channel not found."))

        _ensure_joined(ch.community_id.id)

        # nếu client không gửi lastPostId thì lấy post mới nhất
        Post = request.env["community.hub.post"].sudo()
        if not lastPostId:
            latest = Post.search([("channel_id", "=", channelId)], order="id desc", limit=1)
            lastPostId = latest.id if latest else False
        else:
            lastPostId = int(lastPostId)

        Read = request.env["community.hub.channel.read"].sudo()
        uid = request.env.user.id
        r = Read.search([("channel_id", "=", channelId), ("user_id", "=", uid)], limit=1)

        vals = {
            "community_id": ch.community_id.id,
            "channel_id": channelId,
            "user_id": uid,
            "last_read_post_id": lastPostId or False,
            "last_read_at": fields.Datetime.now(),
        }
        if r:
            # chỉ tăng, không giảm
            if r.last_read_post_id and lastPostId and r.last_read_post_id.id > lastPostId:
                vals["last_read_post_id"] = r.last_read_post_id.id
            r.write(vals)
        else:
            Read.create(vals)

        # trả lại unread mới cho community hiện tại (để update badge ngay)
        unread = _unread_counts_for_user(uid, community_ids=[ch.community_id.id])
        return {"ok": True, "unread": unread}
    @http.route("/community_hub/open", type="http", auth="user", website=False)
    def community_hub_open(self, message_id=None, community_id=0, channel_id=0, post_id=0, tab="posts", **kw):
        # mark as read (tuỳ bạn)
        if message_id:
            mid = int(message_id)
            pid = request.env.user.partner_id.id
            notif = request.env["mail.notification"].sudo().search([
                ("mail_message_id", "=", mid),
                ("res_partner_id", "=", pid),
            ])
            if notif:
                notif.write({"is_read": True})

        # QUAN TRỌNG: redirect ra /web#... (hash)
        return request.redirect(
            _hub_dashboard_url(
                community_id=int(community_id or 0),
                channel_id=int(channel_id or 0),
                post_id=int(post_id or 0),
                tab=tab or "posts",
            )
        )
    @http.route("/community_hub/hub_url_from_record", type="json", auth="user")
    def hub_url_from_record(self, res_model=None, res_id=None):
        try:
            if not res_model or not res_id:
                return {"ok": False}

            res_id = int(res_id)
            if res_model not in ("community.hub.post", "community.hub.channel", "community.hub"):
                return {"ok": False}

            rec = request.env[res_model].browse(res_id).exists()
            if not rec:
                return {"ok": False}

            community_id = None
            channel_id = None
            post_id = None

            if res_model == "community.hub.post":
                post_id = rec.id
                channel_id = rec.channel_id.id if hasattr(rec, "channel_id") and rec.channel_id else None
                community_id = rec.community_id.id if hasattr(rec, "community_id") and rec.community_id else None
                if not community_id and channel_id:
                    # fallback nếu post không có community_id trực tiếp
                    try:
                        community_id = rec.channel_id.community_id.id
                    except Exception:
                        pass

            elif res_model == "community.hub.channel":
                channel_id = rec.id
                community_id = rec.community_id.id if hasattr(rec, "community_id") and rec.community_id else None

            elif res_model == "community.hub":
                community_id = rec.id

            url = _hub_dashboard_url(
                community_id=community_id,
                channel_id=channel_id,
                post_id=post_id,
                tab="posts",
            )
            return {"ok": True, "url": url}

        except AccessError:
            return {"ok": False}
        except Exception:
            _logger.exception("hub_url_from_record failed")
            return {"ok": False}