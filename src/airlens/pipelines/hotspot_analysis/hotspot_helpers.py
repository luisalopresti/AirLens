import numpy as np
import pandas as pd
import geopandas as gpd
from libpysal import weights
import esda
from splot import esda as esdaplot
import matplotlib.pyplot as plt
import seaborn as sns
import contextily as ctx


# ------------------------------------------------
#            LOCAL MORAN'S I FUNCTIONS
# ------------------------------------------------


def optimal_k_Local_Moran(gdf: gpd.GeoDataFrame,
                          pollutant_column: str,
                          k_searchspace: tuple[int, int] = (2, 20)):
    k_values = range(k_searchspace[0], k_searchspace[1])
    significant_counts = []
    optimal_k = None
    prev_count = -1

    for k in k_values:
        # compute weight matrix for different values of k
        knn_weights = weights.KNN.from_dataframe(gdf, k=k)
        knn_weights.transform = "r"

        # Local Moran's I
        # NOTE: Moran_Local operated on CENTROIDS
        moran_loc = esda.Moran_Local(gdf[pollutant_column], knn_weights, permutations=999, seed=42)

        # number of significant units with 5% confidence level (p < 0.05)
        sig_count = np.sum(moran_loc.p_sim < 0.05)
        significant_counts.append(sig_count)

        # check if count decreased compared to previous k (ignore first iteration)
        # stop iterating over k_values at first decrease and use k previous to the drop
        if prev_count != -1 and sig_count < prev_count:
            optimal_k = k - 1  # previous k value
            break

        prev_count = sig_count

    # if no decrease found, choose the largest k
    if optimal_k is None:
        optimal_k = k_values[-1]
    return optimal_k



def weights_and_lags(gdf: gpd.GeoDataFrame,
                    pollutant_column: str, 
                    k_value: int):
    gdf_w = gdf.copy()
    w = weights.distance.KNN.from_dataframe(gdf_w, k=k_value)
    w.transform = 'r' # row-standardization
    # spatial lag
    gdf_w['w'] = weights.lag_spatial(w, gdf_w[pollutant_column])
    gdf_w['std'] = gdf_w[pollutant_column] - gdf_w[pollutant_column].mean()
    gdf_w['w_std'] = weights.lag_spatial(w, gdf_w['std'])
    return gdf_w, w



def moran_plots(gdf, pollutant, lisa):
    fig, axs = plt.subplots(1, 2, figsize=(14, 6))

    # Moran quadrants plot
    sns.regplot(x='std', y='w_std', data=gdf, ci=None, ax=axs[0])
    axs[0].axvline(0, color='k', alpha=0.5)
    axs[0].axhline(0, color='k', alpha=0.5)

    # get centers for quadrant label placement
    x_min, x_max = axs[0].get_xlim()
    y_min, y_max = axs[0].get_ylim()
    x_mid_neg = x_min / 2
    x_mid_pos = x_max / 2
    y_mid_neg = y_min / 2
    y_mid_pos = y_max / 2

    axs[0].text(x_mid_pos, y_mid_pos, 'HH', fontsize=20, color='r', ha='center', va='center')
    axs[0].text(x_mid_pos, y_mid_neg, 'HL', fontsize=20, color='r', ha='center', va='center')
    axs[0].text(x_mid_neg, y_mid_pos, 'LH', fontsize=20, color='r', ha='center', va='center')
    axs[0].text(x_mid_neg, y_mid_neg, 'LL', fontsize=20, color='r', ha='center', va='center')

    axs[0].set_xlabel('Mean-centered ' + pollutant)
    axs[0].set_ylabel('Spatial Lag of Mean-centered ' + pollutant)
    axs[0].set_title('Moran Scatterplot')
    axs[0].grid(True)

    # LISA plot    
    sns.kdeplot(lisa.Is, ax=axs[1], fill=True)
    sns.rugplot(lisa.Is, ax=axs[1])
    axs[1].set_title("Distribution of Local Moran's I")
    axs[1].set_xlabel("Local Moran's I values")
    axs[1].set_ylabel("Density")

    plt.tight_layout()
    return fig



def local_morans_plot(gdf, lisa):

    fig, axs = plt.subplots(nrows=2, ncols=2, figsize=(12, 12))
    axs = axs.flatten()

    # 1. choropleth of local morans I statistics
    gdf.assign(Is=lisa.Is).plot(column='Is',
                                cmap='plasma',
                                scheme='quantiles',
                                k=5,
                                edgecolor=None,
                                linewidth=2,
                                alpha=0.8,
                                legend=True,
                                ax=axs[0])
    ctx.add_basemap(axs[0], crs=gdf.crs)
    axs[0].set_axis_off()
    axs[0].set_title("Local Moran's I")

    # 2. color spatial unit by morans quadrant 
    esdaplot.lisa_cluster(lisa, gdf, p=1, ax=axs[1])
    ctx.add_basemap(axs[1], crs=gdf.crs)
    axs[1].set_axis_off()
    axs[1].set_title("Moran's Quadrant")


    # 3. map of significant units
    labels = pd.Series(
        1 * (lisa.p_sim < 0.05), # 1 if significant, 0 otherwise
        index=gdf.index
    ).map({1: 'Significant', 0: 'Non-Significant'})

    gdf.assign(cl=labels).plot(column='cl',
                                categorical=True,
                                k=2,
                                cmap='Paired',
                                linewidth=2,
                                edgecolor=None,
                                legend=True,
                                ax=axs[2])
    ctx.add_basemap(axs[2], crs=gdf.crs)
    axs[2].set_axis_off()
    axs[2].set_title('Statistical Significance')


    # 4. morans cluster map
    # 5% significance level to select statistically significant roads
    esdaplot.lisa_cluster(lisa, gdf, p=0.05, ax=axs[3])
    ctx.add_basemap(axs[3], crs=gdf.crs)
    axs[3].set_axis_off()
    axs[3].set_title('Moran Cluster Map')


    fig.tight_layout()
    return fig



# ------------------------------------------------
#              TXT SUMMARY LOCAL STATS
# ------------------------------------------------

def assign_cluster_and_significance(gdf, lisa, confidence_level = 0.05):
    '''Add cluster assignment to dataframe & cnt significant obs per cluster'''
    gdf_lisa = gdf.copy()
    # add quadrant and p-value to df
    gdf_lisa['q'] = lisa.q
    gdf_lisa['p_sim'] = lisa.p_sim
    # add significant (bool) column: 1 if significance at 5% Confidence Level (default), else 0
    sig = 1 * (lisa.p_sim < confidence_level)
    gdf_lisa['significance'] = sig

    # assign significant observation to quadrant
    quadrant_labels = {0: 'Non-Significant', 
                       1: 'HH', 2: 'LH', 3: 'LL', 4: 'HL'}
    gdf_lisa['significant_quadrant'] = pd.Series(lisa.q * sig, 
                                      index = gdf_lisa.index).map(quadrant_labels)
    
    return gdf_lisa


def summary_morans_stats(gdf, lisa):
    # significant spatial unit per quadrant at given confidence
    sig_units_5CI = assign_cluster_and_significance(gdf, lisa, confidence_level=0.05)
    sig_units_1CI = assign_cluster_and_significance(gdf, lisa, confidence_level=0.01)

    # count of units per cluster
    lisa_summary = 'Observation per Quadrant\n'
    counts = pd.Series(lisa.q).value_counts()
    lisa_summary += str(counts)
    lisa_summary += '\n\n'

    # % units clustering significantly
    perc_cluster_5CI = (lisa.p_sim < 0.05).sum() * 100 / len(lisa.p_sim)
    perc_cluster_1CI = (lisa.p_sim < 0.01).sum() * 100 / len(lisa.p_sim)
    lisa_summary += f'~ {round( perc_cluster_5CI , 2)}% of spatial units are considered to be part of a significant spatial cluster at 5% confidence level.\n\n'
    lisa_summary += 'Significant Observation per Quadrant at 5% Confidence Level:\n'
    lisa_summary += str(pd.Series(sig_units_5CI['significant_quadrant']).value_counts())
    lisa_summary += '\n\n'

    lisa_summary += f'~ {round( perc_cluster_1CI , 2)}% of spatial units are considered to be part of a significant spatial cluster at 1% confidence level.\n\n'
    lisa_summary += 'Significant Observation per Quadrant at 1% Confidence Level:\n'
    lisa_summary += str(pd.Series(sig_units_1CI['significant_quadrant']).value_counts())

    return lisa_summary