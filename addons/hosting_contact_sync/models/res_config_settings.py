from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    hosting_contact_api_url = fields.Char(
        string="Hosting Contact API URL",
        config_parameter="hosting_contact_sync.api_url",
    )
    hosting_contact_api_token = fields.Char(
        string="Hosting Contact API Token",
        config_parameter="hosting_contact_sync.api_token",
    )
    hosting_contact_api_timeout = fields.Integer(
        string="Timeout (seconds)",
        config_parameter="hosting_contact_sync.api_timeout",
        default=20,
    )
    # hosting_contact_auto_create_lead = fields.Boolean(
    #     string="Tự tạo lead sau khi lấy dữ liệu",
    #     config_parameter="hosting_contact_sync.auto_create_lead",
    #     default=True,
    # )
    hosting_contact_verify_ssl = fields.Boolean(
        string="Verify SSL",
        config_parameter="hosting_contact_sync.verify_ssl",
        default=True,
    )
    hosting_contact_receive_token = fields.Char(
        string="Website -> Odoo Receive Token",
        config_parameter="hosting_contact_sync.receive_token",
    )