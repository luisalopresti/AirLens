import geopandas as gpd
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Optional

'''
Created on May 19, 2025

@author: Luisa Lo Presti

Functions overview:

1. temporal_trends -> produces basic visualizations of temporal trends and patterns of the target pollutant;
                    may aid in initial exploration of temperal dimension of air quality data.

'''

def temporal_trends(cleaned_air_gdf: gpd.GeoDataFrame,
                     pollutant_column: str,
                     timestamp_column: str,
                     reference_value: Optional[int] = None):
    '''
    Basic visualizations of temporal trends and patterns.
    Input:
        - cleaned_air_gdf: geodataframe with point observations cleaned from outliers
        - pollutant_column: name of the column containing the pollutant values
        - timestamp_column: name of the column containing the timestamps
        - reference_value: an optional integer to set an horizontal line on the linechart as a reference
        (e.g., concentration limit we do not wish to overcome)

    Return a single plot containing the following subplots:
    boxplot of concentration by hour,
    heatmap of concentration by month and day,
    and linechart with 5-day moving average.
    '''
    gdf = cleaned_air_gdf.copy()

    # sort by timestamp
    gdf.sort_values(by=[timestamp_column], inplace=True)
    gdf.reset_index(drop=True, inplace=True)

    # PLOT
    fig = plt.figure(constrained_layout=True, figsize=(16, 10))
    gs = fig.add_gridspec(2, 2, height_ratios=[1, 1.2])

    # Plot 1: Boxplot by Hour 

    # extract hour
    gdf['hour'] = gdf[timestamp_column].dt.hour
    # boxplot
    ax1 = fig.add_subplot(gs[0, 0])
    sns.boxplot(
        x='hour', y=pollutant_column, data=gdf,
        showfliers=False,
        boxprops={"facecolor": (.3, .5, .7, .5)},
        medianprops={"color": "r", "linewidth": 2},
        ax=ax1
    )
    ax1.set_title('Pollutant Concentration by Hour')
    ax1.set_xlabel('Hour of Day')
    ax1.set_ylabel('Pollutant Concentration')
    ax1.grid(True)



    # Plot 2: Heatmap

    # group by month (including year for multiple years data) 
    gdf['year_month'] = gdf[timestamp_column].dt.to_period('M').astype(str)
    pivot = gdf.groupby(['hour', 'year_month'])[pollutant_column].mean().unstack()

    # heatmap
    ax2 = fig.add_subplot(gs[0, 1])
    sns.heatmap(pivot, cmap="Reds", annot=False, ax=ax2)
    ax2.set_title('Average Pollutant Concentration by Hour and Month')
    ax2.set_xlabel('Year-Month')
    ax2.set_ylabel('Hour of Day')
    ax2.tick_params(axis='x', rotation=45)
    ax2.tick_params(axis='y', rotation=0)



    # Plot 3: Timeseries of DAILY MEDIAN OF HOURLY CONCENTRATION 

    # COMPUTE DAILY MEDIAN OF HOURLY CONCENTRATION
    # compute hourly medians
    df_hourly = gdf.groupby(gdf[timestamp_column].dt.floor('h'))[pollutant_column].median().reset_index()
    df_hourly.dropna(subset=[pollutant_column], inplace=True)
    # compute daily medians from hourly medians
    df_hourly['date'] = df_hourly[timestamp_column].dt.date
    df_daily_median_of_hourly = df_hourly.groupby('date')[pollutant_column].median().reset_index()


    # 5-days moving avg
    df_daily_median_of_hourly['5days_moving_avg'] = df_daily_median_of_hourly[pollutant_column].rolling(window=5, min_periods=1).mean()
    # PLOT TIMESERIES
    ax3 = fig.add_subplot(gs[1, :]) # full width on second row
    sns.scatterplot(data=df_daily_median_of_hourly, x='date', y=pollutant_column, color='blue', alpha=0.6, label='Daily Median of Hourly Concentration', ax=ax3)
    ax3.plot(df_daily_median_of_hourly['date'], df_daily_median_of_hourly['5days_moving_avg'], color='black', linestyle='--', label='5-day Moving Average')
    
    if reference_value:
        # reference value if provided
        ax3.axhline(reference_value, color='red', linestyle='--', label='Reference Value')

    ax3.set_title('Daily Median of Hourly Concentration')
    ax3.set_ylabel('Pollutant Concentration')
    ax3.set_xlabel('')
    ax3.tick_params(axis='x', rotation=45)

    # # y-axis limit
    # q1 = df_daily_median_of_hourly[pollutant_column].quantile(0.10)
    # q3 = df_daily_median_of_hourly[pollutant_column].quantile(0.75)
    # iqr = q3 - q1
    # upper_bound = q3 + 1.5 * iqr
    # ax3.set_ylim(0, upper_bound)

    ax3.legend()
    return fig