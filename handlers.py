# handlers.py - Пользовательские обработчики

from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import math
from datetime import datetime
import asyncio

from database import db
from models import Product, Order
from keyboards import *
from utils import get_product_quantities, parse_product_file, format_card_number, is_admin
from config import ADMIN_IDS

router = Router()

# ============================================
# СОСТОЯНИЯ
# ============================================

class UserStates(StatesGroup):
    selecting_city = State()
    selecting_product = State()
    selecting_quantity = State()
    payment = State()

class AdminStates(StatesGroup):
    waiting_for_photo = State()

# ============================================
# ФУНКЦИИ УВЕДОМЛЕНИЙ
# ============================================

async def notify_users_about_new_product(bot, product: Product):
    users = db.get_all_users()
    
    description_text = f"\nОписание: {product.description}" if product.description else ""
    
    text = f"""✅ <b>Новый товар!</b>

📍 {product.city} - {product.name} - {product.quantity} - {product.price}₽ - ✅ В наличии{description_text}

🔑 Код товара: <code>/{product.product_code}</code>

💡 Нажмите на код, чтобы быстро перейти к товару"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"🔑 Перейти к товару /{product.product_code}",
            callback_data=f"goto_product_{product.product_code}"
        )]
    ])
    
    for user_id in users:
        if db.is_user_blocked(user_id):
            continue
        try:
            await bot.send_message(
                user_id,
                text,
                parse_mode='HTML',
                reply_markup=keyboard
            )
            await asyncio.sleep(0.05)
        except:
            pass

# ============================================
# КОМАНДЫ
# ============================================

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if db.is_user_blocked(user_id):
        return
    
    await state.clear()
    
    db.add_user(
        user_id,
        message.from_user.username,
        message.from_user.first_name,
        message.from_user.last_name
    )
    
    admin = is_admin(user_id)
    text = "⚡ Привет я современный помощник воспользуйся меню ниже ⬇️"
    keyboard = get_main_menu(admin)
    await message.answer(text, reply_markup=keyboard)

@router.message(Command("code"))
async def get_product_by_code_command(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if db.is_user_blocked(user_id):
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer(
            "❌ Используйте: /code КОД\n"
            "Например: /code zipp765432"
        )
        return
    
    code = parts[1].strip().lower()
    product = db.get_product_by_code(code)
    
    if not product:
        await message.answer("❌ Товар с таким кодом не найден")
        return
    
    if not product['in_stock']:
        await message.answer("❌ Товар уже продан!")
        return
    
    description = product.get('description', '')
    description_text = f"\n<b>Описание:</b> {description}" if description else ""
    
    await state.update_data(
        product_id=product['id'],
        product_name=product['name'],
        product_city=product['city'],
        product_quantity=product['quantity'],
        product_price=product['price'],
        product_description=description,
        product_code=product['product_code']
    )
    
    card = db.get_setting('card_number', '')
    formatted_card = format_card_number(card) if card else 'не указана'
    
    text = f"""<b>Товар</b> {product['name']}
<b>Количество:</b> {product['quantity']}
<b>Цена:</b> {product['price']}₽
{description_text}
<b>Статус:</b> ✅ В наличии
<b>🔑 Код:</b> <code>/{product['product_code']}</code>

<b>💳 Перевод на карту:</b> {formatted_card}

<b>❗ После оплаты обязательно нажмите кнопку ✅ Я оплатил ❗</b>"""
    
    keyboard = get_payment_keyboard(card)
    await message.answer(text, reply_markup=keyboard, parse_mode='HTML')

@router.message(lambda message: message.text and message.text.startswith('/zipp'))
async def handle_zipp_code(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if db.is_user_blocked(user_id):
        return
    
    code = message.text.strip().lower()
    product = db.get_product_by_code(code)
    
    if not product:
        await message.answer("❌ Товар с таким кодом не найден")
        return
    
    if not product['in_stock']:
        await message.answer("❌ Товар уже продан!")
        return
    
    description = product.get('description', '')
    description_text = f"\n<b>Описание:</b> {description}" if description else ""
    
    await state.update_data(
        product_id=product['id'],
        product_name=product['name'],
        product_city=product['city'],
        product_quantity=product['quantity'],
        product_price=product['price'],
        product_description=description,
        product_code=product['product_code']
    )
    
    card = db.get_setting('card_number', '')
    formatted_card = format_card_number(card) if card else 'не указана'
    
    text = f"""<b>Товар</b> {product['name']}
<b>Количество:</b> {product['quantity']}
<b>Цена:</b> {product['price']}₽
{description_text}
<b>Статус:</b> ✅ В наличии
<b>🔑 Код:</b> <code>/{product['product_code']}</code>

<b>💳 Перевод на карту:</b> {formatted_card}

<b>❗ После оплаты обязательно нажмите кнопку ✅ Я оплатил ❗</b>"""
    
    keyboard = get_payment_keyboard(card)
    await message.answer(text, reply_markup=keyboard, parse_mode='HTML')

# ============================================
# ПОЛЬЗОВАТЕЛЬСКИЕ ТОВАРЫ
# ============================================

@router.callback_query(F.data == "show_products")
async def show_products(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if db.is_user_blocked(user_id):
        await callback.answer()
        return
    
    await state.clear()
    await state.set_state(UserStates.selecting_city)
    
    cities = db.get_cities()
    if not cities:
        await callback.message.edit_text(
            "😕 К сожалению, пока нет доступных городов",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
            ])
        )
        await callback.answer()
        return
    
    keyboard = get_cities_keyboard(cities, 0, False)
    await callback.message.edit_text("💦 Выберите город", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("select_city_"))
async def select_city_products(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if db.is_user_blocked(user_id):
        await callback.answer()
        return
    
    city = callback.data.replace("select_city_", "")
    await state.update_data(selected_city=city)
    
    products = db.get_products_by_city(city)
    if not products:
        await callback.message.edit_text(
            f"😕 В городе {city} пока нет товаров",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_cities")]
            ])
        )
        await callback.answer()
        return
    
    product_data = []
    for product in products:
        product_data.append({
            'id': product.id,
            'name': product.name,
            'quantity': product.quantity,
            'price': product.price,
            'description': product.description,
            'in_stock': product.in_stock,
            'product_code': product.product_code
        })
    
    keyboard = get_products_keyboard(product_data)
    await callback.message.edit_text(
        f"💦 Товары по городу {city}",
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data == "back_to_cities")
async def back_to_cities(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if db.is_user_blocked(user_id):
        await callback.answer()
        return
    
    await state.set_state(UserStates.selecting_city)
    cities = db.get_cities()
    keyboard = get_cities_keyboard(cities, 0, False)
    await callback.message.edit_text("💦 Выберите город", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "close_products")
async def close_products(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if db.is_user_blocked(user_id):
        await callback.answer()
        return
    
    await state.clear()
    await callback.message.delete()
    admin = is_admin(user_id)
    keyboard = get_main_menu(admin)
    await callback.message.answer(
        "⚡ Привет я современный помощник воспользуйся меню ниже ⬇️",
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data.startswith("goto_product_"))
async def goto_product_by_code(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if db.is_user_blocked(user_id):
        await callback.answer()
        return
    
    code = callback.data.replace("goto_product_", "")
    product = db.get_product_by_code(code)
    
    if not product:
        await callback.answer("❌ Товар не найден или уже продан!", show_alert=True)
        return
    
    if not product['in_stock']:
        await callback.answer("❌ Товар уже продан!", show_alert=True)
        return
    
    description = product.get('description', '')
    description_text = f"\n<b>Описание:</b> {description}" if description else ""
    
    await state.update_data(
        product_id=product['id'],
        product_name=product['name'],
        product_city=product['city'],
        product_quantity=product['quantity'],
        product_price=product['price'],
        product_description=description,
        product_code=product['product_code']
    )
    
    card = db.get_setting('card_number', '')
    formatted_card = format_card_number(card) if card else 'не указана'
    
    text = f"""<b>Товар</b> {product['name']}
<b>Количество:</b> {product['quantity']}
<b>Цена:</b> {product['price']}₽
{description_text}
<b>Статус:</b> ✅ В наличии
<b>🔑 Код:</b> <code>/{product['product_code']}</code>

<b>💳 Перевод на карту:</b> {formatted_card}

<b>❗ После оплаты обязательно нажмите кнопку ✅ Я оплатил ❗</b>"""
    
    keyboard = get_payment_keyboard(card)
    
    if callback.message:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=keyboard, parse_mode='HTML')
    else:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
    
    await callback.answer()

# ============================================
# ПОКУПКА И ОПЛАТА
# ============================================

@router.callback_query(F.data.startswith("buy_product_"))
async def buy_product(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if db.is_user_blocked(user_id):
        await callback.answer()
        return
    
    product_id = int(callback.data.replace("buy_product_", ""))
    
    products = db.get_all_products()
    product_data = next((p for p in products if p['id'] == product_id), None)
    
    if not product_data or not product_data['in_stock']:
        await callback.answer("❌ Товар уже продан!", show_alert=True)
        return
    
    description = product_data.get('description', '')
    description_text = f"\n<b>Описание:</b> {description}" if description else ""
    
    await state.update_data(
        product_id=product_id,
        product_name=product_data['name'],
        product_city=product_data['city'],
        product_quantity=product_data['quantity'],
        product_price=product_data['price'],
        product_description=description,
        product_code=product_data['product_code'],
        buyer_id=user_id,
        buyer_username=callback.from_user.username or 'Не указан'
    )
    
    card = db.get_setting('card_number', '')
    formatted_card = format_card_number(card) if card else 'не указана'
    
    text = f"""<b>Товар</b> {product_data['name']}
<b>Количество:</b> {product_data['quantity']}
<b>Цена:</b> {product_data['price']}₽
{description_text}
<b>Статус:</b> ✅ В наличии
<b>🔑 Код:</b> <code>/{product_data['product_code']}</code>

<b>💳 Перевод на карту:</b> {formatted_card}

<b>❗ После оплаты обязательно нажмите кнопку ✅ Я оплатил ❗</b>"""
    
    keyboard = get_payment_keyboard(card)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
    await callback.answer()

@router.callback_query(F.data == "payment_confirmed")
async def payment_confirmed(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    
    if db.is_user_blocked(user_id):
        await callback.answer()
        return
    
    data = await state.get_data()
    
    if not data or 'product_id' not in data:
        await callback.answer("❌ Ошибка: данные о товаре не найдены", show_alert=True)
        return
    
    product_code = data.get('product_code', '')
    buyer_id = data.get('buyer_id', user_id)
    buyer_username = data.get('buyer_username', callback.from_user.username or 'Не указан')
    product_name = data.get('product_name', 'Товар')
    product_city = data.get('product_city', 'Не указан')
    product_quantity = data.get('product_quantity', '')
    product_price = data.get('product_price', 0)
    product_description = data.get('product_description', '')
    product_id = data.get('product_id')
    
    try:
        order = Order(
            user_id=user_id,
            product_name=product_name,
            city=product_city,
            quantity=product_quantity,
            price=product_price,
            description=product_description,
            created_at=datetime.now(),
            product_code=product_code,
            is_auto=False
        )
        
        order_id = db.add_order(order)
        db.update_product_stock(product_id, False)
        
        await state.update_data(
            order_id=order_id,
            buyer_id=buyer_id,
            buyer_username=buyer_username,
            product_name=product_name,
            product_city=product_city,
            product_quantity=product_quantity,
            product_price=product_price,
            product_description=product_description,
            product_code=product_code
        )
        
        db.set_setting(f"order_{order_id}_buyer_id", str(buyer_id))
        db.set_setting(f"order_{order_id}_buyer_username", buyer_username)
        db.set_setting(f"order_{order_id}_product_name", product_name)
        db.set_setting(f"order_{order_id}_product_city", product_city)
        db.set_setting(f"order_{order_id}_product_quantity", product_quantity)
        db.set_setting(f"order_{order_id}_product_price", str(product_price))
        db.set_setting(f"order_{order_id}_product_description", product_description)
        db.set_setting(f"order_{order_id}_product_code", product_code)
        
        await callback.message.edit_text(
            f"Спасибо за покупку, в течение 30 минут вы получите товар!\n\n"
            f"🔑 Код товара: <code>/{product_code}</code>",
            parse_mode='HTML'
        )
        
        description_text = f"\n📝 Описание: {product_description}" if product_description else ""
        
        admin_text = f"""<b>✅ Продан Товар</b>
📍 {product_city} - {product_name} - {product_quantity} - {product_price}₽{description_text}
🔑 Код: <code>/{product_code}</code>
👤 Покупатель: @{buyer_username} (ID: {buyer_id})"""
        
        admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📸 Отправить фото", callback_data=f"send_photo_{order_id}")],
            [InlineKeyboardButton(text="❌ Закрыть", callback_data="close_admin_order")]
        ])
        
        for admin_id in ADMIN_IDS:
            if db.is_user_blocked(admin_id):
                continue
            try:
                await callback.bot.send_message(
                    admin_id,
                    admin_text,
                    parse_mode='HTML',
                    reply_markup=admin_keyboard
                )
            except:
                pass
        
        print(f"✅ Заказ {order_id} создан, данные сохранены")
        
    except Exception as e:
        print(f"❌ Ошибка в payment_confirmed: {e}")
        import traceback
        traceback.print_exc()
        await callback.message.edit_text(
            "❌ Произошла ошибка при подтверждении оплаты. Пожалуйста, обратитесь к администратору."
        )
    
    await callback.answer()

@router.callback_query(F.data == "close_payment")
async def close_payment(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if db.is_user_blocked(user_id):
        await callback.answer()
        return
    
    await state.clear()
    await callback.message.delete()
    admin = is_admin(user_id)
    keyboard = get_main_menu(admin)
    await callback.message.answer(
        "⚡ Привет я современный помощник воспользуйся меню ниже ⬇️",
        reply_markup=keyboard
    )
    await callback.answer()

# ============================================
# ОТПРАВКА ФОТО
# ============================================

@router.callback_query(F.data.startswith("send_photo_"))
async def send_photo_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    order_id = int(callback.data.replace("send_photo_", ""))
    
    data = await state.get_data()
    buyer_id = data.get('buyer_id')
    buyer_username = data.get('buyer_username', 'Покупатель')
    product_name = data.get('product_name', 'Товар')
    product_code = data.get('product_code', '')
    
    if not buyer_id:
        print(f"⚠️ Данные не найдены в состоянии, ищем в БД для заказа {order_id}")
        
        buyer_id_str = db.get_setting(f"order_{order_id}_buyer_id", "")
        if buyer_id_str:
            buyer_id = int(buyer_id_str)
            buyer_username = db.get_setting(f"order_{order_id}_buyer_username", "Покупатель")
            product_name = db.get_setting(f"order_{order_id}_product_name", "Товар")
            product_code = db.get_setting(f"order_{order_id}_product_code", "")
            print(f"✅ Данные получены из БД: buyer_id={buyer_id}, product={product_name}")
        else:
            order = db.get_order_by_id(order_id)
            if order:
                buyer_id = order.get('user_id')
                buyer_username = f"User {buyer_id}"
                product_name = order.get('product_name', 'Товар')
                product_code = order.get('product_code', '')
                print(f"✅ Данные получены из заказа: buyer_id={buyer_id}")
            else:
                await callback.answer("❌ Данные о заказе не найдены. Пожалуйста, создайте заказ заново.", show_alert=True)
                return
    
    await state.update_data(
        sending_order_id=order_id,
        buyer_id=buyer_id,
        buyer_username=buyer_username,
        product_name=product_name,
        product_code=product_code
    )
    
    await state.set_state(AdminStates.waiting_for_photo)
    
    await callback.message.delete()
    await callback.message.answer(
        f"📸 Отправьте фото для покупателя\n\n"
        f"👤 Покупатель: @{buyer_username} (ID: {buyer_id})\n"
        f"📦 Товар: {product_name}\n"
        f"🔑 Код: /{product_code}\n\n"
        f"Фото будет отправлено покупателю без описания и без текста."
    )
    await callback.answer()

@router.message(AdminStates.waiting_for_photo)
async def send_photo_process(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔️ Доступ запрещен")
        await state.clear()
        return
    
    data = await state.get_data()
    buyer_id = data.get('buyer_id')
    buyer_username = data.get('buyer_username', 'Покупатель')
    product_name = data.get('product_name', 'Товар')
    product_code = data.get('product_code', '')
    
    if not buyer_id:
        await message.answer("❌ Ошибка: покупатель не найден. Пожалуйста, начните заново.")
        await state.clear()
        return
    
    if not message.photo:
        await message.answer(
            "❌ Пожалуйста, отправьте фото.\n"
            "Нажмите на 📎 и выберите фото."
        )
        return
    
    try:
        await message.bot.send_photo(
            chat_id=buyer_id,
            photo=message.photo[-1].file_id,
            caption=None
        )
        
        admin_success_text = f"""✅ Фото отправлено покупателю!

👤 Покупатель: @{buyer_username} (ID: {buyer_id})
📦 Товар: {product_name}
🔑 Код: <code>/{product_code}</code>"""
        
        await message.answer(
            admin_success_text,
            parse_mode='HTML'
        )
        
        keyboard = get_main_menu(True)
        await message.answer(
            "⚙️ Вы вернулись в главное меню",
            reply_markup=keyboard
        )
        
    except Exception as e:
        await message.answer(f"❌ Ошибка при отправке фото: {e}")
    
    await state.clear()

@router.callback_query(F.data == "close_admin_order")
async def close_admin_order(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    await callback.message.delete()
    
    keyboard = get_main_menu(True)
    await callback.message.answer(
        "⚡ Привет я современный помощник воспользуйся меню ниже ⬇️",
        reply_markup=keyboard
    )
    await callback.answer()

# ============================================
# ОБЩИЕ НАВИГАЦИОННЫЕ ОБРАБОТЧИКИ
# ============================================

@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if db.is_user_blocked(user_id):
        await callback.answer()
        return
    
    await state.clear()
    await callback.message.delete()
    admin = is_admin(user_id)
    keyboard = get_main_menu(admin)
    await callback.message.answer(
        "⚡ Привет я современный помощник воспользуйся меню ниже ⬇️",
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data == "page_info")
async def page_info(callback: CallbackQuery):
    await callback.answer()