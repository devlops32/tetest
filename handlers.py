# handlers.py - ПОЛНАЯ ИСПРАВЛЕННАЯ ВЕРСИЯ (ВСЕ ОБРАБОТЧИКИ)

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
# ПОДТВЕРЖДЕНИЕ ОПЛАТЫ
# ============================================

@router.callback_query(F.data == "payment_confirmed")
async def payment_confirmed(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if db.is_user_blocked(user_id):
        await callback.answer()
        return
    
    data = await state.get_data()
    product_code = data.get('product_code', '')
    buyer_id = data.get('buyer_id', user_id)
    buyer_username = data.get('buyer_username', 'Не указан')
    
    order = Order(
        user_id=user_id,
        product_name=data['product_name'],
        city=data['product_city'],
        quantity=data['product_quantity'],
        price=data['product_price'],
        created_at=datetime.now(),
        product_code=product_code,
        is_auto=False
    )
    
    db.add_order(order)
    db.update_product_stock(data['product_id'], False)
    
    await state.update_data(
        order_id=order.id,
        buyer_id=buyer_id,
        buyer_username=buyer_username,
        product_name=data['product_name'],
        product_city=data['product_city'],
        product_quantity=data['product_quantity'],
        product_price=data['product_price'],
        product_code=product_code
    )
    
    await callback.message.edit_text(
        f"Спасибо за покупку, в течение 30 минут вы получите товар!\n\n"
        f"🔑 Код товара: <code>/{product_code}</code>",
        parse_mode='HTML'
    )
    
    admin_text = f"""<b>✅ Продан Товар</b>
📍 {data['product_city']} - {data['product_name']} - {data['product_quantity']} - {data['product_price']}₽
🔑 Код: <code>/{product_code}</code>
👤 Покупатель: @{buyer_username} (ID: {buyer_id})"""
    
    admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📸 Отправить фото", callback_data=f"send_photo_{order.id}")],
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
    
    await state.update_data(
        sending_order_id=order_id,
        admin_message_id=callback.message.message_id,
        admin_chat_id=callback.message.chat.id
    )
    
    await state.set_state(AdminStates.waiting_for_photo)
    
    await callback.message.delete()
    await callback.message.answer(
        "📸 Отправьте фото для покупателя\n\n"
        "Фото будет отправлено покупателю без описания и без текста."
    )
    await callback.answer()

@router.message(AdminStates.waiting_for_photo)
async def send_photo_process(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔️ Доступ запрещен")
        await state.clear()
        return
    
    data = await state.get_data()
    order_id = data.get('sending_order_id')
    buyer_id = data.get('buyer_id')
    buyer_username = data.get('buyer_username', 'Покупатель')
    product_name = data.get('product_name', 'Товар')
    product_code = data.get('product_code', '')
    
    if not order_id or not buyer_id:
        await message.answer("❌ Ошибка: заказ или покупатель не найден")
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
# 💳 ОПЛАТА
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
# 📊 СТАТИСТИКА (ОБЩАЯ)
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
# 👥 ПОЛЬЗОВАТЕЛИ
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

@router.callback_query(F.data == "users_list")
async def users_list(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    users = db.get_all_users_full()
    await state.update_data(users_list=users, users_page=0)
    
    keyboard = get_users_list_keyboard(users, 0)
    text = f"👥 ВСЕ ПОЛЬЗОВАТЕЛИ\n\nВсего: {len(users)}"
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("users_page_"))
async def users_page(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    page = int(callback.data.replace("users_page_", ""))
    data = await state.get_data()
    users = data.get('users_list', [])
    
    keyboard = get_users_list_keyboard(users, page)
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "users_active")
async def users_active(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    users = db.get_users_by_activity(7)
    
    if not users:
        await callback.answer("❌ Нет активных пользователей за 7 дней", show_alert=True)
        return
    
    text = "📊 АКТИВНЫЕ ПОЛЬЗОВАТЕЛИ (7 дней)\n\n"
    for user in users[:10]:
        username = user.get('username', 'Нет username')
        first_name = user.get('first_name', 'Без имени')
        text += f"👤 {first_name} (@{username}) - {user['orders_count']} заказов, {user['total_spent']}₽\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="users_back")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "users_stats")
async def users_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    total_users = db.get_users_count()
    subscribed = db.get_subscribed_users_count()
    blocked = db.get_blocked_count()
    
    all_orders = db.get_auto_orders(365)
    total_spent = sum(o.get('price', 0) for o in all_orders)
    
    cities = db.get_cities()
    city_stats = []
    for city in cities:
        products = db.get_products_by_city(city)
        city_stats.append(f"📍 {city}: {len(products)} товаров")
    
    text = f"""📊 СТАТИСТИКА ПОЛЬЗОВАТЕЛЕЙ

👥 Всего пользователей: {total_users}
🟢 Подписаны: {subscribed}
🔒 Заблокированы: {blocked}
📈 Всего заказов: {db.get_orders_count()}
💰 Общая выручка: {total_spent}₽

🏙️ По городам:
{chr(10).join(city_stats[:5])}"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="users_back")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "users_blocked")
async def users_blocked_list(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    users = db.get_blocked_users()
    await state.update_data(blocked_users=users)
    
    if not users:
        await callback.answer("❌ Нет заблокированных пользователей", show_alert=True)
        return
    
    keyboard = get_blocked_users_keyboard(users, 0)
    await callback.message.edit_text(
        f"🔒 ЗАБЛОКИРОВАННЫЕ ПОЛЬЗОВАТЕЛИ\n\nВсего: {len(users)}",
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data.startswith("blocked_page_"))
async def blocked_users_page(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    page = int(callback.data.replace("blocked_page_", ""))
    data = await state.get_data()
    users = data.get('blocked_users', [])
    
    keyboard = get_blocked_users_keyboard(users, page)
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("user_info_"))
async def user_info(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    user_id = int(callback.data.replace("user_info_", ""))
    user_data = db.get_user_stats(user_id)
    
    if not user_data:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return
    
    stats = user_data.get('stats', {})
    last_orders = user_data.get('last_orders', [])
    is_blocked = user_data.get('is_blocked', False)
    
    text = f"""👤 ИНФОРМАЦИЯ О ПОЛЬЗОВАТЕЛЕ{" 🔒" if is_blocked else ""}

🆔 ID: {user_data['user_id']}
👤 Имя: {user_data.get('first_name', 'Не указано')}
📛 Username: @{user_data.get('username', 'Не указан')}
📅 Зарегистрирован: {user_data.get('created_at', '')[:10]}

📊 Статистика:
• Всего заказов: {stats.get('total_orders', 0)}
• Потрачено: {stats.get('total_spent', 0)}₽
• Средний чек: {stats.get('avg_price', 0):.0f}₽

🔒 Статус: {'<b>ЗАБЛОКИРОВАН</b>' if is_blocked else '✅ Не заблокирован'}
{"📅 Заблокирован: " + user_data.get('blocked_at', '')[:10] if is_blocked else ''}

📦 Последние заказы:"""
    
    if last_orders:
        for order in last_orders[:3]:
            text += f"\n  • {order['product_name']} | {order['price']}₽ | {order.get('created_at', '')[:10]}"
    else:
        text += "\n  • Нет заказов"
    
    keyboard = get_user_info_keyboard(user_id, is_blocked)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
    await callback.answer()

# ============================================
# ОСТАЛЬНЫЕ ОБРАБОТЧИКИ ПОЛЬЗОВАТЕЛЕЙ
# ============================================

@router.callback_query(F.data.startswith("user_orders_"))
async def user_orders(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    user_id = int(callback.data.replace("user_orders_", ""))
    orders = db.get_user_orders(user_id, 10)
    await state.update_data(user_orders=orders, user_orders_page=0)
    
    if not orders:
        await callback.answer("❌ У пользователя нет заказов", show_alert=True)
        return
    
    keyboard = get_user_orders_keyboard(orders, 0)
    await callback.message.edit_text(
        f"📦 ИСТОРИЯ ЗАКАЗОВ\n\nВсего: {len(orders)} заказов",
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data.startswith("user_orders_page_"))
async def user_orders_page(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    page = int(callback.data.replace("user_orders_page_", ""))
    data = await state.get_data()
    orders = data.get('user_orders', [])
    
    keyboard = get_user_orders_keyboard(orders, page)
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("user_block_"))
async def user_block(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    user_id = int(callback.data.replace("user_block_", ""))
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, заблокировать", callback_data=f"user_confirm_block_{user_id}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data=f"user_info_{user_id}")
        ]
    ])
    
    user_data = db.get_user_stats(user_id)
    if user_data:
        name = user_data.get('first_name', 'Пользователь')
        await callback.message.edit_text(
            f"⚠️ ВНИМАНИЕ!\n\n"
            f"Вы уверены, что хотите заблокировать пользователя {name}?\n\n"
            f"После блокировки:\n"
            f"❌ Пользователь не сможет пользоваться ботом\n"
            f"❌ Уведомления не будут отправляться\n"
            f"❌ При /start не будет ответа\n\n"
            f"Вы всегда сможете разблокировать его.",
            reply_markup=keyboard
        )
    await callback.answer()

@router.callback_query(F.data.startswith("user_confirm_block_"))
async def user_confirm_block(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    user_id = int(callback.data.replace("user_confirm_block_", ""))
    
    if db.block_user(user_id):
        await callback.answer("🔒 Пользователь заблокирован!", show_alert=True)
        
        user_data = db.get_user_stats(user_id)
        if user_data:
            stats = user_data.get('stats', {})
            text = f"""👤 ИНФОРМАЦИЯ О ПОЛЬЗОВАТЕЛЕ 🔒

🆔 ID: {user_data['user_id']}
👤 Имя: {user_data.get('first_name', 'Не указано')}
📛 Username: @{user_data.get('username', 'Не указан')}
📅 Зарегистрирован: {user_data.get('created_at', '')[:10]}

📊 Статистика:
• Всего заказов: {stats.get('total_orders', 0)}
• Потрачено: {stats.get('total_spent', 0)}₽

🔒 Статус: <b>ЗАБЛОКИРОВАН</b>
📅 Заблокирован: {datetime.now().strftime('%Y-%m-%d %H:%M')}"""
            
            keyboard = get_user_info_keyboard(user_id, is_blocked=True)
            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
    else:
        await callback.answer("❌ Ошибка при блокировке пользователя", show_alert=True)

@router.callback_query(F.data.startswith("user_unblock_"))
async def user_unblock(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    user_id = int(callback.data.replace("user_unblock_", ""))
    
    if db.unblock_user(user_id):
        await callback.answer("🔓 Пользователь разблокирован!", show_alert=True)
        
        user_data = db.get_user_stats(user_id)
        if user_data:
            stats = user_data.get('stats', {})
            text = f"""👤 ИНФОРМАЦИЯ О ПОЛЬЗОВАТЕЛЕ

🆔 ID: {user_data['user_id']}
👤 Имя: {user_data.get('first_name', 'Не указано')}
📛 Username: @{user_data.get('username', 'Не указан')}
📅 Зарегистрирован: {user_data.get('created_at', '')[:10]}

📊 Статистика:
• Всего заказов: {stats.get('total_orders', 0)}
• Потрачено: {stats.get('total_spent', 0)}₽

🔓 Статус: <b>Разблокирован</b>"""
            
            keyboard = get_user_info_keyboard(user_id, is_blocked=False)
            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
    else:
        await callback.answer("❌ Ошибка при разблокировке пользователя", show_alert=True)

@router.callback_query(F.data.startswith("user_delete_"))
async def user_delete(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    user_id = int(callback.data.replace("user_delete_", ""))
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"user_confirm_delete_{user_id}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data=f"user_info_{user_id}")
        ]
    ])
    
    await callback.message.edit_text(
        "⚠️ ВНИМАНИЕ!\n\n"
        "Вы уверены, что хотите удалить этого пользователя?\n"
        "Все данные пользователя будут безвозвратно удалены.",
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data.startswith("user_confirm_delete_"))
async def user_confirm_delete(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    user_id = int(callback.data.replace("user_confirm_delete_", ""))
    
    if db.delete_user(user_id):
        await callback.answer("✅ Пользователь удален!", show_alert=True)
        
        keyboard = get_users_menu()
        await callback.message.edit_text(
            "👥 УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ\n\n"
            "Пользователь успешно удален.",
            reply_markup=keyboard
        )
    else:
        await callback.answer("❌ Ошибка при удалении пользователя", show_alert=True)

@router.callback_query(F.data.startswith("user_message_"))
async def user_message_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    user_id = int(callback.data.replace("user_message_", ""))
    await state.update_data(message_user_id=user_id)
    await state.set_state(AdminStates.user_message)
    
    await callback.message.edit_text("📝 Введите сообщение для пользователя:\n(можно использовать HTML-разметку)")
    await callback.answer()

@router.message(AdminStates.user_message)
async def user_message_send(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔️ Доступ запрещен")
        return
    
    data = await state.get_data()
    user_id = data.get('message_user_id')
    
    if not user_id:
        await message.answer("❌ Ошибка: пользователь не найден")
        await state.clear()
        return
    
    if db.is_user_blocked(user_id):
        await message.answer("❌ Пользователь заблокирован, сообщение не отправлено")
        await state.clear()
        return
    
    try:
        await message.bot.send_message(
            user_id,
            f"📨 <b>Сообщение от администратора:</b>\n\n{message.text}",
            parse_mode='HTML'
        )
        await message.answer("✅ Сообщение отправлено пользователю!")
    except Exception as e:
        await message.answer(f"❌ Ошибка при отправке: {e}")
    
    await state.clear()
    
    user_data = db.get_user_stats(user_id)
    if user_data:
        stats = user_data.get('stats', {})
        is_blocked = user_data.get('is_blocked', False)
        text = f"""👤 ИНФОРМАЦИЯ О ПОЛЬЗОВАТЕЛЕ{" 🔒" if is_blocked else ""}

🆔 ID: {user_data['user_id']}
👤 Имя: {user_data.get('first_name', 'Не указано')}
📛 Username: @{user_data.get('username', 'Не указан')}
📅 Зарегистрирован: {user_data.get('created_at', '')[:10]}

📊 Статистика:
• Всего заказов: {stats.get('total_orders', 0)}
• Потрачено: {stats.get('total_spent', 0)}₽"""
        
        keyboard = get_user_info_keyboard(user_id, is_blocked)
        await message.answer(text, reply_markup=keyboard, parse_mode='HTML')

@router.callback_query(F.data == "users_mailing")
async def mailing_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    keyboard = get_mailing_keyboard()
    await callback.message.edit_text(
        "📬 РАССЫЛКА\n\nВыберите получателей:",
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data.startswith("mailing_"))
async def mailing_select(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    target = callback.data.replace("mailing_", "")
    await state.update_data(mailing_target=target)
    await state.set_state(AdminStates.mailing_message)
    
    users = get_all_users_for_mailing(target)
    total = len(users)
    
    if target == "all":
        text = f"👥 Всем пользователям ({total} чел.)"
    else:
        await callback.answer("❌ Неверный выбор", show_alert=True)
        return
    
    if total == 0:
        await callback.answer("❌ Нет получателей для рассылки", show_alert=True)
        return
    
    await callback.message.edit_text(
        f"📬 РАССЫЛКА\n\nПолучатели: {text}\n\n📝 Введите сообщение для рассылки:\n(можно использовать HTML-разметку)"
    )
    await callback.answer()

@router.message(AdminStates.mailing_message)
async def mailing_send(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔️ Доступ запрещен")
        return
    
    data = await state.get_data()
    target = data.get('mailing_target')
    
    users = get_all_users_for_mailing(target)
    
    if not users:
        await message.answer("❌ Нет получателей для рассылки")
        await state.clear()
        return
    
    sent, failed, blocked_skipped = await send_mailing(message.bot, users, message.text)
    
    await state.clear()
    
    await message.answer(
        f"✅ РАССЫЛКА ЗАВЕРШЕНА!\n\n"
        f"📨 Отправлено: {sent}\n"
        f"❌ Не доставлено: {failed}\n"
        f"🔒 Пропущено (заблокированы): {blocked_skipped}"
    )
    
    keyboard = get_users_menu()
    await message.answer(
        "👥 УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ",
        reply_markup=keyboard
    )

@router.callback_query(F.data == "users_back")
async def users_back(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    await state.clear()
    await admin_users_menu(callback, state)

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
# АДМИНКА - УПРАВЛЕНИЕ ТОВАРАМИ (ДОБАВЛЕНИЕ)
# ============================================

@router.callback_query(F.data == "admin_products_add")
async def admin_products_add(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    cities = db.get_cities()
    if not cities:
        await callback.message.edit_text(
            "❌ Сначала добавьте города!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_products_back")]
            ])
        )
        await callback.answer()
        return
    
    keyboard = get_admin_city_products_keyboard(cities, 0)
    await callback.message.edit_text(
        "💦 Товары\n📍 Выберите город для товара",
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data.startswith("admin_city_page_"))
async def change_admin_city_page(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    page = int(callback.data.replace("admin_city_page_", ""))
    cities = db.get_cities()
    keyboard = get_admin_city_products_keyboard(cities, page)
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("admin_city_products_"))
async def admin_city_products(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    city = callback.data.replace("admin_city_products_", "")
    await state.update_data(admin_city=city)
    
    products_from_file = parse_product_file('list.txt')
    product_names = list(products_from_file.keys())
    
    if not product_names:
        await callback.message.edit_text(
            "❌ Нет доступных товаров для добавления",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_admin_products")]
            ])
        )
        await callback.answer()
        return
    
    keyboard = []
    row = []
    for i, name in enumerate(product_names):
        row.append(InlineKeyboardButton(
            text=name,
            callback_data=f"admin_add_product_{name}"
        ))
        if len(row) == 4:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_admin_products")])
    
    await callback.message.edit_text(
        f"💦 Выберите товар для города {city}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("admin_add_product_"))
async def admin_add_product(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    product_name = callback.data.replace("admin_add_product_", "")
    data = await state.get_data()
    city = data.get('admin_city', '')
    
    quantities = get_product_quantities(product_name)
    
    if not quantities:
        await callback.answer("❌ Нет доступных количеств для этого товара", show_alert=True)
        return
    
    await state.update_data(
        adding_product_name=product_name,
        adding_product_city=city
    )
    
    keyboard = get_product_quantity_keyboard(quantities, product_name)
    await callback.message.edit_text(
        f"💦 Выберите количество для {product_name}",
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data.startswith("qty_"))
async def select_quantity(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    parts = callback.data.split("_", 2)
    if len(parts) < 3:
        await callback.answer("❌ Ошибка", show_alert=True)
        return
    
    product_name = parts[1]
    quantity = parts[2]
    
    await state.update_data(product_quantity=quantity)
    await state.set_state(AdminStates.add_product_price)
    
    await callback.message.edit_text(
        f"Введите цену товара {product_name} ({quantity})"
    )
    await callback.answer()

@router.message(AdminStates.add_product_price)
async def add_product_price(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔️ Доступ запрещен")
        return
    
    try:
        price = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите корректную цену (только цифры)")
        return
    
    data = await state.get_data()
    
    product = Product(
        city=data['adding_product_city'],
        name=data['adding_product_name'],
        quantity=data['product_quantity'],
        price=price,
        in_stock=True
    )
    
    db.add_product(product)
    await state.clear()
    
    products = db.get_products_by_city(product.city)
    added_product = None
    for p in products:
        if p.name == product.name and p.quantity == product.quantity and p.price == product.price:
            added_product = p
            break
    
    code = added_product.product_code if added_product else 'неизвестен'
    
    await message.answer(
        f"✅ Товар 📍 {product.city} - {product.name} - {product.quantity} - {product.price}₽ добавлен!\n"
        f"🔑 Код товара: <code>/{code}</code>",
        parse_mode='HTML'
    )
    
    if added_product:
        await notify_users_about_new_product(message.bot, added_product)
    
    cities = db.get_cities()
    keyboard = get_admin_city_products_keyboard(cities, 0)
    await message.answer(
        "💦 Товары\n📍 Выберите город для товара",
        reply_markup=keyboard
    )

# ============================================
# АДМИНКА - СТАТИСТИКА ТОВАРОВ
# ============================================

@router.callback_query(F.data == "admin_products_stats")
async def admin_products_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    stats = db.get_products_stats()
    
    text = f"""📊 СТАТИСТИКА ТОВАРОВ

📦 Всего товаров: {stats['total']}
✅ В наличии: {stats['in_stock']}
❌ Продано: {stats['sold']}

💰 Средняя цена: {stats['avg_price']:.0f}₽
🔽 Минимальная цена: {stats['min_price']}₽
🔼 Максимальная цена: {stats['max_price']}₽
💎 Общая стоимость: {stats['total_value']}₽

📋 По городам:"""
    
    for city in stats.get('by_city', [])[:5]:
        text += f"\n   • {city['city']}: {city['count']} шт. ({city['in_stock']} в наличии)"
    
    text += "\n\n🏆 Популярные товары:"
    for product in stats.get('by_product', [])[:5]:
        text += f"\n   • {product['name']}: {product['sold_count']} продано"
    
    keyboard = get_admin_products_stats_keyboard()
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "admin_products_stats_cities")
async def admin_products_stats_cities(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    stats = db.get_products_stats()
    
    text = "📊 СТАТИСТИКА ПО ГОРОДАМ\n\n"
    for city in stats.get('by_city', []):
        text += f"📍 {city['city']}\n"
        text += f"   Всего: {city['count']} шт.\n"
        text += f"   ✅ В наличии: {city['in_stock']}\n"
        text += f"   ❌ Продано: {city['sold']}\n\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_products_stats")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "admin_products_stats_sales")
async def admin_products_stats_sales(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    stats = db.get_products_stats()
    total_orders = db.get_orders_count()
    
    text = f"""📈 СТАТИСТИКА ПРОДАЖ

📦 Всего продано товаров: {stats['sold']}
👥 Всего заказов: {total_orders}
💰 Общая стоимость проданных товаров: {sum(p['price'] for p in db.get_all_products() if not p['in_stock'])}₽

🏆 Топ продаваемых товаров:"""
    
    for product in stats.get('by_product', []):
        if product['sold_count'] > 0:
            text += f"\n   • {product['name']}: {product['sold_count']} шт."
    
    if not any(p['sold_count'] > 0 for p in stats.get('by_product', [])):
        text += "\n   • Нет проданных товаров"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_products_stats")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

# ============================================
# АДМИНКА - РЕДАКТИРОВАНИЕ ТОВАРОВ
# ============================================

@router.callback_query(F.data.startswith("product_change_price_"))
async def product_change_price_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    product_id = int(callback.data.replace("product_change_price_", ""))
    await state.update_data(editing_product_id=product_id)
    await state.set_state(AdminStates.edit_product_price)
    
    product = db.get_product_by_id(product_id)
    current_price = product['price'] if product else 0
    
    await callback.message.edit_text(
        f"💰 ИЗМЕНЕНИЕ ЦЕНЫ\n\nТекущая цена: {current_price}₽\n\nВведите новую цену (только цифры):"
    )
    await callback.answer()

@router.message(AdminStates.edit_product_price)
async def product_change_price_process(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔️ Доступ запрещен")
        return
    
    try:
        new_price = int(message.text.strip())
        if new_price <= 0:
            await message.answer("❌ Цена должна быть больше 0")
            return
    except ValueError:
        await message.answer("❌ Введите корректную цену (только цифры)")
        return
    
    data = await state.get_data()
    product_id = data.get('editing_product_id')
    
    if db.update_product_price(product_id, new_price):
        await message.answer(f"✅ Цена успешно изменена на {new_price}₽")
    else:
        await message.answer("❌ Ошибка при изменении цены")
    
    await state.clear()
    
    product = db.get_product_by_id(product_id)
    if product:
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
        await message.answer(text, reply_markup=keyboard, parse_mode='HTML')

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