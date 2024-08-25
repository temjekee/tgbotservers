import logging
import asyncio
import uuid
import shutil
import aiofiles
from pathlib import Path
from telegram.error import BadRequest
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackContext, filters, CallbackQueryHandler
from webflow import get_templates, get_random_template
from convertpdf import generate_pdf
from config import TOKEN
from concurrent.futures import ThreadPoolExecutor

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Пул потоков для работы с блокирующими задачами
executor = ThreadPoolExecutor(max_workers=5)

# Глобальный словарь для хранения данных о PDF по сообщениям
pdf_data = {}  # message_id -> template_url
user_pdf_history = {}  # user_id -> list of message_ids

# Кнопки для выбора категории
CATEGORY_BUTTONS = [
    ['Technology Websites', 'Design Websites'],
    ['Business Websites', 'Blog Websites'],
    ['Marketing Websites', 'Photography & Video Websites'],
    ['Entertainment Websites', 'Food & drink Websites'],
    ['Travel Websites', 'Education Websites'],
    ['Sports Websites', 'Medical Websites'],
    ['Beauty & Wellness Websites', 'Fashion Websites'],
]

# Глобальная переменная category_mapping
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

# Кнопки обратной связи, генерации нового PDF и выбора другой категории
CONTACT_BUTTON = InlineKeyboardButton("Мне понравилось, свяжитесь со мной!", callback_data='contact')
NEW_PDF_BUTTON = InlineKeyboardButton("Сгенерировать еще один вариант!", callback_data='new_pdf')
CHOOSE_CATEGORY_BUTTON = InlineKeyboardButton("Выбрать другую категорию", callback_data='choose_category')

TEMP_DIRS = {}  # {temp_dir: creation_time}

async def cleanup_temp_dirs(context: CallbackContext) -> None:
    """Фоновая задача для очистки старых временных директорий."""
    now = datetime.now()
    for temp_dir, creation_time in list(TEMP_DIRS.items()):
        if now - creation_time > timedelta(minutes=5):
            try:
                shutil.rmtree(temp_dir)
                logging.info(f"Временная директория {temp_dir} успешно удалена через 5 минут.")
                TEMP_DIRS.pop(temp_dir)
            except Exception as e:
                logging.error(f"Ошибка при удалении временной директории {temp_dir}: {e}")

async def start(update: Update, context: CallbackContext) -> None:
    logging.info("Received /start command")
    reply_markup = ReplyKeyboardMarkup(CATEGORY_BUTTONS, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        'Привет! Я бот компании InChain Digital. Можешь выбрать категорию и я тебя покажу, как твой сайт мог бы выглядеть!',
        reply_markup=reply_markup
    )

async def handle_category_selection(update: Update, context: CallbackContext) -> None:
    category = update.message.text
    if category in category_mapping:
        category_key = category_mapping[category]
        context.user_data['current_category'] = category_key
        await generate_and_send_pdf(update, context, category, category_key)
    else:
        await update.message.reply_text('Вы выбрали неизвестную категорию. Пожалуйста, выберите одну из предложенных кнопок.')

async def safe_delete_message(bot, chat_id, message_id):
    """Пробует удалить сообщение, если оно существует."""
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
        logging.info(f"Сообщение с ID: {message_id} было удалено.")
    except Exception as e:
        logging.error(f"Ошибка при удалении сообщения с ID: {message_id}: {e}")

async def safe_delete_temp_dir(temp_dir: Path):
    """Безопасное удаление временной директории с логированием ошибок."""
    try:
        shutil.rmtree(temp_dir)
        logging.info(f"Временная директория удалена: {temp_dir}")
    except Exception as e:
        logging.error(f"Ошибка при удалении временной директории {temp_dir}: {e}")

async def update_status_message(bot, chat_id, message_id, status):
    """Обновляет статусное сообщение с прогрессом."""
    try:
        await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=status)
    except Exception as e:
        logging.error(f"Ошибка при обновлении статусного сообщения: {e}")

async def generate_pdf_and_save(template, temp_dir):
    """Функция только для генерации и сохранения PDF."""
    try:
        pdf_path = await generate_pdf(template, temp_dir)
        return pdf_path
    except Exception as e:
        logging.error(f"Ошибка генерации PDF: {e}")
        return None

async def send_pdf(update: Update, context: CallbackContext, pdf_path: str, template: str) -> None:
    """Функция только для отправки PDF."""
    if pdf_path:
        pdf_filename = Path(pdf_path).name  # Извлекаем имя файла
        async with aiofiles.open(pdf_path, 'rb') as pdf_file:
            pdf_content = await pdf_file.read()  # Асинхронное чтение файла

        reply_markup = InlineKeyboardMarkup([[CONTACT_BUTTON], [NEW_PDF_BUTTON], [CHOOSE_CATEGORY_BUTTON]])

        try:
            if update.message:
                sent_message = await update.message.reply_document(
                    pdf_content, filename=pdf_filename
                )
            else:
                sent_message = await context.bot.send_document(
                    chat_id=update.callback_query.message.chat_id,
                    document=pdf_content,
                    filename=pdf_filename
                )

            pdf_data[sent_message.message_id] = template
            user_id = update.effective_user.id
            if user_id not in user_pdf_history:
                user_pdf_history[user_id] = []
            user_pdf_history[user_id].append(sent_message.message_id)

            logging.info(f"PDF отправлен: {pdf_path}")

            # Отправляем сообщение с вопросом и кнопками
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Сайт был сделан. Что теперь ты бы хотел сделать дальше? Выбери из трех вариантов:",
                reply_markup=reply_markup
            )
        except Exception as e:
            logging.error(f"Ошибка при отправке PDF: {e}")
            await update.message.reply_text("Произошла ошибка при отправке PDF. Попробуйте снова.")

async def generate_and_send_pdf(update: Update, context: CallbackContext, category: str, category_key: str) -> None:
    try:
        # Асинхронно получаем шаблоны
        templates = await get_templates(category_key)
        logging.info(f"Templates found: {templates}")

        if templates:
            template = get_random_template(templates)
            logging.info(f"Selected template: {template}")
            if template:
                waiting_message = None
                if update.message:
                    waiting_message = await update.message.reply_text('Создание PDF... Пожалуйста, подождите.')
                elif update.callback_query:
                    waiting_message = await context.bot.send_message(
                        chat_id=update.callback_query.message.chat_id,
                        text='Создание PDF... Пожалуйста, подождите.'
                    )

                # Создаем временную директорию
                temp_dir = Path(f"temp_{uuid.uuid4().hex}")
                temp_dir.mkdir(parents=True, exist_ok=True)
                TEMP_DIRS[temp_dir] = datetime.now()

                # Сохраняем шаблон в user_data до создания PDF
                context.user_data['last_template'] = template

                try:
                    # Статусные сообщения
                    status_updates = [
                        "🔍 Обработка...",
                        "📜 Генерация...",
                        "💾 Создание...",
                        "🔄 Завершение процесса..."
                    ]

                    for status in status_updates:
                        await update_status_message(context.bot, waiting_message.chat_id, waiting_message.message_id, status)
                        await asyncio.sleep(10)  # Задержка перед следующим обновлением статуса

                    # Генерация PDF в фоне
                    pdf_path = await generate_pdf_and_save(template, temp_dir)
                except Exception as e:
                    logging.error(f"Ошибка генерации PDF: {e}")
                    await update.message.reply_text(f'Не удалось создать PDF для шаблона {template}. Попробуйте снова.')
                    raise

                if pdf_path:
                    await send_pdf(update, context, pdf_path, template)
                    await safe_delete_message(context.bot, waiting_message.chat_id, waiting_message.message_id)
                    # Удаляем временные файлы после отправки
                    asyncio.create_task(safe_delete_temp_dir(temp_dir))
                else:
                    await update.message.reply_text(f'Не удалось создать PDF для шаблона {template}. Попробуйте снова.')
                    await safe_delete_message(context.bot, waiting_message.chat_id, waiting_message.message_id)
                    asyncio.create_task(safe_delete_temp_dir(temp_dir))
            else:
                await update.message.reply_text(f'Не удалось найти шаблоны для категории {category}. Попробуйте снова.')
        else:
            await update.message.reply_text(f'Не удалось найти шаблоны для категории {category}. Попробуйте снова.')
    except Exception as e:
        logging.error(f"Ошибка в процессе генерации и отправки PDF: {e}")
        await update.message.reply_text("Произошла ошибка при обработке запроса. Попробуйте снова.")

async def handle_button_click(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    
    try:
        # Отвечаем на callback_query сразу, чтобы предотвратить его устаревание
        await query.answer()

        if query.data == 'contact':
            template_url = context.user_data.get('last_template')

            if template_url:
                await query.message.reply_text("Пожалуйста, введите ваш адрес электронной почты.")
                context.user_data['waiting_for_email'] = True
                context.user_data['template_url'] = template_url
                logging.info(f"Waiting for email input from user. Associated template: {template_url}")
            else:
                await query.message.reply_text("Ошибка: шаблон не найден.")
        
        elif query.data == 'new_pdf':
            category_key = context.user_data.get('current_category')
            category_name = next((k for k, v in category_mapping.items() if v == category_key), None)

            if category_key and category_name:
                # Выполняем генерацию PDF в фоне
                asyncio.create_task(generate_and_send_pdf(update, context, category_name, category_key))
            else:
                await query.message.reply_text("Ошибка: категория не найдена.")
        
        elif query.data == 'choose_category':
            reply_markup = ReplyKeyboardMarkup(CATEGORY_BUTTONS, one_time_keyboard=True, resize_keyboard=True)
            await query.message.reply_text("Выберите новую категорию для вашего будущего сайта:", reply_markup=reply_markup)

    except BadRequest as e:
        logging.error(f"Error in handling button click: {e}")
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Произошла ошибка при обработке вашего запроса. Попробуйте снова.")

async def handle_email_input(update: Update, context: CallbackContext) -> None:
    logging.info(f"Received message: {update.message.text}")

    if context.user_data.get('waiting_for_email'):
        email = update.message.text
        logging.info(f"Email received: {email}")
        context.user_data['waiting_for_email'] = False

        template_url = context.user_data.get('template_url')

        if template_url:
            group_chat_id = -1002201196372  # ID группы для отправки данных
            message_text = f"Новый запрос на контакт:\nEmail: {email}\nШаблон: {template_url}"

            try:
                await context.bot.send_message(chat_id=group_chat_id, text=message_text)
                logging.info("Email and template URL sent to group chat.")
                await update.message.reply_text("Спасибо! Мы свяжемся с вами.")
            except Exception as e:
                logging.error(f"Error sending message to group: {e}")
        else:
            await update.message.reply_text("Ошибка: шаблон не найден.")
    else:
        logging.info("Message received but not in 'waiting_for_email' state, ignoring.")

def main() -> None:
    application = Application.builder().token(TOKEN).build()

    # Добавляем обработчики команд и сообщений
    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex('^(Technology|Design|Business|Blog|Marketing|Photography & Video|Entertainment|Food & drink|Travel|Education|Sports|Medical|Beauty & Wellness|Fashion) Websites$'), handle_category_selection))
    application.add_handler(CallbackQueryHandler(handle_button_click))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'.*@.*\..*'), handle_email_input))

    # Запускаем фоновую задачу для очистки временных директорий
    application.job_queue.run_repeating(cleanup_temp_dirs, interval=60)

    application.run_polling()

if __name__ == '__main__':
    main()
