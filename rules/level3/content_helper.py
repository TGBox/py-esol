import calendar
from datetime import datetime
import re
from typing import Any, Dict, List, Optional


class ContentHelper:
    """Shared helper methods for Stufe 3 content validation rules."""

    @staticmethod
    def is_valid_date(date_str: str, allow_partial_zero: bool = False) -> bool:
        if not re.match(r"^\d{8}$", date_str):
            return False

        year = int(date_str[0:4])
        month = int(date_str[4:6])
        day = int(date_str[6:8])

        if year < 1900 or year > 2100:
            return False

        if allow_partial_zero:
            if month == 0 and day == 0:
                return True
            if day == 0 and 1 <= month <= 12:
                return True

        if month < 1 or month > 12:
            return False

        _, max_days = calendar.monthrange(year, month)
        return 1 <= day <= max_days

    @staticmethod
    def is_date_in_future(
        date_str: str, reference_date: Optional[str] = None
    ) -> bool:
        if not re.match(r"^\d{8}$", date_str):
            return False

        if reference_date is None:
            reference_date = datetime.now().strftime("%Y%m%d")

        return date_str > reference_date

    @staticmethod
    def is_valid_ik(ik: str) -> bool:
        return re.match(r"^\d{9}$", ik) is not None

    @staticmethod
    def is_valid_ik_check_digit(ik: str) -> bool:
        if not ContentHelper.is_valid_ik(ik):
            return False

        # Nur Ziffern an Position 3 bis 8 (Index 2 bis 7) verwenden!
        # Die Stellen 1 und 2 (Klassifikation) fließen NICHT ein.
        digits_3_to_8 = [int(d) for d in ik[2:8]]

        # Gewichtung von rechts nach links: 1, 2, 1, 2, 1, 2
        # (Bezogen auf Index 0 bis 5 entspricht das [2, 1, 2, 1, 2, 1])
        weights = [2, 1, 2, 1, 2, 1]
        sum_val = 0

        for i in range(6):
            product = digits_3_to_8[i] * weights[i]
            # Quersumme bei zweistelligen Produkten (oder product // 10 + product % 10)
            sum_val += (product // 10) + (product % 10)

        # Die Prüfziffer ist direkt der Rest modulo 10 (Einerstelle)
        expected_check_digit = sum_val % 10

        return int(ik[8]) == expected_check_digit

    @staticmethod
    def parse_decimal(value: Optional[str]) -> Optional[float]:
        if value is None or value == "":
            return None

        normalized = value.replace(",", ".")
        try:
            return float(normalized)
        except ValueError:
            return None

    @staticmethod
    def format_decimal(value: float, decimals: int = 2) -> str:
        formatted = f"{value:.{decimals}f}"
        return formatted.replace(".", ",")

    @staticmethod
    def round_commercial(value: float, decimals: int = 2) -> float:
        # Commercial rounding (round half up)
        from decimal import Decimal, ROUND_HALF_UP

        d = Decimal(str(value))
        return float(
            d.quantize(Decimal(10) ** -decimals, rounding=ROUND_HALF_UP)
        )

    @staticmethod
    def is_valid_time(time_str: str) -> bool:
        if not re.match(r"^\d{4}$", time_str):
            return False

        hours = int(time_str[0:2])
        minutes = int(time_str[2:4])
        return 0 <= hours <= 23 and 0 <= minutes <= 59

    @staticmethod
    def is_valid_rechnungsnummer_part(value: str) -> bool:
        if not value:
            return False

        if " " in value:
            return False

        if not re.match(r"^[a-zA-Z0-9\-/]+$", value):
            return False

        if re.search(r"^[\-/]", value) or re.search(r"[\-/]$", value):
            return False

        if re.search(r"[\-/]{2,}", value):
            return False

        return True

    @staticmethod
    def is_valid_email(email: str) -> bool:
        if re.search(r"[äöüÄÖÜß]", email):
            return False

        pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
        return re.match(pattern, email) is not None

    @staticmethod
    def get_field(
        segment: Dict[str, Any], index: int, sub_index: Optional[int] = None
    ) -> Optional[str]:
        fields = segment.get("fields", [])
        if index >= len(fields):
            return None

        field = fields[index]

        if sub_index is not None:
            if isinstance(field, list):
                return field[sub_index] if sub_index < len(field) else None
            return field if sub_index == 0 else None

        if isinstance(field, list):
            return ":".join([str(f) for f in field])

        return str(field) if field is not None else None

    @staticmethod
    def get_message_type_for_segment(
        seg_index: int, messages: List[Dict[str, Any]]
    ) -> Optional[str]:
        for msg in messages:
            if msg["start"] <= seg_index <= msg["end"]:
                return msg["type"]
        return None

    @staticmethod
    def get_message_for_segment(
        seg_index: int, messages: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        for msg in messages:
            if msg["start"] <= seg_index <= msg["end"]:
                return msg
        return None

    @staticmethod
    def get_file_vk(parsed_segments: List[Dict[str, Any]]) -> Optional[str]:
        for seg in parsed_segments:
            if seg.get("tag") == "FKT":
                return ContentHelper.get_field(seg, 0)
        return None

    @staticmethod
    def get_file_leistungsbereich(parsed_segments: List[Dict[str, Any]]) -> Optional[str]:
        for seg in parsed_segments:
            if seg.get("tag") == "UNB":
                return ContentHelper.get_field(seg, 5)
        return None

    @staticmethod
    def extract_inv_blocks(
        message: Dict[str, Any],
    ) -> List[List[Dict[str, Any]]]:
        blocks = []
        current_block = []
        in_inv_block = False

        for seg in message.get("segments", []):
            tag = seg.get("tag")

            if tag in ["UNH", "FKT", "REC", "UNT"]:
                continue

            if tag == "INV":
                if in_inv_block and current_block:
                    blocks.append(current_block)
                current_block = [seg]
                in_inv_block = True
            elif in_inv_block:
                current_block.append(seg)

        if in_inv_block and current_block:
            blocks.append(current_block)

        return blocks