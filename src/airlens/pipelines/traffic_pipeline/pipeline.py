from kedro.pipeline import Pipeline, node
from .nodes import get_traffic
from .nodes import add_georef
from .nodes import aggregate_traffic_spatially
from .nodes import plot_avg_traffic_by_site
from .nodes import viz_traffic_and_pollutant

def create_pipeline(**kwargs):
    return Pipeline([
        ## GET/PARSE TRAFFIC DATA
        node(
            func=get_traffic,
            inputs={
                "traffic_df":"raw_traffic_data",
                "traffic_timestamp":"params:traffic_timestamp_col",
                "sites_ID":"params:traffic_sites_ID",
                "count_column":"params:traffic_count_col",
                "timestamp_format":"params:traffic_timestamp_format",
                "start_day":"params:start_time",
                "end_day":"params:end_time",
                "start_hour":"params:start_hour",
                "end_hour":"params:end_hour",
                "weekdays_only":"params:weekdays_only"
            },
            outputs="avg_traffic_count_per_site",
            name="get_avg_traffic_count"
        ),
        ## ADD COORDINATES
        node(
            func=add_georef,
            inputs={
                    "site_avg_traffic_df":"avg_traffic_count_per_site",
                    "site_location_gdf":"traffic_site_location",
                    "site_location_IDcolumn":"params:traffic_ID_locationfile"
            },
            outputs="geo_avg_traffic_count_per_site",
            name="gdf_traffic_count"
        ),
        ## PLOT AVG TRAFFIC BY SITE
        node(
            func=plot_avg_traffic_by_site,
            inputs=["geo_avg_traffic_count_per_site"],
            outputs="map_traffic_by_site",
            name="map_traffic_by_site"
        ),
        ## AGGREGATE AT SPATIAL UNIT OF ANALYSIS
        node(
            func=aggregate_traffic_spatially,
            inputs={
                "air_gdf":"ED_aggregated_air",
                "site_avg_traffic_gdf":"geo_avg_traffic_count_per_site",
                "crs_metric":"params:crs_metric"
            },
            outputs="spatialunit_aggr_traffic",
            name="aggr_traffic"
        ),
        ## MAP OF POLLUTANT AND TRAFFIC 
        node(
            func=viz_traffic_and_pollutant,
            inputs={
                    "air_traffic_gdf":"spatialunit_aggr_traffic",
                    "pollutant_column":"params:pollutant"
            },
            outputs="map_pollutant_traffic",
            name="map_pollutant_traffic"
        )
    ])
