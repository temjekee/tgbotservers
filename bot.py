import logging
import uuid
import asyncio
import urllib.parse
from config import celery_app, POST_PDF_BUTTONS
from tasks import celery_app
from pathlib import Path
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackContext, filters, CallbackQueryHandler
from celery import Celery
from celery.result import AsyncResult
import aiohttp
from bs4 import BeautifulSoup
import random

# Вставьте сюда ваш Telegram Bot Token
TOKEN = '7523844020:AAEwv9bZcvGC4ChKz20zZIFxWIQdKLEWAyg'
GROUP_CHAT_ID = -1002201196372

# Настройка Celery для взаимодействия с Redis
celery_app = Celery('tasks', broker='redis://localhost:6379/0', backend='redis://localhost:6379/0')
logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)

# Глобальные переменные для кнопок и категорий
CATEGORY_BUTTONS = [
    ['Technology Websites', 'Design Websites'],
    ['Business Websites', 'Blog Websites'],
    ['Marketing Websites', 'Photography & Video Websites'],
    ['Entertainment Websites', 'Food & drink Websites'],
    ['Travel Websites', 'Education Websites'],
    ['Sports Websites', 'Medical Websites'],
    ['Beauty & Wellness Websites', 'Fashion Websites'],
]

category_mapping = {
    'Technology Websites': 'technology-websites',
    'Design Websites': 'design-websites',
    'Business Websites': 'business-websites',
    'Blog Websites': 'blog-websites',
    'Marketing Websites': 'marketing-websites',
    'Photography & Video Websites': 'photography-and-video-websites',
    'Entertainment Websites': 'entertainment-websites',
    'Food & drink Websites': 'food-and-drink-websites',
    'Travel Websites': 'travel-websites',
    'Education Websites': 'education-websites',
    'Sports Websites': 'sports-websites',
    'Medical Websites': 'medical-websites',
    'Beauty & Wellness Websites': 'beauty-and-wellness-websites',
    'Fashion Websites': 'fashion-websites',
}

# Кнопки обратной связи и выбора категории
CONTACT_BUTTON = InlineKeyboardButton("Мне понравилось, свяжитесь со мной!", callback_data='contact')
NEW_PDF_BUTTON = InlineKeyboardButton("Сгенерировать еще один вариант!", callback_data='new_pdf')
CHOOSE_CATEGORY_BUTTON = InlineKeyboardButton("Выбрать другую категорию", callback_data='choose_category')
POST_PDF_BUTTONS = InlineKeyboardMarkup([[CONTACT_BUTTON], [NEW_PDF_BUTTON], [CHOOSE_CATEGORY_BUTTON]])

# Функция для запуска бота
def main() -> None:
    application = Application.builder().token(TOKEN).build()

    # Обработчики команд и сообщений
    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex('^(Technology|Design|Business|Blog|Marketing|Photography & Video|Entertainment|Food & drink|Travel|Education|Sports|Medical|Beauty & Wellness|Fashion) Websites$'), handle_category_selection))
    application.add_handler(CallbackQueryHandler(handle_button_click))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'.*@.*\..*'), handle_email_input))

    application.run_polling()

# Обработчик команды /start
async def start(update: Update, context: CallbackContext) -> None:
    reply_markup = ReplyKeyboardMarkup(CATEGORY_BUTTONS, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        'Привет! Я бот компании InChain Digital. Можешь выбрать категорию, и я покажу тебе, как твой сайт мог бы выглядеть!',
        reply_markup=reply_markup
    )

async def get_templates(category_key: str) -> list:
    url = f"https://webflow.com/templates/category/{category_key}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status != 200:
                logging.error(f"Failed to fetch templates from {url}")
                return []
            page_content = await response.text()
            soup = BeautifulSoup(page_content, 'html.parser')
            templates = [a['href'] for a in soup.select('a.tm-templates-preview_link') if 'href' in a.attrs]
            return templates

def get_random_template(templates: list) -> str:
    return random.choice(templates) if templates else None

# Обработчик выбора категории
async def handle_category_selection(update: Update, context: CallbackContext) -> None:
    category = update.message.text
    if category in category_mapping:
        category_key = category_mapping[category]
        context.user_data['current_category'] = category_key

        # Генерация и отправка PDF
        asyncio.create_task(generate_and_send_pdf(update, context, category, category_key))
    else:
        await update.message.reply_text('Вы выбрали неизвестную категорию. Пожалуйста, выберите одну из предложенных кнопок.')


async def generate_and_send_pdf(update: Update, context: CallbackContext, category: str, category_key: str) -> None:
    templates = await get_templates(category_key)
    random_template = get_random_template(templates)
    if not random_template:
        await update.message.reply_text("Не удалось найти шаблоны для выбранной категории.")
        return
    
    if urllib.parse.urlparse(random_template).netloc == '':
        url_template = f"https://webflow.com{random_template}"
    else:
        url_template = random_template

    context.user_data['template_url'] = url_template  # Сохраняем ссылку на шаблон в контексте

    temp_dir = f"temp_{uuid.uuid4().hex}"
    task = celery_app.send_task('generate_pdf_task', args=[url_template, temp_dir, update.message.chat_id])
    await update.message.reply_text('Создание PDF... Пожалуйста, подождите.')

# Обработчик нажатия кнопок
async def handle_button_click(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()

    if query.data == 'contact':
        await query.message.reply_text("Введите ваш e-mail для связи. Спасибо!")
        context.user_data['awaiting_email'] = True  # Устанавливаем флаг ожидания email
    elif query.data == 'new_pdf':
        category_key = context.user_data.get('current_category')
        if category_key:
            asyncio.create_task(generate_and_send_pdf(update, context, category_key, category_key))
    elif query.data == 'choose_category':
        reply_markup = ReplyKeyboardMarkup(CATEGORY_BUTTONS, one_time_keyboard=True, resize_keyboard=True)
        await query.message.reply_text("Выберите новую категорию для вашего будущего сайта:", reply_markup=reply_markup)

# Обработчик ввода email
async def handle_email_input(update: Update, context: CallbackContext) -> None:
    if context.user_data.get('awaiting_email'):
        email = update.message.text
        template_url = context.user_data.get('template_url')
        if email and template_url:
            await bot.send_message(
                chat_id=GROUP_CHAT_ID,
                text=f"Получен новый контакт!\nEmail: {email}\nШаблон: {template_url}"
            )
            await update.message.reply_text("Спасибо! Ваши данные отправлены.")
            context.user_data['awaiting_email'] = False  # Сбрасываем флаг ожидания email
        else:
            await update.message.reply_text("Произошла ошибка. Попробуйте снова.")
    else:
        await update.message.reply_text("Пожалуйста, выберите действие с помощью кнопок ниже.")

if __name__ == '__main__':
    main()
