import numpy as np
import pandas as pd
import geopandas as gpd
import re
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from typing import Optional, Tuple, List
from typing import Union, Literal
from collections import Counter
from sklearn.preprocessing import StandardScaler
from mgwr.gwr import GWR, MGWR
from mgwr.sel_bw import Sel_BW

import matplotlib.gridspec as gridspec
import contextily as ctx
from pysal.explore import esda
from pysal.lib import weights

import itertools 
import random
import math

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


def gwr_model(X: np.array, 
              y: np.array,
              coords: np.array,
              kernel: str,
              criterion: str):
    '''Geographically Weighted Regression model'''
    # select optimal bandwidth using cross-validation 
    # (adaptive method by default, i.e., bandwidth represents the number of nearest neighbours)
    selector = Sel_BW(coords, y, X, kernel=kernel)
    bw = selector.search(criterion=criterion, bw_min=2, bw_max=X.shape[0] - 1) # max num unit minus one (itself)
    # print('Optimal Bandwidth (adaptive):', bw)

    # fit GWR model
    gwr_model = GWR(coords, y, X, bw, kernel=kernel)
    gwr_results = gwr_model.fit()
    return gwr_results, bw


def run_gwr_model(air_gdf: gpd.GeoDataFrame,
                  pollutant_column: str,
                  criterion: str = 'AICc',
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
    # get model inputs
    X, y, coords, predictors, air_gdf = prepare_gwr_data(air_gdf, pollutant_column, crs_metric)

    # perform GWR
    gwr_results, bw = gwr_model(X, y, coords, kernel, criterion)

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
    # labels dict, to get short variable names for plot title
    abbreviation_dict = variables_shortnames_dict()

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
                    legend_kwds={'bbox_to_anchor':(1.9, 1), 'fontsize': 19},  
                    ax=axes[i,0])

        air_gdf.plot(column=f'gwr_{chosen_variable}', 
                    cmap = 'coolwarm', 
                    linewidth=0.05, 
                    scheme = 'FisherJenks', 
                    k=5, 
                    legend=False, 
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

        axes[i,0].set_title(f'{model_name}: {abbreviation_dict[chosen_variable]}', fontsize=27)
        axes[i,1].set_title(r'Significant coeffs ($\alpha$ = 0.05)', fontsize=27)
        axes[i,2].set_title(r'Significant coeffs (corrected $\alpha$)', fontsize=27)

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
    title_size, label_size = 20, 15

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
    ax0.set_title(f'{model_name} Residuals\n' + moran_caption, fontsize=title_size)
    ax0.axis('off')

    colorbar = ax0.get_figure().axes[-1]
    colorbar.tick_params(labelsize=label_size) # increse number size on colorbar

    # Standard Deviation Bar Chart
    ax1 = fig.add_subplot(gs[0, 1])
    ax1.bar(predictors, predictors_std, color="#7EBDFD")
    ax1.set_title('Spatial Non-Stationarity', fontsize=title_size)
    ax1.set_ylabel('Coefficient Std', fontsize=label_size)
    ax1.tick_params(axis='y', labelsize=label_size)
    ax1.set_xticks(range(len(predictors)))
    ax1.set_xticklabels(predictors, rotation=45, ha='right', fontsize=label_size)

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
    ax2.set_title('Coefficient Ranges (Min-Max)', fontsize=title_size)
    ax2.set_ylabel('Coefficient Estimate', fontsize=label_size)
    ax2.tick_params(axis='y', labelsize=label_size)
    ax2.set_xticks(range(len(predictors)))
    ax2.set_xticklabels(predictors, rotation=45, ha='right', fontsize=label_size)

    return fig


def GWR_local_R2(modelling_gdf: gpd.GeoDataFrame,
                 gwr_results: dict):
    '''Plot Local R2 Map for GWR'''
    modelling_gdf['gwr_localR2'] = gwr_results['gwr_model'].localR2
    fig, ax = plt.subplots(figsize=(8, 6))
    modelling_gdf.plot(column = 'gwr_localR2', 
                       cmap = 'coolwarm', 
                       linewidth = 0.01, 
                       scheme = 'FisherJenks', 
                       k = 5, 
                       legend = True, 
                       legend_kwds = {'loc': 'upper left', 
                                      # 'bbox_to_anchor': (1.05, 1),
                                      'fontsize':14}, 
                       ax = ax)
    ctx.add_basemap(ax, crs=modelling_gdf.crs)
    ax.set_title('GWR Local R2', fontsize=20)
    ax.axis("off")
    # plt.subplots_adjust(right=0.7) # add space on right to accomodate legend
    return fig

## -------------------------------------------------------------
##          MULTISCALE GEOGRAPHICALLY WEIGHTED REGRESSION
## -------------------------------------------------------------


def mgwr_model(X: np.array, 
               y: np.array, 
               coords: np.array,
               kernel: str, 
               criterion: str, 
               bw_initial_guess: int):
    '''Multiscale Geographically Weighted Regression model'''
    # MGWR bandwidth selector
    selector = Sel_BW(coords, y, X, kernel=kernel, multi=True)
    bws = selector.search(criterion = criterion,
                          multi_bw_min = [2], 
                          multi_bw_max = [X.shape[0] - 1],
                          init_multi = bw_initial_guess) 

    # fit MGWR
    mgwr_model = MGWR(coords, y, X, selector, kernel=kernel)
    mgwr_results = mgwr_model.fit()
    return mgwr_results, bws


def run_mgwr_model(air_gdf: gpd.GeoDataFrame,
                   pollutant_column: str,
                   criterion: str = 'AICc',
                   kernel: str = "exponential",
                   bw_initial_guess: int = 10,
                   crs_metric: Optional[str] = "EPSG:3857") -> dict:
    # get model inputs
    X, y, coords, predictors, air_gdf = prepare_gwr_data(air_gdf, pollutant_column, crs_metric)

    # call MGWR 
    mgwr_results, bws = mgwr_model(X, y, coords, kernel, criterion, bw_initial_guess)

    res = {
        "model_info": f"MultiScale Geographically Weighted Regression (MGWR), kernel = {kernel}",
        "gwr_bandwidth": bws,
        "gwr_params": pd.DataFrame(mgwr_results.params, columns=['Intercept'] + predictors, index=air_gdf.index),
        "gwr_model": mgwr_results
    }
    return res



def create_radarchart(data_list, 
                      labels, 
                      legends,
                      num_spatial_units,
                      X_VERTICAL_TICK_PADDING,
                      X_HORIZONTAL_TICK_PADDING,
                      COLORS):
    '''
    Plot radarchart.

    Inputs:
        - data_list: list of list of the same length; 
                    each list must contain one value for each vertex of the radarchart
        - labels: list of string; one name for each vertex of the radarchart
        - legend: list of string, must be same length as data_list. 
                  represent the legend name for each list in data_list
        - num_spatial_units: total number of unit (max of the radarchart)
        - X_VERTICAL_TICK_PADDING: vertical label padding from plot (on even ticks)
        - X_HORIZONTAL_TICK_PADDING: horizontal label padding from plot (on odd ticks)
        - COLORS: list of color codes, one for element in data_list
    '''
    # plt.style.use('seaborn-v0_8')

    num_vars = len(labels)
    angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()
    angles += angles[:1] # close the loop

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))

    # plot
    for data, label, color in zip(data_list, legends, COLORS):
        data_extended = data + data[:1]
        ax.plot(angles, data_extended, label=label, color=color, lw=2, marker="o", markersize=8)
        ax.fill(angles, data_extended, alpha=0.1, color=color)

    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_thetagrids(np.degrees(angles[:-1]), labels, fontsize=14)
    ax.set_rlabel_position(0)
    ax.set_ylim(0, int(math.ceil(num_spatial_units / 10) * 10))
    ax.set_title("Bandwidths Comparison", size=16, pad=16)

    # legend handles (markers + lines)
    handles = [
        Line2D([], [], c=color, lw=2, marker="o", markersize=8, label=label)
        for label, color in zip(legends, COLORS)
    ]

    legend = ax.legend(
        handles=handles,
        loc=(1, 0), # legend bottom-right outside plot
        labelspacing=1.5, # space between labels
        frameon=True # legend frame
    )

    for text in legend.get_texts():
        # legend font size
        text.set_fontsize(12)

    # tick label padding
    XTICKS = ax.xaxis.get_major_ticks()

    for i, tick in enumerate(XTICKS):
        if i % 2 == 0:
            tick.set_pad(X_VERTICAL_TICK_PADDING)
        else:
            tick.set_pad(X_HORIZONTAL_TICK_PADDING)

    plt.tight_layout()
    return fig


def bandwidth_radarchart(gwr_results, 
                         mgwr_results,
                         X_VERTICAL_TICK_PADDING = 15,
                         X_HORIZONTAL_TICK_PADDING = 25,
                         COLORS = [ "#a9a9a9", "#007ad2", "#b60428"]):
    '''
    Returns radarchart of bandwidth of different models (i.e., Global, GWR and MGWR),
    for comparison of spatial effects (global vs local).
    Simple application of the `create_radarchart` function.

    Input:
        - gwr_results: dictionary of GWR results (must contain key `gwr_bandwidth`)
        - mgwr_results: dictionary of GWR results (must contain keys `gwr_params` and `gwr_bandwidth`)
        - X_VERTICAL_TICK_PADDING: vertical label padding from plot (on even ticks)
        - X_HORIZONTAL_TICK_PADDING: horizontal label padding from plot (on odd ticks)
        - COLORS: list of 3 color codes, one for bandwidth of each model
    
    Returns radarchart.
    '''
    # labels
    labels = mgwr_results['gwr_params'].columns.to_list()
    labels.remove('Intercept')
    # rename labels
    labels = [variables_shortnames_dict()[lab] for lab in labels]

    # num vars and units
    num_vars = len(labels)
    num_spatial_units = len(mgwr_results['gwr_params'])

    # bandwiths
    GWR = [gwr_results['gwr_bandwidth']] * num_vars
    MGWR = mgwr_results['gwr_bandwidth'][1:].tolist() # [1:] to remove intercept bw
    Global = [len(mgwr_results['gwr_params'])] * num_vars # for global model (ie OLS)

    # return radarchart
    return create_radarchart(data_list=[Global, GWR, MGWR], 
                             labels=labels, 
                             legends=["Global", "GWR", "MGWR"], 
                             num_spatial_units=num_spatial_units,
                             X_VERTICAL_TICK_PADDING = X_VERTICAL_TICK_PADDING,
                             X_HORIZONTAL_TICK_PADDING = X_HORIZONTAL_TICK_PADDING,
                             COLORS = COLORS)


## -------------------------------------------------------------
##         RANDOM SEARCH OF BEST EXPLANATORY VARIABLES
## -------------------------------------------------------------

def gwr_with_random_search(modelling_gdf: gpd.GeoDataFrame,
                           target_pollutant: str,
                           model_type: str = "GWR",
                           N_search: Union[int, Literal["all"]] = 100, # number of iterations
                           kernel: str = "bisquare", 
                           criterion: str = "AICc", 
                           bw_initial_guess: Optional[int] = 10,
                           crs_metric: Optional[str] = "EPSG:3857") -> pd.DataFrame:
    '''
    Fits an GWR or MGWR model with random search for best explanatory variables combination.
    Returns the fitted model and diagnostics as DataFrame.

    Parameters:
        - modelling_gdf: GeoDataFrame containing the target variable, explanatory variables, and geometry.
        - target_pollutant: name of the column to be used as the target variable.
        - model_type: type of model to fit. Options are 'GWR' or 'MGWR' (case-insensitive).
        - N_search: number of random combinations of predictors to test during model selection.
                    If N_search = total number of combinations or is set to 'all', 
                    the function will perform exhaustive search over all combinations of predictors.
        - kernel: kernel function to use in bandwidth selection. 
                Options include: 'bisquare', 'gaussian', 'exponential'.
        - criterion: criterion for bandwidth selection (commonly, 'AICc' or 'CV')
        - bw_initial_guess: initial bandwidth guess for MGWR optimization.
        - crs_metric: coordinate reference system for accurate spatial distance calculations.

    Returns:
        A DataFrame sorted by AICc containing:
            - covariates: list of selected predictors for the model
            - diagnostics and performance metrics (AIC, AICc, R2, adj. R2)
            - gwr_model: the fitted GWR/MGWR model object for reuse or inspection
    '''

    if not (isinstance(N_search, int) and N_search >= 1) and N_search != "all":
        raise ValueError("N_search must be a positive integer or 'all'")

    model_type = model_type.lower()
    if model_type not in ['gwr', 'mgwr']:
        raise ValueError("model_type must be either 'gwr' or 'mgwr'")

    # set seeds
    np.random.seed(42)
    random.seed(42)

    result = []

    # get model inputs
    X, y, coords, predictors, _ = prepare_gwr_data(modelling_gdf, 
                                                   target_pollutant, 
                                                   crs_metric)


    # select all possible combinations of columns (min 2 cols)
    all_combos = []
    for r in range(2, len(predictors) + 1):
        all_combos.extend(itertools.combinations(range(len(predictors)), r))
    
    if N_search == "all":
        # exhaustive search 
        sampled_combos = all_combos
        print(f"Running exhaustive search over {len(sampled_combos)} combinations.")
    else:
        # random search
        # shuffle and get random N_search combinations
        random.shuffle(all_combos)
        sampled_combos = all_combos[:min(N_search, len(all_combos))]
        print(f"Running random search with {len(sampled_combos)} combinations.")

    for i, cols in enumerate(sampled_combos):
        covariates_used = [predictors[j] for j in cols]

        try:
            if model_type == 'gwr':
                # perform GWR
                model, _ = gwr_model(X[:, cols], y, coords, kernel, criterion)
            else:
                # perform MGWR
                model, _ = mgwr_model(X[:, cols], y, coords, kernel, criterion, bw_initial_guess)
            
            # store results
            result.append({
                'covariates': covariates_used,
                'AIC': model.aic,
                'AICc': model.aicc,
                'R2': model.R2,
                'adj. R2': model.adj_R2,
                'gwr_model': model
            })

            print(f"[{i+1}/{len(sampled_combos)}] Success: {covariates_used} | AICc: {model.aicc:.2f}")
        
        except Exception as e:
            print(f"[{i+1}/{len(sampled_combos)}] Failed for {covariates_used}: {e}")

    results_gwr = pd.DataFrame(result)
    results_gwr = results_gwr.sort_values('AICc', ascending=True)
    return results_gwr