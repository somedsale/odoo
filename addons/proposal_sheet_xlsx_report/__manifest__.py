{
    'name': 'Proposal Sheet XLSX Report',
    'version': '1.0',
    'summary': 'Export Proposal Sheet to Excel',
    'author': 'Your Name',
    'category': 'Custom',
    'depends': ['base', 'report_xlsx', 'proposal_sheet'],  # thay bằng module proposal sheet của bạn
    'data': [
        'views/proposal_sheet_report.xml',
    ],
    'installable': True,
    'application': False,
}
