import pandas as pd
import numpy as np
import geopandas as gpd


def flag_faulty_sites(df_time_series, site_col, value_col, zero_frac_threshold=0.8):
    '''Utility function. Flag sites where zero counts exceed a threshold (e.g., > 80% zeros)'''
    # df_time_series: rows are time steps, columns: site, value
    zero_frac = df_time_series.groupby(site_col)[value_col].apply(lambda x: (x==0).mean())
    faulty_sites_ids = zero_frac[zero_frac > zero_frac_threshold].index # index is site id
    return faulty_sites_ids


def idw_interpolation(gdf_to_fill, value_col, power=2, max_neighbors=None):
    ''' 
    Interpolate missing values in value_col using IDW.
    
    Parameters:
    - gdf_to_fill: GeoDataFrame with polygon geometries
    - value_col: name of the column with values to interpolate 
    - power (default = 2): power for IDW 
    - max_neighbors: optional max number of nearest neighbors to use. 
                    If not specified, all units available will be used.

    Returns gdf with an additional column named `value_col`+_idw containing 
    the interpolated values.
    '''
    gdf = gdf_to_fill.copy()
    gdf['centroid'] = gdf.geometry.centroid
    
    # retrive missing and known values
    known = gdf[gdf[value_col].notna()].copy()
    unknown = gdf[gdf[value_col].isna()].copy()
    
    interpolated_values = []

    for idx_u, row_u in unknown.iterrows():
        centroid_u = row_u['centroid']
        
        # compute distances to centroids of units with known value
        distances = known['centroid'].apply(lambda c: centroid_u.distance(c))
        distances = distances.replace(0, 1e-12)
        
        # if passed as input, use only the closest N neighbors
        # otherwise, use all known-value units
        if max_neighbors:
            distances = distances.nsmallest(max_neighbors)

        weights = 1 / (distances ** power)
        weighted_vals = known.loc[distances.index, value_col] * weights
        
        interpolated_val = weighted_vals.sum() / weights.sum()
        interpolated_values.append((idx_u, interpolated_val))

    # add interpolated values
    result_col = f"{value_col}_idw"
    gdf[result_col] = gdf[value_col]
    for idx, val in interpolated_values:
        gdf.at[idx, result_col] = val

    gdf.drop(columns=['centroid'], inplace=True)
    return gdf