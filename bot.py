"""
Dacha bron qilish Telegram bot
Til: O'zbek / Rus (tanlov beriladi)
Kutubxona: aiogram 3.x
Ma'lumotlar: kod ichida (dachalar) + bookings.json (bronlar)
"""

import asyncio
import json
import logging
import os
from datetime import datetime

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

# ============ SOZLAMALAR ============
BOT_TOKEN = os.getenv("BOT_TOKEN", "SIZNING_BOT_TOKENINGIZ_BU_YERGA")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "")  # admin telegram ID (ixtiyoriy)
BOOKINGS_FILE = "bookings.json"

logging.basicConfig(level=logging.INFO)

# ============ DACHALAR RO'YXATI (shu yerda tahrirlang) ============
DACHAS = {
    "dacha_1": {
        "name_uz": "🏡 Chimyon dachasi",
        "name_ru": "🏡 Дача Чимган",
        "desc_uz": "3 xonali, basseyn, mangal, 8 kishi uchun. Narxi: 800,000 so'm/kecha",
        "desc_ru": "3 комнаты, бассейн, мангал, до 8 человек. Цена: 800,000 сум/ночь",
    },
    "dacha_2": {
        "name_uz": "🌲 Bo'stonliq dachasi",
        "name_ru": "🌲 Дача Бустанлык",
        "desc_uz": "2 xonali, tog' manzarasi, 5 kishi uchun. Narxi: 500,000 so'm/kecha",
        "desc_ru": "2 комнаты, вид на горы, до 5 человек. Цена: 500,000 сум/ночь",
    },
    "dacha_3": {
        "name_uz": "🏊 Yangiobod dachasi",
        "name_ru": "🏊 Дача Янгиабад",
        "desc_uz": "4 xonali, katta hovli, sauna, 10 kishi uchun. Narxi: 1,200,000 so'm/kecha",
        "desc_ru": "4 комнаты, большой двор, сауна, до 10 человек. Цена: 1,200,000 сум/ночь",
    },
}

TEXTS = {
    "uz": {
        "choose_lang": "Tilni tanlang / Выберите язык:",
        "welcome": "Assalomu alaykum! Dacha bron qilish botiga xush kelibsiz. 🏡\n\nQuyidagi menyudan foydalaning:",
        "menu_list": "📋 Dachalar ro'yxati",
        "menu_my": "🗂 Mening bronlarim",
        "choose_dacha": "Dachani tanlang:",
        "back": "⬅️ Orqaga",
        "book_btn": "✅ Shu dachani bron qilish",
        "ask_checkin": "Kirish sanasini kiriting (masalan: 15.08.2026):",
        "ask_checkout": "Chiqish sanasini kiriting (masalan: 18.08.2026):",
        "ask_name": "Ismingizni kiriting:",
        "ask_phone": "Telefon raqamingizni kiriting (masalan: +998901234567):",
        "invalid_date": "❌ Sana noto'g'ri formatda. Masalan: 15.08.2026 shaklida kiriting.",
        "invalid_date_order": "❌ Chiqish sanasi kirish sanasidan keyin bo'lishi kerak.",
        "invalid_phone": "❌ Telefon raqami noto'g'ri. Masalan: +998901234567",
        "confirm": "Bronni tasdiqlaysizmi?\n\n🏡 {dacha}\n📅 {checkin} - {checkout}\n👤 {name}\n📞 {phone}",
        "confirm_yes": "✅ Tasdiqlash",
        "confirm_no": "❌ Bekor qilish",
        "booked": "🎉 Bronlash muvaffaqiyatli qabul qilindi! Tez orada operator siz bilan bog'lanadi.",
        "cancelled": "Bekor qilindi.",
        "no_bookings": "Sizda hozircha bronlar yo'q.",
        "your_bookings": "🗂 Sizning bronlaringiz:\n\n",
        "new_admin_booking": "🆕 Yangi bron!\n\n🏡 {dacha}\n📅 {checkin} - {checkout}\n👤 {name}\n📞 {phone}\n🆔 User: {user_id}",
    },
    "ru": {
        "choose_lang": "Tilni tanlang / Выберите язык:",
        "welcome": "Здравствуйте! Добро пожаловать в бот бронирования дач. 🏡\n\nВыберите пункт меню:",
        "menu_list": "📋 Список дач",
        "menu_my": "🗂 Мои брони",
        "choose_dacha": "Выберите дачу:",
        "back": "⬅️ Назад",
        "book_btn": "✅ Забронировать эту дачу",
        "ask_checkin": "Введите дату заезда (например: 15.08.2026):",
        "ask_checkout": "Введите дату выезда (например: 18.08.2026):",
        "ask_name": "Введите ваше имя:",
        "ask_phone": "Введите номер телефона (например: +998901234567):",
        "invalid_date": "❌ Неверный формат даты. Пример: 15.08.2026",
        "invalid_date_order": "❌ Дата выезда должна быть позже даты заезда.",
        "invalid_phone": "❌ Неверный номер телефона. Пример: +998901234567",
        "confirm": "Подтвердить бронь?\n\n🏡 {dacha}\n📅 {checkin} - {checkout}\n👤 {name}\n📞 {phone}",
        "confirm_yes": "✅ Подтвердить",
        "confirm_no": "❌ Отменить",
        "booked": "🎉 Бронь успешно оформлена! Скоро с вами свяжется оператор.",
        "cancelled": "Отменено.",
        "no_bookings": "У вас пока нет броней.",
        "your_bookings": "🗂 Ваши брони:\n\n",
        "new_admin_booking": "🆕 Новая бронь!\n\n🏡 {dacha}\n📅 {checkin} - {checkout}\n👤 {name}\n📞 {phone}\n🆔 User: {user_id}",
    },
}

router = Router()


# ============ HOLATLAR (FSM) ============
class BookingStates(StatesGroup):
    choosing_dacha = State()
    entering_checkin = State()
    entering_checkout = State()
    entering_name = State()
    entering_phone = State()
    confirming = State()


# ============ YORDAMCHI FUNKSIYALAR ============
def load_bookings():
    if os.path.exists(BOOKINGS_FILE):
        with open(BOOKINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_booking(booking: dict):
    bookings = load_bookings()
    bookings.append(booking)
    with open(BOOKINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(bookings, f, ensure_ascii=False, indent=2)


def get_lang(data: dict) -> str:
    return data.get("lang", "uz")


def lang_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="lang_uz"),
                InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru"),
            ]
        ]
    )


def main_menu_kb(lang: str) -> InlineKeyboardMarkup:
    t = TEXTS[lang]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t["menu_list"], callback_data="menu_list")],
            [InlineKeyboardButton(text=t["menu_my"], callback_data="menu_my")],
        ]
    )


def dacha_list_kb(lang: str) -> InlineKeyboardMarkup:
    buttons = []
    for key, d in DACHAS.items():
        buttons.append(
            [InlineKeyboardButton(text=d[f"name_{lang}"], callback_data=f"view_{key}")]
        )
    buttons.append([InlineKeyboardButton(text=TEXTS[lang]["back"], callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def dacha_detail_kb(lang: str, dacha_key: str) -> InlineKeyboardMarkup:
    t = TEXTS[lang]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t["book_btn"], callback_data=f"book_{dacha_key}")],
            [InlineKeyboardButton(text=t["back"], callback_data="menu_list")],
        ]
    )


def confirm_kb(lang: str) -> InlineKeyboardMarkup:
    t = TEXTS[lang]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=t["confirm_yes"], callback_data="confirm_yes"),
                InlineKeyboardButton(text=t["confirm_no"], callback_data="confirm_no"),
            ]
        ]
    )


def parse_date(text: str):
    try:
        return datetime.strptime(text.strip(), "%d.%m.%Y")
    except ValueError:
        return None


# ============ HANDLERLAR ============
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(TEXTS["uz"]["choose_lang"], reply_markup=lang_kb())


@router.callback_query(F.data.startswith("lang_"))
async def choose_lang(callback: CallbackQuery, state: FSMContext):
    lang = callback.data.split("_")[1]
    await state.update_data(lang=lang)
    t = TEXTS[lang]
    await callback.message.edit_text(t["welcome"], reply_markup=main_menu_kb(lang))
    await callback.answer()


@router.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    await callback.message.edit_text(TEXTS[lang]["welcome"], reply_markup=main_menu_kb(lang))
    await callback.answer()


@router.callback_query(F.data == "menu_list")
async def menu_list(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    await callback.message.edit_text(TEXTS[lang]["choose_dacha"], reply_markup=dacha_list_kb(lang))
    await callback.answer()


@router.callback_query(F.data.startswith("view_"))
async def view_dacha(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    dacha_key = callback.data.replace("view_", "")
    d = DACHAS[dacha_key]
    text = f"{d[f'name_{lang}']}\n\n{d[f'desc_{lang}']}"
    await callback.message.edit_text(text, reply_markup=dacha_detail_kb(lang, dacha_key))
    await callback.answer()


@router.callback_query(F.data.startswith("book_"))
async def start_booking(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    dacha_key = callback.data.replace("book_", "")
    await state.update_data(dacha_key=dacha_key)
    await state.set_state(BookingStates.entering_checkin)
    await callback.message.answer(TEXTS[lang]["ask_checkin"])
    await callback.answer()


@router.message(BookingStates.entering_checkin)
async def enter_checkin(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    dt = parse_date(message.text)
    if not dt:
        await message.answer(TEXTS[lang]["invalid_date"])
        return
    await state.update_data(checkin=message.text.strip(), checkin_dt=dt.isoformat())
    await state.set_state(BookingStates.entering_checkout)
    await message.answer(TEXTS[lang]["ask_checkout"])


@router.message(BookingStates.entering_checkout)
async def enter_checkout(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    dt = parse_date(message.text)
    if not dt:
        await message.answer(TEXTS[lang]["invalid_date"])
        return
    checkin_dt = datetime.fromisoformat(data["checkin_dt"])
    if dt <= checkin_dt:
        await message.answer(TEXTS[lang]["invalid_date_order"])
        return
    await state.update_data(checkout=message.text.strip())
    await state.set_state(BookingStates.entering_name)
    await message.answer(TEXTS[lang]["ask_name"])


@router.message(BookingStates.entering_name)
async def enter_name(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    await state.update_data(name=message.text.strip())
    await state.set_state(BookingStates.entering_phone)
    await message.answer(TEXTS[lang]["ask_phone"])


@router.message(BookingStates.entering_phone)
async def enter_phone(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    phone = message.text.strip()
    if not (phone.startswith("+") and phone[1:].isdigit() and len(phone) >= 10):
        await message.answer(TEXTS[lang]["invalid_phone"])
        return
    await state.update_data(phone=phone)
    d = DACHAS[data["dacha_key"]]
    text = TEXTS[lang]["confirm"].format(
        dacha=d[f"name_{lang}"],
        checkin=data["checkin"],
        checkout=data["checkout"],
        name=data["name"],
        phone=phone,
    )
    await state.set_state(BookingStates.confirming)
    await message.answer(text, reply_markup=confirm_kb(lang))


@router.callback_query(F.data == "confirm_yes", BookingStates.confirming)
async def confirm_booking(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    lang = get_lang(data)
    d = DACHAS[data["dacha_key"]]

    booking = {
        "user_id": callback.from_user.id,
        "username": callback.from_user.username,
        "dacha": d["name_uz"],
        "checkin": data["checkin"],
        "checkout": data["checkout"],
        "name": data["name"],
        "phone": data["phone"],
        "created_at": datetime.now().isoformat(),
    }
    save_booking(booking)

    await callback.message.edit_text(TEXTS[lang]["booked"])

    if ADMIN_CHAT_ID:
        admin_text = TEXTS["uz"]["new_admin_booking"].format(
            dacha=d["name_uz"],
            checkin=data["checkin"],
            checkout=data["checkout"],
            name=data["name"],
            phone=data["phone"],
            user_id=callback.from_user.id,
        )
        try:
            await bot.send_message(ADMIN_CHAT_ID, admin_text)
        except Exception as e:
            logging.warning(f"Adminga xabar yuborilmadi: {e}")

    await state.clear()
    await callback.message.answer(TEXTS[lang]["welcome"], reply_markup=main_menu_kb(lang))
    await callback.answer()


@router.callback_query(F.data == "confirm_no", BookingStates.confirming)
async def cancel_booking(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    await state.clear()
    await state.update_data(lang=lang)
    await callback.message.edit_text(TEXTS[lang]["cancelled"])
    await callback.message.answer(TEXTS[lang]["welcome"], reply_markup=main_menu_kb(lang))
    await callback.answer()


@router.callback_query(F.data == "menu_my")
async def my_bookings(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    t = TEXTS[lang]
    bookings = load_bookings()
    user_bookings = [b for b in bookings if b["user_id"] == callback.from_user.id]

    if not user_bookings:
        text = t["no_bookings"]
    else:
        text = t["your_bookings"]
        for b in user_bookings:
            text += f"🏡 {b['dacha']}\n📅 {b['checkin']} - {b['checkout']}\n\n"

    await callback.message.edit_text(text, reply_markup=main_menu_kb(lang))
    await callback.answer()


# ============ ISHGA TUSHIRISH ============
async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
