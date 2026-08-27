# keyboards.py - Клавиатуры

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Optional, Dict
import math
from datetime import datetime

def get_main_menu(is_admin: bool = False) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="💦 Товары", callback_data="show_products")]
    ]
    if is_admin:
        buttons.append([InlineKeyboardButton(text="⚙️ Админка", callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_admin_menu() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="📍 Города", callback_data="admin_cities"),
            InlineKeyboardButton(text="💦 Товары", callback_data="admin_products_menu")
        ],
        [
            InlineKeyboardButton(text="💳 Оплата", callback_data="admin_payment"),
            InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users")
        ],
        [
            InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"),
            InlineKeyboardButton(text="🤖 Авто-продажи", callback_data="auto_sell")
        ],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_cities_keyboard(cities: List[str], page: int = 0, is_admin: bool = False) -> InlineKeyboardMarkup:
    per_page = 8
    total_pages = math.ceil(len(cities) / per_page) if cities else 1
    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_cities = cities[start_idx:end_idx]
    
    keyboard = []
    
    if is_admin:
        for city in page_cities:
            keyboard.append([
                InlineKeyboardButton(text=f"📍 {city}", callback_data=f"admin_city_{city}"),
                InlineKeyboardButton(text="❌", callback_data=f"delete_city_{city}")
            ])
        keyboard.append([InlineKeyboardButton(text="➕ Добавить город", callback_data="add_city")])
    else:
        for city in page_cities:
            keyboard.append([InlineKeyboardButton(text=f"📍 {city}", callback_data=f"select_city_{city}")])
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"city_page_{page-1}"))
    nav_buttons.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="page_info"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"city_page_{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main" if not is_admin else "back_to_admin")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_products_keyboard(products: List[dict]) -> InlineKeyboardMarkup:
    keyboard = []
    for product in products:
        status = "✅ В наличии"
        button_text = f"{product['name']} | {product['quantity']} | {product['price']}₽ | {status}"
        keyboard.append([InlineKeyboardButton(
            text=button_text,
            callback_data=f"buy_product_{product['id']}"
        )])
    
    keyboard.append([InlineKeyboardButton(text="❌ Закрыть", callback_data="close_products")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_admin_city_products_keyboard(cities: List[str], page: int = 0) -> InlineKeyboardMarkup:
    per_page = 8
    total_pages = math.ceil(len(cities) / per_page) if cities else 1
    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_cities = cities[start_idx:end_idx]
    
    keyboard = []
    for city in page_cities:
        keyboard.append([InlineKeyboardButton(text=f"📍 {city}", callback_data=f"admin_city_products_{city}")])
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"admin_city_page_{page-1}"))
    nav_buttons.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="page_info"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"admin_city_page_{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_admin")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_product_quantity_keyboard(quantities: List[str], product_name: str) -> InlineKeyboardMarkup:
    keyboard = []
    row = []
    for i, qty in enumerate(quantities):
        row.append(InlineKeyboardButton(
            text=qty,
            callback_data=f"qty_{product_name}_{qty}"
        ))
        if len(row) == 4:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_city_products")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_payment_keyboard(card_number: str) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="✅ Я оплатил", callback_data="payment_confirmed")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="close_payment")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_admin_payment_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="✏️ Изменить карту", callback_data="change_card")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_admin")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_users_menu() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="👥 Все пользователи", callback_data="users_list")],
        [InlineKeyboardButton(text="🔒 Заблокированные", callback_data="users_blocked")],
        [InlineKeyboardButton(text="📊 Активные пользователи", callback_data="users_active")],
        [InlineKeyboardButton(text="📈 Статистика пользователей", callback_data="users_stats")],
        [InlineKeyboardButton(text="📬 Рассылка", callback_data="users_mailing")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_admin")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_users_list_keyboard(users: List[Dict], page: int = 0) -> InlineKeyboardMarkup:
    per_page = 5
    total_pages = math.ceil(len(users) / per_page) if users else 1
    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_users = users[start_idx:end_idx]
    
    keyboard = []
    for user in page_users:
        username = user.get('username', 'Нет username')
        first_name = user.get('first_name', 'Без имени')[:15]
        orders = user.get('orders_count', 0)
        
        if user.get('is_blocked', False):
            status = "🔒"
        else:
            status = "🟢"
        
        keyboard.append([
            InlineKeyboardButton(
                text=f"{status} {first_name} (@{username}) - {orders} заказов",
                callback_data=f"user_info_{user['user_id']}"
            )
        ])
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"users_page_{page-1}"))
    nav_buttons.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="page_info"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"users_page_{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    keyboard.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data="users_back")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_blocked_users_keyboard(users: List[Dict], page: int = 0) -> InlineKeyboardMarkup:
    per_page = 5
    total_pages = math.ceil(len(users) / per_page) if users else 1
    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_users = users[start_idx:end_idx]
    
    keyboard = []
    for user in page_users:
        username = user.get('username', 'Нет username')
        first_name = user.get('first_name', 'Без имени')[:15]
        blocked_at = user.get('blocked_at', '')[:10]
        
        keyboard.append([
            InlineKeyboardButton(
                text=f"🔒 {first_name} (@{username}) - {blocked_at}",
                callback_data=f"user_info_{user['user_id']}"
            )
        ])
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"blocked_page_{page-1}"))
    nav_buttons.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="page_info"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"blocked_page_{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="users_back")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_user_info_keyboard(user_id: int, is_blocked: bool = False) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="📊 История заказов", callback_data=f"user_orders_{user_id}")],
        [InlineKeyboardButton(text="📬 Отправить сообщение", callback_data=f"user_message_{user_id}")],
    ]
    
    if is_blocked:
        buttons.append([InlineKeyboardButton(text="🔓 Разблокировать", callback_data=f"user_unblock_{user_id}")])
    else:
        buttons.append([InlineKeyboardButton(text="🔒 Заблокировать", callback_data=f"user_block_{user_id}")])
    
    buttons.append([InlineKeyboardButton(text="❌ Удалить пользователя", callback_data=f"user_delete_{user_id}")])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="users_list")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_user_orders_keyboard(orders: List[Dict], page: int = 0) -> InlineKeyboardMarkup:
    per_page = 3
    total_pages = math.ceil(len(orders) / per_page) if orders else 1
    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_orders = orders[start_idx:end_idx]
    
    keyboard = []
    for order in page_orders:
        created = order.get('created_at', '')[:10]
        keyboard.append([
            InlineKeyboardButton(
                text=f"🛒 {order['product_name']} | {order['price']}₽ | {created}",
                callback_data=f"order_detail_{order.get('id', 0)}"
            )
        ])
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"user_orders_page_{page-1}"))
    nav_buttons.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="page_info"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"user_orders_page_{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="users_list")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_mailing_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="👥 Всем пользователям", callback_data="mailing_all")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="users_back")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_admin_products_management_menu() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="📋 Все товары", callback_data="admin_products_list")],
        [InlineKeyboardButton(text="➕ Добавить товар", callback_data="admin_products_add")],
        [InlineKeyboardButton(text="📊 Статистика товаров", callback_data="admin_products_stats")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_admin")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_products_list_keyboard(products: List[Dict], page: int = 0) -> InlineKeyboardMarkup:
    per_page = 6
    total_pages = math.ceil(len(products) / per_page) if products else 1
    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_products = products[start_idx:end_idx]
    
    keyboard = []
    for product in page_products:
        status = "✅" if product['in_stock'] else "❌"
        keyboard.append([
            InlineKeyboardButton(
                text=f"{status} {product['name']} | {product['quantity']} | {product['price']}₽",
                callback_data=f"admin_product_edit_{product['id']}"
            )
        ])
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"admin_prod_page_{page-1}"))
    nav_buttons.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="page_info"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"admin_prod_page_{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_products_back")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_product_edit_keyboard(product_id: int, in_stock: bool) -> InlineKeyboardMarkup:
    status_action = "❌ Снять с продажи" if in_stock else "✅ Вернуть в продажу"
    
    buttons = [
        [InlineKeyboardButton(text="✏️ Изменить цену", callback_data=f"product_change_price_{product_id}")],
        [InlineKeyboardButton(text="📝 Изменить название", callback_data=f"product_change_name_{product_id}")],
        [InlineKeyboardButton(text="📊 Изменить количество", callback_data=f"product_change_quantity_{product_id}")],
        [InlineKeyboardButton(text=f"{status_action}", callback_data=f"product_toggle_stock_{product_id}")],
        [InlineKeyboardButton(text="❌ Удалить товар", callback_data=f"product_delete_{product_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_products_list")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_admin_products_stats_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="📊 По городам", callback_data="admin_products_stats_cities")],
        [InlineKeyboardButton(text="📈 Продажи", callback_data="admin_products_stats_sales")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_products_back")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_confirm_delete_keyboard(product_id: int) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"product_confirm_delete_{product_id}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data=f"admin_product_edit_{product_id}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_auto_sell_menu() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="🆕 Создать кампанию", callback_data="auto_create")],
        [InlineKeyboardButton(text="📋 Активные кампании", callback_data="auto_campaigns")],
        [InlineKeyboardButton(text="📊 Статистика продаж", callback_data="auto_stats")],
        [InlineKeyboardButton(text="⏹️ Остановить все", callback_data="auto_stop_all")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_admin")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_campaign_cities_keyboard(cities: List[str], selected: List[str] = None) -> InlineKeyboardMarkup:
    if selected is None:
        selected = []
    
    keyboard = []
    for city in cities:
        status = "✅" if city in selected else "⬜"
        keyboard.append([
            InlineKeyboardButton(
                text=f"{status} {city}",
                callback_data=f"camp_city_{city}"
            )
        ])
    
    keyboard.append([
        InlineKeyboardButton(text="✅ Готово", callback_data="camp_cities_done"),
        InlineKeyboardButton(text="❌ Очистить", callback_data="camp_cities_clear")
    ])
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="auto_sell_back")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_campaign_products_keyboard(products: List[str], selected: List[str] = None) -> InlineKeyboardMarkup:
    if selected is None:
        selected = []
    
    keyboard = []
    row = []
    for i, product in enumerate(products):
        status = "✅" if product in selected else "⬜"
        row.append(InlineKeyboardButton(
            text=f"{status} {product[:15]}",
            callback_data=f"camp_prod_{product}"
        ))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    
    keyboard.append([
        InlineKeyboardButton(text="✅ Готово", callback_data="camp_products_done"),
        InlineKeyboardButton(text="❌ Очистить", callback_data="camp_products_clear")
    ])
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="camp_cities_done")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_campaign_quantities_keyboard(quantities: List[str], selected: List[str] = None) -> InlineKeyboardMarkup:
    if selected is None:
        selected = []
    
    keyboard = []
    row = []
    for i, qty in enumerate(quantities):
        status = "✅" if qty in selected else "⬜"
        row.append(InlineKeyboardButton(
            text=f"{status} {qty}",
            callback_data=f"camp_qty_{qty}"
        ))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    
    keyboard.append([
        InlineKeyboardButton(text="✅ Готово", callback_data="camp_qty_done"),
        InlineKeyboardButton(text="❌ Очистить", callback_data="camp_qty_clear")
    ])
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="camp_products_done")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_campaign_days_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    for days in [1, 3, 5, 7, 10, 14, 30]:
        buttons.append([InlineKeyboardButton(
            text=f"📅 {days} дней",
            callback_data=f"camp_days_{days}"
        )])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="camp_qty_done")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_campaign_price_keyboard(products: List[str]) -> InlineKeyboardMarkup:
    keyboard = []
    for product in products:
        keyboard.append([
            InlineKeyboardButton(
                text=f"💰 {product} - введите цену",
                callback_data=f"camp_price_{product}"
            )
        ])
    keyboard.append([InlineKeyboardButton(text="✅ Все цены введены", callback_data="camp_price_done")])
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="camp_days_select")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_campaign_list_keyboard(campaigns: List[Dict]) -> InlineKeyboardMarkup:
    keyboard = []
    for camp in campaigns:
        status = "🟢" if camp['is_active'] else "🔴"
        days_left = camp['days'] - (datetime.now() - datetime.fromisoformat(camp['started_at'])).days
        keyboard.append([
            InlineKeyboardButton(
                text=f"{status} {camp['name']} (осталось {max(0, days_left)}д)",
                callback_data=f"camp_info_{camp['id']}"
            )
        ])
    
    if not keyboard:
        keyboard.append([InlineKeyboardButton(text="❌ Нет активных кампаний", callback_data="noop")])
    
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="auto_sell_back")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_campaign_info_keyboard(campaign_id: int) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="⏹️ Остановить кампанию", callback_data=f"camp_stop_{campaign_id}")],
        [InlineKeyboardButton(text="📊 Детальная статистика", callback_data=f"camp_stats_{campaign_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="auto_campaigns")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_auto_stats_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="📅 За сегодня", callback_data="stats_today")],
        [InlineKeyboardButton(text="📊 За неделю", callback_data="stats_week")],
        [InlineKeyboardButton(text="📈 За месяц", callback_data="stats_month")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="auto_sell_back")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)