from odoo import api, SUPERUSER_ID


def post_init_hook(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    payments = env['account.payment.request'].search([
        ('proposal_sheet_id', '!=', False)
    ])
    for payment in payments:
        if not payment.line_ids:
            env['account.payment.request.line'].create({
                'payment_request_id': payment.id,
                'proposal_sheet_id': payment.proposal_sheet_id.id,
                'amount': payment.total or payment.proposal_sheet_id.amount_total or 0.0,
            })