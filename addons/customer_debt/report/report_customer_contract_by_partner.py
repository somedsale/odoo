# -*- coding: utf-8 -*-
from odoo import models, api
from collections import defaultdict
import datetime

CONTRACT_TYPE_ORDER = {
    'preparing': 0,
    'done': 1,
    'paused': 2,
    'bad_debt': 3,
}
CONTRACT_TYPE_LABELS = {
    'preparing': 'Công trình đang chuẩn bị thực hiện',
    'done':      'Đã hoàn thành',
    'paused':    'Tạm ngưng',
    'bad_debt':  'Công nợ khó đòi',
}


class ReportCustomerContractByPartner(models.AbstractModel):
    _name = 'report.customer_debt.customer_contract_by_partner_report'
    _description = 'Báo cáo chi tiết hợp đồng theo từng khách hàng'

    # ---------- Utils ----------
    def _fmt_date(self, d):
        if not d:
            return ''
        try:
            return d.strftime('%d/%m/%Y')
        except Exception:
            return str(d)

    def _safe_num(self, val):
        try:
            f = float(val)
            return f if abs(f) > 1e-9 else None
        except Exception:
            return None

    def _collect_settlement_info(self, contract):
        """Ghép chuỗi Số HS và Ngày HS quyết toán (an toàn field)."""
        nums, dts = [], []
        for s in getattr(contract, 'settlement_ids', []):
            num = getattr(s, 'number', False) or getattr(s, 'code', False) or getattr(s, 'name', False)
            if num:
                nums.append(str(num))
            dt = getattr(s, 'date', False) or getattr(s, 'settlement_date', False) or getattr(s, 'create_date', False)
            if dt:
                try:
                    dts.append(dt.strftime('%d/%m/%Y'))
                except Exception:
                    dts.append(str(dt))
        return (', '.join(nums) or '-', ', '.join(dts) or '-')

    # ---------- Build rows: Invoice -> Receipts (residual running per line) ----------
    def _build_rows_for_contract(self, contract):
        """
        Với mỗi HĐ:
          - Mỗi Hóa đơn in nhiều dòng (mỗi dòng 1 phiếu thu liên kết trực tiếp invoice_id).
          - Dòng đầu của Hóa đơn: có Ngày/Số/Số tiền hóa đơn + residual sau dòng (sau khi trừ phiếu thu ở dòng đó).
          - Các dòng phiếu thu tiếp theo: chỉ in cột Thu + residual, KHÔNG lặp lại cột hóa đơn.
          - Không có phiếu thu -> 1 dòng, residual = số tiền hóa đơn.
          - HSQT (Số/Ngày + Số tiền) chỉ in 1 lần ở Hóa đơn đầu tiên của HĐ.
          - **MỚI:** Phiếu thu không gắn hóa đơn (tạm ứng) vẫn hiển thị, residual âm lũy kế.
        """
        # HS quyết toán (in 1 lần/hợp đồng)
        sett_numbers, sett_dates = self._collect_settlement_info(contract)

        rows = []
        first_invoice_of_contract = True

        # Sắp xếp hóa đơn theo ngày + id
        invoices = contract.invoice_ids.sorted(
            key=lambda inv: (getattr(inv, 'date', False) or getattr(inv, 'invoice_date', False) or datetime.date.min, inv.id)
        )

        # === 1) In hóa đơn + phiếu thu gắn trực tiếp ===
        for inv in invoices:
            inv_date   = getattr(inv, 'date', False) or getattr(inv, 'invoice_date', False)
            inv_date_s = self._fmt_date(inv_date)
            inv_num_s  = getattr(inv, 'invoice_number', False) or getattr(inv, 'name', False) or getattr(inv, 'move_name', False) or ''
            inv_total  = float(getattr(inv, 'amount_total', 0.0) or 0.0)

            # Phiếu thu gắn trực tiếp hóa đơn này
            receipts = getattr(inv, 'account_receipt_ids', self.env['account.receipt'])
            receipts = receipts.sorted(key=lambda r: (getattr(r, 'date', False) or getattr(r, 'receipt_date', False) or datetime.date.min, r.id))

            residual_running = inv_total

            if receipts:
                for idx, r in enumerate(receipts):
                    r_date = getattr(r, 'date', False) or getattr(r, 'receipt_date', False) or getattr(r, 'payment_date', False)
                    r_amt  = float(getattr(r, 'amount', 0.0) or 0.0)

                    # residual sau dòng hiện tại
                    residual_running -= r_amt

                    rows.append({
                        'is_first_line_of_invoice': (idx == 0),

                        # Cột Hóa đơn (chỉ dòng đầu)
                        'invoice_date':   inv_date_s if idx == 0 else '',
                        'invoice_number': inv_num_s  if idx == 0 else '',
                        'invoice_amount': inv_total  if (idx == 0 and inv_total) else None,

                        # Cột Phiếu thu (dòng nào cũng có thể có)
                        'receipt_date':   self._fmt_date(r_date),
                        'receipt_amount': self._safe_num(r_amt),

                        # Cột Còn nợ sau dòng
                        'residual_after': residual_running,

                        # HSQT: in 1 lần ở hóa đơn đầu tiên của HĐ
                        'print_contract_columns': (idx == 0 and first_invoice_of_contract),
                        'sett_numbers': sett_numbers if (idx == 0 and first_invoice_of_contract) else '',
                        'sett_dates':   sett_dates   if (idx == 0 and first_invoice_of_contract) else '',
                    })
            else:
                # Không có phiếu thu -> 1 dòng
                rows.append({
                    'is_first_line_of_invoice': True,
                    'invoice_date':   inv_date_s,
                    'invoice_number': inv_num_s,
                    'invoice_amount': inv_total if inv_total else None,
                    'receipt_date':   '',
                    'receipt_amount': None,
                    'residual_after': inv_total if inv_total else None,
                    'print_contract_columns': first_invoice_of_contract,
                    'sett_numbers': sett_numbers if first_invoice_of_contract else '',
                    'sett_dates':   sett_dates   if first_invoice_of_contract else '',
                })

            first_invoice_of_contract = False

        # === 2) Thêm PHIẾU THU KHÔNG GẮN HÓA ĐƠN (tạm ứng) ===
        # Lấy tất cả phiếu thu thuộc hợp đồng nhưng không có invoice_id
        receipts_unlinked = contract.receipt_ids.filtered(lambda r: not getattr(r, 'invoice_id', False))
        receipts_unlinked = receipts_unlinked.sorted(
            key=lambda r: (getattr(r, 'date', False) or getattr(r, 'receipt_date', False) or datetime.date.min, r.id)
        )

        if receipts_unlinked:
            advance_running = 0.0  # lũy kế tạm ứng (âm)
            for idx, r in enumerate(receipts_unlinked):
                r_date = getattr(r, 'date', False) or getattr(r, 'receipt_date', False) or getattr(r, 'payment_date', False)
                r_amt  = float(getattr(r, 'amount', 0.0) or 0.0)
                advance_running += r_amt

                rows.append({
                    'is_first_line_of_invoice': False,

                    # Không có hóa đơn => để trống các cột hóa đơn
                    'invoice_date':   '',
                    'invoice_number': '',
                    'invoice_amount': None,

                    # Phiếu thu
                    'receipt_date':   self._fmt_date(r_date),
                    'receipt_amount': self._safe_num(r_amt),

                    # residual âm lũy kế (tạm ứng)
                    'residual_after': -advance_running,

                    # HSQT: nếu hợp đồng không có hóa đơn nào -> in 1 lần ở dòng đầu của tạm ứng
                    'print_contract_columns': (idx == 0 and len(invoices) == 0),
                    'sett_numbers': sett_numbers if (idx == 0 and len(invoices) == 0) else '',
                    'sett_dates':   sett_dates   if (idx == 0 and len(invoices) == 0) else '',
                })

        # Không có hóa đơn & cũng không có phiếu thu -> vẫn trả 1 dòng để hiện hợp đồng
        if not invoices and not receipts_unlinked:
            rows.append({
                'is_first_line_of_invoice': True,
                'invoice_date': '',
                'invoice_number': '',
                'invoice_amount': None,
                'receipt_date': '',
                'receipt_amount': None,
                'residual_after': None,
                'print_contract_columns': True,
                'sett_numbers': sett_numbers,
                'sett_dates':   sett_dates,
            })

        return rows

    # ---------- Build report ----------
    @api.model
    def _get_report_values(self, docids, data=None):
        partners = self.env['res.partner'].browse(docids)
        result = []

        for partner in partners:
            contracts = self.env['customer.contract'].search([('partner_id', '=', partner.id)])
            debt_summary = self.env['customer.debt.summary'].search([
                ('partner_id', '=', partner.id)
            ], limit=1)
            old_debt = debt_summary.old_debt if debt_summary else 0.0
            # === 1) Tổng hóa đơn, phiếu thu, dụng thư phiếu, với cơ sở tống hợp đồng ===
            grouped = defaultdict(list)

            for c in contracts:
                amount_final = sum(c.settlement_ids.mapped('amount_settlement')) or 0.0

                # Tổng theo hóa đơn ↔ phiếu thu (đúng, không cộng trùng theo dòng)
                amount_invoiced = sum(c.invoice_ids.mapped('amount_total')) or 0.0
                amount_paid = sum(
                    sum(float(getattr(r, 'amount', 0.0) or 0.0) for r in getattr(inv, 'account_receipt_ids', self.env['account.receipt']))
                    for inv in c.invoice_ids
                ) or 0.0
                # Cộng thêm các phiếu thu KHÔNG gắn hóa đơn (tạm ứng)
                amount_paid += sum(float(getattr(r, 'amount', 0.0) or 0.0)
                                   for r in c.receipt_ids.filtered(lambda x: not getattr(x, 'invoice_id', False))) or 0.0

                amount_due = amount_invoiced - amount_paid

                numbers_str, dates_str = self._collect_settlement_info(c)

                grouped[c.contract_type or 'preparing'].append({
                    'id': c.id,
                    'project': c.project_id,
                    'name': c.display_name or c.name,

                    'sett_numbers': numbers_str,
                    'sett_dates':   dates_str,

                    'amount_total': c.amount_total or 0.0,   # Giá trị HĐ
                    'amount_final': amount_final,            # HSQT Số tiền
                    'amount_invoiced': amount_invoiced,      # Hóa đơn: Số tiền
                    'amount_paid': amount_paid,              # Thu: Số tiền (kể cả tạm ứng)
                    'amount_due': amount_due,                # Còn nợ
                    'warranty_amount': c.warranty_amount or 0.0,
                    'warranty_period': f"{c.warranty_time or 0} tháng",

                    'rows': self._build_rows_for_contract(c),
                })

            # Sắp xếp & tổng
            group_keys_sorted = sorted(grouped.keys(), key=lambda k: CONTRACT_TYPE_ORDER.get(k, 999))
            group_blocks = []
            grand_totals = {
                'amount_total': 0.0, 'amount_final': 0.0,
                'amount_invoiced': 0.0, 'amount_paid': 0.0,
                'amount_due': 0.0, 'warranty_amount': 0.0,
            }
            for gkey in group_keys_sorted:
                items = sorted(grouped[gkey], key=lambda r: ((r['project'] and r['project'].name) or '', r['name'] or ''))
                gtot = {
                    'amount_total':     sum(x['amount_total']     for x in items),
                    'amount_final':     sum(x['amount_final']     for x in items),
                    'amount_invoiced':  sum(x['amount_invoiced']  for x in items),
                    'amount_paid':      sum(x['amount_paid']      for x in items),
                    'amount_due':       sum(x['amount_due']       for x in items),
                    'warranty_amount':  sum(x['warranty_amount']  for x in items),
                }
                for k in grand_totals.keys():
                    grand_totals[k] += gtot[k]
                group_blocks.append({
                    'key': gkey,
                    'label': CONTRACT_TYPE_LABELS.get(gkey, 'Khác'),
                    'items': items,
                    'totals': gtot,
                })

            result.append({
                'partner': partner,
                'groups': group_blocks,
                'grand_totals': grand_totals,
            })

        return {
            'doc_ids': partners.ids,
            'doc_model': 'res.partner',
            'partners_data': result,
            'res_company': self.env.company,
            'user_id': self.env.user,
            'datetime': datetime,
            'old_debt': old_debt,
            'residual_total': grand_totals['amount_due'] + old_debt,
        }
