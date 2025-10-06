import numpy as np
from shapely.geometry import box
import geopandas as gpd
import pandas as pd
from rasterio.features import shapes
import xarray as xr
from typing import Optional

from .buildings_morphology import fractal_dimension, shape_compactness, building_adjacency

'''
Created on June 6, 2025

@author: Luisa Lo Presti

Functions overview:

1. raster_to_building_gdf -> reads geoTIFF containing buildings data and produces a geodataframe from it.

2. clip_to_bbox -> filters buildings geodataframe according to the area of interest.

3. compute_buildings_morph_prop -> computes buildings morphology metrics, 
                                    with the assistance of `buildings_morphology.py` functions.

4. aggregate_buildings_spatially -> aggregates the computed metrics at the selected spatial unit level.
'''


def raster_to_building_gdf(rds: xr.DataArray) -> gpd.GeoDataFrame:
    '''Read geoTiff and transform to gdf'''
    # select first band (only 1 band in Copernicus Urban Atlas - Building Height Data)
    da = rds.sel(band=1)

    # load data using .values
    array = da.values
    mask = ~np.isnan(array)
    transform = da.rio.transform()
    crs = da.rio.crs

    # convert raster to vector (dicts)
    result = (
        {'properties': {'value': v}, 'geometry': s}
        for s, v in shapes(array, mask=mask, transform=transform)
    )

    # to gdf
    building_gdf = gpd.GeoDataFrame.from_features(result, crs=crs)
    building_gdf.rename(columns={'value':'height'}, inplace=True)
    return building_gdf


def clip_to_bbox(building_gdf: gpd.GeoDataFrame, 
                 air_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    ''' Clip buildings data to bounding box of air data. '''
    bbox = air_gdf.total_bounds
    bbox_geom = box(*bbox)

    building_gdf = building_gdf.to_crs(air_gdf.crs)

    building_gdf = building_gdf[building_gdf.geometry.intersects(bbox_geom)].reset_index(drop=True)
    return building_gdf


def compute_buildings_morph_prop(building_gdf: gpd.GeoDataFrame,
                                 crs_metric: Optional[str] = "EPSG:3857") -> gpd.GeoDataFrame:
    ## 3D SHAPE COMPACTNESS
    building_gdf["3D_compactness"] = shape_compactness(building_gdf, crs_metric)
    ## FRACTAL DIMENSION
    building_gdf["fractal_dim"] = fractal_dimension(building_gdf, crs_metric)
    ## BUILDING ADJACENCY
    building_gdf["building_adj"] = building_adjacency(building_gdf, crs_metric)
    ## buildings footprint area
    building_gdf["footprint_area"] = building_gdf.to_crs(crs_metric).area
    return building_gdf


def aggregate_buildings_spatially(building_gdf: gpd.GeoDataFrame,
                                  air_gdf: gpd.GeoDataFrame,
                                  crs_metric: Optional[str] = "EPSG:3857") -> gpd.GeoDataFrame:
    '''Aggregate building propriety at the spatial unit level chosen for air_gdf'''
    # assign buildings to spatial unit
    air_geoms = air_gdf.copy()
    air_geoms.loc[:,'SpatialUnitGeometry'] = air_geoms.geometry
    building_air_gdf = gpd.sjoin(building_gdf, air_geoms, how='right', predicate='within')

    # group by spatial unit and get avg 3D compactness for each unit
    buildings_by_spatialunit = building_air_gdf.groupby('SpatialUnitID').agg({'3D_compactness':'mean',
                                                                            'building_adj':'mean', 
                                                                            'fractal_dim':'mean',
                                                                            'footprint_area':'sum'}).reset_index()
    
    # merge to original data
    building_air_gdf = pd.merge(buildings_by_spatialunit, air_gdf, on='SpatialUnitID')
    building_air_gdf = gpd.GeoDataFrame(building_air_gdf, geometry='geometry', crs=air_geoms.crs)

    # area covered by buildings for each spatial unit
    building_air_gdf['build_cover_area'] = building_air_gdf['footprint_area'] / building_air_gdf.geometry.to_crs(crs_metric).area
    building_air_gdf.drop(columns=['footprint_area'], inplace=True)
    return building_air_gdf