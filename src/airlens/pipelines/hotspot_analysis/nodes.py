# dependencies
import geopandas as gpd
import matplotlib.pyplot as plt 
import contextily as ctx
import geopandas as gpd
import esda
from typing import Optional
import numpy as np 
np.random.seed(42)

from .hotspot_helpers import optimal_k_Local_Moran, weights_and_lags
from .hotspot_helpers import moran_plots, local_morans_plot
from .hotspot_helpers import summary_morans_stats

'''
Created on May 19, 2025

@author: Luisa Lo Presti

`hotspot_analysis/nodes.py` contains the hotspot analysis functions, incorporated in the hotspot_analysis pipeline.

The following functions are found below:

1. viz_pollutant: visualize the pollutant concentration at the chosen spatial unit of aggregation.

2. hotspot_analysis: performs hotspot analysis using Local Moran's I and returns informative plots and 
text summary statistics.
'''

def viz_pollutant(gdf: gpd.GeoDataFrame, 
                  pollutant_column: str):
    '''
    Visualize pollutant concentration by geometry:
    Input:
        - gdf: geodata aggregated by chosen spatial unit
        - pollutant_column: name of the column containing the pollutant to analyse
    Returns visualization of pollutant concentration per spatial unit 
    using quadrant colormap.
    '''
    fig, ax = plt.subplots(1, figsize=(9, 9))

    gdf.plot(
        column=pollutant_column,
        cmap='coolwarm', # 'OrRd',
        scheme='quantiles',
        k=5,
        edgecolor=None,
        linewidth=2,
        alpha=0.8,
        legend=True,
        legend_kwds=dict(loc=2),
        ax=ax
    )
    ax.set_title(f"{pollutant_column} concentration")

    ctx.add_basemap(
        ax,
        crs=gdf.crs,
        source=ctx.providers.CartoDB.VoyagerNoLabels,
        # source=ctx.providers.CartoDB.Positron
    )

    ax.set_axis_off()

    return fig



def hotspot_analysis(gdf: gpd.GeoDataFrame,
                     pollutant_column: str,
                     crs_metric: Optional[str] = "EPSG:3857"):
    '''
    Use Local Moran's I to detect hotspots;
    returns maps, plots and text of summary statistics.

    Input:
        - gdf: geodataframe with the pollutant aggregated at the chosen spatial unit
        - pollutant_column: name of the column containing pollutant values
        - crs_metric: metric system to project geometries
    Returns:
        - scatter_lisa_plot: moran's quadrant plot and plot of distribution of local moran's I
        - local_morans_maps: maps of local moran's I value/quadrant for each spatial unit
        - lisa_summary: text summary of spatial units at different confidence levels
    '''
    gdf.to_crs(crs_metric, inplace=True)
    # get k value for Local Moran's I using KNN weight matrix
    k = optimal_k_Local_Moran(gdf, pollutant_column)
    # get weights 
    gdf_w, w = weights_and_lags(gdf, pollutant_column, k)
    # compute lisa
    lisa = esda.moran.Moran_Local(gdf_w[pollutant_column], w, seed=42)
    # produce morans plots
    scatter_lisa_plot = moran_plots(gdf_w, pollutant_column, lisa)
    # morans maps
    local_morans_maps = local_morans_plot(gdf_w, lisa)
    # text with LISA summary
    lisa_summary = summary_morans_stats(gdf, lisa)

    return scatter_lisa_plot, local_morans_maps, lisa_summary