import geopandas as gpd
import pandas as pd
from shapely.geometry import box
from typing import Optional

'''
Created on June 9, 2025

@author: Luisa Lo Presti

Functions overview:

1. trees_in_unit -> assign street trees to each spatial unit.

2. tree_features -> for each spatial units, computes number of trees and canopy cover.

'''

def trees_in_unit(tree_gdf: gpd.GeoDataFrame,
                  air_gdf: gpd.GeoDataFrame):
    '''
    Assign Trees to Spatial Unit.
    
    Usea `within` for a one-to-one spatial join;
    may use `intersects` to not lose trees at the intersections 
    between spatial unit but multiple countings would occur.
    '''
    # assign IDs for tree geoms
    tree_gdf['TreeID'] = range(1, len(tree_gdf)+1)

    # reproject to same crs
    air_geoms = air_gdf.to_crs(tree_gdf.crs)

    # retain only area of interest
    bbox = air_geoms.total_bounds
    bbox_geom = box(*bbox)
    tree_gdf = tree_gdf[tree_gdf.geometry.intersects(bbox_geom)].reset_index(drop=True)

    # assign trees to spatial unit 
    air_geoms = air_geoms[['SpatialUnitID', 'geometry']].copy()
    return gpd.sjoin(tree_gdf, air_geoms, how='right', predicate='within')


def tree_features(tree_to_unit_gdf: gpd.GeoDataFrame,
                  air_gdf: gpd.GeoDataFrame,
                  crs_metric: Optional[str] = "EPSG:3857"):
    # ensure same metric crs
    air_gdf = air_gdf.to_crs(crs_metric)
    tree_to_unit_gdf = tree_to_unit_gdf.to_crs(air_gdf.crs)

    # 1. compute number of trees for spatial unit
    aggr_trees_per_unit = tree_to_unit_gdf.groupby('SpatialUnitID').agg(
        total_trees_area=('area', 'sum'), # compute tot area covered by trees per unit
        count_trees=('SpatialUnitID', 'size') # compute number of trees for spatial unit
    ).reset_index()
    tree_air_gdf = pd.merge(aggr_trees_per_unit, air_gdf, on='SpatialUnitID', how='right')
    tree_air_gdf = gpd.GeoDataFrame(tree_air_gdf, geometry='geometry', crs=air_gdf.crs)

    # 2. compute percentage of area covered by trees (canopy cover)
    tree_air_gdf['canopy_cover'] = (tree_air_gdf.total_trees_area / tree_air_gdf.area) * 100
    tree_air_gdf.drop(columns=['total_trees_area'], inplace=True)

    return tree_air_gdf
