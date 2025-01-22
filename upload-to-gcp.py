# %%
from google.cloud import storage
import os
# Function to upload file to Google Cloud Storage
def upload_to_gcs(local_file_path, bucket_name, gcs_file_path):
    # Initialize a Cloud Storage client
    storage_client = storage.Client()
    # Reference to the bucket
    bucket = storage_client.bucket(bucket_name)
    # Upload the file
    blob = bucket.blob(gcs_file_path)
    blob.upload_from_filename(local_file_path)
    print(f"File {local_file_path} uploaded to {gcs_file_path}.")

# Upload the CSV to Google Cloud Storage
local_file_path = 'scraped_whitehouse_posts.csv'
bucket_name = 'your-life-in-data'
gcs_file_path = "executive-orders/scraped_whitehouse_posts.csv"

# Upload the file to GCS
upload_to_gcs(local_file_path, bucket_name, gcs_file_path)

print("Scraping complete. New data saved locally and uploaded to Google Cloud Storage.")

# %%



