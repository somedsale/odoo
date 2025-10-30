from odoo import models, fields

class DocumentWorkspace(models.Model):
    _name = 'smd.document.workspace'
    _description = 'Document Workspace'

    name = fields.Char('Workspace Name', required=True)
    parent_id = fields.Many2one('smd.document.workspace', string='Parent Workspace')
    child_ids = fields.One2many('smd.document.workspace', 'parent_id', string='Sub Workspaces')
    team_ids = fields.Many2many(
        'smd.document.team',
        'smd_workspace_team_rel',
        'workspace_id',
        'team_id',
        string='Teams Allowed'
    )
    description = fields.Text('Description')
    document_ids = fields.One2many('smd.document.file', 'workspace_id', string='Documents')
