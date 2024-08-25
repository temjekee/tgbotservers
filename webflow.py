import aiohttp
from bs4 import BeautifulSoup
import random
import logging

async def get_templates(category):
    url = f"https://webflow.com/templates/category/{category}"
    logging.info(f"Fetching URL: {url}")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    logging.info(f"Response Status Code: {response.status}")
                    text = await response.text()
                else:
                    logging.error(f"Failed to fetch URL: {url}. Status Code: {response.status}")
                    return []
    except aiohttp.ClientError as e:
        logging.error(f"HTTP request failed for URL: {url}. Error: {e}")
        return []

    soup = BeautifulSoup(text, 'html.parser')
    templates = []

    # Извлекаем все элементы шаблонов
    for item in soup.find_all('div', role='listitem', class_='tm-templates_grid_item'):
        preview_link = item.find('a', class_='tm-templates-preview_link')
        if preview_link:
            href = preview_link.get('href')
            if href:
                templates.append(href)
    
    logging.info(f"Templates found: {templates}")
    return templates

def get_random_template(templates):
    return random.choice(templates) if templates else None
