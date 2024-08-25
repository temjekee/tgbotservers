import os
import uuid
import asyncio
import aiofiles
from PIL import Image
from playwright.async_api import async_playwright
from reportlab.pdfgen import canvas
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)

async def auto_scroll(page, temp_dir):
    """Прокручивает страницу и делает скриншоты."""
    viewport_height = 1080
    viewport_width = 1920
    overlap = 10
    screenshots = []

    await page.set_viewport_size({"width": viewport_width, "height": viewport_height})

    hide_elements_script = '''
    const styles = `
        .fixed-navbar,
        .navbar,
        .navbar-wrapper,
        .header,
        .navbar_component,
        .navigation-fixed-menu,
        .navbar-absolute,
        .navigation,
        .navbar-main {
            position: static !important;
        }
    `;
    const styleSheet = document.createElement("style");
    styleSheet.type = "text/css";
    styleSheet.innerText = styles;
    document.head.appendChild(styleSheet);
    '''
    await page.evaluate(hide_elements_script)

    await page.evaluate('window.scrollTo(0, 0);')
    full_height = await page.evaluate('document.body.scrollHeight')

    await asyncio.sleep(5)

    y = 0
    while y < full_height:
        remaining_height = full_height - y
        clip_height = min(viewport_height, remaining_height)

        await page.set_viewport_size({"width": viewport_width, "height": clip_height})
        await page.evaluate(f'window.scrollTo(0, {y});')
        await asyncio.sleep(1)

        screenshot_path = temp_dir / f'screenshot_part_{y // (viewport_height - overlap) + 1}.png'
        logging.info(f"Saving screenshot to: {screenshot_path}")
        await page.screenshot(path=str(screenshot_path), full_page=False)
        if not screenshot_path.exists():
            raise FileNotFoundError(f"Screenshot was not created: {screenshot_path}")
        screenshots.append(screenshot_path)
        y += viewport_height - overlap

        if remaining_height <= viewport_height:
            break

    return screenshots

async def merge_screenshots(screenshot_paths, temp_dir):
    """Объединяет скриншоты в одно изображение."""
    images = [Image.open(path) for path in screenshot_paths]
    widths, heights = zip(*(i.size for i in images))
    total_height = sum(heights) - (len(images) - 1) * 10
    max_width = max(widths)

    new_image = Image.new('RGB', (max_width, total_height))

    y_offset = 0
    for image in images:
        new_image.paste(image, (0, y_offset))
        y_offset += image.height - 10

    merged_image_path = temp_dir / 'fullpage_screenshot.png'
    logging.info(f"Merging images to: {merged_image_path}")
    new_image.save(merged_image_path)

    if not merged_image_path.exists():
        raise FileNotFoundError(f"Merged image was not created: {merged_image_path}")
    
    return merged_image_path

async def convert_to_pdf(image_path, temp_dir):
    """Конвертирует объединенное изображение в PDF с использованием ReportLab."""
    pdf_path = temp_dir / 'output_fullpage.pdf'
    logging.info(f"Конвертация {image_path} в PDF: {pdf_path}")
    
    img = Image.open(image_path)
    width, height = img.size

    c = canvas.Canvas(str(pdf_path), pagesize=(width, height))
    c.drawImage(str(image_path), 0, 0, width=width, height=height)
    c.save()

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF не был создан: {pdf_path}")
    
    return pdf_path

async def generate_pdf(url, temp_dir):
    """Создает PDF из URL и возвращает путь к файлу."""
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            logging.info("Начало обработки страницы")

            await page.goto(url, wait_until='networkidle')
            await page.add_style_tag(content='.w-webflow-badge, a.buy-this-template.w-inline-block, a.all-templates.w-inline-block, div.hire-popup, div.hireus-badge-wrapper, div.promotion-labels-wrapper, div.buy-template, div.hire-us{ opacity: 0 !important; }')

            await asyncio.sleep(5)

            logging.info("Начало автоскроллинга")

            screenshots = await auto_scroll(page, temp_dir)
            
            logging.info("Автоскроллинг завершен, объединение скриншотов")
            
            full_screenshot_path = await merge_screenshots(screenshots, temp_dir)
            pdf_path = await convert_to_pdf(full_screenshot_path, temp_dir)
            
            logging.info(f'PDF создан: {pdf_path}')

            return str(pdf_path)

    except Exception as e:
        logging.error(f'Ошибка: {e}')
        return None
