from odoo import fields, models


class CrmLead(models.Model):
    _inherit = "crm.lead"

    hosting_contact_id = fields.Many2one(
        "hosting.contact",
        string="Hosting Contact",
        index=True,
        copy=False,
    )
    hosting_remote_id = fields.Char(
        string="Hosting Remote ID",
        index=True,
        copy=False,
    )
    hosting_product = fields.Char(
        string="Sản phẩm quan tâm",
        copy=False,
    )
    hosting_message = fields.Text(
        string="Nội dung từ hosting",
        copy=False,
    )