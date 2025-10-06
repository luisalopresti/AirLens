import pandas as pd
import geopandas as gpd
from shapely.geometry import box
from typing import Optional

'''
Created on June 9, 2025

@author: Luisa Lo Presti

Functions overview:

1. landuse_to_unit -> prepares landuse data and assign them to corresponding spatial unit.

2. landuse_features -> computes the percentage of the area covered by each urban landuse for each spatial unit.

'''

def landuse_to_unit(landuse_gdf: gpd.GeoDataFrame,
                    air_gdf: gpd.GeoDataFrame,
                    landuse_column: str = 'class_2018'):
    '''
    Prepare landuse data and assign them to corresponding spatial unit.

    1. Ensure landuse gdf only contains data for the area of interest 
    2. Clip landuse polygons when covering more than one spatial unit
        and assign them to the relative unit.
    3. Return geodataframe with (clipped) landuse geometries uniquely 
        assigned to their spatial unit.

    Inputs:
        - landuse_gdf: GeoDataFrame of landuse polygons,
                    containing the specified `landuse_column`.
        - air_gdf: GeoDataFrame of air quality data, containing 'SpatialUnitID'.
        - landuse_column: column name in `landuse_gdf` representing landuse class names. 
                        Default is 'class_2018' as per v13 of Copernicus Urban Atlas Land Cover.

    Output:
        - GeoDataFrame containing landuse labels and geometries assigned 
            to the respective spatial unit.
    '''
    # retain only area of interest
    air_gdf = air_gdf.to_crs(landuse_gdf.crs)
    bbox = air_gdf.total_bounds
    bbox_geom = box(*bbox)
    landuse_gdf = landuse_gdf[landuse_gdf.geometry.intersects(bbox_geom)].reset_index(drop=True)

    # clip geometries so that each landuse-polygon is contained within a single spatial unit
    clipped_landuse_poly = []
    for idx, polygon in air_gdf.iterrows():
        clipped = gpd.clip(landuse_gdf, polygon.geometry)
        
        if not clipped.empty:
            clipped = clipped.copy()
            clipped['SpatialUnitID'] = polygon['SpatialUnitID']
            clipped_landuse_poly.append(clipped)

    # concat all clipped landuse polygons
    clipped_landuse = gpd.GeoDataFrame(pd.concat(clipped_landuse_poly, ignore_index=True), crs=landuse_gdf.crs)
    return clipped_landuse[[landuse_column, 'geometry', 'SpatialUnitID']].copy()


def landuse_features(landuse_gdf: gpd.GeoDataFrame,
                     air_gdf: gpd.GeoDataFrame,
                     landuse_column: str = 'class_2018',
                     max_zero_fraction: float = 0.25,
                     crs_metric: Optional[str] = "EPSG:3857"):
    '''
    For each spatial unit, compute the percentage of the area covered by each urban landuse.
    Landuses with fraction of zeros over `max_zero_fraction` are removed.

    Inputs:
        - landuse_gdf: GeoDataFrame of landuse polygons. 
                    Must contain 'SpatialUnitID' and the specified `landuse_column`.
        - air_gdf: GeoDataFrame of air quality data, containing 'SpatialUnitID'.
        - landuse_column: column name in `landuse_gdf` representing landuse class names. 
                        Default is 'class_2018' as per v13 of Copernicus Urban Atlas Land Cover.
        - max_zero_fraction: float number representing the max fraction of zeros allowed
                        in a landuse class column before dropping it. 
                        Default is 0.25 (i.e., drop if >25% of rows are zero, 
                        namely if a landuse is not present in over 25% of spatial units).
        - crs_metric: metric CRS for areas computation.

    Output:
        A new version of air_gdf augmented with landuse columns, reporting the
        percentage of area covered by each retained landuse class per spatial unit.    
    '''
    # 0. for each spatial unit, get total area covered by each landuse class
    landuse_gdf['Area'] = landuse_gdf.to_crs(crs_metric).area
    area_by_landuse = landuse_gdf.groupby(['SpatialUnitID', landuse_column])['Area'].sum().reset_index()

    # pivot to have landuse as columns
    pv_area_by_landuse = area_by_landuse.pivot(index='SpatialUnitID', columns=landuse_column, values='Area').fillna(0)
    pv_area_by_landuse.reset_index(inplace=True)


    ## 1. normalize names
    pv_area_by_landuse.columns = (
        pv_area_by_landuse.columns
        .str.lower() # lowercase
        .str.replace(r'[^\w\s]', '', regex=True) # remove punctuation
        .str.replace(r'\s+', ' ', regex=True) # replace multiple spaces with a single space
        .str.strip() # remove whitespace
    )
    pv_area_by_landuse.columns = pv_area_by_landuse.columns.str.replace(r'\s+', '_', regex=True)


    ## 2. evaluate whether there is significant variability in the data (eg overpresence of 0s):
    # (default) filter out column if 25% (or more) of the data are 0 
    zero_fraction = (pv_area_by_landuse == 0).sum() / len(pv_area_by_landuse)
    pv_area_by_landuse = pv_area_by_landuse.loc[:, zero_fraction <= max_zero_fraction].copy()


    ## 3. compute percentage of spatial unit area covered by each landtype of interest
    air_landuse_gdf = pd.merge(air_gdf, pv_area_by_landuse, left_on='SpatialUnitID', right_on='spatialunitid', how='left')
    for col in pv_area_by_landuse.columns.drop('spatialunitid').to_list():
        air_landuse_gdf[col] = (air_landuse_gdf[col] / air_landuse_gdf.to_crs(crs_metric).area) * 100
    air_landuse_gdf.drop(columns=['spatialunitid'], inplace=True)
    
    return air_landuse_gdf


