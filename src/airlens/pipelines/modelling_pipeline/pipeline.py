from kedro.pipeline import Pipeline, node
from .nodes import run_gwr_model, run_mgwr_model
from .nodes import analyze_gwr_significance
from .nodes import plot_gwr_coefficients_from_summary
from .nodes import plot_gwr_diagnostics

def create_pipeline(**kwargs):
    return Pipeline([
        ## FIT GWR MODEL
        node(
            func=run_gwr_model,
            inputs={
                "air_gdf":"modelling_gdf",
                "pollutant_column":"params:pollutant",
                "crs_metric":"params:crs_metric"
            },
            outputs="gwr_model",
            name="run_gwr"
        ),
        ## ANALYZE COEFFICIENTS SIGNIFICANCE 
        node(
            func=analyze_gwr_significance,
            inputs={
                "gwr_results":"gwr_model",
                "air_gdf":"modelling_gdf",
                "pollutant_column":"params:pollutant"
            },
            outputs="gwr_significance",
            name="gwr_coeffs_significance"
        ),
        ## PLOT COEFFICIENTS BY SIGNIFICANCE
        node(
            func=plot_gwr_coefficients_from_summary,
            inputs="gwr_significance",
            outputs="gwr_significance_maps",
            name="gwr_significance_maps"
        ),
        ## DIAGNOSTICS GWR
        node(
            func=plot_gwr_diagnostics,
            inputs={
                "air_gdf":"modelling_gdf",
                "gwr_results":"gwr_model",
                "pollutant_column":"params:pollutant",
                "crs_latlon":"params:crs_latlon",
                "crs_metric":"params:crs_metric"
            },
            outputs="gwr_diagnostics_plot",
            name="gwr_diagnostics"
        ),



        ## FIT MGWR MODEL
        node(
            func=run_mgwr_model,
            inputs={
                "air_gdf":"modelling_gdf",
                "pollutant_column":"params:pollutant",
                "crs_metric":"params:crs_metric"
            },
            outputs="mgwr_model",
            name="run_mgwr"
        ),

        ## REUSE GWR FUNCTION FOR MGWR DIAGNOSTICS AND PLOTS
        node(
            func=analyze_gwr_significance,
            inputs={
                "gwr_results":"mgwr_model",
                "air_gdf":"modelling_gdf",
                "pollutant_column":"params:pollutant"
            },
            outputs="mgwr_significance",
            name="mgwr_coeffs_significance"
        ),
        node(
            func=plot_gwr_coefficients_from_summary,
            inputs="mgwr_significance",
            outputs="mgwr_significance_maps",
            name="mgwr_significance_maps"
        ),
        node(
            func=plot_gwr_diagnostics,
            inputs={
                "air_gdf":"modelling_gdf",
                "gwr_results":"mgwr_model",
                "pollutant_column":"params:pollutant",
                "crs_latlon":"params:crs_latlon",
                "crs_metric":"params:crs_metric"
            },
            outputs="mgwr_diagnostics_plot",
            name="mgwr_diagnostics"
        )
    ])




