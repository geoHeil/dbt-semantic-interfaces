from typing import Dict

from dbt_semantic_interfaces.implementations.semantic_manifest import (
    PydanticSemanticManifest,
)
from dbt_semantic_interfaces.transformations.metric_time_granularity import (
    SetMetricTimeGranularityRule,
)
from dbt_semantic_interfaces.transformations.semantic_manifest_transformer import (
    PydanticSemanticManifestTransformer,
)
from dbt_semantic_interfaces.transformations.transform_rule import (
    SemanticManifestTransformRule,
)
from dbt_semantic_interfaces.type_enums import TimeGranularity


class SliceNamesRule(SemanticManifestTransformRule):
    """Slice the names of semantic model elements in a model.

    NOTE: specifically for testing
    """

    @staticmethod
    def transform_model(semantic_manifest: PydanticSemanticManifest) -> PydanticSemanticManifest:  # noqa: D
        for semantic_model in semantic_manifest.semantic_models:
            semantic_model.name = semantic_model.name[:3]
        return semantic_manifest


def test_can_configure_model_transform_rules(  # noqa: D
    simple_semantic_manifest__with_primary_transforms: PydanticSemanticManifest,
) -> None:
    pre_model = simple_semantic_manifest__with_primary_transforms
    assert not all(len(x.name) == 3 for x in pre_model.semantic_models)

    # Confirms that a custom transformation works `for ModelTransformer.transform`
    rules = [SliceNamesRule()]
    transformed_model = PydanticSemanticManifestTransformer.transform(pre_model, ordered_rule_sequences=(rules,))
    assert all(len(x.name) == 3 for x in transformed_model.semantic_models)


def test_set_time_granularity_rule(  # noqa: D
    simple_semantic_manifest__with_primary_transforms: PydanticSemanticManifest,
) -> None:
    pre_model = simple_semantic_manifest__with_primary_transforms

    metric_exists_without_time_granularity = False
    configured_default_granularities: Dict[str, TimeGranularity] = {}
    for metric in pre_model.metrics:
        if metric.time_granularity:
            configured_default_granularities[metric.name] = metric.time_granularity
            metric_exists_without_time_granularity = True

    assert (
        pre_model.metrics and metric_exists_without_time_granularity
    ), "If there are no metrics without a configured time_granularity, this tests nothing."

    rules = [SetMetricTimeGranularityRule()]
    transformed_model = PydanticSemanticManifestTransformer.transform(pre_model, ordered_rule_sequences=(rules,))

    for metric in transformed_model.metrics:
        assert metric.time_granularity, f"No time_granularity set in transformation for metric '{metric.name}'"
        if metric.name in configured_default_granularities:
            assert (
                metric.time_granularity == configured_default_granularities[metric.name]
            ), f"Time granularity was unexpected changed during transformation for metric '{metric.name}"
        if metric.name == "monthly_times_yearly_bookings":
            assert metric.time_granularity == TimeGranularity.YEAR
