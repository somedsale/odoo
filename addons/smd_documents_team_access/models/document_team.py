from odoo import models, fields

class DocumentTeam(models.Model):
    _name = 'smd.document.team'
    _description = 'Document Team'

    name = fields.Char('Team Name', required=True)
    leader_id = fields.Many2one('res.users', string='Leader', required=True)
    member_ids = fields.Many2many('res.users', string='Members')
    description = fields.Text('Description')

    workspace_ids = fields.Many2many(
        'smd.document.workspace',
        'smd_workspace_team_rel',
        'team_id',
        'workspace_id',
        string='Accessible Workspaces'
    )
