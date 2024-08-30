import asyncio
import logging
import shutil
from pathlib import Path
from telegram import Bot

async def send_pdf_and_buttons(bot, chat_id, pdf_path, post_pdf_buttons, max_retries=3):
    """Отправка PDF и последующее сообщение с кнопками с повторными попытками."""
    for attempt in range(max_retries):
        try:
            logging.info("Открытие PDF для отправки клиенту...")
            with open(pdf_path, 'rb') as pdf_file:
                await bot.send_document(chat_id=chat_id, document=pdf_file, filename=Path(pdf_path).name)
            logging.info(f"PDF отправлен клиенту: {chat_id}")

            # Отправка сообщения с выбором действий после отправки PDF
            logging.info("Отправка сообщения с кнопками...")
            await bot.send_message(chat_id=chat_id, text="Пример сайта был отправлен. Просьба выбрать следующее действие.", reply_markup=post_pdf_buttons)
            logging.info(f"Сообщение с кнопками отправлено клиенту: {chat_id}")
            break  # Успешная отправка, выходим из цикла
        except Exception as e:
            logging.error(f"Ошибка при отправке PDF или сообщения с кнопками: {e}")
            if attempt < max_retries - 1:
                wait_time = 2 ** (attempt + 1)  # Увеличиваем время ожидания с каждой неудачной попыткой
                logging.info(f"Повторная попытка отправки ({attempt + 1}/{max_retries}) через {wait_time} секунд...")
                await asyncio.sleep(wait_time)
            else:
                logging.error("Превышено количество попыток отправки PDF и сообщения.")


async def remove_temp_dir(temp_dir: Path):
    """Асинхронное удаление временной директории."""
    try:
        if temp_dir.exists() and temp_dir.is_dir():
            logging.info(f"Удаление временной директории: {temp_dir}")
            shutil.rmtree(temp_dir)
            logging.info(f"Временная директория удалена: {temp_dir}")
    except Exception as e:
        logging.error(f"Ошибка при удалении временной директории: {e}")
