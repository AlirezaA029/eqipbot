"""
Telegram Member Manager Bot – MVP
Stack:
- Python 3.10+
- aiogram v3.7+
- aiosqlite (برای ذخیره ساده در صورت نیاز)
- APScheduler (برای رویدادهای دوره‌ای)

Features:
1) /start → welcome + 2 دکمه: "عضویت در گروه" / "چت ناشناس"
2) فرم عضویت مرحله‌ای → name, city, dob, dorm → نمایش قوانین (rules.txt) → دکمه موافقم/نیستم
3) اگر موافقم → درخواست به ادمین‌ها میره با دکمه تایید/رد
   اگر موافق نیستم → پیام خداحافظی
4) تایید ادمین → ارسال لینک کانال/گروه/ویژه به کاربر
5) رد ادمین → پیام محترمانه رد شدن
6) چت ناشناس → ارسال لینک ربات ناشناس
"""
import asyncio
import os
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv

# --- بارگذاری env ---
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()}
ADMIN_GROUP_ID = int(os.getenv("ADMIN_GROUP_ID", "0")) or None
MAIN_GROUP_ID = int(os.getenv("MAIN_GROUP_ID", "0")) or None
CHANNEL_LINK = os.getenv("CHANNEL_LINK", "")
GROUP_LINK = os.getenv("GROUP_LINK", "")
SPECIAL_LINK = os.getenv("SPECIAL_LINK", "")
ANON_BOT_URL = os.getenv("ANON_BOT_URL", "")

# --- ساخت Bot و Dispatcher ---
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

# --- FSM States ---
class Register(StatesGroup):
    name = State()
    city = State()
    dob = State()
    dorm = State()
    rules = State()

# --- Helpers ---
async def get_rules_text() -> str:
    try:
        with open("rules.txt", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "قوانین در دسترس نیستند."

def save_application(user_id: int, data: dict):
    """ذخیره اطلاعات کاربر در فایل applications.txt"""
    with open("applications.txt", "a", encoding="utf-8") as f:
        f.write(
            f"ID: {user_id}\n"
            f"نام: {data.get('name')}\n"
            f"شهر: {data.get('city')}\n"
            f"تولد: {data.get('dob')}\n"
            f"خوابگاهی: {data.get('dorm')}\n"
            f"{'-'*30}\n"
        )

# --- Handlers ---
@dp.message(CommandStart())
async def start_cmd(message: Message, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 عضویت در گروه", callback_data="join")],
        [InlineKeyboardButton(text="💬 چت ناشناس", callback_data="anon")]
    ])
    await message.answer("سلام! خوش آمدید 👋 یکی از گزینه‌ها رو انتخاب کنید:", reply_markup=kb)

# --- ثبت‌نام مرحله‌ای ---
@dp.callback_query(F.data == "join")
async def start_register(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("لطفاً نام و نام خانوادگی خود را وارد کنید:")
    await state.set_state(Register.name)

@dp.message(Register.name)
async def reg_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("محل اقامت خود را وارد کنید:")
    await state.set_state(Register.city)

@dp.message(Register.city)
async def reg_city(message: Message, state: FSMContext):
    await state.update_data(city=message.text)
    await message.answer("تاریخ تولد خود را وارد کنید (مثال: 1380-01-01):")
    await state.set_state(Register.dob)

@dp.message(Register.dob)
async def reg_dob(message: Message, state: FSMContext):
    await state.update_data(dob=message.text)
    await message.answer("آیا خوابگاهی هستید؟ (بله/خیر)")
    await state.set_state(Register.dorm)

@dp.message(Register.dorm)
async def reg_dorm(message: Message, state: FSMContext):
    await state.update_data(dorm=message.text)
    rules = await get_rules_text()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ موافقم", callback_data="agree")],
        [InlineKeyboardButton(text="❌ موافق نیستم", callback_data="disagree")]
    ])
    await message.answer(rules, reply_markup=kb)
    await state.set_state(Register.rules)

# --- قوانین موافق/مخالف ---
@dp.callback_query(F.data == "agree")
async def agree_rules(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user_id = callback.from_user.id

    # ذخیره اطلاعات در فایل
    save_application(user_id, data)

    text = (
        f"📥 درخواست عضویت جدید:\n"
        f"👤 نام: {data.get('name')}\n"
        f"🏙 شهر: {data.get('city')}\n"
        f"🎂 تولد: {data.get('dob')}\n"
        f"🏠 خوابگاهی: {data.get('dorm')}\n"
        f"🆔 {user_id}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="تایید ✅", callback_data=f"approve:{user_id}"),
        InlineKeyboardButton(text="رد ❌", callback_data=f"reject:{user_id}")
    ]])
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text, reply_markup=kb)
        except Exception:
            pass

    await callback.message.answer("اطلاعات شما ثبت شد ✅ پس از بررسی نتیجه اعلام می‌شود.")
    await state.clear()

@dp.callback_query(F.data == "disagree")
async def disagree_rules(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("🙏 ممنون از وقتی که گذاشتی. موفق باشید!")
    await state.clear()

# --- تایید/رد ادمین ---
@dp.callback_query(F.data.startswith("approve:"))
async def approve_user(callback: CallbackQuery):
    user_id = int(callback.data.split(":")[1])
    text = (
        "🎉 تبریک! به مجموعه ما خوش آمدید.\n"
        f"📌 کانال: {CHANNEL_LINK}\n"
        f"👥 گروه: {GROUP_LINK}\n"
        f"⭐ گروه ویژه: {SPECIAL_LINK}"
    )
    try:
        await bot.send_message(user_id, text)
        await callback.answer("تایید شد و لینک‌ها ارسال گردید.")
    except:
        await callback.answer("ارسال به کاربر ناموفق بود.")

@dp.callback_query(F.data.startswith("reject:"))
async def reject_user(callback: CallbackQuery):
    user_id = int(callback.data.split(":")[1])
    try:
        await bot.send_message(user_id, "متاسفانه درخواست شما تایید نشد. موفق باشید 🙏")
        await callback.answer("رد شد و پیام ارسال گردید.")
    except:
        await callback.answer("ارسال به کاربر ناموفق بود.")

# --- چت ناشناس ---
@dp.callback_query(F.data == "anon")
async def anon_chat(callback: CallbackQuery):
    if ANON_BOT_URL:
        await callback.message.answer(f"برای ارسال پیام ناشناس از این لینک استفاده کنید:\n{ANON_BOT_URL}")
    else:
        await callback.message.answer("چت ناشناس فعال نیست.")

# --- Main ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
