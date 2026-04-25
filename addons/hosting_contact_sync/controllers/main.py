import json
import logging

from odoo import http, fields
from odoo.http import request

_logger = logging.getLogger(__name__)


class HostingContactSyncController(http.Controller):

    @http.route('/hosting_contact_sync/receive', type='http', auth='public', methods=['GET', 'POST'], csrf=False)
    def receive_contact(self, **kwargs):
        try:
            if request.httprequest.method == 'GET':
                return request.make_response(
                    json.dumps({'success': True, 'message': 'route ok'}, ensure_ascii=False),
                    headers=[('Content-Type', 'application/json; charset=utf-8')],
                    status=200,
                )

            token = request.httprequest.headers.get('X-API-KEY')
            secret = request.env['ir.config_parameter'].sudo().get_param(
                'hosting_contact_sync.receive_token', ''
            )

            if not secret or token != secret:
                return request.make_response(
                    json.dumps({'success': False, 'message': 'Unauthorized'}, ensure_ascii=False),
                    headers=[('Content-Type', 'application/json; charset=utf-8')],
                    status=401,
                )

            data = json.loads(request.httprequest.get_data(as_text=True) or '{}')

            remote_id = str(data.get('remote_id') or '').strip()
            if not remote_id:
                return request.make_response(
                    json.dumps({'success': False, 'message': 'Thiếu remote_id'}, ensure_ascii=False),
                    headers=[('Content-Type', 'application/json; charset=utf-8')],
                    status=400,
                )

            created_at = data.get('created_at')
            remote_created_at = False
            if created_at:
                try:
                    remote_created_at = fields.Datetime.to_datetime(created_at)
                except Exception:
                    remote_created_at = False

            HostingContact = request.env['hosting.contact'].sudo()
            Lead = request.env['crm.lead'].sudo()
            ICP = request.env['ir.config_parameter'].sudo()

            vals = {
                'remote_id': remote_id,
                'title': (data.get('title') or '').strip(),
                'contact_name': (data.get('name') or '').strip(),
                'phone': (data.get('phone') or '').strip(),
                'email': (data.get('email') or '').strip(),
                'message': (data.get('message') or '').strip(),
                'product': (data.get('product') or '').strip(),
                'remote_created_at': remote_created_at,
                'last_fetch_at': fields.Datetime.now(),
                'raw_payload': json.dumps(data, ensure_ascii=False, indent=2),
                'sync_error': False,
            }

            rec = HostingContact.search([('remote_id', '=', remote_id)], limit=1)
            created = False

            if rec:
                rec.write(vals)
            else:
                rec = HostingContact.create(vals)
                created = True
                rec._post_new_contact_message()
                rec._notify_sale_users_new_contact()

            auto_create_lead = ICP.get_param('hosting_contact_sync.auto_create_lead', 'True') == 'True'

            if auto_create_lead:
                lead_name = rec.title or rec.product or rec.contact_name or 'Khách liên hệ từ website'
                description_parts = []
                if rec.product:
                    description_parts.append(f'Sản phẩm quan tâm: {rec.product}')
                if rec.message:
                    description_parts.append(f'Nội dung:\n{rec.message}')
                if rec.remote_id:
                    description_parts.append(f'Remote ID: {rec.remote_id}')

                lead_vals = {
                    'name': lead_name,
                    'contact_name': rec.contact_name or False,
                    'phone': rec.phone or False,
                    'email_from': rec.email or False,
                    'description': '\n\n'.join(description_parts),
                    'type': 'lead',
                    'hosting_contact_id': rec.id,
                    'hosting_remote_id': rec.remote_id,
                    'hosting_product': rec.product or rec.title or False,
                    'hosting_message': rec.message or False,
                }

                lead = rec.lead_id
                if not lead and rec.remote_id:
                    lead = Lead.search([('hosting_remote_id', '=', rec.remote_id)], limit=1)

                if lead:
                    lead.write(lead_vals)
                else:
                    lead = Lead.create(lead_vals)

                rec.write({
                    'lead_id': lead.id,
                    'sync_state': 'synced',
                    'sync_error': False,
                    'last_sync_at': fields.Datetime.now(),
                })

            return request.make_response(
                json.dumps({
                    'success': True,
                    'message': 'Đã nhận dữ liệu từ website',
                    'id': rec.id,
                    'created': created,
                    'lead_id': rec.lead_id.id if rec.lead_id else False,
                }, ensure_ascii=False),
                headers=[('Content-Type', 'application/json; charset=utf-8')],
                status=200,
            )

        except Exception as e:
            _logger.exception("Lỗi receive contact from website")
            return request.make_response(
                json.dumps({'success': False, 'message': str(e)}, ensure_ascii=False),
                headers=[('Content-Type', 'application/json; charset=utf-8')],
                status=500,
            )