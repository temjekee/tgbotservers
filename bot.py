import logging
import asyncio
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackContext, filters, CallbackQueryHandler
from webflow import get_templates, get_random_template
from convertpdf import generate_pdf
from config import TOKEN

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

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

# Кнопки обратной связи и генерации нового PDF
CONTACT_BUTTON = InlineKeyboardButton("Мне понравилось, хочу чтобы со мной связались", callback_data='contact')
NEW_PDF_BUTTON = InlineKeyboardButton("Сгенерировать еще один PDF", callback_data='new_pdf')

async def start(update: Update, context: CallbackContext) -> None:
    logging.info("Received /start command")
    reply_markup = ReplyKeyboardMarkup(CATEGORY_BUTTONS, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        'Привет! Выберите категорию для поиска шаблонов:',
        reply_markup=reply_markup
    )

async def handle_category_selection(update: Update, context: CallbackContext) -> None:
    category = update.message.text
    if category in category_mapping:
        category_key = category_mapping[category]
        context.user_data['current_category'] = category_key  # Сохраняем текущую категорию для повторного использования
        await generate_and_send_pdf(update, context, category, category_key)
    else:
        await update.message.reply_text('Вы выбрали неизвестную категорию. Пожалуйста, выберите одну из предложенных кнопок.')

async def generate_and_send_pdf(update: Update, context: CallbackContext, category: str, category_key: str) -> None:
    templates = get_templates(category_key)
    logging.info(f"Templates found: {templates}")

    if templates:
        template = get_random_template(templates)
        logging.info(f"Selected template: {template}")
        if template:
            # Сохраняем статус ожидания перед созданием PDF
            if update.message:
                waiting_message = await update.message.reply_text(
                    f'Вот случайный шаблон для категории {category}: {template}\n\nСоздание PDF... Пожалуйста, подождите.'
                )
            else:
                # При работе через callback_query
                waiting_message = await context.bot.send_message(
                    chat_id=update.callback_query.message.chat_id,
                    text=f'Вот случайный шаблон для категории {category}: {template}\n\nСоздание PDF... Пожалуйста, подождите.'
                )

            try:
                pdf_path = await asyncio.wait_for(generate_pdf(template, waiting_message.chat_id, waiting_message.message_id, context.bot), timeout=1000)
                if pdf_path:
                    with open(pdf_path, 'rb') as pdf_file:
                        reply_markup = InlineKeyboardMarkup([[CONTACT_BUTTON], [NEW_PDF_BUTTON]])

                        if update.message:
                            sent_message = await update.message.reply_document(pdf_file, reply_markup=reply_markup)
                        else:
                            sent_message = await context.bot.send_document(
                                chat_id=update.callback_query.message.chat_id,
                                document=pdf_file,
                                reply_markup=reply_markup
                            )

                        # Сохраняем данные о сообщении и шаблоне
                        pdf_data[sent_message.message_id] = template

                        # Обновляем историю PDF для пользователя
                        user_id = update.effective_user.id
                        if user_id not in user_pdf_history:
                            user_pdf_history[user_id] = []
                        user_pdf_history[user_id].append(sent_message.message_id)

                    logging.info(f"PDF отправлен: {pdf_path}")
                    await safe_delete_message(context.bot, waiting_message.chat_id, waiting_message.message_id)
                else:
                    await update.message.reply_text(f'Не удалось создать PDF для шаблона {template}. Попробуйте снова.')
                    await safe_delete_message(context.bot, waiting_message.chat_id, waiting_message.message_id)
            except asyncio.TimeoutError:
                await update.message.reply_text("Время ожидания создания PDF истекло. Попробуйте позже.")
            except Exception as e:
                logging.error(f"Ошибка генерации PDF: {e}")
        else:
            await update.message.reply_text(f'Не удалось найти шаблоны для категории {category}. Попробуйте снова.')
    else:
        await update.message.reply_text(f'Не удалось найти шаблоны для категории {category}. Попробуйте снова.')

async def safe_delete_message(bot, chat_id, message_id):
    """Пробует удалить сообщение, если оно существует."""
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
        logging.info(f"Сообщение с ID: {message_id} было удалено.")
    except Exception as e:
        logging.error(f"Ошибка при удалении сообщения с ID: {message_id}: {e}")

async def handle_button_click(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    if query.data == 'contact':
        await query.answer()

        # Получаем шаблон, который связан с сообщением
        template_url = pdf_data.get(query.message.message_id)

        if template_url:
            await query.message.reply_text("Пожалуйста, введите ваш адрес электронной почты.")
            context.user_data['waiting_for_email'] = True
            context.user_data['template_url'] = template_url  # Сохраняем этот URL для отправки в группу
            logging.info(f"Waiting for email input from user. Associated template: {template_url}")
        else:
            # Если шаблон не найден в конкретном сообщении, используем последний созданный шаблон
            last_template = context.user_data.get('last_template')
            if last_template:
                context.user_data['template_url'] = last_template
                await query.message.reply_text("Пожалуйста, введите ваш адрес электронной почты.")
                context.user_data['waiting_for_email'] = True
                logging.info(f"Using last template. Associated template: {last_template}")
            else:
                await query.message.reply_text("Ошибка: шаблон не найден.")
    elif query.data == 'new_pdf':
        await query.answer()

        # Используем сохраненную категорию для генерации нового PDF
        category_key = context.user_data.get('current_category')
        category_name = next((k for k, v in category_mapping.items() if v == category_key), None)

        if category_key and category_name:
            await generate_and_send_pdf(update, context, category_name, category_key)
        else:
            await query.message.reply_text("Ошибка: категория не найдена.")

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

    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex('^(Technology|Design|Business|Blog|Marketing|Photography & Video|Entertainment|Food & drink|Travel|Education|Sports|Medical|Beauty & Wellness|Fashion) Websites$'), handle_category_selection))
    application.add_handler(CallbackQueryHandler(handle_button_click))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'.*@.*\..*'), handle_email_input))

    application.run_polling()

if __name__ == '__main__':
    main()
