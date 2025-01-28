import logging
import os
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.executor import start_polling  # Обновленный импорт
from bs4 import BeautifulSoup
import aiohttp
import asyncio
import time

# Настройки
API_TOKEN = os.getenv("API_TOKEN")  # Используйте переменные окружения для токена
TRIAL_PERIOD_DAYS = 2  # Пробный период в днях
PRICE_PER_WEEK = 10  # Цена за 7 дней в $

# Логирование
logging.basicConfig(level=logging.INFO)

# Инициализация бота
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Пользователи с активной подпиской
active_users = {}

# Функция для проверки подписки
def is_user_subscribed(user_id):
    if user_id in active_users:
        end_time = active_users[user_id]
        return time.time() < end_time
    return False

# Команда /start
@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    if is_user_subscribed(message.from_user.id):
        await message.reply("Добро пожаловать! Вы можете искать лучшие места в Таиланде.")
    else:
        trial_end = time.time() + TRIAL_PERIOD_DAYS * 86400
        active_users[message.from_user.id] = trial_end
        await message.reply(f"Добро пожаловать! У вас есть {TRIAL_PERIOD_DAYS} дня пробного доступа.")

# Асинхронный парсер данных с TripAdvisor
async def parse_tripadvisor(price_segment="budget"):
    url = f"https://www.tripadvisor.ru/Restaurants-g293915-Thailand.html"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers={"User-Agent": "Mozilla/5.0"}) as response:
            if response.status != 200:
                logging.error("Не удалось получить данные с сайта TripAdvisor")
                return []
            text = await response.text()
    
    soup = BeautifulSoup(text, 'html.parser')

    # Пример парсинга кафе
    cafes = []
    for item in soup.find_all("div", class_="_1llCuDZj")[:10]:  # Ограничимся 10 местами
        name = item.find("a", class_="_15_ydu6b")
        if name:
            name_text = name.text
            link = "https://www.tripadvisor.ru" + name["href"]
            cafes.append({"name": name_text, "link": link})

    return cafes

# Функция для отправки списка мест
async def send_places(message, price_segment):
    if not is_user_subscribed(message.from_user.id):
        await message.reply("Ваш пробный период истёк. Для продолжения оплатите доступ: $10 за 7 дней.")
        return

    places = await parse_tripadvisor(price_segment=price_segment)
    if not places:
        await message.reply("К сожалению, ничего не найдено.")
        return

    response = f"Лучшие места в сегменте '{price_segment}':\n\n"
    for place in places:
        response += f"{place['name']} - [Ссылка]({place['link']})\n"

    await message.reply(response, parse_mode="Markdown")

# Обработка команд
@dp.message_handler(commands=['budget'])
async def send_budget_places(message: types.Message):
    await send_places(message, "budget")

@dp.message_handler(commands=['medium'])
async def send_medium_places(message: types.Message):
    await send_places(message, "medium")

@dp.message_handler(commands=['premium'])
async def send_premium_places(message: types.Message):
    await send_places(message, "premium")

# Команда оплаты
@dp.message_handler(commands=['pay'])
async def send_payment_info(message: types.Message):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("Оплатить $10", url="https://your-payment-link.com"))
    await message.reply("Для продления доступа оплатите $10 за 7 дней.", reply_markup=keyboard)

# Запуск бота
if __name__ == "__main__":
    start_polling(dp, skip_updates=True)  # Обновленный вызов функции
