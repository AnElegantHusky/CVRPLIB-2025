import logging
import os
import requests

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def download_instance(file_url: str) -> None:
    instance_name = file_url.split('/')[-1]

    try:
        response = requests.get(file_url)  # Send a GET request to fetch the raw HTML content
        response.raise_for_status()  # Check that the request was successful

        full_path = os.path.join('instances')
        os.makedirs(full_path, exist_ok=True)

        with open(os.path.join(full_path, instance_name), 'w', encoding='utf-8') as file:
            file.write(response.text)

        logger.info(f'Downloaded {file_url} into instance folder')

    except requests.exceptions.RequestException as e:
        logger.error("Error fetching the website content:", e)


def download_all_instances() -> None:
    url = 'http://vrp.galgos.inf.puc-rio.br/media/com_vrp/instances/X/'

    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')

    # Find all links to text files (Assuming they end with '.vrp')
    file_links = []
    for link in soup.find_all('a', href=True):
        if link['href'].endswith('.vrp') or link['href'].endswith('.sol'):
            file_links.append(link['href'])

    # Download and save each file
    for file_url in file_links:
        download_instance(f'{url}{file_url}')


download_all_instances()
