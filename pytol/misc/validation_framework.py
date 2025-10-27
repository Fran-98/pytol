"""
Unified Validation Framework for pytol library.

Consolidates the scattered validation functions (_validate_*) across files
into a coherent, extensible framework with consistent validation patterns.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Tuple, Optional, Union
from dataclasses import dataclass
from enum import Enum
import math


class ValidationSeverity(Enum):
    """Severity levels for validation issues."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ValidationIssue:
    """Represents a single validation issue."""
    severity: ValidationSeverity
    message: str
    field: Optional[str] = None
    value: Optional[Any] = None
    suggestion: Optional[str] = None
    code: Optional[str] = None


@dataclass
class ValidationResult:
    """Comprehensive validation result."""
    is_valid: bool
    issues: List[ValidationIssue]
    warnings_count: int
    errors_count: int
    critical_count: int
    
    @property
    def has_warnings(self) -> bool:
        return self.warnings_count > 0
    
    @property
    def has_errors(self) -> bool:
        return self.errors_count > 0
    
    @property
    def has_critical(self) -> bool:
        return self.critical_count > 0
    
    def get_issues_by_severity(self, severity: ValidationSeverity) -> List[ValidationIssue]:
        """Get all issues of a specific severity."""
        return [issue for issue in self.issues if issue.severity == severity]
    
    def get_summary(self) -> str:
        """Get a summary of validation results."""
        if self.is_valid:
            return "✓ Validation passed"
        
        parts = []
        if self.critical_count > 0:
            parts.append(f"{self.critical_count} critical")
        if self.errors_count > 0:
            parts.append(f"{self.errors_count} errors")
        if self.warnings_count > 0:
            parts.append(f"{self.warnings_count} warnings")
        
        return f"✗ Validation failed: {', '.join(parts)}"


class BaseValidator(ABC):
    """Abstract base class for all validators."""
    
    def __init__(self, strict: bool = False):
        """
        Initialize validator.
        
        Args:
            strict: If True, warnings are treated as errors
        """
        self.strict = strict
        self.issues: List[ValidationIssue] = []
    
    def add_issue(
        self, 
        severity: ValidationSeverity, 
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        suggestion: Optional[str] = None,
        code: Optional[str] = None
    ):
        """Add a validation issue."""
        issue = ValidationIssue(severity, message, field, value, suggestion, code)
        self.issues.append(issue)
    
    def validate(self, data: Any) -> ValidationResult:
        """
        Validate data and return comprehensive result.
        
        Args:
            data: Data to validate
            
        Returns:
            ValidationResult with all issues found
        """
        self.issues.clear()
        self._validate_impl(data)
        return self._build_result()
    
    @abstractmethod
    def _validate_impl(self, data: Any):
        """Implement specific validation logic."""
        pass
    
    def _build_result(self) -> ValidationResult:
        """Build the final validation result."""
        warnings = sum(1 for issue in self.issues if issue.severity == ValidationSeverity.WARNING)
        errors = sum(1 for issue in self.issues if issue.severity == ValidationSeverity.ERROR)
        critical = sum(1 for issue in self.issues if issue.severity == ValidationSeverity.CRITICAL)
        
        # In strict mode, warnings become errors
        if self.strict:
            errors += warnings
            warnings = 0
        
        is_valid = errors == 0 and critical == 0
        
        return ValidationResult(
            is_valid=is_valid,
            issues=self.issues.copy(),
            warnings_count=warnings,
            errors_count=errors,
            critical_count=critical
        )


class PositionValidator(BaseValidator):
    """Validator for 3D positions."""
    
    def __init__(self, strict: bool = False, bounds: Optional[Tuple[float, float, float, float, float, float]] = None):
        """
        Initialize position validator.
        
        Args:
            strict: If True, warnings treated as errors
            bounds: Optional bounds as (min_x, max_x, min_y, max_y, min_z, max_z)
        """
        super().__init__(strict)
        self.bounds = bounds
    
    def _validate_impl(self, data: Any):
        """Validate position data."""
        if not isinstance(data, (tuple, list)):
            self.add_issue(
                ValidationSeverity.CRITICAL,
                f"Position must be tuple or list, got {type(data).__name__}",
                field="position",
                value=data,
                suggestion="Use (x, y, z) tuple format"
            )
            return
        
        if len(data) != 3:
            self.add_issue(
                ValidationSeverity.CRITICAL,
                f"Position must have exactly 3 coordinates, got {len(data)}",
                field="position",
                value=data,
                suggestion="Use (x, y, z) format with 3 coordinates"
            )
            return
        
        x, y, z = data
        
        # Check if coordinates are numeric
        for i, (coord, name) in enumerate([(x, 'x'), (y, 'y'), (z, 'z')]):
            if not isinstance(coord, (int, float)):
                self.add_issue(
                    ValidationSeverity.ERROR,
                    f"Coordinate {name} must be numeric, got {type(coord).__name__}",
                    field=f"position.{name}",
                    value=coord,
                    suggestion="Use numeric values for coordinates"
                )
                continue
            
            if not math.isfinite(coord):
                self.add_issue(
                    ValidationSeverity.ERROR,
                    f"Coordinate {name} must be finite, got {coord}",
                    field=f"position.{name}",
                    value=coord,
                    suggestion="Use finite numeric values"
                )
        
        # Check bounds if provided
        if self.bounds and all(isinstance(coord, (int, float)) and math.isfinite(coord) for coord in data):
            min_x, max_x, min_y, max_y, min_z, max_z = self.bounds
            
            if not (min_x <= x <= max_x):
                self.add_issue(
                    ValidationSeverity.WARNING,
                    f"X coordinate {x} outside bounds [{min_x}, {max_x}]",
                    field="position.x",
                    value=x,
                    suggestion=f"Use X coordinate between {min_x} and {max_x}"
                )
            
            if not (min_y <= y <= max_y):
                self.add_issue(
                    ValidationSeverity.WARNING,
                    f"Y coordinate {y} outside bounds [{min_y}, {max_y}]",
                    field="position.y",
                    value=y,
                    suggestion=f"Use Y coordinate between {min_y} and {max_y}"
                )
            
            if not (min_z <= z <= max_z):
                self.add_issue(
                    ValidationSeverity.WARNING,
                    f"Z coordinate {z} outside bounds [{min_z}, {max_z}]",
                    field="position.z",
                    value=z,
                    suggestion=f"Use Z coordinate between {min_z} and {max_z}"
                )


class NumericValidator(BaseValidator):
    """Validator for numeric values with range and type checking."""
    
    def __init__(
        self, 
        strict: bool = False,
        min_value: Optional[Union[int, float]] = None,
        max_value: Optional[Union[int, float]] = None,
        allow_negative: bool = True,
        allow_zero: bool = True,
        integer_only: bool = False
    ):
        super().__init__(strict)
        self.min_value = min_value
        self.max_value = max_value
        self.allow_negative = allow_negative
        self.allow_zero = allow_zero
        self.integer_only = integer_only
    
    def _validate_impl(self, data: Any):
        """Validate numeric data."""
        if not isinstance(data, (int, float)):
            self.add_issue(
                ValidationSeverity.ERROR,
                f"Value must be numeric, got {type(data).__name__}",
                value=data,
                suggestion="Use a numeric value (int or float)"
            )
            return
        
        if not math.isfinite(data):
            self.add_issue(
                ValidationSeverity.ERROR,
                f"Value must be finite, got {data}",
                value=data,
                suggestion="Use a finite numeric value"
            )
            return
        
        if self.integer_only and not isinstance(data, int):
            if not data.is_integer():
                self.add_issue(
                    ValidationSeverity.WARNING,
                    f"Expected integer value, got float {data}",
                    value=data,
                    suggestion="Use an integer value"
                )
        
        if not self.allow_negative and data < 0:
            self.add_issue(
                ValidationSeverity.ERROR,
                f"Negative values not allowed, got {data}",
                value=data,
                suggestion="Use a non-negative value"
            )
        
        if not self.allow_zero and data == 0:
            self.add_issue(
                ValidationSeverity.ERROR,
                "Zero value not allowed",
                value=data,
                suggestion="Use a non-zero value"
            )
        
        if self.min_value is not None and data < self.min_value:
            self.add_issue(
                ValidationSeverity.WARNING,
                f"Value {data} below minimum {self.min_value}",
                value=data,
                suggestion=f"Use value >= {self.min_value}"
            )
        
        if self.max_value is not None and data > self.max_value:
            self.add_issue(
                ValidationSeverity.WARNING,
                f"Value {data} above maximum {self.max_value}",
                value=data,
                suggestion=f"Use value <= {self.max_value}"
            )


class ListValidator(BaseValidator):
    """Validator for lists with size and element validation."""
    
    def __init__(
        self,
        strict: bool = False,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None,
        element_validator: Optional[BaseValidator] = None,
        allow_empty: bool = True,
        unique_elements: bool = False
    ):
        super().__init__(strict)
        self.min_length = min_length
        self.max_length = max_length
        self.element_validator = element_validator
        self.allow_empty = allow_empty
        self.unique_elements = unique_elements
    
    def _validate_impl(self, data: Any):
        """Validate list data."""
        if not isinstance(data, (list, tuple)):
            self.add_issue(
                ValidationSeverity.ERROR,
                f"Expected list or tuple, got {type(data).__name__}",
                value=data,
                suggestion="Use a list or tuple"
            )
            return
        
        length = len(data)
        
        if not self.allow_empty and length == 0:
            self.add_issue(
                ValidationSeverity.ERROR,
                "Empty list not allowed",
                value=data,
                suggestion="Provide at least one element"
            )
        
        if self.min_length is not None and length < self.min_length:
            self.add_issue(
                ValidationSeverity.WARNING,
                f"List length {length} below minimum {self.min_length}",
                value=data,
                suggestion=f"Provide at least {self.min_length} elements"
            )
        
        if self.max_length is not None and length > self.max_length:
            self.add_issue(
                ValidationSeverity.WARNING,
                f"List length {length} above maximum {self.max_length}",
                value=data,
                suggestion=f"Use at most {self.max_length} elements"
            )
        
        if self.unique_elements and length > len(set(data)):
            self.add_issue(
                ValidationSeverity.WARNING,
                "List contains duplicate elements",
                value=data,
                suggestion="Remove duplicate elements"
            )
        
        # Validate individual elements
        if self.element_validator:
            for i, element in enumerate(data):
                element_result = self.element_validator.validate(element)
                for issue in element_result.issues:
                    # Modify the field to include list index
                    field = f"[{i}]" if issue.field is None else f"[{i}].{issue.field}"
                    self.add_issue(
                        issue.severity,
                        issue.message,
                        field=field,
                        value=issue.value,
                        suggestion=issue.suggestion,
                        code=issue.code
                    )


class DictValidator(BaseValidator):
    """Validator for dictionaries with required fields and value validation."""
    
    def __init__(
        self,
        strict: bool = False,
        required_fields: Optional[List[str]] = None,
        optional_fields: Optional[List[str]] = None,
        field_validators: Optional[Dict[str, BaseValidator]] = None,
        allow_extra_fields: bool = True
    ):
        super().__init__(strict)
        self.required_fields = required_fields or []
        self.optional_fields = optional_fields or []
        self.field_validators = field_validators or {}
        self.allow_extra_fields = allow_extra_fields
    
    def _validate_impl(self, data: Any):
        """Validate dictionary data."""
        if not isinstance(data, dict):
            self.add_issue(
                ValidationSeverity.ERROR,
                f"Expected dictionary, got {type(data).__name__}",
                value=data,
                suggestion="Use a dictionary"
            )
            return
        
        # Check required fields
        for field in self.required_fields:
            if field not in data:
                self.add_issue(
                    ValidationSeverity.ERROR,
                    f"Required field '{field}' missing",
                    field=field,
                    suggestion=f"Add '{field}' field to dictionary"
                )
        
        # Check for extra fields
        if not self.allow_extra_fields:
            allowed_fields = set(self.required_fields + self.optional_fields)
            for field in data:
                if field not in allowed_fields:
                    self.add_issue(
                        ValidationSeverity.WARNING,
                        f"Unexpected field '{field}'",
                        field=field,
                        value=data[field],
                        suggestion="Remove unexpected field or add to optional_fields"
                    )
        
        # Validate field values
        for field, validator in self.field_validators.items():
            if field in data:
                field_result = validator.validate(data[field])
                for issue in field_result.issues:
                    # Modify the field to include parent field
                    issue_field = field if issue.field is None else f"{field}.{issue.field}"
                    self.add_issue(
                        issue.severity,
                        issue.message,
                        field=issue_field,
                        value=issue.value,
                        suggestion=issue.suggestion,
                        code=issue.code
                    )


class CompositeValidator(BaseValidator):
    """Validator that combines multiple validators."""
    
    def __init__(self, validators: List[BaseValidator], strict: bool = False):
        super().__init__(strict)
        self.validators = validators
    
    def _validate_impl(self, data: Any):
        """Run all validators on the data."""
        for validator in self.validators:
            result = validator.validate(data)
            self.issues.extend(result.issues)


def create_mission_validator() -> CompositeValidator:
    """Create a validator for mission data structures."""
    return CompositeValidator([
        DictValidator(
            required_fields=['map_name', 'objectives'],
            optional_fields=['units', 'weather', 'time'],
            field_validators={
                'objectives': ListValidator(
                    min_length=1,
                    element_validator=DictValidator(
                        required_fields=['type', 'position'],
                        field_validators={
                            'position': PositionValidator()
                        }
                    )
                )
            }
        )
    ])


def create_unit_validator() -> CompositeValidator:
    """Create a validator for unit data structures."""
    return CompositeValidator([
        DictValidator(
            required_fields=['type', 'position', 'heading'],
            optional_fields=['fuel', 'ammo', 'skill'],
            field_validators={
                'position': PositionValidator(),
                'heading': NumericValidator(min_value=0, max_value=360),
                'fuel': NumericValidator(min_value=0, max_value=1),
                'skill': NumericValidator(min_value=0, max_value=1)
            }
        )
    ])


def create_airbase_validator() -> CompositeValidator:
    """Create a validator for airbase data structures."""
    return CompositeValidator([
        DictValidator(
            required_fields=['position', 'runway_heading', 'runway_length'],
            optional_fields=['elevation', 'facilities'],
            field_validators={
                'position': PositionValidator(),
                'runway_heading': NumericValidator(min_value=0, max_value=360),
                'runway_length': NumericValidator(min_value=500, max_value=5000, allow_negative=False),
                'elevation': NumericValidator(min_value=-500, max_value=5000)
            }
        )
    ])


def validate_data(data: Any, validator: BaseValidator, print_results: bool = True) -> ValidationResult:
    """
    Convenience function to validate data and optionally print results.
    
    Args:
        data: Data to validate
        validator: Validator to use
        print_results: Whether to print validation results
        
    Returns:
        ValidationResult
    """
    result = validator.validate(data)
    
    if print_results:
        print(result.get_summary())
        
        if result.issues:
            print("\nValidation Issues:")
            for issue in result.issues:
                icon = {
                    ValidationSeverity.INFO: "ℹ",
                    ValidationSeverity.WARNING: "⚠",
                    ValidationSeverity.ERROR: "✗",
                    ValidationSeverity.CRITICAL: "🔥"
                }.get(issue.severity, "?")
                
                field_info = f" [{issue.field}]" if issue.field else ""
                print(f"  {icon} {issue.severity.value.upper()}{field_info}: {issue.message}")
                
                if issue.suggestion:
                    print(f"    💡 Suggestion: {issue.suggestion}")
    
    return result