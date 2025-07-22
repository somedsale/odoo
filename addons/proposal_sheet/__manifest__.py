{
    'name': 'Proposal Sheet',
    'version': '1.0',
    'category': 'Project',
    'summary': 'Quản lý phiếu đề xuất vật tư/chi phí từ nhiệm vụ',
    'depends': ['project', 'product', 'project_material', 'cost_estimate','uom', 'mail'],
    'data': [
        'security/security.xml',
        'security/proposal_rule.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'report/report_proposal_sheet_pdf.xml',          # file khai báo <report>
        'report/report_proposal_sheet_template.xml',     # file chứa QWeb template
        'views/proposal_reject_wizard_views.xml',
        'views/proposal_sheet_views.xml',
        'views/task_inherit_view.xml',
        'views/project_task_form_inherit_show_team_lead.xml',
        'views/project_task_estimate_material_views.xml',
    ],
    'installable': True,
    'application': True,
}
