from abc import ABC, abstractmethod
from typing import List
from validation_context import ValidationContext
from validation_error import ValidationError


class RuleInterface(ABC):
    """Contract for all validation rules."""

    @abstractmethod
    def validate(self, context: ValidationContext) -> List[ValidationError]:
        """Execute validation and return any findings (errors/warnings)."""
        pass

    @abstractmethod
    def get_stufe(self) -> int:
        """The Prüfstufe this rule belongs to (1, 2, 3, 4, etc.)."""
        pass