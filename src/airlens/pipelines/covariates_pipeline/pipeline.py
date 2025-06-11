from kedro.pipeline import Pipeline, node
from .nodes import combine_covariates
from .nodes import covariates_filtering
from .nodes import plot_correlation_matrix
from .nodes import plot_variable_distributions
from .nodes import reduce_multicollinearity

def create_pipeline(**kwargs):
    return Pipeline([
        ## MERGE AIR AND COVARIATES IN A UNIQUE GDF
        node(
            func=combine_covariates,
            inputs={
                "air_gdf":"ED_aggregated_air",
                "traffic_gdf":"air_traffic_gdf",
                "building_gdf":"air_build_morph_gdf",
                "road_gdf":"air_road_gdf",
                "street_profile_gdf":"unit_street_profile",
                "tree_gdf":"air_trees_features",
                "landuse_gdf":"landuse_perc_per_unit"
                },
            outputs="merged_covs_air",
            name="merged_covariates"
        ),
        ## FILTER COVARIATES BASED ON CORRELATION WITH POLLUTANT
        ## AND COEFFICIENT OF VARIABILITY
        node(
            func=covariates_filtering,
            inputs={
                "cov_gdf":"merged_covs_air",
                "pollutant_column":"params:pollutant"
            },
            outputs="filtered_covs_air",
            name="filtering"
        ),
        ## PLOT CORRELATION MATRIX
        node(
            func=plot_correlation_matrix,
            inputs={
                "df":"filtered_covs_air",
                "target":"params:pollutant"
            },
            outputs="plot_corr_matrix",
            name="corr_matrix"
        ),
        ## PLOT DISTRIBUTION OF VARIABLES
        node(
            func=plot_variable_distributions,
            inputs={
                "df":"filtered_covs_air",
                "target":"params:pollutant"
            },
            outputs="plot_hists",
            name="hist_plot"
        ),
        ## REDUCE MULTICOLLINEARITY WITH VIF
        node(
            func=reduce_multicollinearity,
            inputs={
                "df":"filtered_covs_air",
                "target_pollutant":"params:pollutant"
            },
            outputs="modelling_gdf",
            name="vif"
        )
    ])




