import os
import logging
import airflow 
import numpy as np
import pandas as pd

from airflow import DAG
from airflow.utils.dates import days_ago
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

from google.cloud import storage
from airflow.providers.google.cloud.operators.bigquery import BigQueryCreateExternalTableOperator

PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
BUCKET = os.environ.get("GCP_GCS_BUCKET")

path_to_local_home = os.environ.get("AIRFLOW_HOME","/opt/airflow")
path_to_creds = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
BigQueryDataset = os.environ.get("BIGQUERY_DATASET","production_latest_dataset")

#create dictionary with the years and urls
years_dict = dict()
years_dict['2017'] = 'http://kilimodata.org/datastore/dump/40f681c0-20e6-4dc4-9c70-dcdb19b8940e?bom=True'
years_dict['2018'] = 'http://kilimodata.org/datastore/dump/4babb6fc-a24c-4e6b-8528-114658e0b402?bom=True'

#preprocess the data
def convert_string_to_int(value):
    if pd.isna(value):
        return np.nan
    return round(int(float(value.replace(',', ''))))

 ###"TWEAK" THE DATA

def clean_data(file_path,year):
    data = pd.read_csv(file_path)
    
    #clean data
    data = data.replace(' -   ',np.nan)
    #drop null
    data.dropna(inplace=True)
    data.reset_index(drop=True,inplace=True)
    data[['Value-farm gate (Ksh)','Production (MT)','Area (Ha)']] = data[['Value-farm gate (Ksh)','Production (MT)','Area (Ha)']].applymap(convert_string_to_int)
    #data['Yield (MT/Ha)'] = data['Production (MT)'] / data['Area (Ha)']
    data['COUNTY'] = data.COUNTY.str.strip().str.upper()
    data['CROP'] = data.CROP.str.strip()
    #add features to the data
    data['Year'] = year
    data['Year'] = pd.to_datetime(data['Year'])#,format='%Y').dt.year
    data['Value-farm gate (Ksh)'] = [int(float(x)) if pd.notna(x) else np.nan for x in data['Value-farm gate (Ksh)']]
    return data

#function to convert a csv file to parquet format

def convert_csv_to_parquet(file_csv,file_parquet,year):
    df = clean_data(f"{path_to_local_home}/{file_csv}",year)
    df.to_parquet(f"{path_to_local_home}/{file_parquet}")

def upload_to_gcs(bucket, object_name, local_file):
    #workaround to prevent time-out when uploading files > 6mb
    storage.blob._MAX_MULTIPART_SIZE = 5 * 1024 * 1024
    storage.blob._DEFAULT_CHUNKSIZE = 5 * 1024 * 1024

    # Create a GCS client with credentials
    storage_client = storage.Client.from_service_account_json(path_to_creds)

    # Retrieves the bucket
    bucket = storage_client.bucket(bucket)

    # Uploads the file
    blob = bucket.blob(object_name)
    blob.upload_from_filename(local_file)

default_args = {
    "owner":"airflow",
    "start_date":days_ago(1),
    "depends_on_past":False,
    "retries":1,
}

#DAG
with DAG(
    dag_id="ingest_data_dag",
    schedule_interval="@daily",
    default_args=default_args,
    catchup=False,
    max_active_runs=1,
    tags=["dtc-de"]
) as dag:
    
    for year,url in years_dict.items():
        csv_file = f'production_{year}.csv'
        parquet_file = f'production_{year}_data.parquet'

        download_data_task = BashOperator(
            task_id=f"download_data_task_{year}",
            bash_command=f"curl -sS {url} > {path_to_local_home}/{csv_file}"
        )

        csv_to_parquet = PythonOperator(
            task_id=f"csv_to_parquet_{year}",
            python_callable=convert_csv_to_parquet,
            op_kwargs={
                "file_csv": csv_file,
                "file_parquet": parquet_file,
                "year": year
            }
        )

        from_local_to_gcs_task = PythonOperator(
            task_id=f"from_local_to_gcs_task_{year}",
            python_callable=upload_to_gcs,
            op_kwargs={
                "bucket": BUCKET,
                "object_name": f"raw/{parquet_file}",
                "local_file": f"{path_to_local_home}/{parquet_file}"
            }
        )

        bigquery_to_external_table_task = BigQueryCreateExternalTableOperator(
            task_id=f"bigquery_to_external_table_task_{year}",
            table_resource={
                "tableReference":{
                    "projectId": PROJECT_ID,
                    "datasetId": BigQueryDataset,
                    "tableId": f"production_table_{year}"
                },
                "externalDataConfiguration":{
                    "sourceFormat": "PARQUET",
                    "sourceUris": [f"gs://{BUCKET}/raw/{parquet_file}"],
                }
            }
        )

        download_data_task >> csv_to_parquet >> from_local_to_gcs_task >> bigquery_to_external_table_task
