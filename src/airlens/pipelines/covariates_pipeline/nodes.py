import geopandas as gpd
import pandas as pd
from functools import reduce
from typing import Optional
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from scipy.stats import pearsonr
from math import ceil
from statsmodels.stats.outliers_influence import variance_inflation_factor
from statsmodels.tools.tools import add_constant
from matplotlib.figure import Figure

from ..viz_utils import variables_shortnames_dict


def combine_covariates(air_gdf: gpd.GeoDataFrame,
                        traffic_gdf: Optional[gpd.GeoDataFrame] = None,
                        building_gdf: Optional[gpd.GeoDataFrame] = None,
                        road_gdf: Optional[gpd.GeoDataFrame] = None,
                        street_profile_gdf: Optional[gpd.GeoDataFrame] = None,
                        tree_gdf: Optional[gpd.GeoDataFrame] = None,
                        landuse_gdf: Optional[gpd.GeoDataFrame] = None) -> gpd.GeoDataFrame:
    '''
    Merge covariates and original air gdf by SpatialUnitID column.
    '''
    # list of all covariates
    covariates_gdfs = [traffic_gdf, building_gdf, road_gdf,
                       street_profile_gdf, tree_gdf, landuse_gdf]

    # remove None is any
    covariates_gdfs = [df for df in covariates_gdfs if df is not None]

    if len(covariates_gdfs)==0:
        raise ValueError("No covariates to merge.")

    # make sure not to have duplicated cols by removing columns that are repeating
    # (pollutant and geometry columns)
    rep_cols = air_gdf.columns.drop('SpatialUnitID')
    covariates_gdfs = [df.drop(columns=rep_cols, errors='ignore') for df in covariates_gdfs]

    # merge by spatial unit id
    merged = reduce(lambda left, right: pd.merge(left, right, on='SpatialUnitID', how='outer'), 
                    covariates_gdfs + [air_gdf])

    # remove rows (units) with missing values for covariates ## NOTE quick fix for empty hex 
    merged = merged.dropna()

    return gpd.GeoDataFrame(merged, geometry='geometry', crs=air_gdf.crs)


def covariates_filtering(cov_gdf: gpd.GeoDataFrame, 
                         pollutant_column: str,
                         corr_threshold: float = 0.2,
                         coeff_variability_threshold: float = 0.1) -> gpd.GeoDataFrame:
    gdf = cov_gdf.copy()

    # 1. CORRELATION FILTERING
    # drop predictors with (abs) low corr with target
    correlations = gdf.drop(columns=['SpatialUnitID', 'geometry']).corr().abs()
    covs_to_keep = correlations[correlations[pollutant_column] > corr_threshold].index.to_list()
    covs_to_keep.extend(['SpatialUnitID', 'geometry'])
    gdf = gdf[covs_to_keep]

    # 2. COEFFICIENT OF VARIABILITY FILTERING
    # check coefficient of variability and 
    # filter out low variation 
    # (0.1-0.5 is considered low tomoderate range)
    covariates_cols = gdf.columns.drop(['SpatialUnitID', 'geometry'])
    summary_stats = pd.DataFrame({
        # 'mean': gdf[covariates_cols].mean(),
        # 'std': gdf[covariates_cols].std(),
        # 'min': gdf[covariates_cols].min(),
        # 'max': gdf[covariates_cols].max(),
        'coef_variation': gdf[covariates_cols].std() / gdf[covariates_cols].mean() # [0, inf]
    })
    low_var = summary_stats[summary_stats['coef_variation'] < coeff_variability_threshold].index.to_list()
    if len(low_var)!=0:
        gdf.drop(columns=low_var, inplace=True)

    return gdf


def plot_correlation_matrix(df, 
                            target,
                            figsize=(12, 10), 
                            cmap='coolwarm', 
                            mask_upper=True,
                            annotate=True, 
                            title='Correlation Matrix', 
                            sigstars=True) -> Figure:
    '''  
    Produce plot of correlation matrix

    Inputs:
        - df: DataFrame with target and covariates
        - target: target column to highlight (optional)
        - figsize: tuple, figure size
        - cmap: str or matplotlib colormap
        - mask_upper: bool, whether to mask upper triangle
        - annotate: bool, whether to show correlation coefficients
        - title: str, plot title
        - sigstars: bool, whether to add p-value as stars for significance
    ''' 
    df = df[df.columns.drop(['SpatialUnitID', 'geometry'])].copy()
    
    # get cleaned variable names for plot
    short_names = variables_shortnames_dict()
    df = df.rename(columns=short_names)

    # correlation matrix
    corr = df.corr()

    # calculate p-values
    if sigstars:
        pvals = pd.DataFrame(np.ones(corr.shape), columns=corr.columns, index=corr.index)
        for i in corr.columns:
            for j in corr.columns:
                if i != j:
                    _, p = pearsonr(df[i], df[j])
                    pvals.loc[i, j] = p

    # mask upper triangle
    mask = np.triu(np.ones_like(corr, dtype=bool)) if mask_upper else None

    # setup plot
    sns.set(style='white', font_scale=1.2)
    fig, ax = plt.subplots(figsize=figsize)

    # add annotations with significance stars 
    if annotate:
        annot = corr.round(2).astype(str)
        if sigstars:
            for i in annot.columns:
                for j in annot.index:
                    if i != j:
                        p = pvals.loc[j, i]
                        if p < 0.001:
                            annot.loc[j, i] += '***'
                        elif p < 0.01:
                            annot.loc[j, i] += '**'
                        elif p < 0.05:
                            annot.loc[j, i] += '*'
        annot = annot.values
    else:
        annot = False

    # heatmap
    sns.heatmap(corr, mask=mask, cmap=cmap, annot=annot, fmt='', 
                square=True, linewidths=0.5, 
                cbar_kws={'shrink': 0.8, 'label': 'Pearson r'},
                ax=ax)

    # rectangle highlighting target row of correlation if target is passed
    if target and target in df.columns:
        idx = list(corr.columns).index(target)
        # draw rectangles around the row of target
        ax.add_patch(plt.Rectangle((0, idx), corr.shape[1]-1, 1, 
                                   fill=False, edgecolor='darkred', lw=5,
                                   # bring rect to front and avoid clipping
                                   zorder=10, clip_on=False))

    plt.title(title, fontsize=16)
    plt.xticks(rotation=90, ha='center')
    plt.yticks(rotation=0)

    plt.tight_layout()
    return fig


def plot_variable_distributions(df: pd.DataFrame, 
                                target: str = None, 
                                bins: int = 30) -> Figure:
    '''
    Plot grid of histograms for all numeric variables in the dataframe

    Inputs:
        - df: DataFrame with target and covariates
        - target: target column to highlight (optional)
        - bins: number of bins for histograms
    '''
    sns.set(style="whitegrid", font_scale=1.1)
    
    df = df.copy()
    short_names = variables_shortnames_dict()
    df = df.rename(columns=short_names)
    
    numeric_df = df.select_dtypes(include=np.number)
    if 'SpatialUnitID' in numeric_df.columns:
        numeric_df.drop(columns=['SpatialUnitID'], inplace=True)
    cols = numeric_df.columns.tolist()
    
    if target and target in cols:
        # move target first
        cols.insert(0, cols.pop(cols.index(target)))

    n_vars = len(cols)
    n_cols = 3
    n_rows = ceil(n_vars / n_cols)
    
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(n_cols * 5, n_rows * 3.5))
    axes = axes.flatten()
    
    for i, var in enumerate(cols):
        ax = axes[i]
        sns.histplot(data=numeric_df, x=var, bins=bins, kde=True, ax=ax,
                     color="steelblue" if var != target else "darkred",
                     edgecolor="white", linewidth=0.5)
        ax.set_title(var, fontsize=12)
        ax.set_xlabel("")
        ax.set_ylabel("Count")

    # remove unused subplots
    for j in range(i+1, len(axes)):
        axes[j].set_visible(False)
        
    fig.suptitle("Distributions of Target Pollutant and Covariates", fontsize=16)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    
    return fig



def reduce_multicollinearity(df: gpd.GeoDataFrame, 
                             target_pollutant: str, 
                             threshold: float = 5.0, 
                             verbose: bool = True, 
                             const: bool = True) -> gpd.GeoDataFrame:
    '''
    Iteratively remove features with high Variance Inflation Factor (VIF) 
    to mitigate multicollinearity among covariates.
    NOTE: adding a constant ensures that VIF are calculated in the presence 
    of an intercept, common in regression models.

    Input:
        - df: DataFrame with target and covariates
        - target: target column to remove from VIF computation
        - threshold: VIF threshold above which a variable will be removed 
                (default is 5.0)
        - verbose: if True, prints details of removed variables 
                (default is True)
        - const: if True, adds a constant term for VIF calculation 
                (default is True).
                VIF is based on OLS R-squared.
                Thus, to compute reliable VIF values, you need to 
                either add a constant (the intercept on the OLS model),
                or to standardize the variables.

    Reurn a GeoDataFrame with reduced multicollinearity among features.
    '''
    fixed_elements = ['SpatialUnitID', 'geometry', target_pollutant]

    variables = df[df.columns.drop(fixed_elements)].copy()

    # add constant for VIF calculation if needed
    if const:
        variables = add_constant(variables)

    dropped = True
    while dropped:
        dropped = False
        vif = pd.Series(
            [variance_inflation_factor(variables.values, i)
             for i in range(variables.shape[1])],
            index=variables.columns
        )

        # exclude constant from consideration (if present)
        if 'const' in vif.index:
            vif_no_const = vif.drop('const')
        else:
            vif_no_const = vif

        max_vif = vif_no_const.max()
        if max_vif > threshold:
            max_var = vif_no_const.idxmax()
            if verbose:
                print(f"Dropping '{max_var}' with VIF={max_vif:.2f}")
            variables = variables.drop(columns=[max_var])
            dropped = True

    if const and 'const' in variables.columns:
        variables = variables.drop(columns='const')

    return df[fixed_elements + variables.columns.to_list()]


def plot_covariates_maps(air_gdf: gpd.GeoDataFrame,
                         pollutant_column: str,
                         maps_per_row: int = 2,
                         figsize: tuple = (20,20)) -> Figure:
    # get cleaned variable names for plot
    short_names = variables_shortnames_dict()
    air_gdf = air_gdf.rename(columns=short_names)

    # plot covariates and target (ensure target first)
    predictors = list(air_gdf.columns.drop(['SpatialUnitID', 'geometry', pollutant_column]))
    columns_to_plot = [pollutant_column] + predictors

    # layout
    n_vars = len(columns_to_plot)
    n_rows = ceil(n_vars / maps_per_row)

    fig, axes = plt.subplots(
        nrows=n_rows,
        ncols=maps_per_row,
        figsize=figsize)
    
    axes = axes.flatten()

    for i, col in enumerate(columns_to_plot):
        air_gdf.plot(
            column=col,
            cmap='coolwarm',
            linewidth=0.05,
            scheme='FisherJenks',
            k=6,
            ax=axes[i],
            legend=True,
            legend_kwds={
                'bbox_to_anchor': (1.05, 1),
                'loc': 'upper left',
                'fontsize': 9,
                'title': col,
                'title_fontsize': 10
            }
        )
        axes[i].set_title(col, fontsize=13)
        axes[i].axis('off')

    # hide unused subplots
    for j in range(len(columns_to_plot), len(axes)):
        axes[j].axis('off')

    plt.tight_layout()
    return fig