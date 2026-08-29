# admin_handlers.py - Все админские обработчики

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
    add_product_price = State()
    add_product_description = State()
    change_card = State()
    mailing_message = State()
    user_message = State()
    edit_product_price = State()
    edit_product_name = State()
    edit_product_quantity = State()
    edit_product_description = State()

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
# УПРАВЛЕНИЕ ТОВАРАМИ
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
    description = product.get('description', '')
    description_text = f"\n📝 Описание: {description}" if description else ""
    
    text = f"""✏️ РЕДАКТИРОВАНИЕ ТОВАРА

🆔 ID: {product['id']}
📍 Город: {product['city']}
📦 Название: {product['name']}
📊 Количество: {product['quantity']}
💰 Цена: {product['price']}₽{description_text}
📅 Добавлен: {product['created_at'][:10] if product.get('created_at') else 'Неизвестно'}
🔑 Код: <code>/{product['product_code']}</code>
📌 Статус: {status}

Выберите действие:"""
    
    keyboard = get_product_edit_keyboard(product_id, product['in_stock'])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
    await callback.answer()

# ============================================
# РЕДАКТИРОВАНИЕ ТОВАРА (ЦЕНА, НАЗВАНИЕ, КОЛИЧЕСТВО, ОПИСАНИЕ)
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
        description = product.get('description', '')
        description_text = f"\n📝 Описание: {description}" if description else ""
        text = f"""✏️ РЕДАКТИРОВАНИЕ ТОВАРА

🆔 ID: {product['id']}
📍 Город: {product['city']}
📦 Название: {product['name']}
📊 Количество: {product['quantity']}
💰 Цена: {product['price']}₽{description_text}
📅 Добавлен: {product['created_at'][:10] if product.get('created_at') else 'Неизвестно'}
🔑 Код: <code>/{product['product_code']}</code>
📌 Статус: {status}

Выберите действие:"""
        
        keyboard = get_product_edit_keyboard(product_id, product['in_stock'])
        await message.answer(text, reply_markup=keyboard, parse_mode='HTML')

@router.callback_query(F.data.startswith("product_change_name_"))
async def product_change_name_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    product_id = int(callback.data.replace("product_change_name_", ""))
    await state.update_data(editing_product_id=product_id)
    await state.set_state(AdminStates.edit_product_name)
    
    product = db.get_product_by_id(product_id)
    current_name = product['name'] if product else 'Неизвестно'
    
    await callback.message.edit_text(
        f"📝 ИЗМЕНЕНИЕ НАЗВАНИЯ\n\nТекущее название: {current_name}\n\nВведите новое название товара:"
    )
    await callback.answer()

@router.message(AdminStates.edit_product_name)
async def product_change_name_process(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔️ Доступ запрещен")
        return
    
    new_name = message.text.strip()
    if not new_name:
        await message.answer("❌ Название не может быть пустым")
        return
    
    data = await state.get_data()
    product_id = data.get('editing_product_id')
    
    if db.update_product_name(product_id, new_name):
        await message.answer(f"✅ Название успешно изменено на '{new_name}'")
    else:
        await message.answer("❌ Ошибка при изменении названия")
    
    await state.clear()
    
    product = db.get_product_by_id(product_id)
    if product:
        status = "✅ В наличии" if product['in_stock'] else "❌ Нет в наличии"
        description = product.get('description', '')
        description_text = f"\n📝 Описание: {description}" if description else ""
        text = f"""✏️ РЕДАКТИРОВАНИЕ ТОВАРА

🆔 ID: {product['id']}
📍 Город: {product['city']}
📦 Название: {product['name']}
📊 Количество: {product['quantity']}
💰 Цена: {product['price']}₽{description_text}
📅 Добавлен: {product['created_at'][:10] if product.get('created_at') else 'Неизвестно'}
🔑 Код: <code>/{product['product_code']}</code>
📌 Статус: {status}

Выберите действие:"""
        
        keyboard = get_product_edit_keyboard(product_id, product['in_stock'])
        await message.answer(text, reply_markup=keyboard, parse_mode='HTML')

@router.callback_query(F.data.startswith("product_change_quantity_"))
async def product_change_quantity_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    product_id = int(callback.data.replace("product_change_quantity_", ""))
    await state.update_data(editing_product_id=product_id)
    await state.set_state(AdminStates.edit_product_quantity)
    
    product = db.get_product_by_id(product_id)
    current_quantity = product['quantity'] if product else 'Неизвестно'
    
    possible_quantities = []
    if product:
        products_from_file = parse_product_file('list.txt')
        for name, quantities in products_from_file.items():
            if name == product['name']:
                possible_quantities = quantities
                break
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    if possible_quantities:
        row = []
        for i, qty in enumerate(possible_quantities):
            row.append(InlineKeyboardButton(
                text=qty,
                callback_data=f"product_qty_select_{qty}"
            ))
            if len(row) == 3:
                keyboard.inline_keyboard.append(row)
                row = []
        if row:
            keyboard.inline_keyboard.append(row)
        keyboard.inline_keyboard.append([InlineKeyboardButton(text="✏️ Ввести вручную", callback_data="product_qty_manual")])
    
    keyboard.inline_keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="product_edit_back")])
    
    text = f"""📊 ИЗМЕНЕНИЕ КОЛИЧЕСТВА

Текущее количество: {current_quantity}

Выберите новое количество из списка
или нажмите 'Ввести вручную':"""
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("product_qty_select_"))
async def product_quantity_select(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    new_quantity = callback.data.replace("product_qty_select_", "")
    data = await state.get_data()
    product_id = data.get('editing_product_id')
    
    if db.update_product_quantity(product_id, new_quantity):
        await callback.answer(f"✅ Количество изменено на {new_quantity}", show_alert=True)
    else:
        await callback.answer("❌ Ошибка при изменении количества", show_alert=True)
    
    await state.clear()
    
    product = db.get_product_by_id(product_id)
    if product:
        status = "✅ В наличии" if product['in_stock'] else "❌ Нет в наличии"
        description = product.get('description', '')
        description_text = f"\n📝 Описание: {description}" if description else ""
        text = f"""✏️ РЕДАКТИРОВАНИЕ ТОВАРА

🆔 ID: {product['id']}
📍 Город: {product['city']}
📦 Название: {product['name']}
📊 Количество: {product['quantity']}
💰 Цена: {product['price']}₽{description_text}
📅 Добавлен: {product['created_at'][:10] if product.get('created_at') else 'Неизвестно'}
🔑 Код: <code>/{product['product_code']}</code>
📌 Статус: {status}

Выберите действие:"""
        
        keyboard = get_product_edit_keyboard(product_id, product['in_stock'])
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')

@router.callback_query(F.data == "product_qty_manual")
async def product_quantity_manual(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    await state.set_state(AdminStates.edit_product_quantity)
    await callback.message.edit_text(
        "✏️ Введите новое количество вручную:\n(например: 0.5 gr, 1 kg, 100 мл и т.д.)"
    )
    await callback.answer()

@router.message(AdminStates.edit_product_quantity)
async def product_change_quantity_process(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔️ Доступ запрещен")
        return
    
    new_quantity = message.text.strip()
    if not new_quantity:
        await message.answer("❌ Количество не может быть пустым")
        return
    
    data = await state.get_data()
    product_id = data.get('editing_product_id')
    
    if db.update_product_quantity(product_id, new_quantity):
        await message.answer(f"✅ Количество успешно изменено на '{new_quantity}'")
    else:
        await message.answer("❌ Ошибка при изменении количества")
    
    await state.clear()
    
    product = db.get_product_by_id(product_id)
    if product:
        status = "✅ В наличии" if product['in_stock'] else "❌ Нет в наличии"
        description = product.get('description', '')
        description_text = f"\n📝 Описание: {description}" if description else ""
        text = f"""✏️ РЕДАКТИРОВАНИЕ ТОВАРА

🆔 ID: {product['id']}
📍 Город: {product['city']}
📦 Название: {product['name']}
📊 Количество: {product['quantity']}
💰 Цена: {product['price']}₽{description_text}
📅 Добавлен: {product['created_at'][:10] if product.get('created_at') else 'Неизвестно'}
🔑 Код: <code>/{product['product_code']}</code>
📌 Статус: {status}

Выберите действие:"""
        
        keyboard = get_product_edit_keyboard(product_id, product['in_stock'])
        await message.answer(text, reply_markup=keyboard, parse_mode='HTML')

@router.callback_query(F.data.startswith("product_change_description_"))
async def product_change_description_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    product_id = int(callback.data.replace("product_change_description_", ""))
    await state.update_data(editing_product_id=product_id)
    await state.set_state(AdminStates.edit_product_description)
    
    product = db.get_product_by_id(product_id)
    current_description = product.get('description', 'Не указано')
    
    keyboard = get_description_keyboard()
    
    await callback.message.edit_text(
        f"📝 ИЗМЕНЕНИЕ ОПИСАНИЯ\n\nТекущее описание: {current_description}\n\nВыберите новое описание:",
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data.startswith("desc_"))
async def product_change_description_select(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    new_description = callback.data.replace("desc_", "")
    data = await state.get_data()
    product_id = data.get('editing_product_id')
    
    if not product_id:
        await callback.answer("❌ Ошибка: ID товара не найден", show_alert=True)
        return
    
    if db.update_product_description(product_id, new_description):
        await callback.answer(f"✅ Описание изменено на {new_description}", show_alert=True)
    else:
        await callback.answer("❌ Ошибка при изменении описания", show_alert=True)
        return
    
    await state.clear()
    
    product = db.get_product_by_id(product_id)
    if product:
        status = "✅ В наличии" if product['in_stock'] else "❌ Нет в наличии"
        description = product.get('description', '')
        description_text = f"\n📝 Описание: {description}" if description else ""
        
        text = f"""✏️ РЕДАКТИРОВАНИЕ ТОВАРА

🆔 ID: {product['id']}
📍 Город: {product['city']}
📦 Название: {product['name']}
📊 Количество: {product['quantity']}
💰 Цена: {product['price']}₽{description_text}
📅 Добавлен: {product['created_at'][:10] if product.get('created_at') else 'Неизвестно'}
🔑 Код: <code>/{product['product_code']}</code>
📌 Статус: {status}

Выберите действие:"""
        
        keyboard = get_product_edit_keyboard(product_id, product['in_stock'])
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
    else:
        await callback.message.edit_text("❌ Товар не найден")
    
    await callback.answer()

# ============================================
# ПЕРЕКЛЮЧЕНИЕ СТАТУСА И УДАЛЕНИЕ ТОВАРА
# ============================================

@router.callback_query(F.data.startswith("product_toggle_stock_"))
async def product_toggle_stock(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    product_id = int(callback.data.replace("product_toggle_stock_", ""))
    
    if db.toggle_product_stock(product_id):
        product = db.get_product_by_id(product_id)
        status = "✅ в наличии" if product['in_stock'] else "❌ нет в наличии"
        await callback.answer(f"✅ Статус изменен: {status}", show_alert=True)
    else:
        await callback.answer("❌ Ошибка при изменении статуса", show_alert=True)
    
    product = db.get_product_by_id(product_id)
    if product:
        status = "✅ В наличии" if product['in_stock'] else "❌ Нет в наличии"
        description = product.get('description', '')
        description_text = f"\n📝 Описание: {description}" if description else ""
        text = f"""✏️ РЕДАКТИРОВАНИЕ ТОВАРА

🆔 ID: {product['id']}
📍 Город: {product['city']}
📦 Название: {product['name']}
📊 Количество: {product['quantity']}
💰 Цена: {product['price']}₽{description_text}
📅 Добавлен: {product['created_at'][:10] if product.get('created_at') else 'Неизвестно'}
🔑 Код: <code>/{product['product_code']}</code>
📌 Статус: {status}

Выберите действие:"""
        
        keyboard = get_product_edit_keyboard(product_id, product['in_stock'])
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')

@router.callback_query(F.data.startswith("product_delete_"))
async def product_delete_confirm(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    product_id = int(callback.data.replace("product_delete_", ""))
    product = db.get_product_by_id(product_id)
    
    if not product:
        await callback.answer("❌ Товар не найден", show_alert=True)
        return
    
    keyboard = get_confirm_delete_keyboard(product_id)
    await callback.message.edit_text(
        f"⚠️ ВНИМАНИЕ!\n\nВы уверены, что хотите удалить товар?\n\n"
        f"📍 Город: {product['city']}\n"
        f"📦 Название: {product['name']}\n"
        f"📊 Количество: {product['quantity']}\n"
        f"💰 Цена: {product['price']}₽\n"
        f"🔑 Код: /{product['product_code']}\n\n"
        f"Это действие нельзя отменить!",
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data.startswith("product_confirm_delete_"))
async def product_confirm_delete(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    product_id = int(callback.data.replace("product_confirm_delete_", ""))
    
    if db.delete_product(product_id):
        await callback.answer("✅ Товар успешно удален!", show_alert=True)
        await admin_products_list(callback, FSMContext())
    else:
        await callback.answer("❌ Ошибка при удалении товара", show_alert=True)

@router.callback_query(F.data == "product_edit_back")
async def product_edit_back(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    await state.clear()
    await admin_products_list(callback, state)

@router.callback_query(F.data == "admin_products_back")
async def admin_products_back(callback: CallbackQuery, state: FSMContext):
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

# ============================================
# ДОБАВЛЕНИЕ ТОВАРА
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
    
    await state.update_data(product_price=price)
    await state.set_state(AdminStates.add_product_description)
    
    keyboard = get_description_keyboard()
    await message.answer(
        "🔧 Выберите описание",
        reply_markup=keyboard
    )

@router.callback_query(F.data.startswith("desc_"))
async def select_description(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    description = callback.data.replace("desc_", "")
    await state.update_data(product_description=description)
    
    data = await state.get_data()
    
    required_fields = ['adding_product_city', 'adding_product_name', 'product_quantity', 'product_price']
    for field in required_fields:
        if field not in data:
            await callback.answer(f"❌ Ошибка: не найдено поле {field}", show_alert=True)
            return
    
    product = Product(
        city=data['adding_product_city'],
        name=data['adding_product_name'],
        quantity=data['product_quantity'],
        price=data['product_price'],
        description=description,
        in_stock=True
    )
    
    db.add_product(product)
    
    products = db.get_products_by_city(product.city)
    added_product = None
    for p in products:
        if p.name == product.name and p.quantity == product.quantity and p.price == product.price:
            added_product = p
            break
    
    code = added_product.product_code if added_product else 'неизвестен'
    
    await callback.message.edit_text(
        f"✅ Товар 📍 {product.city} - {product.name} - {product.quantity} - {product.price}₽ добавлен!\n"
        f"Описание: {description}\n"
        f"🔑 Код товара: <code>/{code}</code>",
        parse_mode='HTML'
    )
    
    if added_product:
        await notify_users_about_new_product(callback.bot, added_product)
    
    await state.clear()
    
    cities = db.get_cities()
    keyboard = get_admin_city_products_keyboard(cities, 0)
    await callback.message.answer(
        "💦 Товары\n📍 Выберите город для товара",
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data == "back_to_quantity")
async def back_to_quantity(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    data = await state.get_data()
    product_name = data.get('adding_product_name', '')
    
    if not product_name:
        await callback.answer("❌ Ошибка", show_alert=True)
        return
    
    quantities = get_product_quantities(product_name)
    keyboard = get_product_quantity_keyboard(quantities, product_name)
    await callback.message.edit_text(
        f"💦 Выберите количество для {product_name}",
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data == "back_to_city_products")
async def back_to_city_products(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    data = await state.get_data()
    city = data.get('admin_city', '')
    
    products_from_file = parse_product_file('list.txt')
    product_names = list(products_from_file.keys())
    
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

@router.callback_query(F.data == "back_to_admin_products")
async def back_to_admin_products(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    cities = db.get_cities()
    keyboard = get_admin_city_products_keyboard(cities, 0)
    await callback.message.edit_text(
        "💦 Товары\n📍 Выберите город для товара",
        reply_markup=keyboard
    )
    await callback.answer()

# ============================================
# СТАТИСТИКА ТОВАРОВ
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