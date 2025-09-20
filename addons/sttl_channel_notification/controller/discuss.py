from odoo import http
from odoo.http import request
from markupsafe import Markup

class DiscussController(http.Controller):
    @http.route('/mail/get_channels', methods=['POST'], type='json', auth='public', csrf=False)
    def mail_get_channels(self, channels, body, model, record):
        record_name = request.env[model].browse(record).name
        base_url = request.env.company.get_base_url()
        url = f"{base_url}/web#id={record}&model={model}&view_type=form"
        link_element = f" <span style='font-weight: bold;'>on</span> <a target='new' href='{url}'>{record_name}</a>"
        body += link_element

        channel_ids = request.env['discuss.channel'].search([('id', 'in', channels)])      
        for channel_id in channel_ids:
            channel_id.message_post(
                body=Markup(body),
                message_type='comment', 
                subtype_xmlid="mail.mt_comment"
            )
        return channels
