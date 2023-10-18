from __future__ import annotations

import enum
import re
from typing import Dict, Generic, List, Optional, Sequence, Tuple

from dbt_semantic_interfaces.enum_extension import assert_values_exhausted
from dbt_semantic_interfaces.protocols import (
    SemanticManifest,
    SemanticManifestT,
    SemanticModel,
)
from dbt_semantic_interfaces.references import (
    ElementReference,
    MetricModelReference,
    SemanticModelElementReference,
    SemanticModelReference,
)
from dbt_semantic_interfaces.type_enums import EntityType, TimeGranularity
from dbt_semantic_interfaces.validations.validator_helpers import (
    FileContext,
    MetricContext,
    SemanticManifestValidationRule,
    SemanticModelContext,
    SemanticModelElementContext,
    SemanticModelElementType,
    ValidationContext,
    ValidationError,
    ValidationIssue,
    validate_safely,
)


@enum.unique
class MetricFlowReservedKeywords(enum.Enum):
    """Enumeration of reserved keywords with helper for accessing the reason they are reserved."""

    METRIC_TIME = "metric_time"
    MF_INTERNAL_UUID = "mf_internal_uuid"

    @staticmethod
    def get_reserved_reason(keyword: MetricFlowReservedKeywords) -> str:
        """Get the reason a given keyword is reserved. Guarantees an exhaustive switch."""
        if keyword is MetricFlowReservedKeywords.METRIC_TIME:
            return (
                "Used as the query input for creating time series metrics from measures with "
                "different time dimension names."
            )
        elif keyword is MetricFlowReservedKeywords.MF_INTERNAL_UUID:
            return "Used internally to reference a column that has a uuid generated by MetricFlow."
        else:
            assert_values_exhausted(keyword)


class UniqueAndValidNameRule(SemanticManifestValidationRule[SemanticManifestT], Generic[SemanticManifestT]):
    """Check that names are unique and valid.

    * Names of elements in semantic models are unique / valid within the semantic model.
    * Names of semantic models, dimension sets and metric sets in the model are unique / valid.
    """

    # name must start with a lower case letter
    # name must end with a number or lower case letter
    # name may include lower case letters, numbers, and underscores
    # name may not contain dunders (two sequential underscores
    NAME_REGEX = re.compile(r"\A[a-z]((?!__)[a-z0-9_])*[a-z0-9]\Z")

    @staticmethod
    def check_valid_name(name: str, context: Optional[ValidationContext] = None) -> List[ValidationIssue]:  # noqa: D
        issues: List[ValidationIssue] = []

        if not UniqueAndValidNameRule.NAME_REGEX.match(name):
            issues.append(
                ValidationError(
                    context=context,
                    message=f"Invalid name `{name}` - names may only contain lower case letters, numbers, "
                    f"and underscores. Additionally, names must start with a lower case letter, cannot end "
                    f"with an underscore, cannot contain dunders (double underscores, or __), and must be "
                    f"at least 2 characters long.",
                )
            )
        if name.upper() in TimeGranularity.list_names():
            issues.append(
                ValidationError(
                    context=context,
                    message=f"Invalid name `{name}` - names cannot match reserved time granularity keywords "
                    f"({TimeGranularity.list_names()})",
                )
            )
        if name.lower() in {reserved_name.value for reserved_name in MetricFlowReservedKeywords}:
            reason = MetricFlowReservedKeywords.get_reserved_reason(MetricFlowReservedKeywords(name.lower()))
            issues.append(
                ValidationError(
                    context=context,
                    message=f"Invalid name `{name}` - this name is reserved by MetricFlow. Reason: {reason}",
                )
            )
        return issues

    @staticmethod
    @validate_safely(whats_being_done="checking semantic model sub element names are unique")
    def _validate_semantic_model_elements(semantic_model: SemanticModel) -> List[ValidationIssue]:
        issues: List[ValidationIssue] = []
        element_info_tuples: List[Tuple[ElementReference, str, ValidationContext]] = []

        if semantic_model.measures:
            for measure in semantic_model.measures:
                element_info_tuples.append(
                    (
                        measure.reference,
                        "measure",
                        SemanticModelElementContext(
                            file_context=FileContext.from_metadata(metadata=semantic_model.metadata),
                            semantic_model_element=SemanticModelElementReference(
                                semantic_model_name=semantic_model.name, element_name=measure.name
                            ),
                            element_type=SemanticModelElementType.MEASURE,
                        ),
                    )
                )
        if semantic_model.entities:
            for entity in semantic_model.entities:
                element_info_tuples.append(
                    (
                        entity.reference,
                        "entity",
                        SemanticModelElementContext(
                            file_context=FileContext.from_metadata(metadata=semantic_model.metadata),
                            semantic_model_element=SemanticModelElementReference(
                                semantic_model_name=semantic_model.name, element_name=entity.name
                            ),
                            element_type=SemanticModelElementType.ENTITY,
                        ),
                    )
                )
        if semantic_model.dimensions:
            for dimension in semantic_model.dimensions:
                element_info_tuples.append(
                    (
                        dimension.reference,
                        "dimension",
                        SemanticModelElementContext(
                            file_context=FileContext.from_metadata(metadata=semantic_model.metadata),
                            semantic_model_element=SemanticModelElementReference(
                                semantic_model_name=semantic_model.name, element_name=dimension.name
                            ),
                            element_type=SemanticModelElementType.DIMENSION,
                        ),
                    )
                )
        name_to_type: Dict[ElementReference, str] = {}

        for name, _type, context in element_info_tuples:
            if name in name_to_type:
                issues.append(
                    ValidationError(
                        context=context,
                        message=f"In semantic model `{semantic_model.name}`, can't use name `{name.element_name}` for "
                        f"a {_type} when it was already used for a {name_to_type[name]}",
                    )
                )
            else:
                name_to_type[name] = _type

        for name, _, context in element_info_tuples:
            issues += UniqueAndValidNameRule.check_valid_name(name=name.element_name, context=context)

        return issues

    @staticmethod
    @validate_safely(whats_being_done="checking model top level element names are sufficiently unique")
    def _validate_top_level_objects(semantic_manifest: SemanticManifest) -> List[ValidationIssue]:
        """Checks names of objects that are not nested."""
        object_info_tuples = []
        issues: List[ValidationIssue] = []
        if semantic_manifest.semantic_models:
            for semantic_model in semantic_manifest.semantic_models:
                context = SemanticModelContext(
                    file_context=FileContext.from_metadata(metadata=semantic_model.metadata),
                    semantic_model=SemanticModelReference(semantic_model_name=semantic_model.name),
                )
                object_info_tuples.append((semantic_model.name, "semantic model", context))
                issues += UniqueAndValidNameRule.check_valid_name(name=semantic_model.name, context=context)

        name_to_type: Dict[str, str] = {}
        for name, type_, context in object_info_tuples:
            if name in name_to_type:
                issues.append(
                    ValidationError(
                        context=context,
                        message=f"Can't use name `{name}` for a {type_} when it was already used for a "
                        f"{name_to_type[name]}",
                    )
                )
            else:
                name_to_type[name] = type_

        if semantic_manifest.metrics:
            metric_names = set()
            for metric in semantic_manifest.metrics:
                metric_context = MetricContext(
                    file_context=FileContext.from_metadata(metadata=metric.metadata),
                    metric=MetricModelReference(metric_name=metric.name),
                )
                issues += UniqueAndValidNameRule.check_valid_name(name=metric.name, context=metric_context)
                if metric.name in metric_names:
                    issues.append(
                        ValidationError(
                            context=metric_context,
                            message=f"Can't use name `{metric.name}` for a metric when it was already used for "
                            "a metric",
                        )
                    )
                else:
                    metric_names.add(metric.name)

        return issues

    @staticmethod
    @validate_safely(whats_being_done="running model validation ensuring elements have adequately unique names")
    def validate_manifest(semantic_manifest: SemanticManifestT) -> Sequence[ValidationIssue]:  # noqa: D
        issues = []
        issues += UniqueAndValidNameRule._validate_top_level_objects(semantic_manifest=semantic_manifest)

        for semantic_model in semantic_manifest.semantic_models:
            issues += UniqueAndValidNameRule._validate_semantic_model_elements(semantic_model=semantic_model)

        return issues


class PrimaryEntityDimensionPairs(SemanticManifestValidationRule[SemanticManifestT], Generic[SemanticManifestT]):
    """All dimension + primary entity pairs across the semantic manifest are unique."""

    @staticmethod
    @validate_safely(
        whats_being_done="validating the semantic model doesn't have dimension + primary entity pair conflicts"
    )
    def _check_semantic_model(  # noqa: D
        semantic_model: SemanticModel, known_pairings: Dict[str, Dict[str, str]]
    ) -> Sequence[ValidationIssue]:
        issues: List[ValidationIssue] = []

        primary_entity = semantic_model.primary_entity
        if primary_entity is None:
            for entity in semantic_model.entities:
                if entity.type is EntityType.PRIMARY:
                    primary_entity = entity.name
                    break

        # If primary entity is still none, return early. It's an issue,
        # but not the subject of this validation. This is handled by
        # PrimaryEntityRule
        if primary_entity is None:
            return issues

        safe = False
        if known_pairings.get(primary_entity) is None:
            known_pairings[primary_entity] = {}
            safe = True

        for dimension in semantic_model.dimensions:
            if safe or known_pairings[primary_entity].get(dimension.name) is None:
                known_pairings[primary_entity][dimension.name] = semantic_model.name
            else:
                issues.append(
                    ValidationError(
                        context=SemanticModelElementContext(
                            file_context=FileContext.from_metadata(metadata=semantic_model.metadata),
                            semantic_model_element=SemanticModelElementReference(
                                semantic_model_name=semantic_model.name, element_name=dimension.name
                            ),
                            element_type=SemanticModelElementType.DIMENSION,
                        ),
                        message="Duplicate dimension + primary entity pairing detected, dimension + primary entity "
                        f"pairings must be unique. Semantic model `{semantic_model.name}` has a primary entity of "
                        f"`{primary_entity}` and dimension `{dimension.name}`, but this pairing is already in use on "
                        f"semantic model `{known_pairings[primary_entity][dimension.name]}`.",
                    )
                )

        return issues

    @staticmethod
    @validate_safely(whats_being_done="validating there are no duplicate dimension primary entity pairs")
    def validate_manifest(semantic_manifest: SemanticManifestT) -> Sequence[ValidationIssue]:  # noqa: D
        issues = []
        known_pairings: Dict[str, Dict[str, str]] = {}
        for semantic_model in semantic_manifest.semantic_models:
            issues += PrimaryEntityDimensionPairs._check_semantic_model(
                semantic_model=semantic_model, known_pairings=known_pairings
            )

        return issues
