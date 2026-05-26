import base64
import io
import re
from datetime import datetime


from odoo import http, _
from odoo.exceptions import UserError
from odoo.http import request, content_disposition


def _to_text(value):
    if value is None:
        return ''
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _to_multiline_text(value):
    """Keep Excel technical specification text exactly enough for display.

    Excel cells may contain line breaks (Alt+Enter), CRLF, tabs and
    non-breaking spaces. For normal columns we still strip text, but for
    the technical note column we preserve internal new lines so OWL can
    render them with white-space: pre-wrap.
    """
    if value is None:
        return ''
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    text = str(value)
    text = text.replace('\r\n', '\n').replace('\r', '\n').replace('\xa0', ' ')
    # Trim each line, but keep line separation from Excel.
    lines = [line.strip() for line in text.split('\n')]
    # Remove only leading/trailing empty lines; keep intentional blank lines inside.
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return '\n'.join(lines)


def _append_multiline(base, extra):
    base = _to_multiline_text(base)
    extra = _to_multiline_text(extra)
    if not extra:
        return base
    if not base:
        return extra
    return base + '\n' + extra


def _to_float(value):
    if value in (None, ''):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return 0.0
    text = text.replace(' ', '').replace('\xa0', '')
    # 1.234.567,89 -> 1234567.89
    if ',' in text and '.' in text:
        text = text.replace('.', '').replace(',', '.')
    else:
        text = text.replace(',', '')
    try:
        return float(text)
    except Exception:
        return 0.0


def _is_group_code(code):
    code = _to_text(code)
    if not code:
        return False
    # I, II, III, I.1, I.2, A, A.1...
    return bool(re.match(r'^[A-ZIVX]+(\.\d+)*\.?$', code, flags=re.I))


def _is_roman_code(code):
    code = _to_text(code).upper().strip('.')
    return bool(code) and bool(re.match(r'^[IVXLCDM]+$', code))


def _is_alpha_level_code(code):
    code = _to_text(code).upper().strip('.')
    # A/B/C... thường là đầu mục cha cấp 1 trong BOQ.
    # Loại I/V/X vì các mã này hay được dùng cho đầu mục con dạng La Mã.
    return bool(re.match(r'^[A-Z]$', code)) and code not in {'I', 'V', 'X'}


def _is_material_code(code):
    code = _to_text(code)
    if not code:
        return False
    return bool(re.match(r'^\d+(\.\d+)*$', code))


def _read_workbook(filename, raw):
    filename_lower = (filename or '').lower()
    if filename_lower.endswith('.xls'):
        try:
            import xlrd
        except Exception as exc:
            raise UserError(_('Server chưa cài thư viện xlrd để đọc file .xls. Vui lòng chạy: pip3 install xlrd')) from exc
        book = xlrd.open_workbook(file_contents=raw)
        sheets = []
        for sheet in book.sheets():
            rows = []
            for r in range(sheet.nrows):
                rows.append([sheet.cell_value(r, c) for c in range(sheet.ncols)])
            sheets.append((sheet.name, rows))
        return sheets

    try:
        import openpyxl
    except Exception as exc:
        raise UserError(_('Server chưa cài thư viện openpyxl để đọc file .xlsx. Vui lòng chạy: pip3 install openpyxl')) from exc

    wb = openpyxl.load_workbook(io.BytesIO(raw), data_only=True)
    sheets = []
    for ws in wb.worksheets:
        rows = []
        for row in ws.iter_rows(values_only=True):
            rows.append(list(row))
        sheets.append((ws.title, rows))
    return sheets


def _normalize_header(value):
    text = _to_text(value).lower()
    text = text.replace('\n', ' ')
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _find_header_row(rows):
    keys = ['stt', 'tên vật tư', 'ten vat tu', 'tên hệ thống', 'ten he thong', 'đơn vị', 'don vi', 'khối lượng', 'khoi luong', 'đơn giá', 'don gia']
    best_idx = 0
    best_score = 0
    for idx, row in enumerate(rows[:40]):
        joined = ' '.join(_normalize_header(c) for c in row)
        score = sum(1 for k in keys if k in joined)
        if score > best_score:
            best_idx = idx
            best_score = score
        if score >= 3:
            return idx
    return best_idx


def _build_column_map(header_row):
    """Detect columns from the Excel header instead of assuming fixed positions.

    The user's files are mostly: STT, Tên vật tư, Đơn vị, Khối lượng, Đơn giá,
    Thành tiền, Ghi chú. Some sheets have slightly different titles, so this
    keeps the import stable.
    """
    result = {
        'stt': 0,
        'name': 1,
        'uom': 2,
        'qty': 3,
        'price': 4,
        'amount': 5,
        'note': 6,
    }
    for idx, value in enumerate(header_row or []):
        text = _normalize_header(value)
        if not text:
            continue
        if text == 'stt' or text.startswith('stt '):
            result['stt'] = idx
        elif 'tên vật tư' in text or 'ten vat tu' in text or 'tên hệ thống' in text or 'ten he thong' in text or 'tên thiết bị' in text:
            result['name'] = idx
        elif 'đơn vị' in text or 'don vi' in text or text in ('đvt', 'dvt'):
            result['uom'] = idx
        elif 'khối lượng' in text or 'khoi luong' in text or 'số lượng' in text or 'so luong' in text:
            result['qty'] = idx
        elif 'đơn giá' in text or 'don gia' in text:
            result['price'] = idx
        elif 'thành tiền' in text or 'thanh tien' in text:
            result['amount'] = idx
        elif 'ghi chú' in text or 'ghi chu' in text or 'thông số' in text or 'thong so' in text:
            result['note'] = idx
    return result



def _build_supplier_quote_column_map(header_row):
    """Detect columns for supplier quote import.

    Supplier import uses the same BOQ layout as estimation import, with supplier
    columns added on the right:
    STT | Tên vật tư | Đơn vị | Khối lượng | Đơn giá DT | Thành tiền DT |
    Đơn giá NCC | Thành tiền NCC | Tên NCC | Thông số/Ghi chú
    """
    result = _build_column_map(header_row)
    result.update({
        'supplier_price': None,
        'supplier_amount': None,
        'supplier_name': None,
        'supplier_note': None,
    })
    for idx, value in enumerate(header_row or []):
        text = _normalize_header(value)
        if not text:
            continue
        if ('đơn giá ncc' in text or 'don gia ncc' in text or
                'giá ncc' in text or 'gia ncc' in text or
                'đơn giá nhà cung cấp' in text or 'don gia nha cung cap' in text):
            result['supplier_price'] = idx
        elif ('thành tiền ncc' in text or 'thanh tien ncc' in text or
                'thành tiền nhà cung cấp' in text or 'thanh tien nha cung cap' in text):
            result['supplier_amount'] = idx
        elif ('tên ncc' in text or 'ten ncc' in text or
                'nhà cung cấp' in text or 'nha cung cap' in text or
                text in ('ncc', 'vendor', 'supplier')):
            result['supplier_name'] = idx
        elif ('ghi chú ncc' in text or 'ghi chu ncc' in text or
                'note ncc' in text):
            result['supplier_note'] = idx

    # In the exported BOQ format, technical note is the last column. If there is
    # no dedicated NCC note, we keep note as the general note column.
    if result.get('supplier_note') is None:
        result['supplier_note'] = result.get('note')
    return result


def _norm_match_text(value):
    text = _to_text(value).lower()
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _cell(row, col_idx):
    if col_idx is False or col_idx is None:
        return ''
    return row[col_idx] if col_idx < len(row) else ''


def _is_summary_row(stt, name):
    text = f"{_to_text(stt)} {_to_text(name)}".lower()
    summary_keywords = [
        'tổng cộng', 'tong cong',
        'tổng giá trị', 'tong gia tri',
        'thuế gtgt', 'thue gtgt',
        'vat',
        'trước thuế', 'truoc thue',
        'sau thuế', 'sau thue',
    ]
    return any(keyword in text for keyword in summary_keywords)


def _looks_like_group_row(stt, name, uom, qty, price):
    """Return True for section/item header rows.

    Besides rows with STT like I, I.1, A.1, the provided Excel file also has
    group rows with blank STT, a name, no unit/quantity/unit price, and only a
    subtotal in the amount column. Those rows must become bid.item records;
    otherwise the following materials have no item_id.
    """
    stt_text = _to_text(stt)
    name_text = _to_text(name)
    if not name_text or _is_summary_row(stt_text, name_text):
        return False
    if _is_group_code(stt_text):
        return True
    if not stt_text and name_text and not _to_text(uom) and not qty and not price:
        return True
    return False



def _extract_section_title(rows, sheet_name, header_idx=None):
    """Use the first row of the sheet as the hạng mục name.

    The Excel template uses the first visible row as the section/title row.
    If that row is blank because of an exported/merged template, fall back to
    the first non-empty row before the detected header, then finally the Excel
    sheet name.
    """
    if not rows:
        return sheet_name

    def row_text(row):
        parts = []
        for cell in row or []:
            text = _to_multiline_text(cell).strip()
            if text:
                parts.append(text)
        return ' '.join(parts).strip()

    # Requirement: tên hạng mục lấy từ hàng đầu tiên của sheet.
    title = row_text(rows[0])
    if title:
        return title

    # Fallback for files where row 1 is blank but title appears before header.
    limit = header_idx if header_idx is not None else min(len(rows), 10)
    for row in rows[:limit]:
        title = row_text(row)
        if title:
            return title
    return sheet_name



def _collect_numeric_parent_codes(data_rows, col):
    """Find material parent rows such as 32 when child rows 32.1/32.2 exist.

    In the user's BOQ template, a row like "32" can be a parent material line
    with only UOM/quantity. Rows "32.1", "32.2" below are the actual component
    materials. If we import 32 as a normal bid.line, the children cannot be
    grouped correctly. This pre-scan lets the parser promote 32 to bid.item.
    """
    parents = set()
    for row in data_rows:
        stt = _to_text(_cell(row, col.get('stt')))
        if re.match(r'^\d+\.\d+(?:\.\d+)*$', stt or ''):
            parents.add(stt.split('.', 1)[0])
    return parents




def _has_blank_material_children(data_rows, start_pos, col):
    """Detect parent-material rows whose children have blank STT cells.

    Some BOQ sheets have a parent material line such as STT 32 with only
    unit/quantity, then several component rows below it where the STT column
    is visually blank. Those component rows must become 32.1, 32.2, ...
    during import/export instead of taking the Excel row number or remaining
    loose lines.
    """
    found_child = False
    # Look only at the contiguous rows below the candidate parent.
    for next_row in data_rows[start_pos + 1:]:
        n_stt = _to_text(_cell(next_row, col.get('stt')))
        n_name = _to_text(_cell(next_row, col.get('name')))
        n_uom = _to_text(_cell(next_row, col.get('uom')))
        n_qty = _to_float(_cell(next_row, col.get('qty')))
        n_price = _to_float(_cell(next_row, col.get('price')))
        n_amount = _to_float(_cell(next_row, col.get('amount')))
        n_note = _to_multiline_text(_cell(next_row, col.get('note')))

        if not n_stt and not n_name and not n_uom and not n_qty and not n_price and not n_amount and not n_note:
            continue

        # A new explicit STT starts a new material or item, so the parent block ends.
        if n_stt:
            return found_child

        # A blank-STT group row with only a name and no numeric columns starts a
        # different structural group, not a material child.
        if n_name and not n_uom and not n_qty and not n_price and not n_amount:
            return found_child

        # Child rows in the user's template normally have blank STT, a name,
        # quantity/price/amount, and optional technical specs.
        if n_name and (n_qty or n_price or n_amount or n_uom):
            found_child = True
            continue

        return found_child
    return found_child

def _is_numeric_material_parent_row(stt, name, uom, qty, price, excel_amount, numeric_parent_codes, has_blank_children=False):
    stt_text = _to_text(stt)
    if not stt_text or not re.match(r'^\d+$', stt_text):
        return False
    if not _to_text(name):
        return False
    # Parent rows in this format have UOM/quantity but no unit price. The amount
    # may be blank or 0. There are two valid patterns:
    # 1) Children already have explicit STT 32.1/32.2 -> numeric_parent_codes.
    # 2) Children have blank STT cells -> lookahead detects has_blank_children.
    if stt_text not in numeric_parent_codes and not has_blank_children:
        return False
    return bool(_to_text(uom) or qty) and not price and not excel_amount

def _parse_sheet(sheet_name, rows):
    header_idx = _find_header_row(rows)
    header_row = rows[header_idx] if header_idx < len(rows) else []
    col = _build_column_map(header_row)
    data_rows = rows[header_idx + 1:]
    numeric_parent_codes = _collect_numeric_parent_codes(data_rows, col)

    section_title = _extract_section_title(rows, sheet_name, header_idx)

    section = {
        # Tên hạng mục lấy theo hàng đầu tiên của sheet, còn code giữ theo tên
        # sheet để không ảnh hưởng logic chọn sheet/import/export.
        'name': section_title,
        'code': sheet_name,
        'sheet_name': sheet_name,
        'items': [],
        'lines': [],
        'amount_total': 0.0,
    }
    current_item = None
    previous_line = None
    item_by_code = {}
    auto_group_no = 0
    last_alpha_code = False
    last_roman_code = False
    current_coded_item = None
    numeric_material_parent_line_by_code = {}
    # Parent material currently being expanded. Some BOQ files put STT only
    # on the parent row (e.g. 32) and leave child STT cells blank. The parent
    # is still a bid.line under the current structural item, not a bid.item.
    active_numeric_material_parent = None
    active_numeric_child_no = 0
    auto_line_key = 0

    for index, row in enumerate(data_rows, start=1):
        stt = _to_text(_cell(row, col.get('stt')))
        name = _to_text(_cell(row, col.get('name')))
        uom = _to_text(_cell(row, col.get('uom')))
        qty = _to_float(_cell(row, col.get('qty')))
        price = _to_float(_cell(row, col.get('price')))
        excel_amount = _to_float(_cell(row, col.get('amount')))
        note = _to_multiline_text(_cell(row, col.get('note')))

        # Some Excel templates split long technical specifications into
        # one or many continuation rows below the material row. If the row
        # has no STT/name/uom/qty/price but has a note/specification, append
        # it to the previous material instead of losing the formatting.
        if not stt and not name and not uom and not qty and not price and note and previous_line:
            previous_line['technical_note'] = _append_multiline(previous_line.get('technical_note'), note)
            continue

        if not stt and not name:
            continue
        if re.match(r'^\(\d+\)$', stt or '') and re.match(r'^\(\d+\)$', name or ''):
            continue
        if _is_summary_row(stt, name):
            continue
        if not name or name.lower() in ['tên vật tư', 'ten vat tu', 'description', 'tên hệ thống, thiết bị']:
            continue

        # Vật tư cha dạng 32, sau đó có các dòng con 32.1/32.2/32.3
        # hoặc các dòng con trống STT. Dòng 32 vẫn là một vật tư thuộc đầu mục
        # hiện tại, không được biến thành đầu mục. Các dòng con sẽ trỏ về dòng
        # vật tư cha này qua parent_line_key.
        has_blank_children = _has_blank_material_children(data_rows, index - 1, col)
        if _is_numeric_material_parent_row(stt, name, uom, qty, price, excel_amount, numeric_parent_codes, has_blank_children):
            auto_line_key += 1
            line_key = f'LINE-{auto_line_key}'
            line_item = current_item
            parent_line = {
                'key': line_key,
                'sequence': index,
                'stt': stt,
                'name': name,
                'uom_name': uom,
                'quantity': qty,
                'price_unit': price,
                'amount_total': 0.0,
                'technical_note': note,
                'item_code': line_item['code'] if line_item else False,
                'item_key': line_item.get('key') if line_item else False,
                'parent_line_key': False,
            }
            section['lines'].append(parent_line)
            if line_item:
                line_item['lines'].append(parent_line)
            numeric_material_parent_line_by_code[stt] = parent_line
            active_numeric_material_parent = parent_line
            active_numeric_child_no = 0
            previous_line = parent_line
            continue

        if _looks_like_group_row(stt, name, uom, qty, price):
            parent_code = False
            parent_key = False
            code = stt

            # Giữ đúng cây đầu mục cha/con khi import.
            # Lưu ý quan trọng: mã đầu mục như I, II có thể lặp lại nhiều lần
            # trong cùng một sheet, ví dụ A/I/II rồi B/I/II. Vì vậy không được
            # dùng code làm khóa duy nhất khi gán vật tư. Ta sinh thêm key nội bộ
            # ITEM-x để line luôn trỏ đúng đầu mục thật.
            if code and '.' in code:
                parent_code = code.rsplit('.', 1)[0]
                parent_item = item_by_code.get(parent_code)
                parent_key = parent_item.get('key') if parent_item else False
            elif code and _is_alpha_level_code(code):
                parent_code = False
                parent_key = False
                last_alpha_code = code
                last_roman_code = False
            elif code and _is_roman_code(code):
                parent_code = last_alpha_code or False
                parent_item = item_by_code.get(parent_code) if parent_code else False
                parent_key = parent_item.get('key') if parent_item else False
                last_roman_code = code
            elif not code:
                # Dòng đầu mục không STT là nhóm con của đầu mục CÓ MÃ gần nhất,
                # không phải con của nhóm không STT ngay phía trên. Điều này giúp
                # PHÒNG BƠM và KHỐI NHÀ CHÍNH cùng là con của I.
                parent_code = current_coded_item['code'] if current_coded_item else False
                parent_key = current_coded_item.get('key') if current_coded_item else False
                auto_group_no += 1
                code = f'GROUP-{auto_group_no}'
            elif current_item:
                parent_code = current_item['code']
                parent_key = current_item.get('key')

            item_key = f'ITEM-{len(section["items"]) + 1}'
            item = {
                'key': item_key,
                'sequence': index,
                'code': code,
                'name': name,
                'parent_code': parent_code,
                'parent_key': parent_key,
                'lines': [],
                'amount_total': 0.0,
                'excel_amount_total': excel_amount,
            }
            section['items'].append(item)
            item_by_code[code] = item
            # Gặp đầu mục mới thì kết thúc trạng thái vật tư cha dạng 32.
            active_numeric_material_parent = None
            active_numeric_child_no = 0
            current_item = item
            if stt:
                current_coded_item = item
            continue

        if name and (_is_material_code(stt) or qty or price or uom):
            amount = qty * price
            # If Excel has a calculated amount but qty/price is not parseable,
            # keep the imported value instead of losing the amount.
            if not amount and excel_amount:
                amount = excel_amount

            line_item = current_item

            # Trường hợp trong Excel dòng cha có STT 32, còn các dòng con bên
            # dưới bị để trống STT. Khi đó tự sinh STT con 32.1, 32.2,... và
            # gắn đúng vào vật tư cha 32.
            parent_line_key = False
            if not stt and active_numeric_material_parent:
                active_numeric_child_no += 1
                stt = f'{active_numeric_material_parent.get("stt")}.{active_numeric_child_no}'
                line_item = current_item
                parent_line_key = active_numeric_material_parent.get('key')

            # Dòng 32.1/32.2/... phải thuộc vật tư cha 32 nếu dòng 32 đã được
            # promote thành bid.item ở trên. Không dùng current_item mù quáng vì
            # sau này có thể còn các cấp khác trong cùng đầu mục.
            elif stt and '.' in stt:
                numeric_parent_code = stt.split('.', 1)[0]
                parent_line = numeric_material_parent_line_by_code.get(numeric_parent_code)
                if parent_line:
                    line_item = current_item
                    active_numeric_material_parent = parent_line
                    parent_line_key = parent_line.get('key')
                    try:
                        child_no = int(stt.split('.', 1)[1].split('.', 1)[0])
                        active_numeric_child_no = max(active_numeric_child_no, child_no)
                    except Exception:
                        pass
                else:
                    # Mã chấm không thuộc vật tư cha dạng 32; kết thúc trạng
                    # thái auto-number để tránh dòng sau bị kéo nhầm vào 32.
                    active_numeric_material_parent = None
                    active_numeric_child_no = 0
            elif stt:
                # Một dòng vật tư có STT mới như 33 hoặc 34 sẽ kết thúc nhóm 32.x.
                active_numeric_material_parent = None
                active_numeric_child_no = 0

            auto_line_key += 1
            line_key = f'LINE-{auto_line_key}'
            line = {
                'key': line_key,
                'sequence': index,
                'stt': stt,
                'name': name,
                'uom_name': uom,
                'quantity': qty,
                'price_unit': price,
                'amount_total': amount,
                'technical_note': note,
                'item_code': line_item['code'] if line_item else False,
                'item_key': line_item.get('key') if line_item else False,
                'parent_line_key': parent_line_key,
            }
            previous_line = line
            section['lines'].append(line)
            section['amount_total'] += amount
            if line_item:
                line_item['lines'].append(line)
                line_item['amount_total'] += amount

    return section


def _safe_sheet_name(name, used=None):
    used = used if used is not None else set()
    text = _to_text(name) or 'Sheet'
    text = re.sub(r'[\\/*?:\[\]]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip() or 'Sheet'
    base = text[:31]
    candidate = base
    idx = 2
    while candidate in used:
        suffix = f' ({idx})'
        candidate = (base[:31 - len(suffix)] + suffix)[:31]
        idx += 1
    used.add(candidate)
    return candidate


def _slug_filename(name):
    text = _to_text(name) or 'du-toan-du-thau'
    text = re.sub(r'[\\/*?:\[\]<>|"\']+', ' ', text)
    text = re.sub(r'\s+', '_', text).strip('_') or 'du-toan-du-thau'
    return text[:120]


class BidImportController(http.Controller):

    @http.route('/bid_estimation/get_sheets', type='json', auth='user')
    def get_sheets(self, filename=None, file_content=None):
        if not file_content:
            raise UserError(_('Vui lòng chọn file Excel.'))

        raw = base64.b64decode(file_content.split(',')[-1])
        sheets = _read_workbook(filename, raw)
        sheet_options = []

        for index, (sheet_name, rows) in enumerate(sheets):
            section = _parse_sheet(sheet_name, rows)
            sheet_options.append({
                'index': index,
                # name vẫn là tên sheet thật để dùng làm khóa selected_sheets.
                'name': sheet_name,
                # title là tên hạng mục lấy từ hàng đầu tiên của sheet.
                'title': section.get('name') or sheet_name,
                'selected': bool(section['items'] or section['lines']),
                'item_count': len(section['items']),
                'line_count': len(section['lines']),
                'amount_total': section['amount_total'],
                'has_data': bool(section['items'] or section['lines']),
            })

        return {
            'filename': filename,
            'sheet_count': len(sheet_options),
            'sheets': sheet_options,
        }

    @http.route('/bid_estimation/import_preview', type='json', auth='user')
    def import_preview(self, filename=None, file_content=None, selected_sheets=None):
        if not file_content:
            raise UserError(_('Vui lòng chọn file Excel.'))

        raw = base64.b64decode(file_content.split(',')[-1])
        sheets = _read_workbook(filename, raw)
        selected_names = set(selected_sheets or [])

        if selected_sheets is not None and not selected_names:
            raise UserError(_('Vui lòng chọn ít nhất 1 sheet để import.'))

        sections = []
        for sheet_name, rows in sheets:
            if selected_sheets is not None and sheet_name not in selected_names:
                continue
            section = _parse_sheet(sheet_name, rows)
            if section['items'] or section['lines']:
                sections.append(section)

        if not sections:
            raise UserError(_('Không tìm thấy dữ liệu vật tư trong các sheet đã chọn.'))

        return {
            'filename': filename,
            'selected_sheets': list(selected_names) if selected_sheets is not None else [s['name'] for s in sections],
            'section_count': len(sections),
            'line_count': sum(len(s['lines']) for s in sections),
            'amount_total': sum(s['amount_total'] for s in sections),
            'sections': sections,
        }

    @http.route('/bid_estimation/create_project', type='json', auth='user')
    def create_project(self, project_name=None, note=None, preview=None):
        if not project_name:
            raise UserError(_('Vui lòng nhập tên dự án dự thầu.'))
        if not preview or not preview.get('sections'):
            raise UserError(_('Chưa có dữ liệu preview để tạo dự án.'))

        Project = request.env['bid.project'].sudo()
        Section = request.env['bid.section'].sudo()
        Item = request.env['bid.item'].sudo()
        Line = request.env['bid.line'].sudo()

        project = Project.create({
            'name': project_name,
            'note': note or '',
        })

        for section_index, section_data in enumerate(preview.get('sections'), start=1):
            section = Section.create({
                'project_id': project.id,
                'sequence': section_index * 10,
                'name': section_data.get('name') or 'Hạng mục',
                'code': section_data.get('code') or '',
            })

            item_map = {}
            pending_items = []
            for item_index, item_data in enumerate(section_data.get('items') or [], start=1):
                parent_id = False
                parent_key = item_data.get('parent_key')
                parent_code = item_data.get('parent_code')
                parent_lookup = parent_key or parent_code
                if parent_lookup and parent_lookup in item_map:
                    parent_id = item_map[parent_lookup].id
                item = Item.create({
                    'project_id': project.id,
                    'section_id': section.id,
                    'parent_id': parent_id,
                    'sequence': item_data.get('sequence') or item_index * 10,
                    'code': item_data.get('code') or '',
                    'name': item_data.get('name') or 'Đầu mục',
                    'is_material_parent': bool(item_data.get('is_material_parent')),
                    'uom_name': item_data.get('uom_name') or '',
                    'quantity': item_data.get('quantity') or 0.0,
                    'price_unit': item_data.get('price_unit') or 0.0,
                })
                item_lookup = item_data.get('key') or item_data.get('code')
                item_map[item_lookup] = item
                # Giữ fallback theo code để không phá dữ liệu preview cũ, nhưng chỉ
                # set nếu chưa có vì code có thể bị lặp trong cùng một sheet.
                if item_data.get('code') and item_data.get('code') not in item_map:
                    item_map[item_data.get('code')] = item
                pending_items.append((item, item_data))

            # Set lại parent sau khi đã tạo đủ tất cả đầu mục, tránh mất cha/con
            # trong trường hợp dòng con xuất hiện khi parent chưa có trong item_map.
            for item, item_data in pending_items:
                parent_lookup = item_data.get('parent_key') or item_data.get('parent_code')
                parent_item = item_map.get(parent_lookup) if parent_lookup else False
                if parent_item and item.parent_id.id != parent_item.id:
                    item.parent_id = parent_item.id

            line_map = {}
            pending_lines = []
            for line_data in section_data.get('lines') or []:
                item = item_map.get(line_data.get('item_key')) or item_map.get(line_data.get('item_code'))
                parent_line = line_map.get(line_data.get('parent_line_key')) if line_data.get('parent_line_key') else False
                line = Line.create({
                    'project_id': project.id,
                    'section_id': section.id,
                    'item_id': item.id if item else False,
                    'parent_id': parent_line.id if parent_line else False,
                    'sequence': line_data.get('sequence') or 10,
                    'stt': line_data.get('stt') or '',
                    'name': line_data.get('name') or 'Vật tư',
                    'uom_name': line_data.get('uom_name') or '',
                    'quantity': line_data.get('quantity') or 0.0,
                    'price_unit': line_data.get('price_unit') or 0.0,
                    'technical_note': line_data.get('technical_note') or '',
                })
                if line_data.get('key'):
                    line_map[line_data.get('key')] = line
                pending_lines.append((line, line_data))

            # Fallback set parent after all lines have been created, useful if a
            # child line appears before its parent in dirty Excel data.
            for line, line_data in pending_lines:
                parent_key = line_data.get('parent_line_key')
                parent_line = line_map.get(parent_key) if parent_key else False
                if parent_line and line.parent_id.id != parent_line.id:
                    line.parent_id = parent_line.id

        return {
            'project_id': project.id,
            'display_name': project.display_name,
        }


    @http.route('/bid_estimation/import_supplier_quotes', type='json', auth='user')
    def import_supplier_quotes(self, project_id=None, filename=None, file_content=None, supplier_name=None):
        """Import supplier prices from an Excel quote file.

        Current required supplier quote layout:
        STT | Tên vật tư | Đơn vị | Khối lượng | Đơn giá trước thuế |
        Thành tiền | Thông số kỹ thuật/Ghi chú

        The supplier name is entered once in the OWL popup. The important fix in
        this version is that the supplier Excel is parsed with the same parser as
        the original estimation file. Therefore sheets with many parent/child
        groups, repeated STT values, and parent material rows like 32 -> 32.1,
        32.2 are matched in the same order/tree instead of being matched by a
        single global STT dictionary that overwrites repeated keys.
        """
        if not project_id:
            raise UserError(_('Không xác định được dự án để import NCC.'))
        if not file_content:
            raise UserError(_('Vui lòng chọn file Excel báo giá NCC.'))
        supplier_name = _to_text(supplier_name)
        if not supplier_name:
            raise UserError(_('Vui lòng nhập tên nhà cung cấp trước khi import.'))

        project = request.env['bid.project'].sudo().browse(int(project_id))
        if not project.exists():
            raise UserError(_('Dự án dự thầu không còn tồn tại.'))

        raw = base64.b64decode(file_content.split(',')[-1])
        sheets = _read_workbook(filename, raw)

        Partner = request.env['res.partner'].sudo()
        Quote = request.env['bid.supplier.quote'].sudo()

        partner = Partner.search([('name', '=ilike', supplier_name)], limit=1)
        if not partner:
            partner = Partner.create({
                'name': supplier_name,
                'supplier_rank': 1,
            })
        elif not partner.supplier_rank:
            partner.supplier_rank = 1

        total_created = 0
        total_updated = 0
        total_skipped = 0
        sheet_results = []

        def find_section(sheet_name, rows):
            header_idx = _find_header_row(rows)
            title = _extract_section_title(rows, sheet_name, header_idx)
            sheet_key = _norm_match_text(sheet_name)
            title_key = _norm_match_text(title)
            for section in project.section_ids:
                if _norm_match_text(section.code) == sheet_key:
                    return section
                if _norm_match_text(section.name) == title_key:
                    return section
            return False

        def pop_first_available(queue, used_line_ids):
            """Return first not-yet-used line from a queue.

            We intentionally use queues rather than a plain dict because many BOQ
            sheets restart numbering under different sub-items, for example:
            A/I/1, A/II/1, B/I/1. A dict keyed by STT would keep only the last
            line and import NCC prices into the wrong material.
            """
            if not queue:
                return False
            for line in queue:
                if line.id not in used_line_ids:
                    used_line_ids.add(line.id)
                    return line
            return False

        for sheet_name, rows in sheets:
            section = find_section(sheet_name, rows)
            if not section:
                total_skipped += 1
                sheet_results.append({
                    'sheet': sheet_name,
                    'created': 0,
                    'updated': 0,
                    'skipped': 1,
                    'message': _('Không tìm thấy hạng mục tương ứng trong dự án.'),
                })
                continue

            # Parse the NCC sheet with the same BOQ parser used for estimate
            # import. This keeps parent/child context and auto-generates child
            # STT like 32.1, 32.2 for blank-STT component rows.
            parsed_section = _parse_sheet(sheet_name, rows)
            parsed_lines = parsed_section.get('lines') or []

            # Build ordered queues by STT and by name. section.line_ids order is
            # the database representation of the original import order.
            lines_by_stt = {}
            lines_by_name = {}
            section_lines = section.line_ids.sorted(lambda l: (l.sequence or 0, l.id))
            for line in section_lines:
                stt_key = _norm_match_text(line.stt)
                name_key = _norm_match_text(line.name)
                if stt_key:
                    lines_by_stt.setdefault(stt_key, []).append(line)
                if name_key:
                    lines_by_name.setdefault(name_key, []).append(line)

            created = updated = skipped = 0
            used_line_ids = set()

            for parsed_line in parsed_lines:
                stt = _to_text(parsed_line.get('stt'))
                name = _to_text(parsed_line.get('name'))
                supplier_price = _to_float(parsed_line.get('price_unit'))
                supplier_note = _to_multiline_text(parsed_line.get('technical_note'))

                if not name and not stt:
                    continue
                if _is_summary_row(stt, name):
                    continue
                if not supplier_price:
                    # Parent material rows such as 32 often have only UOM/qty.
                    # They are kept in the project but should not create an NCC
                    # quote unless the supplier file actually has a unit price.
                    continue

                line = False
                stt_key = _norm_match_text(stt)
                name_key = _norm_match_text(name)

                # 1) Prefer STT queue, because names can be slightly different.
                if stt_key:
                    line = pop_first_available(lines_by_stt.get(stt_key), used_line_ids)

                # 2) Fallback by material name queue.
                if not line and name_key:
                    line = pop_first_available(lines_by_name.get(name_key), used_line_ids)

                if not line:
                    skipped += 1
                    continue

                quote = Quote.search([
                    ('line_id', '=', line.id),
                    ('partner_id', '=', partner.id),
                ], limit=1)
                vals = {
                    'line_id': line.id,
                    'partner_id': partner.id,
                    'price_unit': supplier_price,
                    'note': supplier_note or False,
                }
                if quote:
                    quote.write(vals)
                    updated += 1
                else:
                    Quote.create(vals)
                    created += 1

            total_created += created
            total_updated += updated
            total_skipped += skipped
            sheet_results.append({
                'sheet': sheet_name,
                'section_id': section.id,
                'section_name': section.name,
                'created': created,
                'updated': updated,
                'skipped': skipped,
                'message': _('Đã import NCC cho hạng mục.'),
            })

        return {
            'project_id': project.id,
            'created': total_created,
            'updated': total_updated,
            'skipped': total_skipped,
            'sheets': sheet_results,
        }

    @http.route('/bid_estimation/export_excel/<int:project_id>', type='http', auth='user')
    def export_excel(self, project_id, **kwargs):
        """Export Excel theo đúng format BOQ người dùng gửi.

        Mỗi hạng mục là một sheet riêng. Không xuất thêm sheet tổng hợp/dự toán
        vì mẫu người dùng đưa chỉ gồm các sheet hạng mục. Các cột thành tiền dùng
        công thức Excel để người dùng sửa khối lượng/đơn giá thì file tự tính lại.
        """
        project = request.env['bid.project'].browse(project_id).exists()
        if not project:
            return request.not_found()

        try:
            import xlsxwriter
            from xlsxwriter.utility import xl_rowcol_to_cell
        except Exception as exc:
            raise UserError(_('Server chưa cài thư viện XlsxWriter để xuất Excel. Vui lòng chạy: pip3 install XlsxWriter')) from exc

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        workbook.set_properties({
            'title': project.name or 'Dự toán dự thầu',
            'subject': 'Bid estimation export',
            'author': request.env.user.name or 'Odoo',
        })

        base_font = {'font_name': 'Times New Roman', 'font_size': 11}
        fmt_title = workbook.add_format({
            **base_font, 'bold': True, 'font_size': 12, 'align': 'center',
            'valign': 'vcenter', 'border': 1
        })
        fmt_unit = workbook.add_format({**base_font, 'italic': True, 'align': 'right', 'valign': 'vcenter'})
        fmt_header = workbook.add_format({
            **base_font, 'bold': True, 'bg_color': '#BDD7EE', 'border': 1,
            'align': 'center', 'valign': 'vcenter', 'text_wrap': True
        })
        fmt_header_no = workbook.add_format({
            **base_font, 'bg_color': '#BDD7EE', 'border': 1,
            'align': 'center', 'valign': 'vcenter'
        })
        fmt_group = workbook.add_format({
            **base_font, 'bold': True, 'border': 1, 'align': 'left',
            'valign': 'vcenter', 'text_wrap': True
        })
        fmt_group_code = workbook.add_format({
            **base_font, 'bold': True, 'border': 1, 'align': 'center', 'valign': 'vcenter'
        })
        fmt_text = workbook.add_format({
            **base_font, 'border': 1, 'align': 'left', 'valign': 'top', 'text_wrap': True
        })
        fmt_center = workbook.add_format({
            **base_font, 'border': 1, 'align': 'center', 'valign': 'top', 'text_wrap': True
        })
        fmt_qty = workbook.add_format({
            **base_font, 'border': 1, 'align': 'right', 'valign': 'top', 'num_format': '#,##0.00'
        })
        fmt_money = workbook.add_format({
            **base_font, 'border': 1, 'align': 'right', 'valign': 'top', 'num_format': '#,##0'
        })
        fmt_money_formula = workbook.add_format({
            **base_font, 'border': 1, 'align': 'right', 'valign': 'top', 'num_format': '#,##0'
        })
        fmt_total_label = workbook.add_format({
            **base_font, 'bold': True, 'border': 1, 'align': 'center', 'valign': 'vcenter'
        })
        fmt_total_money = workbook.add_format({
            **base_font, 'bold': True, 'border': 1, 'align': 'right', 'valign': 'vcenter', 'num_format': '#,##0'
        })
        fmt_blank = workbook.add_format({**base_font})

        used_sheet_names = set()
        sections = project.section_ids.sorted(lambda s: (s.sequence, s.id))

        def selected_quote(line):
            # Ưu tiên NCC đã chọn; nếu chưa chọn thì lấy NCC có đơn giá thấp nhất.
            if line.selected_quote_id:
                return line.selected_quote_id
            quotes = line.supplier_quote_ids.filtered(lambda q: q.price_unit > 0).sorted(lambda q: (q.price_unit, q.id))
            return quotes[:1] and quotes[0] or False

        def setup_boq_sheet(ws, title):
            ws.hide_gridlines(2)
            ws.set_landscape()
            ws.set_paper(9)  # A4
            ws.fit_to_pages(1, 0)
            ws.set_margins(left=0.25, right=0.25, top=0.35, bottom=0.35)

            ws.set_column(0, 0, 8)    # STT
            ws.set_column(1, 1, 38)   # Tên vật tư
            ws.set_column(2, 2, 9)    # Đơn vị
            ws.set_column(3, 3, 11)   # Khối lượng
            ws.set_column(4, 4, 16)   # Đơn giá trước thuế
            ws.set_column(5, 5, 18)   # Thành tiền
            ws.set_column(6, 6, 16)   # Đơn giá NCC
            ws.set_column(7, 7, 18)   # Thành tiền NCC
            ws.set_column(8, 8, 26)   # Tên NCC
            ws.set_column(9, 9, 45)   # Thông số kỹ thuật/Ghi chú

            ws.set_row(0, 24)
            ws.set_row(2, 34)
            ws.set_row(3, 20)
            ws.merge_range(0, 0, 0, 9, title, fmt_title)
            ws.merge_range(1, 8, 1, 9, 'Đơn vị tính: đồng', fmt_unit)

            headers = [
                'STT', 'Tên vật tư', 'Đơn vị', 'Khối\nlượng', 'Đơn giá\n(trước thuế)',
                'Thành tiền', 'Đơn giá NCC', 'Thành tiền NCC', 'Tên NCC', 'Thông số kỹ thuật/\nGhi chú'
            ]
            subheaders = ['(1)', '(2)', '(3)', '(4)', '(5)', '(6 = 4 x 5)', '(7)', '(8=4x7)', '(9)', '(10)']
            for col, header in enumerate(headers):
                ws.write(2, col, header, fmt_header)
                ws.write(3, col, subheaders[col], fmt_header_no)
            ws.freeze_panes(4, 0)
            ws.repeat_rows(2, 3)
            return 4

        def write_blank_cells(ws, row, start_col=2):
            for col in range(start_col, 10):
                ws.write(row, col, '', fmt_text)

        def _export_code(code):
            # GROUP-1/GROUP-2 là mã nội bộ sinh ra khi dòng đầu mục trong Excel
            # không có STT. Khi xuất lại thì để trống STT để giống file nhập hơn.
            code = code or ''
            return '' if str(code).upper().startswith('GROUP-') else code

        def write_group_row(ws, row, code, name, item=False):
            ws.write(row, 0, _export_code(code), fmt_group_code)
            # Vật tư cha dạng 32 nên giữ tên như Excel, không upper toàn bộ để
            # nhìn giống dòng vật tư. Đầu mục A/I/II vẫn in đậm/hoa.
            display_name = name or ''
            if not (item and item.is_material_parent):
                display_name = display_name.upper()
            ws.write(row, 1, display_name, fmt_group)

            if item and item.is_material_parent:
                ws.write(row, 2, item.uom_name or '', fmt_center)
                ws.write(row, 3, item.quantity or 0.0, fmt_qty)
                if item.price_unit:
                    qty_cell = xl_rowcol_to_cell(row, 3)
                    price_cell = xl_rowcol_to_cell(row, 4)
                    ws.write(row, 4, item.price_unit, fmt_money)
                    ws.write_formula(row, 5, '=%s*%s' % (qty_cell, price_cell), fmt_money_formula, (item.quantity or 0.0) * (item.price_unit or 0.0))
                else:
                    ws.write(row, 4, '', fmt_money)
                    ws.write(row, 5, '', fmt_money)
                for col in range(6, 10):
                    ws.write(row, col, '', fmt_text)
            else:
                write_blank_cells(ws, row, 2)
            return row + 1

        def write_line_row(ws, row, line):
            quote = selected_quote(line)
            qty_cell = xl_rowcol_to_cell(row, 3)
            bid_price_cell = xl_rowcol_to_cell(row, 4)
            supplier_price_cell = xl_rowcol_to_cell(row, 6)

            ws.write(row, 0, line.stt or line.sequence or '', fmt_center)
            ws.write(row, 1, line.name or '', fmt_text)
            ws.write(row, 2, line.uom_name or '', fmt_center)
            ws.write(row, 3, line.quantity or 0.0, fmt_qty)
            ws.write(row, 4, line.price_unit or 0.0, fmt_money)
            ws.write_formula(row, 5, '=%s*%s' % (qty_cell, bid_price_cell), fmt_money_formula, line.amount_total or 0.0)

            if quote:
                ws.write(row, 6, quote.price_unit or 0.0, fmt_money)
                supplier_value = quote.amount_total or ((line.quantity or 0.0) * (quote.price_unit or 0.0))
            else:
                ws.write(row, 6, '', fmt_money)
                supplier_value = None
            ws.write_formula(
                row, 7,
                '=IF(%s="","",%s*%s)' % (supplier_price_cell, qty_cell, supplier_price_cell),
                fmt_money_formula,
                supplier_value
            )
            ws.write(row, 8, quote.partner_id.name if quote else '', fmt_text)
            ws.write(row, 9, line.technical_note or '', fmt_text)
            return row + 1

        def write_section_content(ws, row, section):
            """Write one hạng mục sheet.

            Requirement: xuất mỗi hạng mục thành một sheet riêng, bố cục giống
            file Excel nhập. Vì vậy phần body chỉ ghi lại các đầu mục/vật tư đã
            import, không chèn thêm sheet tổng hợp hay dòng bao ngoài không có
            trong file gốc. Các cột NCC được thêm vào bên phải cột Thành tiền.
            """
            data_start_row = row
            written_line_ids = set()
            written_item_ids = set()

            def write_item_tree(item, current_row):
                written_item_ids.add(item.id)
                current_row = write_group_row(ws, current_row, item.code or '', item.name or '', item)

                # Giữ đúng thứ tự gốc của Excel: sau một đầu mục có thể vừa có
                # vật tư trực tiếp vừa có vật tư cha/con. Vì vậy phải trộn
                # line_ids và child_ids theo sequence, không được ghi toàn bộ
                # line trước rồi mới tới child item. Trường hợp STT 32 có các
                # dòng con blank-STT sẽ xuất ra 32, 32.1, 32.2... đúng vị trí.
                children_and_lines = list(item.line_ids) + list(item.child_ids)
                children_and_lines.sort(key=lambda rec: (rec.sequence or 0, rec.id))
                for rec in children_and_lines:
                    if rec._name == 'bid.item':
                        current_row = write_item_tree(rec, current_row)
                    else:
                        current_row = write_line_row(ws, current_row, rec)
                        written_line_ids.add(rec.id)
                return current_row

            # Ghi đầy đủ toàn bộ đầu mục cha/con theo cây. Không bỏ qua đầu mục rỗng,
            # vì người dùng cần file xuất giữ cấu trúc giống file nhập.
            root_items = section.item_ids.filtered(lambda i: not i.parent_id).sorted(lambda i: (i.sequence, i.id))
            for item in root_items:
                row = write_item_tree(item, row)

            # Nếu dữ liệu cũ từng import sai parent_id, vẫn ghi các item còn sót để
            # không mất đầu mục cha/con khi xuất Excel.
            orphan_items = section.item_ids.filtered(lambda i: i.id not in written_item_ids).sorted(lambda i: (i.sequence, i.id))
            for item in orphan_items:
                row = write_item_tree(item, row)

            # Vật tư không có đầu mục vẫn phải nằm trong sheet đúng hạng mục.
            loose_lines = section.line_ids.filtered(lambda l: l.id not in written_line_ids).sorted(lambda l: (l.sequence, l.id))
            if loose_lines:
                row = write_group_row(ws, row, '', 'VẬT TƯ CHƯA THUỘC ĐẦU MỤC')
                for line in loose_lines:
                    row = write_line_row(ws, row, line)
                    written_line_ids.add(line.id)

            # Một dòng trống trước tổng cộng, giống file mẫu.
            for col in range(10):
                ws.write(row, col, '', fmt_blank)
            total_row = row + 1

            ws.write(total_row, 0, '', fmt_total_label)
            ws.write(total_row, 1, 'TỔNG CỘNG', fmt_total_label)
            for col in range(2, 5):
                ws.write(total_row, col, '', fmt_total_label)

            # SUM theo vùng liên tục. Dòng nhóm rỗng ở cột F/H nên không ảnh hưởng.
            first_excel_row = data_start_row + 1
            last_excel_row = row
            if last_excel_row >= first_excel_row:
                ws.write_formula(total_row, 5, '=SUM(F%s:F%s)' % (first_excel_row, last_excel_row), fmt_total_money, section.amount_total or 0.0)
                supplier_total = sum(section.line_ids.mapped('selected_amount_total')) or sum(section.line_ids.mapped('supplier_best_amount_total'))
                ws.write_formula(total_row, 7, '=SUM(H%s:H%s)' % (first_excel_row, last_excel_row), fmt_total_money, supplier_total or 0.0)
            else:
                ws.write(total_row, 5, 0, fmt_total_money)
                ws.write(total_row, 7, 0, fmt_total_money)
            ws.write(total_row, 6, '', fmt_total_label)
            ws.write(total_row, 8, '', fmt_total_label)
            ws.write(total_row, 9, '', fmt_total_label)
            return total_row + 1

        def clean_title_name(section):
            # Giữ đúng tinh thần mẫu: HẠNG MỤC: <tên hạng mục>.
            # Một số dữ liệu đã có sẵn prefix "HẠNG MỤC:" hoặc bị lặp 2 lần,
            # nên strip lặp cho tới khi còn tên thật.
            name = section.name or section.code or ''
            while re.match(r'^\s*hạng\s*mục\s*:', name or '', flags=re.I):
                name = re.sub(r'^\s*hạng\s*mục\s*:\s*', '', name, flags=re.I)
            return name.strip()

        if not sections:
            ws = workbook.add_worksheet(_safe_sheet_name('Dự toán', used_sheet_names))
            setup_boq_sheet(ws, 'HẠNG MỤC:')
        else:
            for section in sections:
                sheet_name = section.code or section.name or 'Hạng mục'
                title = 'HẠNG MỤC: %s' % clean_title_name(section)
                ws = workbook.add_worksheet(_safe_sheet_name(sheet_name, used_sheet_names))
                row = setup_boq_sheet(ws, title)
                write_section_content(ws, row, section)

        workbook.close()
        output.seek(0)
        filename = f'{_slug_filename(project.name)}_{datetime.now().strftime("%Y%m%d_%H%M")}.xlsx'
        return request.make_response(
            output.read(),
            headers=[
                ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                ('Content-Disposition', content_disposition(filename)),
            ]
        )
