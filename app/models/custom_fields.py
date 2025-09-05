from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Any, Optional
from enum import Enum


class FieldType(Enum):
    MULTISELECT = "multiselect"
    SELECT = "select"
    TEXT = "text"
    NUMBER = "number"
    BOOLEAN = "boolean"
    DATE = "date"


@dataclass
class CustomFieldConfig:
    """
    Custom field configuration model for defining user-configurable fields.
    """
    field_name: str
    field_type: FieldType
    options: List[str] = field(default_factory=list)
    is_required: bool = False
    default_value: Optional[Any] = None
    description: Optional[str] = None
    validation_rules: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """Validate custom field configuration after initialization."""
        self.validate()

    def validate(self) -> None:
        """Validate custom field configuration data."""
        if not self.field_name or not isinstance(self.field_name, str):
            raise ValueError("Field name must be a non-empty string")
        
        # Validate field name format (alphanumeric and underscores only)
        if not self.field_name.replace('_', '').replace('-', '').isalnum():
            raise ValueError("Field name must contain only alphanumeric characters, hyphens, and underscores")
        
        if not isinstance(self.field_type, FieldType):
            raise ValueError(f"Field type must be a FieldType enum, got {type(self.field_type)}")
        
        if not isinstance(self.options, list):
            raise ValueError("Options must be a list")
        
        if not isinstance(self.is_required, bool):
            raise ValueError("is_required must be a boolean")
        
        if self.description is not None and not isinstance(self.description, str):
            raise ValueError("Description must be a string when provided")
        
        if not isinstance(self.validation_rules, dict):
            raise ValueError("Validation rules must be a dictionary")
        
        # Validate field type specific requirements
        if self.field_type in [FieldType.SELECT, FieldType.MULTISELECT]:
            if not self.options:
                raise ValueError(f"{self.field_type.value} fields must have at least one option")
        
        # Validate default value against field type
        if self.default_value is not None:
            self._validate_default_value()

    def _validate_default_value(self) -> None:
        """Validate default value against field type."""
        if self.field_type == FieldType.TEXT and not isinstance(self.default_value, str):
            raise ValueError("Default value for text field must be a string")
        
        elif self.field_type == FieldType.NUMBER and not isinstance(self.default_value, (int, float)):
            raise ValueError("Default value for number field must be a number")
        
        elif self.field_type == FieldType.BOOLEAN and not isinstance(self.default_value, bool):
            raise ValueError("Default value for boolean field must be a boolean")
        
        elif self.field_type == FieldType.SELECT:
            if self.default_value not in self.options:
                raise ValueError("Default value for select field must be one of the options")
        
        elif self.field_type == FieldType.MULTISELECT:
            if not isinstance(self.default_value, list):
                raise ValueError("Default value for multiselect field must be a list")
            for value in self.default_value:
                if value not in self.options:
                    raise ValueError("All default values for multiselect field must be in options")

    def add_option(self, option: str) -> None:
        """Add an option to select/multiselect fields."""
        if self.field_type not in [FieldType.SELECT, FieldType.MULTISELECT]:
            raise ValueError("Options can only be added to select or multiselect fields")
        
        if not option or not isinstance(option, str):
            raise ValueError("Option must be a non-empty string")
        
        if option not in self.options:
            self.options.append(option)
            self.updated_at = datetime.now()

    def remove_option(self, option: str) -> None:
        """Remove an option from select/multiselect fields."""
        if self.field_type not in [FieldType.SELECT, FieldType.MULTISELECT]:
            raise ValueError("Options can only be removed from select or multiselect fields")
        
        if option in self.options:
            self.options.remove(option)
            self.updated_at = datetime.now()

    def update_options(self, new_options: List[str]) -> None:
        """Update all options for select/multiselect fields."""
        if self.field_type not in [FieldType.SELECT, FieldType.MULTISELECT]:
            raise ValueError("Options can only be updated for select or multiselect fields")
        
        if not isinstance(new_options, list):
            raise ValueError("Options must be a list")
        
        if not new_options:
            raise ValueError("At least one option is required")
        
        for option in new_options:
            if not option or not isinstance(option, str):
                raise ValueError("All options must be non-empty strings")
        
        self.options = new_options
        self.updated_at = datetime.now()

    def validate_value(self, value: Any) -> bool:
        """Validate a value against this field configuration."""
        if value is None:
            return not self.is_required
        
        if self.field_type == FieldType.TEXT:
            return isinstance(value, str)
        
        elif self.field_type == FieldType.NUMBER:
            return isinstance(value, (int, float))
        
        elif self.field_type == FieldType.BOOLEAN:
            return isinstance(value, bool)
        
        elif self.field_type == FieldType.SELECT:
            return isinstance(value, str) and value in self.options
        
        elif self.field_type == FieldType.MULTISELECT:
            if not isinstance(value, list):
                return False
            return all(isinstance(v, str) and v in self.options for v in value)
        
        elif self.field_type == FieldType.DATE:
            return isinstance(value, datetime)
        
        return False

    def get_display_name(self) -> str:
        """Get formatted display name for UI."""
        display_name = self.field_name.replace('_', ' ').replace('-', ' ').title()
        if self.is_required:
            display_name += " *"
        return display_name

    def get_field_info(self) -> dict:
        """Get field information for UI rendering."""
        return {
            "name": self.field_name,
            "type": self.field_type.value,
            "display_name": self.get_display_name(),
            "options": self.options.copy() if self.options else [],
            "is_required": self.is_required,
            "default_value": self.default_value,
            "description": self.description,
            "validation_rules": self.validation_rules.copy()
        }