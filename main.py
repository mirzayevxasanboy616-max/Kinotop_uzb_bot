import asyncio

# MainThread event loop muammosini hal qilish
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
import aiosqlite

# --- TO'G'RILANGAN SOZLAMALAR ---
BOT_TOKEN = "8634039492:AAF_RmClS3qUxkX1QtuS1ABcvbhGwUyFfEE"  
ADMIN_ID = 1316308230   
KANAL_ID = "@kinoqidir_N1"
INSTAGRAM_LINK = "https://instagram.com"  # Siz so'ragan aniq username

logging.basicConfig(level=logging.INFO)

class MovieState(StatesGroup):
    waiting_for_file = State()
    waiting_for_name = State()
    waiting_for_code = State()

class ReqState(StatesGroup):
    waiting_for_ad = State()

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
DB_NAME = "kinobot_fast.db"

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)")
        await db.execute("CREATE TABLE IF NOT EXISTS movies (code TEXT PRIMARY KEY, name TEXT, file_id TEXT, file_type TEXT)")
        await db.execute("CREATE TABLE IF NOT EXISTS requests (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, text TEXT)")
        await db.commit()

def get_channel_keyboard():
    buttons = [
        [InlineKeyboardButton(text="📢 Telegram kanalga a'zo bo'lish", url="https://t.me")],
        [InlineKeyboardButton(text="📸 Instagram sahifamiz", url=INSTAGRAM_LINK)],
        [InlineKeyboardButton(text="✅ Tasdiqlash / Tekshirish", callback_data="check_subs")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_admin_keyboard():
    buttons = [
        [KeyboardButton(text="📊 Statika"), KeyboardButton(text="📝 So'ralgan kinolar")],
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
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        await db.commit()
    
    if await check_subscription(user_id):
        await message.answer("Xush kelibsiz! Kino kodini kiriting va men uni topib beraman. 🎬")
    else:
        await message.answer("Botdan foydalanish uchun Telegram kanalimizga va Instagram sahifamizga a'zo bo'ling, so'ng tasdiqlash tugmasini bosing!", reply_markup=get_channel_keyboard())

@dp.callback_query(F.data == "check_subs")
async def check_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if await check_subscription(user_id):
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer("Rahmat! Obuna tasdiqlandi. Kino kodini yuborishingiz mumkin. 🎬")
    else:
        await callback.answer("Siz hali Telegram kanalimizga a'zo bo'lmadingiz! Kanalga kirib obuna bo'ling va qayta urining. ❌", show_alert=True)

@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("Admin panelga xush kelibsiz, Muhammadjon!", reply_markup=get_admin_keyboard())

@dp.message(F.text == "📊 Statika")
async def show_stats(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT COUNT(*) FROM users") as cursor:
                u_count = (await cursor.fetchone())[0]
            async with db.execute("SELECT COUNT(*) FROM movies") as cursor:
                m_count = (await cursor.fetchone())[0]
        await message.answer(f"📊 **Statistika:**\n\n👥 Foydalanuvchilar: {u_count} ta\n🎬 Kinolar: {m_count} ta")

@dp.message(F.text == "📝 So'ralgan kinolar")
async def show_requests(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT text, COUNT(text) FROM requests GROUP BY text ORDER BY COUNT(text) DESC LIMIT 20") as cursor:
                reqs = await cursor.fetchall()
        if not reqs:
            await message.answer("Hozircha hech narsa so'rashmagan.")
            return
        text = "📝 **Eng ko'p so'ralgan kodlar:**\n\n"
        for r in reqs:
            text += f"🔹 {r[0]} — {r[1]} marta\n"
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
    async with aiosqlite.connect(DB_NAME) as db:
        try:
            await db.execute("INSERT INTO movies (code, name, file_id, file_type) VALUES (?, ?, ?, ?)", 
                           (code, data['name'], data['file_id'], data['file_type']))
            await db.commit()
            await message.answer(f"✅ Saqlandi!\nNom: {data['name']}\nKod: {code}")
        except aiosqlite.IntegrityError:
            await message.answer("❌ Bu kod band! Boshqa kod kiriting.")
    await state.clear()

@dp.message(F.text == "📢 Reklama yuborish")
async def start_ad(message: types.Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        await message.answer("Reklama postini yuboring:")
        await state.set_state(ReqState.waiting_for_ad)

@dp.message(ReqState.waiting_for_ad)
async def send_ad_to_all(message: types.Message, state: FSMContext):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT user_id FROM users") as cursor:
            users = await cursor.fetchall()
    await message.answer("📢 Reklama tarqatilmoqda...")
    count = 0
    for user in users:
        try:
            await message.copy_to(chat_id=user[0])
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
        await message.answer("Botdan foydalanish uchun Telegram kanalimizga va Instagram sahifamizga a'zo bo'ling, so'ng tasdiqlash tugmasini bosing!", reply_markup=get_channel_keyboard())
        return
    
    code = message.text.strip()
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT name, file_id, file_type FROM movies WHERE code = ?", (code,)) as cursor:
            movie = await cursor.fetchone()
        
        if movie:
            m_name, m_file_id, m_file_type = movie
            caption_text = f"🎬 **Kino nomi:** {m_name}\n🔑 **Kodi:** {code}"
            if m_file_type == "video":
                await message.answer_video(video=m_file_id, caption=caption_text)
            else:
                await message.answer_document(document=m_file_id, caption=caption_text)
        else:
            try:
                await db.execute("INSERT INTO requests (user_id, text) VALUES (?, ?)", (user_id, code))
                await db.commit()
            except Exception:
                pass
            await message.answer("❌ Afsuski, bu kod bilan kino topilmadi. So'rovingiz adminga yuborildi!")

import os
from aiohttp import web
import asyncio

async def handle(request):
    return web.Response(text="Bot is running!")

app = web.Application()
app.router.add_get('/', handle)

# Render uchun asosiy ishga tushirish qismi
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # 1. Ma'lumotlar bazasini yaratish
    asyncio.run(init_db())
    
    # 2. Botni fonda (background) ishga tushirish
    print("Maksimal tezlikdagi limitsiz bot ishga tushdi!")
    loop = asyncio.get_event_loop()
    loop.create_task(dp.start_polling(bot))
    
    # 3. Render veb-portini ochiq ushlash
    port = int(os.environ.get("PORT", 10000))
    web.run_app(app, host='0.0.0.0', port=port, loop=loop)
