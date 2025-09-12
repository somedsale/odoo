{
    'name': 'Project Profit & Loss Report',
    'version': '1.0',
    'summary': 'Báo cáo lời - lỗ theo từng công trình/dự án',
    'description': 'Tính toán doanh thu, chi phí và lợi nhuận cho từng dự án',
    'author': 'Duy Nguyen',
    'category': 'custom',
    'depends': ['project' ,'contract_management'],
    'data': [
        'security/ir.model.access.csv',
        'reports/project_profit_report_template.xml',
        'views/project_profit_report_menu_action.xml'
    ],
    'installable': True,
    'application': True,
}
