from kedro.pipeline import Pipeline, node
from .nodes import viz_pollutant
from .nodes import hotspot_analysis


def create_pipeline(**kwargs):
    return Pipeline([
        ## VIZ CONCENTRATION BY UNIT
        node(
            func=viz_pollutant,
            inputs=[
                "ED_aggregated_air",
                "params:pollutant"
                ],
            outputs="concentration_plot",
            name="viz_concentration"
        ),
        ## PERFORM LOCAL MORAN'S I ANALYSIS
        node(
            func=hotspot_analysis,
            inputs=[
                "ED_aggregated_air",
                "params:pollutant",
                "params:crs_metric"
            ],
            outputs=["scatter_lisa_plot", "local_morans_maps", "lisa_summary"],
            name="local_hotspot"
        )
    ])

