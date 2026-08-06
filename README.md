# Dacha bron qilish Telegram bot

## O'rnatish

1. Python 3.10+ o'rnatilgan bo'lishi kerak.
2. Kutubxonalarni o'rnating:
   ```
   pip install -r requirements.txt
   ```
3. [@BotFather](https://t.me/BotFather) orqali yangi bot yarating va tokenni oling.
4. Tokenni muhit o'zgaruvchisi sifatida bering (yoki `bot.py` ichidagi `BOT_TOKEN` qatoriga to'g'ridan-to'g'ri yozing):
   ```
   export BOT_TOKEN="123456:ABC-your-token-here"
   ```
   Windows'da:
   ```
   set BOT_TOKEN=123456:ABC-your-token-here
   ```
5. (Ixtiyoriy) Admin sifatida yangi bronlar haqida xabar olish uchun o'z Telegram ID'ingizni bering:
   ```
   export ADMIN_CHAT_ID="123456789"
   ```
   ID'ni bilish uchun [@userinfobot](https://t.me/userinfobot) ga yozing.

## Ishga tushirish

```
python bot.py
```

## Dachalarni tahrirlash

`bot.py` faylidagi `DACHAS` lug'atiga o'zingizning dachalaringizni qo'shing yoki mavjudlarini tahrirlang:

```python
DACHAS = {
    "dacha_1": {
        "name_uz": "🏡 Dacha nomi",
        "name_ru": "🏡 Название дачи",
        "desc_uz": "Tavsif va narx",
        "desc_ru": "Описание и цена",
    },
    ...
}
```

Har bir dacha uchun kalit (masalan `dacha_1`) unikal bo'lishi kerak.

## Qanday ishlaydi

1. Foydalanuvchi `/start` bosadi → til tanlaydi (UZ/RU).
2. "Dachalar ro'yxati" dan dacha tanlaydi, tavsifini ko'radi.
3. "Bron qilish" tugmasini bosib: kirish sanasi → chiqish sanasi → ism → telefon raqamini kiritadi.
4. Ma'lumotlarni tasdiqlaydi → bron `bookings.json` fayliga saqlanadi va (agar sozlangan bo'lsa) admin'ga xabar boradi.
5. "Mening bronlarim" bo'limida o'z bronlarini ko'rishi mumkin.

## Keyingi qadamlar (ixtiyoriy takomillashtirish)

- Sana band/bo'sh ekanligini avtomatik tekshirish (bir xil sanaga ikki marta bron bo'lmasligi uchun)
- Dachalar rasmlarini yuborish (`message.answer_photo`)
- To'lov integratsiyasi (Payme/Click)
- SQLite bazasiga o'tish (ko'p dacha bo'lsa qulayroq)
