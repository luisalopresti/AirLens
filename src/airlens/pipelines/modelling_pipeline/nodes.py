import numpy as np
import pandas as pd
import geopandas as gpd
import re
import matplotlib.pyplot as plt
from typing import Optional, Tuple, List
from collections import Counter
from sklearn.preprocessing import StandardScaler
from mgwr.gwr import GWR, MGWR
from mgwr.sel_bw import Sel_BW

import matplotlib.gridspec as gridspec
import contextily as ctx
from pysal.explore import esda
from pysal.lib import weights

from ..viz_utils import variables_shortnames_dict


## -------------------------------------------------------------
##               GEOGRAPHICALLY WEIGHTED REGRESSION
## -------------------------------------------------------------

def prepare_gwr_data(air_gdf: gpd.GeoDataFrame,
                    pollutant_column: str,
                    crs_metric: Optional[str] = "EPSG:3857") -> Tuple[np.ndarray, np.ndarray, np.ndarray, List[str], gpd.GeoDataFrame]:
    ''' 
    Prepare data for GWR and MGWR model.

    Args:
        air_gdf: GeoDataFrame with air quality and predictor variables
        pollutant_column: str, target variable name
        crs_metric: CRS to project geometry for accurate distance calculations

    Returns:
        X: scaled predictor variables matrix (2D np.ndarray)
        y: target variable vector reshaped (2D np.ndarray)
        coords: coordinates of centroids (2D np.ndarray)
        predictors: list of predictor column names (List[str])
        air_gdf: GeoDataFrame projected to crs_metric with centroids added
    '''
    # get predictors (already checked for multicollinearity and selected)
    predictors = list(air_gdf.columns.drop(['SpatialUnitID', 'geometry', pollutant_column]))

    # target variable
    y = air_gdf[pollutant_column].values.reshape((-1, 1))

    # independent variables
    X = np.vstack([air_gdf[col].values for col in predictors]).T

    # scale predictors
    scaler = StandardScaler()
    X = scaler.fit_transform(X)

    # prepare centroids coordinates for gwr
    air_gdf = air_gdf.to_crs(crs_metric)
    air_gdf['centroid'] = air_gdf.geometry.centroid
    coords = np.vstack([air_gdf['centroid'].x, air_gdf['centroid'].y]).T

    return X, y, coords, predictors, air_gdf


def run_gwr_model(air_gdf: gpd.GeoDataFrame,
                  pollutant_column: str,
                  kernel: str = "exponential",
                  crs_metric: Optional[str] = "EPSG:3857") -> dict:
    '''
    Run Geographically Weighted Regression model
    
    Args:
        air_gdf: GeoDataFrame with air quality and predictor variables
        pollutant_column: str, target variable name
        crs_metric: CRS to project geometry for accurate distance calculations
        
    Returns:
        dict: dictionary with fitted model and location-specific coefficients
    '''
    X, y, coords, predictors, air_gdf = prepare_gwr_data(air_gdf, pollutant_column, crs_metric)

    # select optimal bandwidth using cross-validation 
    # (adaptive method by default, i.e., bandwidth represents the number of nearest neighbours)
    selector = Sel_BW(coords, y, X, kernel=kernel)
    bw = selector.search()
    # print('Optimal Bandwidth (adaptive):', bw)

    # fit GWR model
    gwr_model = GWR(coords, y, X, bw, kernel=kernel)
    gwr_results = gwr_model.fit()

    res = {
        "model_info": f"Geographically Weighted Regression (GWR), kernel = {kernel}",
        "gwr_bandwidth": bw,
        "gwr_params": pd.DataFrame(gwr_results.params, columns=['Intercept'] + predictors, index=air_gdf.index),
        "gwr_model": gwr_results 
    }

    # NOTE: res usage:
    ## get summary of model as res['gwr_model'].summary()
    ## quick access to performance metrics:
    ## res['gwr_model'].R2
    ## res['gwr_model'].aic
    ## res['gwr_model'].aicc

    return res




def analyze_gwr_significance(gwr_results, air_gdf, pollutant_column) -> dict:
    '''
    Analyze significance of GWR coefficients 
    
    Inputs:
        gwr_model: trained GWRResults object
        air_gdf: GeoDataFrame used to fit the model
        pollutant_column: target pollutant
    
    Returns:
        dict: {
            "air_gdf_with_coeffs": air_gdf with gwr coefficients
            "predictors": predictors used
            "significance_summary": DataFrame with counts of significant coefficients
            "gwr_filtered_t": coefficients significance with alpha 0.05
            "gwr_filtered_t_corrected": coefficients significance with corrected alpha
            }
    '''
    # extract GWR model from results
    gwr_model = gwr_results["gwr_model"]
    # get predictors from air_gdf
    predictors = list(air_gdf.columns.drop(['SpatialUnitID', 'geometry', pollutant_column]))

    # filter t-values: standard alpha = 0.05
    gwr_filtered_t = gwr_model.filter_tvals(alpha=0.05)
    # filter t-values: corrected alpha due to multiple testing
    gwr_filtered_tc = gwr_model.filter_tvals()

    # add coeffs to gdf
    air_gdf = air_gdf.copy()
    all_vars = ['Intercept'] + predictors

    for i, var in enumerate(predictors):
        air_gdf[f'gwr_{var}'] = gwr_model.params[:, i + 1]  # +1 because intercept is at index 0


    # count significance per variable
    def count_significant(filtered_tvals):
        return {
            var: Counter(filtered_tvals[:, i] == 0)[False]  # False = significant
            for i, var in enumerate(all_vars)
        }

    summary_standard = count_significant(gwr_filtered_t) # standard alpha = 0.05
    summary_corrected = count_significant(gwr_filtered_tc) # corrected alpha for multiple testing

    # summary of coeffs significance 
    # with 0.05 alpha and with corrected alpha accounting for multiple testing
    significance_summary = pd.DataFrame({
        "significant_alpha_5perc": summary_standard,
        "significant_corrected_alpha": summary_corrected
    })

    # local multicollinearity checks
    # LCC, VIF, CN, VDP = gwr_model.local_collinearity() # for GWR only

    return {
        "model_info":gwr_results["model_info"],
        "air_gdf_with_coeffs": air_gdf,
        "predictors": predictors,
        "significance_summary": significance_summary,
        "gwr_filtered_t": gwr_filtered_t,
        "gwr_filtered_t_corrected": gwr_filtered_tc
        # "VIF": pd.DataFrame(VIF).describe().round(2), # the max VIF for each variable should be less than 5, to avoid local multicollinearity issues
        # "CN": pd.DataFrame(CN).describe().round(2) # the max CN for each variable should be less than 30, to avoid local multicollinearity issues     
    }


def plot_gwr_coefficients_from_summary(gwr_significance_output: dict,
                                       figsize: tuple = (25,25)):
    '''
    Generate coefficient plots for predictors
    with at least one region significant at alpha = 0.05
    '''
    # extract all needed elements from significance analysis
    model_name = re.findall(r'\((.*?)\)', gwr_significance_output['model_info'])[0]
    air_gdf = gwr_significance_output["air_gdf_with_coeffs"]
    gwr_filtered_t = gwr_significance_output["gwr_filtered_t"]
    gwr_filtered_tc = gwr_significance_output["gwr_filtered_t_corrected"]
    predictors = gwr_significance_output["predictors"]

    fig, axes = plt.subplots(nrows=len(predictors), ncols=3, figsize=figsize)

    for i in range(len(predictors)):
        chosen_variable = predictors[i]
        
        air_gdf.plot(column=f'gwr_{chosen_variable}', 
                    cmap = 'coolwarm', 
                    linewidth=0.01, 
                    scheme = 'FisherJenks', 
                    k=5, 
                    legend=True, 
                    legend_kwds={'bbox_to_anchor':(1.10, 0.96)},  
                    ax=axes[i,0])

        air_gdf.plot(column=f'gwr_{chosen_variable}', 
                    cmap = 'coolwarm', 
                    linewidth=0.05, 
                    scheme = 'FisherJenks', 
                    k=5, 
                    legend=False, 
                    legend_kwds={'bbox_to_anchor':(1.10, 0.96)},  
                    ax=axes[i, 1])
        
        air_alpha = air_gdf[gwr_filtered_t[:,i+1] == 0]

        if len(air_alpha) > 0 :
            air_alpha.plot(color='white', 
                            linewidth=0.05, 
                            edgecolor='black', 
                            ax=axes[i,1])


        air_gdf.plot(column=f'gwr_{chosen_variable}', 
                    cmap = 'coolwarm', 
                    linewidth=0.05, 
                    scheme = 'FisherJenks', 
                    k=5, 
                    legend=False, 
                    legend_kwds={'bbox_to_anchor':(1.10, 0.96)}, 
                    ax=axes[i,2])
        
        air_alpha_corrected = air_gdf[gwr_filtered_tc[:,i+1] == 0]
        
        if len(air_alpha_corrected) > 0 :
            air_alpha_corrected.plot(color='white', 
                                    linewidth=0.05, 
                                    edgecolor='black', 
                                    ax=axes[i,2])

        axes[i,0].axis("off")
        axes[i,1].axis("off")
        axes[i,2].axis("off")

        # axes[i,0].set_title(f'GWR: {chosen_variable} - all coeffs', fontsize=12)
        # axes[i,1].set_title(f'GWR: {chosen_variable} - significant coeffs (0.05)', fontsize=12)
        # axes[i,2].set_title(f'GWR: {chosen_variable} - significant coeffs (corrected alpha)', fontsize=12)

        axes[i,0].set_title(f'{model_name}: {chosen_variable}', fontsize=12)
        axes[i,1].set_title(f'{model_name}: Significant coeffs (alpha = 0.05)', fontsize=12)
        axes[i,2].set_title(f'{model_name}: Significant coeffs (corrected alpha)', fontsize=12)

    return fig



def plot_gwr_diagnostics(air_gdf: gpd.GeoDataFrame,
                        gwr_results: dict,
                        pollutant_column: str,
                        crs_latlon: Optional[str] = "EPSG:4326",
                        crs_metric: Optional[str] = "EPSG:3857",
                        figsize: tuple = (14, 10)):
    '''
    Returns diagnostic plot with:
        - residuals map + Global Moran's I
        - standard deviation of coefficient estimates
        - coefficient ranges (min, median, max)

    Inputs:
        - air_gdf: GeoDataFrame with input data
        - gwr_results: object containing fitted GWR model 
        - pollutant_column: name of the target variable column
        - crs_latlon: CRS for plotting
        - crs_metric: CRS for distance calculations
        - figsize: tuple, figure size
    '''
    # extract model name
    model_name = re.findall(r'\((.*?)\)', gwr_results['model_info'])[0]
    
    # set seeds for reproducibility of Moran's I
    np.random.seed(42)  

    # rename variables for plot labels
    short_names = variables_shortnames_dict()
    air_gdf = air_gdf.rename(columns=short_names)
    predictors = air_gdf.columns.drop(['SpatialUnitID', 'geometry', pollutant_column])

    # residuals
    gdf_residuals = air_gdf.copy()
    gdf_residuals = gdf_residuals.to_crs(crs_latlon)

    gwr_model = gwr_results['gwr_model']
    gdf_residuals['residuals'] = gwr_model.resid_response

    # spatial weights and Moran's I
    coords = list(zip(
        gdf_residuals.to_crs(crs_metric).geometry.centroid.x,
        gdf_residuals.to_crs(crs_metric).geometry.centroid.y
    ))
    w = weights.DistanceBand(coords, threshold=2000, silence_warnings=True)
    mi = esda.Moran(gwr_model.resid_response, w)
    moran_caption = f"Moran's I = {mi.I:.3f}, p = {mi.p_sim:.3f}"

    # GWR parameter stats
    params = gwr_model.params[:, 1:] # exclude intercept
    predictors_mean = params.mean(axis=0)
    predictors_std = params.std(axis=0)
    predictors_min = params.min(axis=0)
    predictors_max = params.max(axis=0)
    predictors_median = np.median(params, axis=0)

    # PLOTS
    fig = plt.figure(figsize=figsize, constrained_layout=True)
    gs = gridspec.GridSpec(2, 2, figure=fig, width_ratios=[1.3, 1])

    # Residual Map
    ax0 = fig.add_subplot(gs[:, 0])
    gdf_residuals.plot(
        column='residuals', cmap='coolwarm', ax=ax0,
        legend=True, legend_kwds={'shrink': 0.6}
    )
    ctx.add_basemap(ax0, crs=crs_latlon)
    ax0.set_title(f'{model_name} Residuals\n' + moran_caption, fontsize=14)
    ax0.axis('off')

    # Standard Deviation Bar Chart
    ax1 = fig.add_subplot(gs[0, 1])
    ax1.bar(predictors, predictors_std, color="#7EBDFD")
    ax1.set_title('Spatial Non-Stationarity', fontsize=14)
    ax1.set_ylabel('Coefficient Std')
    ax1.set_xticks(range(len(predictors)))
    ax1.set_xticklabels(predictors, rotation=45, ha='right')

    # Coefficient Range Plot
    ax2 = fig.add_subplot(gs[1, 1])
    lower_errors = predictors_median - predictors_min
    upper_errors = predictors_max - predictors_median
    asymmetric_error = [lower_errors, upper_errors]

    ax2.errorbar(
        x=range(len(predictors)), y=predictors_median,
        yerr=asymmetric_error, fmt='o', color="#2279CF",
        ecolor='gray', capsize=5, markersize=6
    )
    ax2.set_title('Coefficient Ranges (Min-Max)', fontsize=14)
    ax2.set_ylabel('Coefficient Estimate')
    ax2.set_xticks(range(len(predictors)))
    ax2.set_xticklabels(predictors, rotation=45, ha='right')

    return fig


## -------------------------------------------------------------
##          MULTISCALE GEOGRAPHICALLY WEIGHTED REGRESSION
## -------------------------------------------------------------


def run_mgwr_model(air_gdf: gpd.GeoDataFrame,
                   pollutant_column: str,
                   kernel: str = "exponential",
                   crs_metric: Optional[str] = "EPSG:3857") -> dict:
    X, y, coords, predictors, air_gdf = prepare_gwr_data(air_gdf, pollutant_column, crs_metric)

    # MGWR bandwidth selector
    selector = Sel_BW(coords, y, X, kernel=kernel, multi=True)
    bws = selector.search(multi_bw_min=[2])

    # fit MGWR
    mgwr_model = MGWR(coords, y, X, selector, kernel=kernel)
    mgwr_results = mgwr_model.fit()

    res = {
        "model_info": f"MultiScale Geographically Weighted Regression (MGWR), kernel = {kernel}",
        "gwr_bandwidth": bws,
        "gwr_params": pd.DataFrame(mgwr_results.params, columns=['Intercept'] + predictors, index=air_gdf.index),
        "gwr_model": mgwr_results
    }
    return res