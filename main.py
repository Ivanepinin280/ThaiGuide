import logging
import os
import asyncio
import aiohttp
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, Router
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command
from aiogram.utils.markdown import hlink

# Настройки
API_TOKEN = os.getenv("API_TOKEN")
TRIAL_PERIOD_DAYS = 2  # Пробный период в днях
PRICE_PER_WEEK = 10  # Цена за 7 дней в $
TRIPADVISOR_URL = "https://www.tripadvisor.ru/Restaurants-g293915-Thailand.html"

# Логирование
logging.basicConfig(level=logging.INFO)

# Инициализация бота
bot = Bot(token=API_TOKEN, parse_mode="HTML")
dp = Dispatcher()
router = Router()
dp.include_router(router)

# Хранилище подписок
active_users = {}

# Функция проверки подписки
def is_user_subscribed(user_id: int) -> bool:
    """Проверяет, есть ли у пользователя активная подписка"""
    return user_id in active_users and datetime.now() < active_users[user_id]

# Команда /start
@router.message(Command("start"))
async def send_welcome(message: types.Message):
    user_id = message.from_user.id

    if is_user_subscribed(user_id):
        await message.answer("🎉 Добро пожаловать! Вы можете искать лучшие места в Таиланде.")
    else:
        trial_end = datetime.now() + timedelta(days=TRIAL_PERIOD_DAYS)
        active_users[user_id] = trial_end
        await message.answer(f"✨ Добро пожаловать! У вас есть {TRIAL_PERIOD_DAYS} дня пробного доступа.")

# Асинхронный парсер данных с TripAdvisor
async def parse_tripadvisor():
    """Парсит список ресторанов из TripAdvisor"""
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(TRIPADVISOR_URL, headers={"User-Agent": "Mozilla/5.0"}) as response:
                if response.status != 200:
                    logging.error(f"Ошибка {response.status} при получении данных с TripAdvisor")
                    return []

                text = await response.text()
        except Exception as e:
            logging.error(f"Ошибка запроса к TripAdvisor: {e}")
            return []

    from bs4 import BeautifulSoup  # Импортируем здесь, чтобы избежать ошибки при деплое
    soup = BeautifulSoup(text, "html.parser")

    places = []
    for item in soup.find_all("div", class_="_1llCuDZj")[:10]:  # Ограничимся 10 местами
        name_tag = item.find("a", class_="_15_ydu6b")
        if name_tag:
            name = name_tag.text
            link = "https://www.tripadvisor.ru" + name_tag["href"]
            places.append({"name": name, "link": link})

    return places

# Функция отправки списка мест
async def send_places(message: types.Message):
    """Отправляет пользователю список мест"""
    user_id = message.from_user.id

    if not is_user_subscribed(user_id):
        await message.answer("❌ Ваш пробный период истёк. Оплатите подписку за $10 / 7 дней.")
        return

    places = await parse_tripadvisor()
    if not places:
        await message.answer("😞 Не удалось найти заведения. Попробуйте позже.")
        return

    response = "🍽 Лучшие места в Таиланде:\n\n"
    for place in places:
        response += f"🔹 {hlink(place['name'], place['link'])}\n"

    await message.answer(response)

# Команды для получения списка мест
@router.message(Command("places"))
async def send_places_command(message: types.Message):
    await send_places(message)

# Команда оплаты
@router.message(Command("pay"))
async def send_payment_info(message: types.Message):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="💳 Оплатить $10", url="https://your-payment-link.com")]]
    )
    await message.answer("💰 Для продления доступа оплатите $10 за 7 дней.", reply_markup=keyboard)

# Функция очистки подписок (удаляет устаревшие записи)
async def clean_expired_subscriptions():
    """Удаляет подписки, если срок истёк"""
    while True:
        now = datetime.now()
        expired_users = [user_id for user_id, end_time in active_users.items() if end_time < now]

        for user_id in expired_users:
            del active_users[user_id]

        await asyncio.sleep(3600)  # Проверять раз в час

# Основная функция запуска бота
async def main():
    """Запускает бота и процесс очистки подписок"""
    asyncio.create_task(clean_expired_subscriptions())  # Запускаем фоновую очистку подписок
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

