# -*- coding: utf-8 -*-
import mimetypes
import os
import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)

class DocumentFile(models.Model):
    _name = 'smd.document.file'
    _description = 'Document File'
    _rec_name = 'name'

    # ============================================================
    # FIELDS
    # ============================================================
    name = fields.Char('File Title', required=True)
    file_name = fields.Char('File Name')
    file_data = fields.Binary('File Data', attachment=False, required=True)
    mimetype = fields.Char('MIME Type')
    attachment_id = fields.Many2one('ir.attachment', string='Attachment', ondelete='cascade')
    preview_html = fields.Html('Preview', compute='_compute_preview_html', sanitize=False)

    workspace_id = fields.Many2one('smd.document.workspace', string='Workspace')
    owner_id = fields.Many2one('res.users', string='Owner', default=lambda self: self.env.user)
    access_type = fields.Selection([
        ('private', 'Private'),
        ('team', 'Team'),
        ('public', 'Public'),
    ], string='Access Type', default='team')

    note = fields.Text('Description / Notes')

    # ============================================================
    # CREATE / WRITE / DELETE
    # ============================================================
    @api.model
    def create(self, vals):
        rec = super().create(vals)
        if vals.get('file_data') and not self.env.context.get('bypass_sync'):
            rec._sync_attachment()
        return rec

    def write(self, vals):
        res = super().write(vals)
        if ('file_data' in vals or 'name' in vals or 'file_name' in vals) and not self.env.context.get('bypass_sync'):
            for rec in self:
                rec._sync_attachment()
        return res


    def unlink(self):
        self.mapped('attachment_id').unlink()
        return super().unlink()

    # ============================================================
    # ATTACHMENT SYNC (không còn recursion)
    # ============================================================
    def _sync_attachment(self):
        """Tạo hoặc cập nhật ir.attachment, tránh vòng lặp recursion."""
        self.ensure_one()
        if not self.file_data:
            return

        # Ngăn đệ quy
        if self.env.context.get('bypass_sync'):
            return

        fname = (self.file_name or self.name or 'file').strip()
        name_root, ext = os.path.splitext(fname)
        mt = self.mimetype or mimetypes.guess_type(fname)[0] or 'application/octet-stream'
        if not ext or len(ext) <= 1:
            guessed_ext = mimetypes.guess_extension(mt)
            fname = name_root + (guessed_ext or '.bin')

        vals = {
            'name': fname,
            'datas': self.file_data,
            'mimetype': mt,
            'res_model': self._name,
            'res_id': self.id,
            'public': self.access_type == 'public',
        }

        # Ghi dưới context bypass để không kích hoạt lại write()
        if self.attachment_id:
            self.attachment_id.with_context(bypass_sync=True).sudo().write(vals)
        else:
            att = self.env['ir.attachment'].with_context(bypass_sync=True).sudo().create(vals)
            self.with_context(bypass_sync=True).sudo().write({
                'attachment_id': att.id,
                'file_name': fname,
                'mimetype': mt,
            })


    # ============================================================
    # PREVIEW (Không tự gọi sync để tránh recursion)
    # ============================================================
    def _compute_preview_html(self):
        """Sinh HTML preview cho form view"""
        for rec in self:
            html = "<span style='color:gray'>Không có file.</span>"
            if not rec.attachment_id:
                rec.preview_html = html
                continue

            att_id = rec.attachment_id.id
            mt = rec.mimetype or ''
            if 'image' in mt:
                html = f'<img src="/web/content/{att_id}" width="400" style="border:1px solid #ccc; border-radius:8px;">'
            elif 'pdf' in mt:
                html = f'<iframe src="/web/content/{att_id}" width="100%" height="600" frameborder="0"></iframe>'
            elif 'video' in mt:
                html = f'<video src="/web/content/{att_id}" width="100%" height="400" controls="controls"></video>'
            elif 'audio' in mt:
                html = f'<audio src="/web/content/{att_id}" controls="controls" style="width:100%"></audio>'
            else:
                html = (
                    f"<div style='color:gray'>"
                    f"Không có preview cho định dạng này.<br/>"
                    f"<a href='/web/content/{att_id}?download=true' target='_blank'>Tải xuống file</a>"
                    f"</div>"
                )
            rec.preview_html = html

    # ============================================================
    # ACTION
    # ============================================================
    def open_file(self):
        self.ensure_one()
        if not self.attachment_id:
            return False
        return {
            'type': 'ir.actions.act_url',
            'url': f"/web/content/{self.attachment_id.id}?download=true",
            'target': 'new',
        }
