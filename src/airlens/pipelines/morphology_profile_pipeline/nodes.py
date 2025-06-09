import pandas as pd
import geopandas as gpd
import momepy
from typing import Optional

def compute_street_profile(clipped_roads_gdf: gpd.GeoDataFrame,
                            building_gdf: gpd.GeoDataFrame,
                            height_col: str = "height",
                            distance: float = 50,
                            tick_length: float = 50,
                            crs_metric: Optional[str] = "EPSG:3857"):
    '''
    Compute street profile metrics (street-buildings interaction).

    Inputs:
        clipped_roads_gdf: road gdf with spatial unit IDs 
                        (namely each road is clipped to be contained within a single spatial unit)
        building_gdf: buildings gdf containing height attribute
        height_col: column name of buildings height in building_gdf
        distance: distance between perpendicular ticks for street profile
        tick_length: length of the ticks for street profile
        crs_metric: metric CRS to project gdf

    Output:
        Pandas dataframe with street profile metrics and Spatial Unit ID column.
    '''

    clipped_roads_gdf = clipped_roads_gdf.to_crs(crs_metric)
    building_gdf = building_gdf.to_crs(clipped_roads_gdf.crs)

    # street profile
    street_profile = momepy.street_profile(
        clipped_roads_gdf,
        building_gdf,
        height=building_gdf[height_col],
        distance=distance,
        tick_length=tick_length
    )
    street_profile['SpatialUnitID'] = clipped_roads_gdf.SpatialUnitID

    # compute avg street profile characteristics per spatial unit
    unit_avg_street_profile = street_profile.groupby(['SpatialUnitID']).agg('mean').reset_index()

    return unit_avg_street_profile
