from kedro.pipeline import Pipeline, node
from .nodes import run_gwr_model, run_mgwr_model
from .nodes import analyze_gwr_significance
from .nodes import plot_gwr_coefficients_from_summary
from .nodes import plot_gwr_diagnostics
from .nodes import GWR_local_R2
from .nodes import gwr_with_random_search

def create_pipeline(**kwargs):
    return Pipeline([
        ## FIT GWR MODEL
        node(
            func=run_gwr_model,
            inputs={
                "air_gdf":"modelling_gdf",
                "pollutant_column":"params:pollutant",
                "kernel": "params:gwr_kernel",
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
        ## GWR LOCAL R2
        node(
            func=GWR_local_R2,
            inputs={
                "modelling_gdf": "modelling_gdf",
                "gwr_results":"gwr_model"
            },
            outputs="gwr_localR2",
            name="localR2"
        ),



        ## FIT MGWR MODEL
        node(
            func=run_mgwr_model,
            inputs={
                "air_gdf":"modelling_gdf",
                "pollutant_column":"params:pollutant",
                "kernel": "params:mgwr_kernel",
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
        ),

        ## GWR with RANDOM SEARCH OF BEST COVARIATES COMBINATIONS
        node(
            func=gwr_with_random_search,
            inputs={
                # may use gdf before VIF removal (`filtered_covs_air`), 
                # to eval all combinations - 
                # multicollinearity implicitely accounted using AICc
                # but inspection afterwards must be done
                "modelling_gdf":"filtered_covs_air", 
                "target_pollutant":"params:pollutant",
                "model_type":"params:test_model_1", ## GWR
                "N_search":"params:n_random_search",
                "kernel":"params:gwr_kernel",
                "crs_metric":"params:crs_metric"
            },
            outputs="gwr_random_search",
            name="gwr_random_search"
        ),

        ## MGWR with RANDOM SEARCH
        node(
            func=gwr_with_random_search,
            inputs={
                "modelling_gdf":"filtered_covs_air", 
                "target_pollutant":"params:pollutant",
                "model_type":"params:test_model_2", ## MGWR
                "N_search":"params:n_random_search",
                "kernel":"params:mgwr_kernel",
                "crs_metric":"params:crs_metric"
            },
            outputs="mgwr_random_search",
            name="mgwr_random_search"
        )
    ])


## TODO: RE-CHECK CORRECTNESS OF MGWR PLOTS

## ALSO: DETERMINE BEST CHOICE FOR KERNEL FOR NO2 --> USED EXPONENTIAL, MAYBE BISQUARE BETTER? --> chosen via AIC/AICc

## TODO: RUN EXHAUSTIVE SEARCH FOR BEST MODEL???
## TODO: ADD OPTIONAL SPATIAL CROSS VALIDATION FOR GWR 
# (mgwr implementation does not have predict attribute duw to multiple bandwidth complexity)

## TODO: comment input and outputs for all functions, across all pipelines