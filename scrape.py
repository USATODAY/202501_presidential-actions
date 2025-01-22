# %% [markdown]
# Scraping executive actions by president Donald Trump starting Jan 20, 2025
# 

# %%
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from google.cloud import storage
import os




# Base URL of the webpage to scrape
base_url = "https://www.whitehouse.gov/presidential-actions/page/{}/"

# Initialize a list to store post data
data = []

# Function to create a session with retry strategy
def create_session():
    session = requests.Session()
    retries = Retry(total=5, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    session.mount('https://', HTTPAdapter(max_retries=retries))
    return session

# Function to scrape a single page
def scrape_page(session, page_number, scraped_links):
    url = base_url.format(page_number)
    response = session.get(url)
    response.raise_for_status()  # Ensure the request was successful
    soup = BeautifulSoup(response.content, 'html.parser')
    posts = soup.find_all('li', class_='wp-block-post')

    for post in posts:
        title_element = post.find('h2', class_='wp-block-post-title')
        link_element = title_element.find('a')
        date_element = post.find('time')
        category_element = post.find('div', class_='taxonomy-category').find('a')

        title = title_element.get_text(strip=True)
        link = link_element['href']
        date = date_element['datetime']
        category = category_element.get_text(strip=True)

        # Only scrape if the link hasn't been scraped before
        if link not in scraped_links:
            data.append({
                'Title': title,
                'Link': link,
                'Date': date,
                'Category': category
            })
            scraped_links.add(link)  # Add to the set of scraped links

# Function to scrape details from a single URL
def scrape_details(session, url):
    response = session.get(url)
    response.raise_for_status()  # Ensure the request was successful
    soup = BeautifulSoup(response.content, 'html.parser')

    try:
        name = soup.find('div', class_="wp-block-whitehouse-topper__eyebrow").text.strip()
    except AttributeError:
        name = None

    try:
        headline = soup.find('h1', class_="wp-block-whitehouse-topper__headline").text.strip().title()
    except AttributeError:
        headline = None

    try:
        date = soup.find('div', class_="wp-block-post-date").text.strip()
    except AttributeError:
        date = None

    try:
        byline = soup.find('div', class_="wp-block-whitehouse-topper__meta--byline").text.strip()
    except AttributeError:
        byline = None

    # Start of the content extraction
    try:
        content_section = soup.find(
            'div', class_="entry-content wp-block-post-content has-global-padding is-layout-constrained wp-block-post-content-is-layout-constrained"
        )
        if content_section:
            content_parts = []

            # Extract text from all `p` elements
            for p in content_section.find_all('p'):
                content_parts.append(p.get_text(strip=True))

            # Extract text from tables inside `figure` elements and capture all rows and columns
            for table in content_section.find_all('table'):
                for row in table.find_all('tr'):
                    cells = [cell.get_text(strip=True) for cell in row.find_all(['td', 'th'])]
                    content_parts.append(' | '.join(cells))  # Combine table row cells with a delimiter

            # Include other block-level elements like `div`, `span` (e.g., for additional text content)
            for div in content_section.find_all(['div', 'span']):
                div_text = div.get_text(strip=True)
                if div_text:  # Only append non-empty text
                    content_parts.append(div_text)

            # Combine all parts into a single content string, separated by newlines
            content = '\n'.join(content_parts)

        else:
            content = None

    except AttributeError:
        content = None

    return {
        'Name': name,
        'Headline': headline,
        'Date': date,
        'Byline': byline,
        'Content': content
    }

# Load the already scraped links (if any) from a CSV or file
def load_scraped_links():
    try:
        # Load previously scraped data from a CSV file (or database)
        df = pd.read_csv('scraped_whitehouse_posts.csv')
        return set(df['Link'])  # Return a set of links from the CSV
    except FileNotFoundError:
        return set()  # If no file exists, return an empty set

# Save new data to a CSV file
def save_scraped_data(new_data):
    df = pd.DataFrame(new_data)
    df.to_csv('scraped_whitehouse_posts.csv', mode='a', header=False, index=False)

# Create a session
session = create_session()

# Load previously scraped links
scraped_links = load_scraped_links()

# Find the total number of pages
initial_response = session.get(base_url.format(1))
initial_response.raise_for_status()
soup = BeautifulSoup(initial_response.content, 'html.parser')
pagination = soup.find('div', class_='wp-block-query-pagination-numbers')

# Extract the number of pages
if pagination:
    pages = pagination.find_all('a', class_='page-numbers')
    total_pages = max(int(page.get_text()) for page in pages if page.get_text().isdigit())
else:
    total_pages = 1

# Loop through all pages and scrape data
for page_number in range(1, total_pages + 1):
    print(f"Scraping page {page_number} of {total_pages}...")
    scrape_page(session, page_number, scraped_links)
    time.sleep(1)  # Be polite and avoid overwhelming the server

# Create a DataFrame from the data
df = pd.DataFrame(data)

# Initialize a list to store detailed scraped data
scraped_data = []

# Loop through each URL in the DataFrame and scrape details
for index, row in df.iterrows():
    url = row['Link']
    try:
        print(f"Scraping URL: {url}")
        details = scrape_details(session, url)
        details.update({
            'Title': row['Title'],
            'Date': row['Date'],
            'Category': row['Category'],
            'Link': url
        })
        scraped_data.append(details)
        time.sleep(1)  # Be polite and avoid overwhelming the server
    except Exception as e:
        print(f"Error scraping URL {url}: {e}")

# Save the final detailed data
save_scraped_data(scraped_data)
print("data saved locally")


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



