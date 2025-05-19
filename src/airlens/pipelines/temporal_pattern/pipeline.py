from kedro.pipeline import Pipeline, node
from .nodes import temporal_trends


def create_pipeline(**kwargs):
    return Pipeline([
        ## SIMPLE VISUALIZATIONS OF TEMPORAL PATTERNS
        node(
            func=temporal_trends,
            inputs=[
                "cleaned_air_gdf",
                "params:pollutant",
                "params:timestamp_column"
            ],
            outputs="plot_temporal_pattern",
            name="viz_temp_pattern"
        )
    ])

