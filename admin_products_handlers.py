# admin_products_handlers.py - Все обработчики управления товарами

from aiogram import Router, F, types
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import db
from models import Product
from keyboards import *
from utils import get_product_quantities, parse_product_file, format_card_number, is_admin
from config import ADMIN_IDS
from handlers import notify_users_about_new_product

router = Router()

# ============================================
# СОСТОЯНИЯ
# ============================================

class AdminProductStates(StatesGroup):
    add_product_price = State()
    add_product_description = State()
    edit_product_price = State()
    edit_product_name = State()
    edit_product_quantity = State()
    edit_product_description = State()

# ============================================
# МЕНЮ УПРАВЛЕНИЯ ТОВАРАМИ
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
    await state.set_state(AdminProductStates.add_product_price)
    
    await callback.message.edit_text(
        f"Введите цену товара {product_name} ({quantity})"
    )
    await callback.answer()

@router.message(AdminProductStates.add_product_price)
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
    await state.set_state(AdminProductStates.add_product_description)
    
    keyboard = get_description_keyboard()
    await message.answer(
        "🔧 Выберите описание",
        reply_markup=keyboard
    )

@router.callback_query(F.data.startswith("desc_") & ~F.data.startswith("desc_edit_"))
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
# СПИСОК ВСЕХ ТОВАРОВ
# ============================================

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

# ============================================
# РЕДАКТИРОВАНИЕ ТОВАРА (ГЛАВНЫЙ ОБРАБОТЧИК)
# ============================================

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
# ИЗМЕНЕНИЕ ЦЕНЫ
# ============================================

@router.callback_query(F.data.startswith("product_change_price_"))
async def product_change_price_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    product_id = int(callback.data.replace("product_change_price_", ""))
    await state.update_data(editing_product_id=product_id)
    await state.set_state(AdminProductStates.edit_product_price)
    
    product = db.get_product_by_id(product_id)
    current_price = product['price'] if product else 0
    
    await callback.message.edit_text(
        f"💰 ИЗМЕНЕНИЕ ЦЕНЫ\n\nТекущая цена: {current_price}₽\n\nВведите новую цену (только цифры):"
    )
    await callback.answer()

@router.message(AdminProductStates.edit_product_price)
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

# ============================================
# ИЗМЕНЕНИЕ НАЗВАНИЯ
# ============================================

@router.callback_query(F.data.startswith("product_change_name_"))
async def product_change_name_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    product_id = int(callback.data.replace("product_change_name_", ""))
    await state.update_data(editing_product_id=product_id)
    await state.set_state(AdminProductStates.edit_product_name)
    
    product = db.get_product_by_id(product_id)
    current_name = product['name'] if product else 'Неизвестно'
    
    await callback.message.edit_text(
        f"📝 ИЗМЕНЕНИЕ НАЗВАНИЯ\n\nТекущее название: {current_name}\n\nВведите новое название товара:"
    )
    await callback.answer()

@router.message(AdminProductStates.edit_product_name)
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

# ============================================
# ИЗМЕНЕНИЕ КОЛИЧЕСТВА
# ============================================

@router.callback_query(F.data.startswith("product_change_quantity_"))
async def product_change_quantity_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    product_id = int(callback.data.replace("product_change_quantity_", ""))
    await state.update_data(editing_product_id=product_id)
    await state.set_state(AdminProductStates.edit_product_quantity)
    
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
    
    await state.set_state(AdminProductStates.edit_product_quantity)
    await callback.message.edit_text(
        "✏️ Введите новое количество вручную:\n(например: 0.5 gr, 1 kg, 100 мл и т.д.)"
    )
    await callback.answer()

@router.message(AdminProductStates.edit_product_quantity)
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

# ============================================
# ИЗМЕНЕНИЕ ОПИСАНИЯ (ИСПРАВЛЕННАЯ ВЕРСИЯ)
# ============================================

@router.callback_query(F.data.startswith("product_change_description_"))
async def product_change_description_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    product_id = int(callback.data.replace("product_change_description_", ""))
    await state.update_data(editing_product_id=product_id)
    await state.set_state(AdminProductStates.edit_product_description)
    
    product = db.get_product_by_id(product_id)
    if not product:
        await callback.answer("❌ Товар не найден", show_alert=True)
        return
    
    current_description = product.get('description', 'Не указано')
    
    keyboard = get_description_edit_keyboard(product_id)
    
    await callback.message.edit_text(
        f"📝 ИЗМЕНЕНИЕ ОПИСАНИЯ\n\nТекущее описание: {current_description}\n\nВыберите новое описание:",
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data.startswith("desc_edit_"))
async def product_change_description_select(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    parts = callback.data.split("_")
    if len(parts) < 4:
        await callback.answer("❌ Ошибка: неверный формат", show_alert=True)
        return
    
    description = parts[2]
    product_id = int(parts[3])
    
    if db.update_product_description(product_id, description):
        await callback.answer(f"✅ Описание изменено на {description}", show_alert=True)
    else:
        await callback.answer("❌ Ошибка при изменении описания", show_alert=True)
        return
    
    await state.clear()
    
    product = db.get_product_by_id(product_id)
    if product:
        status = "✅ В наличии" if product['in_stock'] else "❌ Нет в наличии"
        desc = product.get('description', '')
        desc_text = f"\n📝 Описание: {desc}" if desc else ""
        
        text = f"""✏️ РЕДАКТИРОВАНИЕ ТОВАРА

🆔 ID: {product['id']}
📍 Город: {product['city']}
📦 Название: {product['name']}
📊 Количество: {product['quantity']}
💰 Цена: {product['price']}₽{desc_text}
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