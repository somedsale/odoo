from odoo import models, fields, api
from odoo.exceptions import UserError
from markupsafe import Markup

class ExpenseProposal(models.Model):
    _name = 'expense.proposal'
    _description = 'Đề xuất chi phí'
    _inherit = ['mail.thread', 'mail.activity.mixin']  # Kế thừa để hỗ trợ theo dõi và thông báo

    name = fields.Char(string='Phiếu đề xuất', readonly=True, default=lambda self: self.env['ir.sequence'].next_by_code('expense.proposal'))
    date = fields.Date(string='Ngày đề xuất', default=fields.Date.today, required=True)
    proposer_id = fields.Many2one('res.users', string='Người đề xuất', default=lambda self: self.env.user, required=True)
    amount = fields.Float(string='Tổng số tiền đề xuất', required=True, compute='_compute_amount', readonly=True)
    expense_proposal_lines = fields.One2many('expense.proposal.line', 'expense_proposal_id', string='Chi tiết')
    payment_request_count = fields.Integer(string="Số phiếu chi", compute='_compute_payment_request_count')
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('submitted', 'Gửi duyệt'),
        ('approved', 'Đã duyệt'),
        ('posted', 'Tạo phiếu chi'),
        ('completed', 'Hoàn tất',),
        ('rejected', 'Từ chối'),
    ], string='Status', default='draft', track_visibility='onchange')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    director_user_id = fields.Many2one('res.users', string="Giám Đốc", default=lambda self: self._default_director_user(), readonly=True)
    @api.model
    def _default_director_user(self):
        group = self.env.ref('custom_director_role.group_director')  # đổi lại module ID cho đúng
        users = self.env['res.users'].search([('groups_id', 'in', group.id)], limit=1)
        return users.id if users else False
    def _send_notification(self, message, partner_ids=None):
        """
        Gửi thông báo vào Chatter + Discuss.
        :param message: Nội dung thông báo (HTML)
        :param partner_ids: Danh sách partner_id nhận thông báo (list[int])
        """
        self.ensure_one()

        if not partner_ids:
            partner_ids = []

        # Xóa follower cũ (nếu cần thiết, có thể bỏ nếu không muốn mất lịch sử)
        # self.message_follower_ids.sudo().unlink()

        # Thêm follower mới
        existing_followers = self.message_partner_ids.ids
        new_partners = [pid for pid in partner_ids if pid not in existing_followers]
        if new_partners:
            self.message_subscribe(partner_ids=new_partners)
        odoodbot_partner = self.env.ref("base.partner_root")

        # Gửi vào chatter + discuss
        self.message_post(
            body=Markup(message),
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
            partner_ids=partner_ids,
            author_id=odoodbot_partner.id,
        )
    def action_submit(self):
        for rec in self:
            if not rec.expense_proposal_lines:
                raise UserError("❌ Phiếu chưa có dòng chi phí nào. Vui lòng thêm ít nhất một dòng trước khi gửi duyệt.")
            invalid_lines = rec.expense_proposal_lines.filtered(lambda l: l.amount <= 0)
            if invalid_lines:
                raise UserError("❌ Có dòng chi phí có số tiền = 0. Vui lòng kiểm tra lại trước khi gửi duyệt.")
            if rec.amount <= 0:
                raise UserError("❌ Không thể gửi duyệt vì tổng số tiền bằng 0.")
        # ✅ Check các dòng chi tiết
            rec.write({'state': 'submitted'})
            if rec.director_user_id and rec.director_user_id.partner_id:
                rec._send_notification(
                    f"📌 Phiếu <b>{rec.name}</b> đã được gửi duyệt và đang chờ Giám đốc xác nhận.",
                    [rec.director_user_id.partner_id.id],  # ✅ fix: lấy partner_id
                )

    def action_approve(self):
        for rec in self:
            rec.write({'state': 'approved'})
            partner_ids = []

            # Người tạo phiếu
            if rec.proposer_id.partner_id:
                partner_ids.append(rec.proposer_id.partner_id.id)

            # Nhóm kế toán
            group_account = self.env.ref("account.group_account_user", raise_if_not_found=False)
            if group_account:
                partner_ids += group_account.users.mapped("partner_id").ids

            if partner_ids:
                rec._send_notification(
                    f"✅ Phiếu <b>{rec.name}</b> đã được Giám đốc duyệt.",
                    partner_ids,
                )



    def action_reject(self):
        self.write({'state': 'rejected'})

    def action_open_reject_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'expense.proposal.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_id': self.id,
            }
        }

    def action_post(self):
        for rec in self:
            if rec.state not in ['approved']:
                raise UserError("Chỉ tạo phiếu chi khi phiếu đề xuất đã được xác nhận/duyệt.")

            if not rec.expense_proposal_lines:
                raise UserError("Không có dòng chi nào để tạo phiếu chi.")

            vals_list = []
            for line in rec.expense_proposal_lines:
                if not line.amount or line.amount <= 0:
                    continue  # bỏ qua dòng 0đ

                vals = {
                    'name': '/',  # sequence sẽ tự cấp trong create()
                    'expense_proposal_id': rec.id,
                    'expense_proposal_line_id': line.id,
                    'proposal_person_id': rec.proposer_id.id,
                    'total': line.amount,
                    'date': line.date or rec.date,
                    'note': line.content,
                    'project_id': line.project_id.id if line.project_id else False,
                    'cost_classification': line.cost_classification,
                    'expense_category_id': line.expense_category_id.id if line.expense_category_id else False,
                    'currency_id': rec.env.company.currency_id.id,
                    'scheduled_date': line.date or rec.date,
                    'payment_type': 'cash',  # hoặc suy từ dòng
                    'state': 'draft',     # hoặc 'draft' nếu muốn kế toán duyệt tiếp
                }
                vals_list.append(vals)

            if not vals_list:
                raise UserError("Tất cả các dòng đều không hợp lệ (số tiền trống/0).")

            prs = self.env['account.payment.request'].create(vals_list)

            # Update each line with the created payment request ID
            for line, pr in zip(rec.expense_proposal_lines, prs):
                if line.amount and line.amount > 0:
                    line.payment_request_id = pr.id

            # Create chatter message with links to payment requests
            # pr_links = '<br>'.join(
            #     f'<a href="#" data-oe-model="account.payment.request" data-oe-id="{pr.id}">{pr.name}</a>'
            #     for pr in prs
            # )
            # rec.message_post(
            #     body=f"Đã tạo {len(prs)} phiếu chi từ Phiếu đề xuất {rec.name}:<br>{pr_links}"
            # )

            self.state = 'completed'
            rec.write({'state': 'posted'})
    def action_draft(self):
        self.write({'state': 'draft'})
    @api.depends('expense_proposal_lines.amount')
    def _compute_amount(self):
        for proposal in self:
            proposal.amount = sum(line.amount for line in proposal.expense_proposal_lines)
    def _compute_payment_request_count(self):
        for rec in self:
            rec.payment_request_count = self.env['account.payment.request'].search_count([
                ('expense_proposal_id', '=', rec.id)
            ])
class ExpenseProposalLine(models.Model):
    _name = 'expense.proposal.line'
    _description = 'Expense Proposal Line'

    expense_proposal_id = fields.Many2one('expense.proposal', string='Expense Proposal')
    content = fields.Char(string='Nội dung chi', required=True)
    amount = fields.Float(string='Số tiền', required=True) 
    date = fields.Date(string='Ngày dự chi', default=fields.Date.today)
    project_id = fields.Many2one('project.project', string='Dự án')
    note = fields.Text(string='Ghi chú')
    object = fields.Many2one('res.partner', string='ĐỐI TƯỢNG/NCC')
    cost_classification = fields.Selection([
        ('employee', 'Khoản vay nội bộ(nhân viên)'),
        ('office', 'Chi phí tại công ty'),
        ('project', 'Chi phí các công trình'),
        ('estimated_cost', 'Chi phí dự kiến theo dự án'),
    ], string="Phân loại chi phí", default='employee',required=True)
    # NEW: Khoản mục
    expense_category_id = fields.Many2one(
        'expense.category', string="Khoản mục",
        domain="[('classification', '=', cost_classification)]",
        help="Chọn khoản mục chi tiết phù hợp với Phân loại chi phí."
    )
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    payment_request_id = fields.Many2one('account.payment.request', string='Phiếu Chi', readonly=True)

    def action_view_payment_request(self):
        self.ensure_one()
        if not self.payment_request_id:
            raise UserError("Không có phiếu chi liên kết với dòng này.")
        return {
            'name': 'Phiếu Chi',
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment.request',
            'view_mode': 'form',
            'res_id': self.payment_request_id.id,
            'target': 'current',
        }