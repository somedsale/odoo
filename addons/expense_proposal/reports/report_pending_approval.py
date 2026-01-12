from odoo import api, models, fields


class ReportPendingApproval(models.AbstractModel):
    _name = 'report.expense_proposal.report_pending_approval'
    _description = 'QWeb Report: Pending Approval Expense Proposals'

    @api.model
    def _get_report_values(self, docids, data=None):

        sheets = self.env['proposal.sheet'].search([
            ('type', 'in', ['other', 'expense']),
            ('state', '=', 'approved'),
        ])

        today = fields.Date.context_today(self)

        groups = {
            'employee': [],
            'office': [],
            'project': [],
            'estimated_cost': [],
            'fixed_cost': [],
            'irregular_expenses': [],
        }
        totals = {k: 0.0 for k in groups.keys()}
        idx = {k: 0 for k in groups.keys()}

        def _get_amount(line):
            if hasattr(line, 'amount'):
                return line.amount or 0.0
            if hasattr(line, 'price_total'):
                return line.price_total or 0.0
            return 0.0

        def _payload(line, stt):
            # Đối tượng / NCC
            obj = ''
            if getattr(line, 'object', False):
                obj = line.object.name or ''
            elif getattr(line, 'vendor_id', False):
                obj = line.vendor_id.display_name or ''
            elif getattr(line, 'partner_id', False):
                obj = line.partner_id.display_name or ''

            # Nội dung
            name = ''
            if getattr(line, 'content', False):
                name = line.content or ''
            elif getattr(line, 'expense_id', False):
                name = line.expense_id.display_name or ''
            elif getattr(line, 'name', False):
                name = line.name or ''

            sheet = getattr(line, 'sheet_id', False)
            project = sheet.project_id.display_name if sheet and sheet.project_id else ''

            note = getattr(line, 'note', '') or ''
            date = getattr(line, 'date', False) or (sheet.date_proposal if sheet else False) or (sheet.create_date.date() if sheet and sheet.create_date else False)

            return {
                'stt': stt,
                'object': obj,
                'name': name,
                'amount': _get_amount(line),
                'project': project,
                'note': note,
                'date': date,
            }

        def _add(cls, line):
            if cls not in totals:
                return
            idx[cls] += 1
            data = _payload(line, idx[cls])
            totals[cls] += data['amount']
            groups[cls].append(data)

        # ====== LOOP THẲNG (KHÔNG KIND) ======
        for s in sheets:
            # 1) Dòng OTHER: phân loại theo cost_classification
            for l in s.expense_noproject_line_ids:
                cls = l.cost_classification or ''
                _add(cls, l)

            # 2) Dòng EXPENSE: cho vào nhóm PROJECT (như bạn đang muốn)
            for l in s.expense_line_ids:
                _add('project', l)

        lists = [{
            'total_employee': totals['employee'],
            'total_office': totals['office'],
            'total_project': totals['project'],
            'total_estimated': totals['estimated_cost'],
            'total_fixed': totals['fixed_cost'],
            'total_irregular': totals['irregular_expenses'],

            'line_employee': groups['employee'],
            'line_office': groups['office'],
            'line_project': groups['project'],
            'line_estimated': groups['estimated_cost'],
            'line_fixed': groups['fixed_cost'],
            'line_irregular': groups['irregular_expenses'],
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
