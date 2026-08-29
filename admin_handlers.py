# admin_handlers.py - Основные админские обработчики

from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import math
from datetime import datetime
import os

from database import db
from models import Product, Order
from keyboards import *
from utils import get_product_quantities, parse_product_file, format_card_number, is_admin
from config import ADMIN_IDS, BACKUP_DIR
from automation import auto_engine

router = Router()

# ============================================
# СОСТОЯНИЯ
# ============================================

class AdminStates(StatesGroup):
    add_city = State()
    change_card = State()
    mailing_message = State()
    user_message = State()

# ============================================
# ГЛАВНАЯ АДМИНКА
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

@router.callback_query(F.data == "back_to_admin")
async def back_to_admin(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    await state.clear()
    keyboard = get_admin_menu()
    await callback.message.edit_text("⚙️ Админка", reply_markup=keyboard)
    await callback.answer()

# ============================================
# УПРАВЛЕНИЕ ГОРОДАМИ
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
# ОПЛАТА
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
# СТАТИСТИКА (ОБЩАЯ)
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
# УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ
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
# ОСТАЛЬНЫЕ ОБРАБОТЧИКИ ПОЛЬЗОВАТЕЛЕЙ
# ============================================

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
            f"⚠️ ВНИМАНИЕ!\n\nВы уверены, что хотите заблокировать пользователя {name}?\n\n"
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
        await user_info(callback, FSMContext())
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
        await user_info(callback, FSMContext())
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
        "⚠️ ВНИМАНИЕ!\n\nВы уверены, что хотите удалить этого пользователя?\n"
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
        await users_list(callback, FSMContext())
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
    await user_info(message, state)

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
# БЕКАП
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