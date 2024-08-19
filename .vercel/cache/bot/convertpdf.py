import asyncio
import os
from PIL import Image
from pyppeteer import launch
from reportlab.pdfgen import canvas

async def auto_scroll(page):
    """Scroll the page and take screenshots."""
    viewport_height = 1080
    viewport_width = 1920
    overlap = 10
    screenshots = []

    await page.setViewport({'width': viewport_width, 'height': viewport_height})

    hide_elements_script = '''
    const styles = `
        .fixed-navbar,  /* Замените на нужные классы или идентификаторы */
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

        await page.setViewport({'width': viewport_width, 'height': clip_height})
        await page.evaluate(f'window.scrollTo(0, {y});')
        await asyncio.sleep(1)

        screenshot_path = f'screenshot_part_{y // (viewport_height - overlap) + 1}.png'
        await page.screenshot({'path': screenshot_path})
        screenshots.append(screenshot_path)
        y += viewport_height - overlap

        if remaining_height <= viewport_height:
            break

    return screenshots

def merge_screenshots(screenshot_paths):
    """Merge screenshots into one image."""
    images = [Image.open(path) for path in screenshot_paths]
    widths, heights = zip(*(i.size for i in images))
    total_height = sum(heights) - (len(images) - 1) * 10
    max_width = max(widths)

    new_image = Image.new('RGB', (max_width, total_height))

    y_offset = 0
    for image in images:
        new_image.paste(image, (0, y_offset))
        y_offset += image.height - 10

    merged_image_path = 'fullpage_screenshot.png'
    new_image.save(merged_image_path)
    return merged_image_path

def convert_to_pdf(image_path):
    """Convert the merged image into a PDF using ReportLab."""
    pdf_path = 'output_fullpage.pdf'
    img = Image.open(image_path)
    width, height = img.size

    c = canvas.Canvas(pdf_path, pagesize=(width, height))
    c.drawImage(image_path, 0, 0, width=width, height=height)
    c.save()
    return pdf_path

async def update_status(bot, chat_id, message_id, new_text):
    """Update the status message."""
    try:
        if message_id is not None:
            # Удаляем старое сообщение
            await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as e:
        print(f"Ошибка при удалении сообщения: {e}")
    
    try:
        # Отправляем новое сообщение
        new_message = await bot.send_message(chat_id=chat_id, text=new_text)
        return new_message.message_id
    except Exception as e:
        print(f"Ошибка при отправке нового сообщения: {e}")
        return None

async def generate_pdf(url, chat_id, message_id, bot):
    """Generate PDF from a URL and return the path."""
    browser = await launch(headless=True)
    page = await browser.newPage()
    screenshots = []
    full_screenshot_path = None

    progress_messages = [
        "🕑 Подготовка...",
        "🔍 Обработка...",
        "📜 Генерация...",
        "💾 Завершение..."
    ]

    try:
        message_id = await update_status(bot, chat_id, message_id, progress_messages[0])
        
        await page.goto(url, {'waitUntil': 'networkidle0', 'timeout': 80000})
        await page.addStyleTag({'content': '.w-webflow-badge, a.buy-this-template.w-inline-block, a.all-templates.w-inline-block, div.hire-popup, div.hireus-badge-wrapper, div.promotion-labels-wrapper, div.buy-template, div.hire-us{ opacity: 0 !important; }'})

        await asyncio.sleep(5)

        message_id = await update_status(bot, chat_id, message_id, progress_messages[1])

        screenshots = await auto_scroll(page)
        
        message_id = await update_status(bot, chat_id, message_id, progress_messages[2])

        full_screenshot_path = merge_screenshots(screenshots)
        pdf_path = convert_to_pdf(full_screenshot_path)

        # Обновляем статус
        await update_status(bot, chat_id, message_id, progress_messages[3])


        print(f'PDF создан: {pdf_path}')
        return pdf_path
        

    except Exception as e:
        print(f'Ошибка: {e}')
        # Обновляем статус с ошибкой
        #await update_status(bot, chat_id, message_id, "❌ Произошла ошибка при создании PDF. Попробуйте снова.")
        return None

    finally:
        await browser.close()

        # Очистка временных файлов
        for path in screenshots:
            if os.path.exists(path):
                os.remove(path)
        if full_screenshot_path and os.path.exists(full_screenshot_path):
            os.remove(full_screenshot_path)
