import requests
from bs4 import BeautifulSoup
import random
import logging

def get_templates(category):
    url = f"https://webflow.com/templates/category/{category}"
    logging.info(f"Fetching URL: {url}")
    
    response = requests.get(url)
    
    if response.status_code == 200:
        logging.info(f"Response Status Code: {response.status_code}")
    else:
        logging.error(f"Failed to fetch URL. Status Code: {response.status_code}")

    soup = BeautifulSoup(response.text, 'html.parser')
    templates = []

    # Проверяем, что контент страницы получен
    if soup:
        # Извлекаем все элементы шаблонов
        for item in soup.find_all('div', role='listitem', class_='tm-templates_grid_item'):
            # Ищем ссылку для предварительного просмотра
            preview_link = item.find('a', class_='tm-templates-preview_link')
            if preview_link:
                href = preview_link.get('href')
                if href:
                    templates.append(href)
    
    logging.info(f"Templates found: {templates}")
    return templates

def get_random_template(templates):
    return random.choice(templates) if templates else None
