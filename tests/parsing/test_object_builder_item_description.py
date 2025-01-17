import logging

import pytest

from dbt_semantic_interfaces.errors import InvalidQuerySyntax
from dbt_semantic_interfaces.parsing.text_input.ti_processor import (
    ObjectBuilderTextProcessor,
)
from dbt_semantic_interfaces.parsing.text_input.valid_method import (
    ConfiguredValidMethodMapping,
)

logger = logging.getLogger(__name__)


def test_valid_object_builder_items() -> None:  # noqa: D
    text_processor = ObjectBuilderTextProcessor()

    valid_items = (
        "Dimension('listing__created_at', entity_path=['host'])",
        "Dimension('listing__created_at', entity_path=['host']).grain('day').date_part('day')",
        "TimeDimension('listing__created_at', time_granularity_name='day', entity_path=['host'], date_part_name='day')",
        "Entity('listing__created_at', entity_path=['host'])",
        "Metric('bookings', group_by=['listing__created_at'])",
    )
    for valid_item in valid_items:
        logger.info(f"Checking {valid_item=}")
        text_processor.get_description(valid_item, ConfiguredValidMethodMapping.DEFAULT_MAPPING)


def test_invalid_object_builder_items() -> None:  # noqa: D
    text_processor = ObjectBuilderTextProcessor()

    invalid_items = (
        "Dimension('listing__created_at').grain('invalid')",
        "Dimension('listing__created_at').date_part('invalid')",
        "TimeDimension('listing__created_at', 'invalid', 'day')",
        "TimeDimension('listing__created_at', 'day', date_part_name='invalid')",
        "TimeDimension('listing__created_at', 'day', date_part_name='month').grain('month')",
        "TimeDimension('listing__created_at', 'day', date_part_name='month').date_part('month')",
        "Entity('listing__created_at').grain('day')",
        "Entity('listing__created_at').date_part('day')",
        "Metric('bookings').grain('day')",
        "Metric('bookings').date_part('day')",
    )
    for invalid_item in invalid_items:
        with pytest.raises(InvalidQuerySyntax):
            logger.info(f"Checking {invalid_item=}")
            text_processor.get_description(invalid_item, ConfiguredValidMethodMapping.DEFAULT_MAPPING)
