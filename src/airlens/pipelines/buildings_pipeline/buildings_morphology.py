import geopandas as gpd
import numpy as np
import momepy
from libpysal import graph
from typing import Optional

def shape_compactness(building_gdf: gpd.GeoDataFrame,
                      crs_metric: Optional[str] = "EPSG:3857"):
    gdf = building_gdf.copy()
    gdf.to_crs(crs_metric, inplace=True)

    ## 3D SHAPE COMPACTNESS
    gdf['perimeter'] = gdf.length
    gdf['area'] = gdf.area
    gdf['volume'] = gdf['area'] * gdf['height']

    gdf['3D_compactness'] = (gdf['perimeter'] * gdf['height'] + gdf['area']) / (gdf['volume']**(2/3))
    return gdf['3D_compactness']


def fractal_dimension(building_gdf: gpd.GeoDataFrame,
                      crs_metric: Optional[str] = "EPSG:3857"):
    gdf = building_gdf.copy()
    gdf.to_crs(crs_metric, inplace=True)

    ## 2. FRACTAL DIMENSION 
    # (measure the complexity and irregularity of geometric shapes)
    gdf['perimeter'] = gdf.length
    gdf['area'] = gdf.area
    gdf['fractal_dim'] = 2 * np.log(gdf['perimeter']/4) / np.log(gdf['area'])
    return gdf['fractal_dim']


def building_adjacency(building_gdf: gpd.GeoDataFrame,
                       crs_metric: Optional[str] = "EPSG:3857"):
    gdf = building_gdf.copy()
    ## 3. BUILDING ADJACENCY
    # ref. https://docs.momepy.org/en/latest/api/momepy.building_adjacency.html
    # define a spatial graph denoting building contiguity
    contig = graph.Graph.build_contiguity(gdf, rook=True) # https://pysal.org/libpysal/generated/libpysal.graph.Graph.html#libpysal.graph.Graph.build_contiguity
    # define a spatial graph denoting the neighborhood
    # assuming pollutant dispersion after certain range, (eg diffusion ~50m)
    neigh = graph.Graph.build_distance_band(gdf.to_crs(crs_metric).centroid, threshold=50) 
    # measure mean interbuilding distance
    gdf['building_adj'] = momepy.building_adjacency(contig, neigh)
    return gdf['building_adj']