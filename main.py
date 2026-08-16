import os
import asyncio
from aiohttp import web

# Event loop sozlamasi
asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())

import logging
import asyncpg
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

# --- SOZLAMALAR ---
BOT_TOKEN = "8634039492:AAF_RmClS3qUxkX1QtuS1ABcvbhGwUyFfEE"
ADMIN_ID = 1316308230
KANAL_ID = "@kinoqidir_N1"
INSTAGRAM_LINK = "https://instagram.com/kinoqidir_uzb"

DATABASE_URL = os.environ.get("DATABASE_URL")

logging.basicConfig(level=logging.INFO)

class MovieState(StatesGroup):
    waiting_for_file = State()
    waiting_for_name = State()
    waiting_for_code = State()

class ReqState(StatesGroup):
    waiting_for_ad = State()

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

async def get_db():
    return await asyncpg.connect(DATABASE_URL)

async def init_db():
    conn = await get_db()
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY
        );
        CREATE TABLE IF NOT EXISTS movies (
            code TEXT PRIMARY KEY,
            name TEXT,
            file_id TEXT,
            file_type TEXT
        );
        CREATE TABLE IF NOT EXISTS requests (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            text TEXT
        );
    """)
    await conn.close()

def get_channel_keyboard():
    buttons = [
        [InlineKeyboardButton(text="📢 Telegram kanalga a'zo bo'lish", url=f"https://t.me/{KANAL_ID.replace('@', '')}")],
        [InlineKeyboardButton(text="📷 Instagram sahifamiz", url=INSTAGRAM_LINK)],
        [InlineKeyboardButton(text="✅ Tasdiqlash / Tekshirish", callback_data="check_subs")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_admin_keyboard():
    buttons = [
        [KeyboardButton(text="📊 Statika"), KeyboardButton(text="📜 So'ralgan kinolar")],
        [KeyboardButton(text="🎬 Kino qo'shish"), KeyboardButton(text="📢 Reklama yuborish")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

async def check_subscription(user_id: int) -> bool:
    if user_id == ADMIN_ID:
        return True
    try:
        member = await bot.get_chat_member(chat_id=KANAL_ID, user_id=user_id)
        if member.status in ["member", "administrator", "creator"]:
            return True
        return False
    except Exception as e:
        print(f"Tekshirishda xato: {e}")
        return False

@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    user_id = message.from_user.id
    conn = await get_db()
    await conn.execute("INSERT INTO users (user_id) VALUES ($1) ON CONFLICT (user_id) DO NOTHING", user_id)
    await conn.close()

    if await check_subscription(user_id):
        await message.answer("Xush kelibsiz! Kino kodini kiriting va men uni topib beraman.")
    else:
        await message.answer("Botdan foydalanish uchun Telegram kanalimizga va Instagram sahifamizga obuna bo'ling:", reply_markup=get_channel_keyboard())

@dp.callback_query(F.data == "check_subs")
async def check_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if await check_subscription(user_id):
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer("Rahmat! Obuna tasdiqlandi. Kino kodini yuborishingiz mumkin.")
    else:
        await callback.answer("Siz hali Telegram kanalimizga a'zo bo'lmadingiz!", show_alert=True)

@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("Admin panelga xush kelibsiz!", reply_markup=get_admin_keyboard())

@dp.message(F.text == "📊 Statika")
async def show_stats(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        conn = await get_db()
        u_count = await conn.fetchval("SELECT COUNT(*) FROM users")
        m_count = await conn.fetchval("SELECT COUNT(*) FROM movies")
        await conn.close()
        await message.answer(f"📊 **Statistika:**\n\n👥 Foydalanuvchilar: {u_count} ta\n🎬 Kinolar: {m_count} ta")

@dp.message(F.text == "📜 So'ralgan kinolar")
async def show_requests(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        conn = await get_db()
        reqs = await conn.fetch("SELECT text, COUNT(text) as count FROM requests GROUP BY text ORDER BY count DESC LIMIT 10")
        await conn.close()
        if not reqs:
            await message.answer("Hozircha hech narsa so'ralmagan.")
            return
        text = "📌 **Eng ko'p so'ralgan kodlar:**\n\n"
        for r in reqs:
            text += f"🔹 `{r['text']}` — {r['count']} marta\n"
        await message.answer(text)

@dp.message(F.text == "🎬 Kino qo'shish")
async def add_movie_start(message: types.Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        await message.answer("Kinoni video yoki fayl ko'rinishida yuboring:")
        await state.set_state(MovieState.waiting_for_file)

@dp.message(MovieState.waiting_for_file, F.video | F.document)
async def process_movie_file(message: types.Message, state: FSMContext):
    file_id = message.video.file_id if message.video else message.document.file_id
    file_type = "video" if message.video else "document"
    await state.update_data(file_id=file_id, file_type=file_type)
    await message.answer("Kino nomini kiriting:")
    await state.set_state(MovieState.waiting_for_name)

@dp.message(MovieState.waiting_for_name)
async def process_movie_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Kino uchun kod kiriting:")
    await state.set_state(MovieState.waiting_for_code)

@dp.message(MovieState.waiting_for_code)
async def process_movie_code(message: types.Message, state: FSMContext):
    code = message.text.strip()
    data = await state.get_data()
    conn = await get_db()
    try:
        await conn.execute(
            "INSERT INTO movies (code, name, file_id, file_type) VALUES ($1, $2, $3, $4)",
            code, data['name'], data['file_id'], data['file_type']
        )
        await message.answer(f"✅ Saqlandi!\n\nNom: {data['name']}\nKod: {code}")
    except asyncpg.UniqueViolationError:
        await message.answer("❌ Bu kod band! Boshqa kod kiriting.")
    finally:
        await conn.close()
    await state.clear()

@dp.message(F.text == "📢 Reklama yuborish")
async def start_ad(message: types.Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        await message.answer("Reklama postini yuboring:")
        await state.set_state(ReqState.waiting_for_ad)

@dp.message(ReqState.waiting_for_ad)
async def send_ad_to_all(message: types.Message, state: FSMContext):
    conn = await get_db()
    users = await conn.fetch("SELECT user_id FROM users")
    await conn.close()
    
    await message.answer("📢 Reklama tarqatilmoqda...")
    count = 0
    for user in users:
        try:
            await message.copy_to(chat_id=user['user_id'])
            count += 1
            await asyncio.sleep(0.04)
        except Exception:
            pass
    await message.answer(f"📢 Reklama {count} ta odamga yuborildi!")
    await state.clear()

@dp.message(F.text)
async def search_movie(message: types.Message):
    user_id = message.from_user.id
    if not await check_subscription(user_id):
        await message.answer("Botdan foydalanish uchun Telegram kanalimizga va Instagram sahifamizga obuna bo'ling:", reply_markup=get_channel_keyboard())
        return

    code = message.text.strip()
    conn = await get_db()
    movie = await conn.fetchrow("SELECT name, file_id, file_type FROM movies WHERE code = $1", code)

    if movie:
        caption_text = f"🎬 **Kino nomi:** {movie['name']}\n🔑 **Kodi:** {code}"
        if movie['file_type'] == "video":
            await message.answer_video(video=movie['file_id'], caption=caption_text)
        else:
            await message.answer_document(document=movie['file_id'], caption=caption_text)
    else:
        try:
            await conn.execute("INSERT INTO requests (user_id, text) VALUES ($1, $2)", user_id, code)
        except Exception:
            pass
        await message.answer("❌ Afsuski, bu kod bilan kino topilmadi.")
    
    await conn.close()

async def handle(request):
    return web.Response(text="Bot is running!")

async def main():
    await init_db()
    
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    print("Maximal tezlikdagi limitssiz bot ishga tushdi!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
