# challan_checker.py
# Student Finance auto-approval: compares the amount being approved with the amount printed on the
# KFT Fee Challan Form image (tbl_pre_disbursement_application_images, image_type economics_picture*).
import io
import logging
import re
from typing import Dict, List, Optional, Tuple

from imports import *

logger = logging.getLogger(__name__)

CHALLAN_IMAGE_TYPE = 'economics_picture'   # file name suffix: economics_picture1, economics_picture2 ...
AMOUNT_TOLERANCE = 0.5                      # rupees

_BEFORE_LABEL = re.compile(r'total\s*amount\s*before', re.I)
_AFTER_LABEL = re.compile(r'total\s*amount\s*after', re.I)
_AMOUNT = re.compile(r'\d[\d,\.\s]*\d|\d')

_reader = None


def _get_reader():
    """EasyOCR is heavy and optional: import it only when a challan has to be read."""
    global _reader
    if _reader is None:
        import easyocr
        _reader = easyocr.Reader(['en'], gpu=False, verbose=False)
    return _reader


def ocr_image(image_bytes: bytes) -> List[Tuple[List, str]]:
    """Returns [(box, text), ...] where box is four (x, y) corners. Raises ImportError when EasyOCR is missing."""
    import numpy as np
    from PIL import Image

    image = Image.open(io.BytesIO(image_bytes)).convert('RGB')
    # The reader copes better with a big image than with a small phone-sized one
    ratio = 1.0
    if image.width < 1400:
        ratio = 1400 / image.width
        image = image.resize((1400, int(image.height * ratio)))
    return [([(x / ratio, y / ratio) for x, y in box], text)
            for box, text, _conf in _get_reader().readtext(np.array(image))]


def _to_amount(text: str) -> Optional[float]:
    match = _AMOUNT.search(text.replace('O', '0').replace('o', '0'))
    if not match:
        return None
    digits = re.sub(r'[^\d.]', '', match.group(0).replace(',', ''))
    try:
        return float(digits) if digits else None
    except ValueError:
        return None


def _center(box) -> Tuple[float, float]:
    xs = [p[0] for p in box]
    ys = [p[1] for p in box]
    return sum(xs) / len(xs), sum(ys) / len(ys)


def _height(box) -> float:
    ys = [p[1] for p in box]
    return max(ys) - min(ys)


def _amount_for_label(items: List[Tuple[List, str]], label: re.Pattern) -> Optional[float]:
    """The value printed on the same row as the label: in the label's own box, or the nearest box to its right."""
    for box, text in items:
        if not label.search(text):
            continue
        after_label = label.split(text, maxsplit=1)[-1]
        amount = _to_amount(after_label) if re.search(r'\d', after_label) else None
        if amount is not None:
            return amount

        cx, cy = _center(box)
        row_height = max(_height(box), 10)
        candidates = []
        for other_box, other_text in items:
            ox, oy = _center(other_box)
            if other_box is box or ox <= cx or abs(oy - cy) > row_height * 0.8:
                continue
            value = _to_amount(other_text) if re.search(r'\d', other_text) else None
            if value is not None:
                candidates.append((ox - cx, value))
        if candidates:
            return min(candidates)[1]
    return None


def parse_challan(items: List[Tuple[List, str]]) -> Dict:
    """Pulls 'Total Amount Before Due' / 'After Due Date' out of the OCR boxes."""
    return {
        'before_due': _amount_for_label(items, _BEFORE_LABEL),
        'after_due': _amount_for_label(items, _AFTER_LABEL),
    }


# Photos (shadows, tilt, blur) often garble the printed labels. "Total Am..." is still recognisable, so the two
# total rows are found from that, and just the value column next to them is cropped, enlarged and read as digits.
_TOTAL_ROW = re.compile(r't[o0]t\w{0,2}\W{0,2}\s*am', re.I)
_AFTER_HINT = re.compile(r'aft|alt|dat', re.I)
_BEFORE_HINT = re.compile(r'bef|delo|befo', re.I)


def read_total_rows(image_bytes: bytes, items: List[Tuple[List, str]]) -> Dict:
    import numpy as np
    from PIL import Image, ImageOps

    rows = sorted(((_center(box)[1], _height(box), text) for box, text in items if _TOTAL_ROW.search(text)))
    if not rows:
        return {'before_due': None, 'after_due': None}

    image = Image.open(io.BytesIO(image_bytes)).convert('L')
    row_h = max(max(h for _, h, _ in rows), 12)
    top = max(int(rows[0][0] - 2 * row_h), 0)
    bottom = min(int(rows[-1][0] + 2.5 * row_h), image.height)
    crop = image.crop((int(image.width * 0.55), top, image.width, bottom))
    crop = ImageOps.autocontrast(crop.resize((crop.width * 2, crop.height * 2), Image.LANCZOS), cutoff=2)

    values = []   # (y in original pixels, amount)
    for box, text, _conf in _get_reader().readtext(np.array(crop), allowlist='0123456789,.'):
        amount = _to_amount(text)
        if amount is not None:
            values.append((top + _center(box)[1] / 2, amount))

    def label_kind(index, text):
        if _BEFORE_HINT.search(text) and not _AFTER_HINT.search(text):
            return 'before_due'
        if _AFTER_HINT.search(text) and not _BEFORE_HINT.search(text):
            return 'after_due'
        return 'before_due' if index == 0 else 'after_due'

    result = {'before_due': None, 'after_due': None}
    free = list(values)
    for index, (y, _h, text) in enumerate(rows[:2]):
        if not free:
            break
        nearest = min(free, key=lambda v: abs(v[0] - y))
        if abs(nearest[0] - y) <= row_h * 1.6:
            result[label_kind(index, text)] = nearest[1]
            free.remove(nearest)
    return result


def read_amounts(image_bytes: bytes) -> Dict:
    """The challan's 'Total Amount Before Due' / 'After Due Date'. Raises ImportError when EasyOCR is missing."""
    items = ocr_image(image_bytes)
    amounts = parse_challan(items)
    if amounts['before_due'] is None and amounts['after_due'] is None:
        amounts = read_total_rows(image_bytes, items)
    return amounts


def get_challan_images(application_no) -> List[bytes]:
    rows = fetch_records("""
        SELECT image_data
        FROM tbl_pre_disbursement_application_images
        WHERE CAST(application_no AS VARCHAR) = %s
          AND LOWER(COALESCE(image_type, '')) LIKE %s
        ORDER BY created_date DESC, pd_ai_id DESC
    """, params=(str(application_no), CHALLAN_IMAGE_TYPE + '%'), is_print=False)
    return [bytes(r['image_data']) for r in rows if r.get('image_data')]


def check_challan(application_no, loan_amount, read_image=read_amounts) -> Dict:
    """
    Compares the approved amount with the challan.
      status  match | mismatch | missing | unreadable | unavailable
      passed  True only for 'match'
    The challan counts as matching when the amount equals the total before or after the due date.
    """
    result = {'status': 'missing', 'passed': False, 'before_due': None, 'after_due': None,
              'loan_amount': float(loan_amount or 0), 'detail': ''}

    images = get_challan_images(application_no)
    if not images:
        result['detail'] = 'No challan image (economics_picture) uploaded for this application'
        return result

    read_any = False
    for image_bytes in images:
        try:
            amounts = read_image(image_bytes)
        except ImportError:
            result['status'] = 'unavailable'
            result['detail'] = 'Challan reader (EasyOCR) is not installed on this server'
            return result
        except Exception as e:
            logger.error(f"Challan read failed for {application_no}: {e}")
            continue
        read_any = True
        if not amounts['before_due'] and not amounts['after_due']:
            continue
        result.update({k: (v or None) for k, v in amounts.items()})
        break

    if result['before_due'] is None and result['after_due'] is None:
        result['status'] = 'unreadable'
        result['detail'] = ('Challan image could not be read' if not read_any
                            else 'Challan image read, but no total amount was found on it')
        return result

    loan = result['loan_amount']
    for key, label in (('before_due', 'before due date'), ('after_due', 'after due date')):
        if result[key] is not None and abs(result[key] - loan) <= AMOUNT_TOLERANCE:
            result.update(status='match', passed=True,
                          detail=f"Approved amount {loan:,.0f} matches the challan total {label} ({result[key]:,.0f})")
            return result

    shown = [f"{label} {result[key]:,.0f}" for key, label in (('before_due', 'before due'), ('after_due', 'after due'))
             if result[key] is not None]
    result.update(status='mismatch',
                  detail=f"Approved amount {loan:,.0f} does not match the challan ({', '.join(shown)})")
    return result
