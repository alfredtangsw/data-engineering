import numpy as np
import pandas as pd
import datetime
import dateutil.parser
from dateutil.relativedelta import relativedelta
import argparse

parser = argparse.ArgumentParser(description='Adjust outliers for your preferred project.')
parser.add_argument('project_id', type=int, help='Input an integer as the ID of your preferred project.')
parser.add_argument('month_range', type=int, default=6, help='Number of months to search forwards and backwards in time after finding an outlier. Default: 6 months')
parser.add_argument('file_name', type=str, help='Specify the filename of the engagement score CSV.')
args = parser.parse_args()

project_id = args.project_id
month_range = args.month_range
file_name = args.file_name

today = datetime.datetime.today()
today_str = str(today.strftime('%d-%m-%Y'))

def parse_date_str(dt):
    dt_obj = dateutil.parser.parse(dt) #convert ISO-8601 date str to datetime obj
    return dt_obj

def iso_date_str(dt_obj):
    iso_dt_str = dt_obj.isoformat()
    return iso_dt_str

def get_outlier_threshold(project_df):

    #get mean and stdev of all project data
    engagement_data = project_df['total_engagement']
    overall_egt_mean = np.mean(engagement_data)
    overall_egt_stdev = np.std(engagement_data)    #numpy default std, ddof = 0
    outlier_threshold = overall_egt_mean + (4 * overall_egt_stdev) 
    return outlier_threshold

def get_outlier_df(project_df):
    
    outlier_threshold = get_outlier_threshold(project_df)
    outlier_mask = project_df['total_engagement'] > outlier_threshold
    outlier_df = project_df[outlier_mask].copy()
    return outlier_df

def get_outlier_boundaries(outlier_dt):

    #define boundaries for outlier adjustment
    lower_bound = pd.Timestamp(datetime.datetime.date(outlier_dt) + relativedelta(months= -month_range))
    upper_bound = pd.Timestamp(datetime.datetime.date(outlier_dt) + relativedelta(months= month_range))
    return lower_bound, outlier_dt, upper_bound


def get_outlier_data(project_df, outlier_df, outlier_ix, final_df):
    
    o_dt = project_df.iloc[outlier_ix,:]['date']
    lower_bound, outlier_dt, upper_bound = get_outlier_boundaries(o_dt)

    #get data for allowed dates within lower and upper bounds
    #exclude outlier itself, else it will always be outside 1-year mean and stdev
    o_year_data_df = project_df[lower_bound <= project_df['date']][project_df['date'] <= upper_bound][project_df['date'] != o_dt]
    o_egt_data = o_year_data_df['total_engagement']

    #get outlier 1-year data mean and stdev
    o_year_mean = np.mean(o_egt_data)
    o_year_stdev = np.std(o_egt_data)
    o_year_threshold = o_year_mean + (4 * o_year_stdev)

    #determine if outlier is greater than Mean + 4 stdev of its 1-year data
    o_engagement = project_df.iloc[outlier_ix,:]['total_engagement']

    if o_engagement > o_year_threshold:
        new_val = o_year_mean + o_year_stdev
        final_df.loc[outlier_ix,'total_engagement'] = new_val    #write new value to the corresponding cell
        print("NEW VALUE: {} | Outlier detected within 1-year data, new value assigned.")

    else:
        new_val = None
        print("NO NEW VAL. Outlier detected vs. overall data, but no new value assigned.")

    return final_df


if __name__ == "__main__":
    #set up dataframe
    df = pd.read_csv(file_name)
    df.columns = [col.lower() for col in df.columns]
    df['date'] = df['date'].map(lambda x: parse_date_str(x))
    df = df.sort_values(by = ['project_id','date'])
    df = df.reset_index(drop=True)
    
    #filter out dataframe rows related to project
    project_df = df[df['project_id'] == project_id]
    
    #get outlier df
    outlier_df = get_outlier_df(project_df)
    final_df = project_df.copy()
    
    if len(list(outlier_df.index)) > 0:
        #initialise the final df to be written out
        for ix in list(outlier_df.index):
            final_df = get_outlier_data(project_df, outlier_df, ix, final_df)
        
        #re-scale relative_engagement    
        final_egt_data = final_df['total_engagement']
        final_df.update({'relative_engagement':[egt/max(final_egt_data) * 100.0 for egt in final_egt_data]})

        #write final_df to a CSV output, date as index
        final_df.update({'date':[iso_date_str(dt) for dt in final_df['date']]})
        final_df = final_df.set_index('date')
        final_df.to_csv('outliers_adjusted_project_'+ str(project_id) + '_'+ today_str + '.csv')
        print("Outliers replaced. Execution complete!")
        
    else:
        print("No outliers detected!")