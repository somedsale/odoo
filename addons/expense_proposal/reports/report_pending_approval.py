from odoo import api, models, fields

class ReportPendingApproval(models.AbstractModel):
    _name = 'report.expense_proposal.report_pending_approval'
    _description = 'QWeb Report: Pending Approval Expense Proposals'

    @api.model
    def _get_report_values(self, docids, data=None):

        # Lấy toàn bộ Phiếu Đề Xuất loại 'other' đã duyệt
        sheets = self.env['proposal.sheet'].search([
            ('type', '=', 'other'),
            ('state', '=', 'approved')
        ])

        today = fields.Date.context_today(self)

        # === DANH SÁCH NHÓM ===
        group_employee = []
        group_office = []
        group_project = []
        group_estimated = []
        group_fixed = []
        group_irregular = []

        totals = {
            'employee': 0.0,
            'office': 0.0,
            'project': 0.0,
            'estimated_cost': 0.0,
            'fixed_cost': 0.0,
            'irregular_expenses': 0.0,
        }

        def _payload(l, idx):
            return {
                'stt': idx,
                'object': l.object.name if l.object else '',
                'name': l.content or '',
                'amount': l.amount or 0.0,
                'project': l.sheet_id.project_id.display_name if l.sheet_id.project_id else '',
                'note': l.note or '',
                'date': l.date,
            }

        # Gom tất cả dòng chi phí ngoài công trình
        all_lines = sheets.mapped('expense_noproject_line_ids')

        # Bộ đếm STT
        idx = {
            'employee': 0,
            'office': 0,
            'project': 0,
            'estimated_cost': 0,
            'fixed_cost': 0,
            'irregular_expenses': 0,
        }

        # Phân loại dòng
        for l in all_lines:
            cls = l.cost_classification  # key: employee / office / project / estimated_cost ...
            if cls not in totals:
                continue

            idx[cls] += 1
            line = _payload(l, idx[cls])
            totals[cls] += l.amount

            if cls == 'employee':
                group_employee.append(line)
            elif cls == 'office':
                group_office.append(line)
            elif cls == 'project':
                group_project.append(line)
            elif cls == 'estimated_cost':
                group_estimated.append(line)
            elif cls == 'fixed_cost':
                group_fixed.append(line)
            elif cls == 'irregular_expenses':
                group_irregular.append(line)

        # TRẢ RA ĐÚNG KEY THEO XML
        lists = [{
            'total_employee': totals['employee'],
            'total_office': totals['office'],
            'total_project': totals['project'],
            'total_estimated': totals['estimated_cost'],
            'total_fixed': totals['fixed_cost'],
            'total_irregular': totals['irregular_expenses'],

            'line_employee': group_employee,
            'line_office': group_office,
            'line_project': group_project,
            'line_estimated': group_estimated,
            'line_fixed': group_fixed,
            'line_irregular': group_irregular,
        }]

        total = sum(totals.values())

        return {
            'doc_model': 'proposal.sheet',
            'docs': sheets,
            'lists': lists,
            'total': total,
            'today': today,
            'company': self.env.company,
        }
