from celery import Celery
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# Настройка Celery
celery_app = Celery('tasks', broker='redis://localhost:6379/0', backend='redis://localhost:6379/0')

# Кнопки обратной связи и выбора категории
CONTACT_BUTTON = InlineKeyboardButton("Мне понравилось, свяжитесь со мной!", callback_data='contact')
NEW_PDF_BUTTON = InlineKeyboardButton("Сгенерировать еще один вариант!", callback_data='new_pdf')
CHOOSE_CATEGORY_BUTTON = InlineKeyboardButton("Выбрать другую категорию", callback_data='choose_category')
POST_PDF_BUTTONS = InlineKeyboardMarkup([[CONTACT_BUTTON], [NEW_PDF_BUTTON], [CHOOSE_CATEGORY_BUTTON]])

