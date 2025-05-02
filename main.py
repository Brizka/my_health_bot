from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
import logging
import datetime
import sqlite3

API_TOKEN = 'YOUR_BOT_TOKEN_HERE'
ADMIN_ID = 123456789  # замените на ваш Telegram ID

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Connect to SQLite
conn = sqlite3.connect('healthmate.db')
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT, age INTEGER, goal TEXT, habit TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS calories (product TEXT, kcal INTEGER)''')
conn.commit()

# Pre-fill calorie database
products = [('яблоко', 52), ('банан', 89), ('хлеб', 265), ('рис', 130), ('курица', 165)]
c.executemany("INSERT OR IGNORE INTO calories (product, kcal) VALUES (?, ?)", products)
conn.commit()

# States
class Register(StatesGroup):
    name = State()
    age = State()
    goal = State()

class HabitState(StatesGroup):
    habit = State()

class CalorieState(StatesGroup):
    product = State()

class BroadcastState(StatesGroup):
    text = State()

# Keyboards
main_kb = ReplyKeyboardMarkup(resize_keyboard=True)
main_kb.add(KeyboardButton("📋 Мои задачи"))
main_kb.add(KeyboardButton("📊 Мой прогресс"), KeyboardButton("🧠 Совет дня"))
main_kb.add(KeyboardButton("🚭 Бросить привычку"), KeyboardButton("🍽 Калории"))

admin_kb = ReplyKeyboardMarkup(resize_keyboard=True)
admin_kb.add(KeyboardButton("📤 Рассылка"), KeyboardButton("👥 Пользователи"))
admin_kb.add(KeyboardButton("↩ Назад"))

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("Добро пожаловать, Админ!", reply_markup=admin_kb)
        return
    await message.answer("Привет! Я твой помощник по здоровью. Как тебя зовут?")
    await Register.name.set()

@dp.message_handler(commands=['admin'])
async def admin_panel(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("Админ-панель:", reply_markup=admin_kb)

@dp.message_handler(Text(equals="📤 Рассылка"))
async def broadcast_entry(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("Введите текст для рассылки:")
        await BroadcastState.text.set()

@dp.message_handler(state=BroadcastState.text)
async def broadcast_send(message: types.Message, state: FSMContext):
    text = message.text
    c.execute("SELECT id FROM users")
    users = c.fetchall()
    for user in users:
        try:
            await bot.send_message(user[0], f"📢 {text}")
        except:
            continue
    await message.answer("✅ Рассылка завершена.", reply_markup=admin_kb)
    await state.finish()

@dp.message_handler(Text(equals="👥 Пользователи"))
async def show_users(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        c.execute("SELECT COUNT(*) FROM users")
        count = c.fetchone()[0]
        await message.answer(f"Всего зарегистрировано: {count} пользователей.")

@dp.message_handler(Text(equals="↩ Назад"))
async def back_to_user(message: types.Message):
    await message.answer("Возвращаю обычное меню", reply_markup=main_kb)

@dp.message_handler(state=Register.name)
async def get_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Сколько тебе лет?")
    await Register.next()

@dp.message_handler(state=Register.age)
async def get_age(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("Пожалуйста, введи возраст цифрами.")
    await state.update_data(age=int(message.text))
    await message.answer("Какая у тебя цель? (например: похудеть, высыпаться)")
    await Register.next()

@dp.message_handler(state=Register.goal)
async def get_goal(message: types.Message, state: FSMContext):
    data = await state.get_data()
    name = data['name']
    age = data['age']
    goal = message.text
    c.execute("INSERT OR IGNORE INTO users (id, name, age, goal) VALUES (?, ?, ?, ?)", (message.from_user.id, name, age, goal))
    conn.commit()
    await message.answer(f"Отлично, {name}! Цель: {goal}. Я буду с тобой каждый день!", reply_markup=main_kb)
    await state.finish()

@dp.message_handler(Text(equals="📋 Мои задачи"))
async def show_tasks(message: types.Message):
    tasks = [
        "✅ Выпей 2 стакана воды",
        "🏃 Прогуляйся 10 минут",
        "🧘 Сделай дыхательное упражнение 5 минут"
    ]
    await message.answer("Твои задачи на сегодня:")
    for task in tasks:
        await message.answer(task)

@dp.message_handler(Text(equals="🧠 Совет дня"))
async def health_tip(message: types.Message):
    tips = [
        "Пейте воду утром натощак.",
        "Сон до 23:00 — лучшее лекарство.",
        "Добавляйте овощи к каждому приёму пищи."
    ]
    await message.answer(f"💡 {tips[datetime.datetime.now().day % len(tips)]}")

@dp.message_handler(Text(equals="📊 Мой прогресс"))
async def progress(message: types.Message):
    c.execute("SELECT goal, habit FROM users WHERE id=?", (message.from_user.id,))
    user = c.fetchone()
    if user:
        await message.answer(f"🎯 Твоя цель: {user[0]}\n🚭 Привычка для отказа: {user[1] or 'не выбрана'}")
    else:
        await message.answer("Ты ещё не зарегистрирован. Напиши /start")

@dp.message_handler(Text(equals="🚭 Бросить привычку"))
async def quit_habit(message: types.Message):
    await message.answer("🚭 Напиши, от какой привычки ты хочешь избавиться.")
    await HabitState.habit.set()

@dp.message_handler(state=HabitState.habit)
async def set_habit(message: types.Message, state: FSMContext):
    c.execute("UPDATE users SET habit=? WHERE id=?", (message.text, message.from_user.id))
    conn.commit()
    await message.answer(f"Отлично, начинаем бороться с привычкой: {message.text}!", reply_markup=main_kb)
    await state.finish()

@dp.message_handler(Text(equals="🍽 Калории"))
async def calories(message: types.Message):
    await message.answer("Введите название продукта, чтобы узнать калорийность.")
    await CalorieState.product.set()

@dp.message_handler(state=CalorieState.product)
async def product_calories(message: types.Message, state: FSMContext):
    product = message.text.lower()
    c.execute("SELECT kcal FROM calories WHERE product=?", (product,))
    result = c.fetchone()
    if result:
        await message.answer(f"🔢 В {product} — {result[0]} ккал на 100 г")
    else:
        await message.answer("❌ Продукт не найден в базе.")
    await state.finish()

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
