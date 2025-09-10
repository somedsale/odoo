from odoo import api, models, fields

class ReportPendingApproval(models.AbstractModel):
    _name = 'report.expense_proposal.report_pending_approval'
    _description = 'QWeb Report: Pending Approval Expense Proposals'

    @api.model
    def _get_report_values(self, docids, data=None):
        proposals = self.env['expense.proposal'].search([('state', '=', 'submitted')])
        today =  fields.Date.context_today(self)

        lists = []
        total = 0
        for p in proposals:
            line_items_employee, line_items_office = [], []
            line_items_project, line_items_estimated_cost = [], []
            totals = {
                'employee': 0.0, 'office': 0.0, 'project': 0.0, 'estimated_cost': 0.0,
            }
            sel = dict(self.env['expense.proposal.line']._fields['cost_classification'].selection)

            def _line_payload(l, idx):
                # object: “Đối tượng/NCC” – tạm lấy theo khoản mục, fallback theo phân loại
                obj = l.object.name if l.object else ''
                return {
                    'stt': idx,
                    'object': obj or '',
                    'name': l.content or '',
                    'amount': l.amount or 0.0,
                    'project': l.project_id.display_name if l.project_id else '',
                    'note': l.note or '',
                    'date': l.date,
                }

            # gom nhóm + đánh số thứ tự theo từng nhóm
            idx_emp = idx_off = idx_prj = idx_est = 0
            for l in p.expense_proposal_lines:
                if not l.amount:
                    continue
                if l.cost_classification == 'employee':
                    idx_emp += 1
                    line_items_employee.append(_line_payload(l, idx_emp))
                    totals['employee'] += l.amount
                elif l.cost_classification == 'office':
                    idx_off += 1
                    line_items_office.append(_line_payload(l, idx_off))
                    totals['office'] += l.amount
                elif l.cost_classification == 'project':
                    idx_prj += 1
                    line_items_project.append(_line_payload(l, idx_prj))
                    totals['project'] += l.amount
                elif l.cost_classification == 'estimated_cost':
                    idx_est += 1
                    line_items_estimated_cost.append(_line_payload(l, idx_est))
                    totals['estimated_cost'] += l.amount
            total = total + sum(totals.values())
            lists.append({
                'total_amount_employee': totals['employee'],
                'total_amount_office': totals['office'],
                'total_amount_project': totals['project'],
                'total_amount_estimated_cost': totals['estimated_cost'],
                'line_items_employee': line_items_employee,
                'line_items_office': line_items_office,
                'line_items_project': line_items_project,
                'line_items_estimated_cost': line_items_estimated_cost,
            })

        return {
            'doc_model': 'expense.proposal',
            'docs': proposals,
            'lists': lists,
            'total': total,
            'today': today,
            'company': self.env.company,
        }
