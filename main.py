import asyncio
import aiohttp
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import os
from dotenv import load_dotenv

load_dotenv()
bot = Bot(os.getenv("API_TOKEN"))
dp = Dispatcher(storage=MemoryStorage())

# Хранилище времени пользователя
user_schedules = {}


# FINITE STATE MACHINE (FSM) для выбора времени
class ScheduleState(StatesGroup):
    waiting_for_time = State()


async def generate_finance_question():
    """Генерирует вопрос по финансовой грамотности используя DeepSeek API"""
    api_key = os.getenv("DEEPSEEK_API_KEY")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    prompt = (
        "Сгенерируй новый практический вопрос по финансовой грамотности для ежедневного задания. "
        "Вопрос должен быть на русском языке, требовать развернутого ответа и охватывать разные аспекты: "
        "инвестиции, бюджетрование, кредиты, сбережения или финансовое планирование. "
        "Формат: четкий и понятный вопрос, который побуждает к размышлениям."
    )

    data = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 500
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                    "https://api.deepseek.com/v1/chat/completions",
                    headers=headers,
                    json=data,
                    timeout=10
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return result['choices'][0]['message']['content']
                return "Не удалось сгенерировать вопрос. Попробуйте позже."

    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        print(f"API Error: {str(e)}")
        return "Извините, сервис генерации вопросов временно недоступен."


# Команда /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await message.answer(
        "Привет! Я бот, который поможет тебе стать финансово грамотным!\n"
        "Давайте установим время для отправки ежедневных заданий.\n"
        "Введите время в формате HH:MM (например, 18:30):"
    )
    await state.set_state(ScheduleState.waiting_for_time)


# Обработка введенного времени
@dp.message(ScheduleState.waiting_for_time)
async def process_time(message: types.Message, state: FSMContext):
    try:
        time_str = message.text
        time_obj = datetime.strptime(time_str, "%H:%M").time()
        user_schedules[message.from_user.id] = time_obj
        await message.answer(f"Время установлено на {time_str}. Вы будете получать задания каждый день в это время.")
        await state.clear()
    except ValueError:
        await message.answer("Неверный формат времени. Пожалуйста, введите время в формате HH:MM.")


# Функция отправки задания
async def send_quiz(user_id: int):
    question = await generate_finance_question()
    await bot.send_message(user_id, f"📚 Ваше задание на сегодня:\n\n{question}")


# Планировщик задач
async def scheduler():
    while True:
        now = datetime.now().time()
        for user_id, scheduled_time in user_schedules.items():
            if now.hour == scheduled_time.hour and now.minute == scheduled_time.minute:
                asyncio.create_task(send_quiz(user_id))
        await asyncio.sleep(60)  # Проверяем каждую минуту


# Запуск бота
async def main():
    asyncio.create_task(scheduler())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())