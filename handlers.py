# handlers.py - Обработчики команд (ПОЛНАЯ ИСПРАВЛЕННАЯ ВЕРСИЯ)

from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import math
from datetime import datetime
import asyncio
import os

from database import db
from models import Product, Order
from keyboards import *
from utils import get_product_quantities, parse_product_file, format_card_number
from config import ADMIN_IDS, BACKUP_DIR

router = Router()

# ============================================
# СОСТОЯНИЯ
# ============================================

class AdminStates(StatesGroup):
    add_city = State()
    add_product_price = State()
    change_card = State()
    mailing_message = State()
    user_message = State()
    edit_product_price = State()
    edit_product_name = State()
    edit_product_quantity = State()
    waiting_for_photo = State()

class UserStates(StatesGroup):
    selecting_city = State()
    selecting_product = State()
    selecting_quantity = State()
    payment = State()

class AutoSellStates(StatesGroup):
    select_cities = State()
    select_products = State()
    select_quantities = State()
    select_days = State()
    enter_prices = State()
    confirm_campaign = State()
    enter_campaign_name = State()

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

# ============================================
# ФУНКЦИИ УВЕДОМЛЕНИЙ
# ============================================

async def notify_users_about_new_product(bot, product: Product):
    users = db.get_all_users()
    
    text = f"""✅ <b>Новый товар!</b>

📍 {product.city} - {product.name} - {product.quantity} - {product.price}₽ - ✅ В наличии

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

async def send_mailing(bot, users: List[int], message_text: str):
    sent = 0
    failed = 0
    blocked_skipped = 0
    
    for user_id in users:
        if db.is_user_blocked(user_id):
            blocked_skipped += 1
            continue
        
        try:
            await bot.send_message(
                user_id,
                f"📢 <b>Рассылка от администратора:</b>\n\n{message_text}",
                parse_mode='HTML'
            )
            sent += 1
            await asyncio.sleep(0.05)
        except:
            failed += 1
    
    return sent, failed, blocked_skipped

def get_all_users_for_mailing(target: str):
    all_users = db.get_all_users_full()
    active_users = [u for u in all_users if not u.get('is_blocked', False)]
    
    if target == "all":
        return [u['user_id'] for u in active_users]
    else:
        return []

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
    
    await state.update_data(
        product_id=product['id'],
        product_name=product['name'],
        product_city=product['city'],
        product_quantity=product['quantity'],
        product_price=product['price'],
        product_code=product['product_code']
    )
    
    card = db.get_setting('card_number', '')
    formatted_card = format_card_number(card) if card else 'не указана'
    
    text = f"""<b>Товар</b> {product['name']}
<b>Количество:</b> {product['quantity']}
<b>Цена:</b> {product['price']}₽
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
    
    await state.update_data(
        product_id=product['id'],
        product_name=product['name'],
        product_city=product['city'],
        product_quantity=product['quantity'],
        product_price=product['price'],
        product_code=product['product_code']
    )
    
    card = db.get_setting('card_number', '')
    formatted_card = format_card_number(card) if card else 'не указана'
    
    text = f"""<b>Товар</b> {product['name']}
<b>Количество:</b> {product['quantity']}
<b>Цена:</b> {product['price']}₽
<b>Статус:</b> ✅ В наличии
<b>🔑 Код:</b> <code>/{product['product_code']}</code>

<b>💳 Перевод на карту:</b> {formatted_card}

<b>❗ После оплаты обязательно нажмите кнопку ✅ Я оплатил ❗</b>"""
    
    keyboard = get_payment_keyboard(card)
    await message.answer(text, reply_markup=keyboard, parse_mode='HTML')

# ============================================
# КОМАНДЫ ДЛЯ БЕКАПА (только для админов)
# ============================================

@router.message(Command("backup"))
async def backup_command(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    status_msg = await message.answer("🔄 Создание резервной копии...")
    
    backup_path = db.create_backup()
    
    if backup_path:
        await status_msg.edit_text(
            f"✅ Резервная копия создана!\n\n"
            f"📁 Путь: {backup_path}\n"
            f"📅 Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"Используйте /backup_list для просмотра всех бекапов"
        )
    else:
        await status_msg.edit_text("❌ Ошибка при создании резервной копии")

@router.message(Command("backup_list"))
async def backup_list_command(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    backups = db.get_backup_list()
    
    if not backups:
        await message.answer("❌ Нет доступных резервных копий")
        return
    
    text = "📋 СПИСОК РЕЗЕРВНЫХ КОПИЙ\n\n"
    for i, backup in enumerate(backups[:20], 1):
        size_kb = backup['size'] / 1024
        created = backup['created'].strftime('%Y-%m-%d %H:%M')
        text += f"{i}. {backup['filename']}\n"
        text += f"   📅 {created} | 📦 {size_kb:.1f} KB\n\n"
    
    if len(backups) > 20:
        text += f"... и еще {len(backups) - 20} файлов\n"
    
    text += f"\nВсего: {len(backups)} бекапов\n"
    text += f"📁 Папка: {BACKUP_DIR}/"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Скачать последний бекап", callback_data="backup_download_latest")],
        [InlineKeyboardButton(text="🔄 Восстановить из бекапа", callback_data="backup_restore_menu")],
        [InlineKeyboardButton(text="🗑️ Очистить старые бекапы", callback_data="backup_cleanup")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_admin")]
    ])
    
    await message.answer(text, reply_markup=keyboard)

@router.callback_query(F.data == "backup_download_latest")
async def backup_download_latest(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    backups = db.get_backup_list()
    if not backups:
        await callback.answer("❌ Нет доступных бекапов", show_alert=True)
        return
    
    latest = backups[0]
    
    try:
        file = FSInputFile(latest['path'])
        await callback.message.answer_document(
            file,
            caption=f"📥 Бекап от {latest['created'].strftime('%Y-%m-%d %H:%M')}\n"
                    f"📦 Размер: {latest['size'] / 1024:.1f} KB"
        )
        await callback.answer("✅ Файл отправлен")
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)

@router.callback_query(F.data == "backup_restore_menu")
async def backup_restore_menu(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    backups = db.get_backup_list()
    if not backups:
        await callback.answer("❌ Нет доступных бекапов", show_alert=True)
        return
    
    keyboard = []
    for i, backup in enumerate(backups[:10]):
        created = backup['created'].strftime('%Y-%m-%d %H:%M')
        keyboard.append([
            InlineKeyboardButton(
                text=f"{i+1}. {created} ({backup['size']/1024:.0f}KB)",
                callback_data=f"backup_restore_{backup['filename']}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="backup_list")])
    
    await callback.message.edit_text(
        "🔄 ВОССТАНОВЛЕНИЕ ИЗ БЕКАПА\n\n"
        "⚠️ ВНИМАНИЕ! Восстановление заменит текущую базу данных.\n"
        "Рекомендуется сначала создать текущий бекап командой /backup\n\n"
        "Выберите бекап для восстановления:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("backup_restore_"))
async def backup_restore_confirm(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    filename = callback.data.replace("backup_restore_", "")
    backup_path = os.path.join(BACKUP_DIR, filename)
    
    if not os.path.exists(backup_path):
        await callback.answer("❌ Файл бекапа не найден", show_alert=True)
        return
    
    await callback.message.edit_text(
        f"⚠️ ПОДТВЕРЖДЕНИЕ ВОССТАНОВЛЕНИЯ\n\n"
        f"Файл: {filename}\n\n"
        f"⚠️ ВНИМАНИЕ! Это действие ЗАМЕНИТ текущую базу данных.\n"
        f"Все текущие данные будут потеряны.\n\n"
        f"Вы уверены?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ ДА, ВОССТАНОВИТЬ", callback_data=f"backup_confirm_restore_{filename}"),
                InlineKeyboardButton(text="❌ ОТМЕНА", callback_data="backup_list")
            ]
        ])
    )
    await callback.answer()

@router.callback_query(F.data.startswith("backup_confirm_restore_"))
async def backup_confirm_restore(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    filename = callback.data.replace("backup_confirm_restore_", "")
    backup_path = os.path.join(BACKUP_DIR, filename)
    
    await callback.message.edit_text("🔄 Восстановление базы данных...")
    
    if db.restore_backup(backup_path):
        await callback.message.edit_text(
            f"✅ БАЗА ДАННЫХ ВОССТАНОВЛЕНА!\n\n"
            f"📁 Файл: {filename}\n"
            f"📅 Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"⚠️ Перезапустите бота для применения изменений!"
        )
    else:
        await callback.message.edit_text("❌ Ошибка при восстановлении базы данных")
    
    await callback.answer()

@router.callback_query(F.data == "backup_cleanup")
async def backup_cleanup(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    backups = db.get_backup_list()
    if not backups:
        await callback.answer("❌ Нет бекапов для удаления", show_alert=True)
        return
    
    to_delete = backups[5:]
    if not to_delete:
        await callback.answer("❌ Нет старых бекапов для удаления", show_alert=True)
        return
    
    count = len(to_delete)
    await callback.message.edit_text(
        f"🗑️ УДАЛЕНИЕ СТАРЫХ БЕКАПОВ\n\n"
        f"Будет удалено: {count} файлов\n\n"
        f"Останется: 5 последних бекапов\n\n"
        f"Вы уверены?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ ДА, УДАЛИТЬ", callback_data="backup_confirm_cleanup"),
                InlineKeyboardButton(text="❌ ОТМЕНА", callback_data="backup_list")
            ]
        ])
    )
    await callback.answer()

@router.callback_query(F.data == "backup_confirm_cleanup")
async def backup_confirm_cleanup(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    try:
        backups = db.get_backup_list()
        deleted = 0
        for backup in backups[5:]:
            try:
                os.remove(backup['path'])
                deleted += 1
            except:
                pass
        
        await callback.message.edit_text(
            f"✅ УДАЛЕНО {deleted} СТАРЫХ БЕКАПОВ!\n\n"
            f"Оставлено: 5 последних бекапов"
        )
    except Exception as e:
        await callback.message.edit_text(f"❌ Ошибка: {e}")
    
    await callback.answer()

@router.callback_query(F.data == "backup_list")
async def backup_list_callback(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    await backup_list_command(callback.message)
    await callback.answer()

# ============================================
# ПОЛЬЗОВАТЕЛЬСКИЕ ОБРАБОТЧИКИ
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
    
    await state.update_data(
        product_id=product['id'],
        product_name=product['name'],
        product_city=product['city'],
        product_quantity=product['quantity'],
        product_price=product['price'],
        product_code=product['product_code']
    )
    
    card = db.get_setting('card_number', '')
    formatted_card = format_card_number(card) if card else 'не указана'
    
    text = f"""<b>Товар</b> {product['name']}
<b>Количество:</b> {product['quantity']}
<b>Цена:</b> {product['price']}₽
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

@router.callback_query(F.data == "unsubscribe")
async def unsubscribe_user(callback: CallbackQuery):
    await callback.answer("❌ Отписка от уведомлений больше не доступна", show_alert=True)

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
    
    await state.update_data(
        product_id=product_id,
        product_name=product_data['name'],
        product_city=product_data['city'],
        product_quantity=product_data['quantity'],
        product_price=product_data['price'],
        product_code=product_data['product_code'],
        buyer_id=user_id,
        buyer_username=callback.from_user.username or 'Не указан'
    )
    
    card = db.get_setting('card_number', '')
    formatted_card = format_card_number(card) if card else 'не указана'
    
    text = f"""<b>Товар</b> {product_data['name']}
<b>Количество:</b> {product_data['quantity']}
<b>Цена:</b> {product_data['price']}₽
<b>Статус:</b> ✅ В наличии
<b>🔑 Код:</b> <code>/{product_data['product_code']}</code>

<b>💳 Перевод на карту:</b> {formatted_card}

<b>❗ После оплаты обязательно нажмите кнопку ✅ Я оплатил ❗</b>"""
    
    keyboard = get_payment_keyboard(card)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
    await callback.answer()

# ============================================
# ПОДТВЕРЖДЕНИЕ ОПЛАТЫ (ИСПРАВЛЕНО)
# ============================================

@router.callback_query(F.data == "payment_confirmed")
async def payment_confirmed(callback: CallbackQuery, state: FSMContext):
    """Обработчик нажатия кнопки ✅ Я оплатил"""
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
    product_id = data.get('product_id')
    
    try:
        order = Order(
            user_id=user_id,
            product_name=product_name,
            city=product_city,
            quantity=product_quantity,
            price=product_price,
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
            product_code=product_code
        )
        
        # СОХРАНЯЕМ В БД
        db.set_setting(f"order_{order_id}_buyer_id", str(buyer_id))
        db.set_setting(f"order_{order_id}_buyer_username", buyer_username)
        db.set_setting(f"order_{order_id}_product_name", product_name)
        db.set_setting(f"order_{order_id}_product_city", product_city)
        db.set_setting(f"order_{order_id}_product_quantity", product_quantity)
        db.set_setting(f"order_{order_id}_product_price", str(product_price))
        db.set_setting(f"order_{order_id}_product_code", product_code)
        
        await callback.message.edit_text(
            f"Спасибо за покупку, в течение 30 минут вы получите товар!\n\n"
            f"🔑 Код товара: <code>/{product_code}</code>",
            parse_mode='HTML'
        )
        
        admin_text = f"""<b>✅ Продан Товар</b>
📍 {product_city} - {product_name} - {product_quantity} - {product_price}₽
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

# ============================================
# ОБРАБОТЧИКИ ДЛЯ ОТПРАВКИ ФОТО
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
# АДМИНСКИЕ ОБРАБОТЧИКИ
# ============================================

@router.callback_query(F.data == "admin_panel")
async def admin_panel(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ У вас нет доступа к админке", show_alert=True)
        return
    
    await state.clear()
    keyboard = get_admin_menu()
    await callback.message.edit_text("⚙️ Админка", reply_markup=keyboard)
    await callback.answer()

# ============================================
# АДМИНКА - УПРАВЛЕНИЕ ГОРОДАМИ
# ============================================

@router.callback_query(F.data == "admin_cities")
async def admin_cities(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    cities = db.get_cities()
    keyboard = get_cities_keyboard(cities, 0, True)
    await callback.message.edit_text("📍 Города", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "add_city")
async def add_city_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    await state.set_state(AdminStates.add_city)
    await callback.message.edit_text("Введите название города или метро")
    await callback.answer()

@router.message(AdminStates.add_city)
async def add_city_process(message: Message, state: FSMContext):
    city_name = message.text.strip()
    if not city_name:
        await message.answer("❌ Название не может быть пустым. Попробуйте снова.")
        return
    
    if db.add_city(city_name):
        await message.answer(f"✅ Город {city_name} добавлен!")
    else:
        await message.answer(f"❌ Город {city_name} уже существует!")
    
    await state.clear()
    cities = db.get_cities()
    keyboard = get_cities_keyboard(cities, 0, True)
    await message.answer("📍 Города", reply_markup=keyboard)

@router.callback_query(F.data.startswith("delete_city_"))
async def delete_city(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    city = callback.data.replace("delete_city_", "")
    if db.delete_city(city):
        await callback.answer(f"✅ Город {city} удален!")
    else:
        await callback.answer(f"❌ Ошибка при удалении города")
    
    cities = db.get_cities()
    keyboard = get_cities_keyboard(cities, 0, True)
    await callback.message.edit_text("📍 Города", reply_markup=keyboard)

@router.callback_query(F.data.startswith("city_page_"))
async def change_city_page(callback: CallbackQuery, state: FSMContext):
    page = int(callback.data.replace("city_page_", ""))
    cities = db.get_cities()
    keyboard = get_cities_keyboard(cities, page, False)
    await callback.message.edit_text("💦 Выберите город", reply_markup=keyboard)
    await callback.answer()

# ============================================
# АДМИНКА - УПРАВЛЕНИЕ ТОВАРАМИ
# ============================================

@router.callback_query(F.data == "admin_products_menu")
async def admin_products_menu(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    await state.clear()
    keyboard = get_admin_products_management_menu()
    await callback.message.edit_text(
        "💦 УПРАВЛЕНИЕ ТОВАРАМИ\n\nВыберите действие:",
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data == "admin_products_list")
async def admin_products_list(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    products = db.get_all_products()
    await state.update_data(products_list=products, products_page=0)
    
    if not products:
        await callback.message.edit_text(
            "❌ Нет добавленных товаров",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_products_back")]
            ])
        )
        await callback.answer()
        return
    
    keyboard = get_products_list_keyboard(products, 0)
    
    total = len(products)
    in_stock = sum(1 for p in products if p['in_stock'])
    sold = total - in_stock
    
    text = f"""📋 ВСЕ ТОВАРЫ

Всего: {total}
✅ В наличии: {in_stock}
❌ Продано: {sold}

Нажмите на товар для редактирования:"""
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("admin_prod_page_"))
async def admin_products_page(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    page = int(callback.data.replace("admin_prod_page_", ""))
    data = await state.get_data()
    products = data.get('products_list', [])
    
    keyboard = get_products_list_keyboard(products, page)
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("admin_product_edit_"))
async def admin_product_edit(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    product_id = int(callback.data.replace("admin_product_edit_", ""))
    product = db.get_product_by_id(product_id)
    
    if not product:
        await callback.answer("❌ Товар не найден", show_alert=True)
        return
    
    await state.update_data(editing_product_id=product_id)
    
    status = "✅ В наличии" if product['in_stock'] else "❌ Нет в наличии"
    
    text = f"""✏️ РЕДАКТИРОВАНИЕ ТОВАРА

🆔 ID: {product['id']}
📍 Город: {product['city']}
📦 Название: {product['name']}
📊 Количество: {product['quantity']}
💰 Цена: {product['price']}₽
📅 Добавлен: {product['created_at'][:10] if product.get('created_at') else 'Неизвестно'}
🔑 Код: <code>/{product['product_code']}</code>
📌 Статус: {status}

Выберите действие:"""
    
    keyboard = get_product_edit_keyboard(product_id, product['in_stock'])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
    await callback.answer()

# ... (остальные обработчики товаров - product_change_price, product_change_name, 
# product_change_quantity, product_toggle_stock, product_delete, product_confirm_delete,
# product_edit_back, admin_products_back, admin_products_add, admin_city_products,
# admin_add_product, qty_, add_product_price, admin_products_stats, 
# admin_products_stats_cities, admin_products_stats_sales)

# ============================================
# АДМИНКА - ОПЛАТА
# ============================================

@router.callback_query(F.data == "admin_payment")
async def admin_payment(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    card = db.get_setting('card_number', '')
    formatted_card = format_card_number(card) if card else 'не указана'
    
    text = f"💳 ОПЛАТА\n\n<b>Ваша карта:</b> {formatted_card}"
    keyboard = get_admin_payment_keyboard()
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
    await callback.answer()

@router.callback_query(F.data == "change_card")
async def change_card_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    await state.set_state(AdminStates.change_card)
    await callback.message.edit_text("💳 ИЗМЕНЕНИЕ КАРТЫ\n\nВведите номер карты в любом формате")
    await callback.answer()

@router.message(AdminStates.change_card)
async def change_card_process(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔️ Доступ запрещен")
        return
    
    card = message.text.strip()
    db.set_setting('card_number', card)
    await state.clear()
    
    formatted_card = format_card_number(card)
    text = f"💳 ОПЛАТА\n\n<b>Ваша карта:</b> {formatted_card}"
    keyboard = get_admin_payment_keyboard()
    
    await message.answer(text, reply_markup=keyboard, parse_mode='HTML')

# ============================================
# АДМИНКА - СТАТИСТИКА
# ============================================

@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    orders_count = db.get_orders_count()
    cities_count = len(db.get_cities())
    products = db.get_all_products()
    products_count = len(products)
    in_stock = sum(1 for p in products if p['in_stock'])
    users_count = db.get_users_count()
    blocked_count = db.get_blocked_count()
    
    total_revenue = sum(p['price'] for p in products if not p['in_stock'])
    
    text = f"""📊 СТАТИСТИКА

👥 Пользователей: {users_count}
🔒 Заблокировано: {blocked_count}
👥 Заказов: {orders_count}
📍 Городов: {cities_count}
💦 Товаров всего: {products_count}
✅ В наличии: {in_stock}
❌ Продано: {products_count - in_stock}
💰 Общая выручка: {total_revenue}₽

📈 Средний чек: {total_revenue // orders_count if orders_count > 0 else 0}₽"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_admin")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

# ============================================
# АДМИНКА - ПОЛЬЗОВАТЕЛИ
# ============================================

@router.callback_query(F.data == "admin_users")
async def admin_users_menu(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    await state.clear()
    keyboard = get_users_menu()
    
    total_users = db.get_users_count()
    subscribed = db.get_subscribed_users_count()
    blocked = db.get_blocked_count()
    active = len(db.get_users_by_activity(7))
    
    text = f"""👥 УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ

📊 Статистика:
👥 Всего пользователей: {total_users}
🟢 Подписаны: {subscribed}
🔒 Заблокированы: {blocked}
📈 Активны за 7 дней: {active}

Выберите действие:"""
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

# ============================================
# АВТО-ПРОДАЖИ
# ============================================

@router.callback_query(F.data == "auto_sell")
async def auto_sell_menu(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    await state.clear()
    keyboard = get_auto_sell_menu()
    await callback.message.edit_text(
        "🤖 АВТОМАТИЧЕСКАЯ ПРОДАЖА\n\n"
        "Создайте кампанию для автоматической продажи товаров.\n"
        "Бот сам будет имитировать активность и продавать товары.",
        reply_markup=keyboard
    )
    await callback.answer()

# ============================================
# ОБЩИЕ НАВИГАЦИОННЫЕ ОБРАБОТЧИКИ
# ============================================

@router.callback_query(F.data == "back_to_admin")
async def back_to_admin(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    await state.clear()
    keyboard = get_admin_menu()
    await callback.message.edit_text("⚙️ Админка", reply_markup=keyboard)
    await callback.answer()

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