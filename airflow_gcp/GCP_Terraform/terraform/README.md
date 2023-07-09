# Setting up GCP Infrastructure using Terraform

I'd recommend two videos which give a step by step breakdown on how to create your GCP project, create your service account and enable
roles to permit airflow to orchestrate the ingestion of data to a bucket in Google Cloud Storage and then to BigQuery. 
Check them out if you're not familiar with Google Cloud Services:
* [Introduction to Terraform Concepts & GCP Prerequisites](https://youtu.be/Hajwnmj0xfQ)
* [Creating GCP Infrastructure with Terraform](https://youtu.be/dNkEgO-CExg)

In order to run successfully, make sure you've done the following steps, as highlighted in the videos linked above:

1. Create a new project

2. Create a service account, add principlas and assign the following roles to them:
  * Viewer
  * Storage Object Admin
  * Storage Admin
  * BigQuery Admin

3. Generate a key for your service account.

4. [Enable IAM Service Account Credentials API](https://console.cloud.google.com/marketplace/product/google/iamcredentials.googleapis.com)

5. Setup terraform by creating the following files:
  * main.tf 
  * variables.tf 
  
You can refer to the [main.tf](/main.tf) and [variables.tf](/variables.tf) files to see how I configured them. Make sure you configure the [variables.tf](/variables.tf) to match with the project details created when setting up your Terraform infrastructure.

6. Create an environment variable called 'GOOGLE_APPLICATION_CREDENTIALS' pointing to your credentials file, for terraform to find it

7. Next run the following Terraform commands: 
* terraform init 
* terraform plan
* terraform apply
terraform destroy - to destroy resources created by Terraform.

8. If everything ran successfully, you should be able to see a bucket created in the Cloud Storeage section and a resource created in BigQuery, as specified in the variables.tf file.
