import numpy as np
import pandas as pd
from .Valhalla_map_matching import split_trajectories_by_gaps
from datetime import timedelta
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import RobustScaler

# --------------------------------------------------------
#     Outliers detection methods in TEMPORAL dimension
# --------------------------------------------------------

def hampel(df, pollutant_col, window_size = 31, sensitivity = 3):
    '''
    Hampel Filter: robust way to detect outliers in timeseries using median and 
    median absolute deviations.
    '''
    # compute rolling median and MAD
    rolling_median = df[pollutant_col].rolling(window=window_size, center=True).median()
    rolling_mad = df[pollutant_col].rolling(window=window_size, center=True).apply(lambda x: np.median(np.abs(x - np.median(x))), raw=True)
    # flag outliers when the absolute difference between the value and median exceeds `sensitivity * MAD`
    outliers = np.abs(df[pollutant_col] - rolling_median) > sensitivity * rolling_mad
    df['hampel_outlier'] = outliers
    return df

def rate_of_change(df, pollutant_col, timestamp_column, th_quantile=0.99, max_gap_seconds=60):
    '''
    Rate of change: determine plausibility of sudden changes in timeseries.
    '''
    df = df.copy()
    df[timestamp_column] = pd.to_datetime(df[timestamp_column])
    df.set_index(timestamp_column, inplace=True)
    
    # compute time difference in seconds
    df['time_diff'] = df.index.to_series().diff().dt.total_seconds()
    
    # detect outliers based on rate of change, aka detect sharp and sudden jumps
    df['rate_of_change'] = df[pollutant_col].diff().abs() # RoC(t) = | X(t) - X(t-1) |
    # normalize by time difference
    df['roc_per_sec'] = df['rate_of_change'] / df['time_diff']
    
    # evaluate whether time gap between consecutive observation is too wide to
    # determine the existance of a sudden spike
    obs_within_maxgap = df['time_diff'] <= max_gap_seconds

    # compare rate_of_change values to thresholds derived from the distribution of changes
    # set threshold to 99 quantile by default; can be changed to 95 for stricter approach
    roc_threshold = df.loc[obs_within_maxgap, 'roc_per_sec'].quantile(th_quantile)
    df['roc_outlier'] = (df['roc_per_sec'] > roc_threshold) & obs_within_maxgap

    return df.reset_index()


def temporal_outlier_detection(df, 
                               split_trajectory_after_maxgap,
                               timestamp_column,
                               pollutant,
                               window_size = 31, 
                               sensitivity = 3,
                               th_quantile = 0.99,
                               max_gap_seconds = 60):
    '''
    Applies Hampel filter & rate of change methods to the
    timeseries defined by the vehicle's trajectory.
    '''
    data = df.copy()

    ## DEFINE TRAJECTORIES
    data = split_trajectories_by_gaps(data, 
                                      time_gap_threshold = timedelta(minutes=split_trajectory_after_maxgap), 
                                      timestamp_column = timestamp_column)

    ## TEMPORAL PATTERNS
    ## COMPUTE POSSIBLE OUTLIERS USING HAMPEL FILTER & RATE OF CHANGE
    possible_outliers = []
    for trjID, trj_ts in data.groupby('trajectoryID'):
        trj_ts = trj_ts.sort_values(by=[timestamp_column]).reset_index(drop=True)
        trj_ts = hampel(trj_ts, pollutant, window_size, sensitivity)
        trj_ts = rate_of_change(trj_ts, pollutant, timestamp_column, th_quantile, max_gap_seconds)
        possible_outliers.extend(trj_ts[(trj_ts.roc_outlier==True)|(trj_ts.hampel_outlier==True)].obsID.to_list())
    
    print(f'Percentage of temporal anomalies: {round(len(possible_outliers)*100/len(data), 2)}% ({len(possible_outliers)} observations).')
    return possible_outliers




# --------------------------------------------------------
#     Outliers detection methods in SPATIAL dimension
# --------------------------------------------------------

def select_best_n_neighbors_for_LOF(X, n_range=range(20,80,10), method='std'):
    ''' 
    Perform Local Outlier Factor (LOF) over a given range of values for the n_neighbors
    parameters, and return the optimized value for n_neighbors and final LOF model.
    To select the optimal n_neighbors we use score spread, based on standard deviation
    or interquartile range.
    '''
    best_score = -np.inf
    best_n = None
    best_model = None

    for n in n_range:
        lof = LocalOutlierFactor(n_neighbors=n, contamination='auto')
        lof.fit(X)
        scores = lof.negative_outlier_factor_

        # compute dispersion
        if method == 'std':
            score = np.std(scores)
        elif method == 'iqr':
            q75, q25 = np.percentile(scores, [75, 25])
            score = q75 - q25
        else:
            raise ValueError("Invalid method. Use 'std' or 'iqr'.")

        if score > best_score:
            # higher score (std or iqr) indicate better separation
            # between outliers and inliers values
            best_score = score
            best_n = n
            best_model = lof

    return best_n, best_model

def best_LOF(df,
             timestamp_column,
             pollutant_column,
             n_range=range(20,80,10), 
             method='std'):
    '''
    Applies Local Outlier Factor with optimized number of neighbors.
    '''
    # get df for LOF without NaN
    loc_df = df.dropna(subset=[pollutant_column]).copy()

    loc_df['hour'] = loc_df[timestamp_column].dt.hour
    coords = loc_df.get_coordinates()
    loc_df['latitude'] = coords.y
    loc_df['longitude'] = coords.x

    scaler = RobustScaler()
    X = scaler.fit_transform(loc_df[['latitude', 'longitude', 'hour', pollutant_column]])
    # X = loc_df[['latitude', 'longitude', 'hour', pollutant_column]].values
    
    best_n, lof_model = select_best_n_neighbors_for_LOF(X, n_range, method)
    print(f'Best N neighbors value for LOF: {best_n}')

    # sklearn docs:
    # Label is 1 for an inlier and -1 for an outlier according to the LOF score and the contamination parameter.
    # With contamination='auto' the score threshold is set to -1.5
    # Thus outliers (label -1) are those observations with score below -1.5
    # reference: https://scikit-learn.org/stable/modules/generated/sklearn.neighbors.LocalOutlierFactor.html#sklearn.neighbors.LocalOutlierFactor 
    labels = lof_model.fit_predict(X)
    scores = lof_model.negative_outlier_factor_

    loc_df.loc[:, 'negative_outlier_factor'] = scores
    loc_df.loc[:, 'labels'] = labels

    spatial_anomalies = loc_df[loc_df.labels == -1].obsID.to_list()
    print(f'Percentage of LOF anomalies: {round(len(spatial_anomalies)*100/len(loc_df), 2)}% ({len(spatial_anomalies)} observations).')

    return spatial_anomalies


