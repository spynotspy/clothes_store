import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.utils import executor
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
import asyncpg

API_TOKEN = '7570710742:AAFrDmDJCWwovuc4ke9vUpb73z7nPl75PjM'

# Настройка бота и хранилища
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)


# Определяем состояния FSM
class Form(StatesGroup):
    waiting_for_registration = State()
    waiting_for_order_quantity = State()
    waiting_for_product_name = State()
    waiting_for_product_name_add = State()
    waiting_for_product_description = State()
    waiting_for_product_price = State()
    waiting_for_product_stock = State()
    waiting_for_category_name = State()
    waiting_for_order_confirmation = State()
    waiting_for_category_deletion = State()
    waiting_for_category_description = State()


async def connect_db():
    return await asyncpg.connect(user='admin', password='1', database='store_db', host='192.168.100.15')


async def create_db():
    conn = await connect_db()
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR UNIQUE,
            first_name VARCHAR,
            last_name VARCHAR,
            telegram_id BIGINT UNIQUE,
            role VARCHAR
        );
        CREATE TABLE IF NOT EXISTS categories (
            id SERIAL PRIMARY KEY,
            name VARCHAR UNIQUE,
            description TEXT
        );
        CREATE TABLE IF NOT EXISTS products (
            id SERIAL PRIMARY KEY,
            name VARCHAR,
            description TEXT,
            price DECIMAL,
            category_id INT REFERENCES categories(id),
            stock INT
        );
        CREATE TABLE IF NOT EXISTS orders (
            id SERIAL PRIMARY KEY,
            user_id INT REFERENCES users(id),
            order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status VARCHAR
        );
        CREATE TABLE IF NOT EXISTS order_items (
            id SERIAL PRIMARY KEY,
            order_id INT REFERENCES orders(id),
            product_id INT REFERENCES products(id),
            quantity INT
        );
    ''')
    await conn.close()


async def show_main_menu(message: types.Message):
    user = await get_user(message.from_user.id)

    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)

    if user['role'] == 'admin':
        # Первая строка с кнопкой "Удалить категорию"
        keyboard.add(types.KeyboardButton("Удалить категорию"))

        # Следующие строки с другими кнопками
        keyboard.add(
            types.KeyboardButton("Добавить категорию"),
            types.KeyboardButton("Добавить продукт")
        )
        keyboard.add(
            types.KeyboardButton("Просмотреть заказы"),
            types.KeyboardButton("Просмотреть пользователей")
        )
        keyboard.add(
            types.KeyboardButton("Просмотреть ассортимент"),
            types.KeyboardButton("Просмотреть категории")
        )

    else:
        keyboard.add(
            types.KeyboardButton("Оформить заказ"),
            types.KeyboardButton("Просмотреть свои заказы")
        )
        keyboard.add(
            types.KeyboardButton("Просмотреть ассортимент"),
            types.KeyboardButton("Просмотреть категории")
        )

    keyboard.add(types.KeyboardButton("Назад"))  # Кнопка "Назад"

    await message.reply("Выберите опцию:", reply_markup=keyboard)


@dp.message_handler(lambda message: message.text == "Просмотреть категории")
async def view_categories(message: types.Message):
    conn = await connect_db()

    # Извлечение всех категорий из базы данных
    categories = await conn.fetch('SELECT * FROM categories')
    await conn.close()

    if not categories:
        await message.reply("Нет существующих категорий.")
        return

    categories_message = "Список категорий:\n\n"
    for category in categories:
        categories_message += f"ID: {category['id']}, Название: {category['name']}, Описание: {category['description']}\n"

    await message.reply(categories_message)


@dp.message_handler(lambda message: message.text == "Просмотреть пользователей")
async def view_users(message: types.Message):
    conn = await connect_db()
    users = await conn.fetch('SELECT * FROM users')
    await conn.close()

    if not users:
        await message.reply("Нет зарегистрированных пользователей.")
        return

    users_message = "Список пользователей:\n\n"
    for user in users:
        users_message += f"ID: {user['id']}, " \
                         f"Имя: {user['first_name']} {user['last_name']}, " \
                         f"Юзернейм: {user['username']}, " \
                         f"Роль: {user['role']}, " \
                         f"Телеграмм ID: {user['telegram_id']}\n"

    await message.reply(users_message)


@dp.message_handler(lambda message: message.text == "Просмотреть заказы", state='*')
async def view_all_orders(message: types.Message):
    conn = await connect_db()
    orders = await conn.fetch('SELECT * FROM orders')

    if not orders:
        await message.reply("Нет оформленных заказов.")
        return

    orders_message = "Все заказы:\n\n"
    for order in orders:
        user = await conn.fetchrow('SELECT first_name, last_name FROM users WHERE id = $1', order['user_id'])
        order_items = await conn.fetch('SELECT oi.quantity, p.name FROM order_items oi '
                                       'JOIN products p ON oi.product_id = p.id '
                                       'WHERE oi.order_id = $1', order['id'])

        orders_message += f"Заказ ID: {order['id']}\n" \
                          f"Пользователь: {user['first_name']} {user['last_name']}\n" \
                          f"Дата оформления: {order['order_date']}\n" \
                          f"Статус: {order['status']}\n" \
                          f"Содержимое заказа:\n"

        if order_items:
            for item in order_items:
                orders_message += f" - {item['quantity']} шт. товара '{item['name']}'\n"
        else:
            orders_message += " - Заказ пуст.\n"

        orders_message += "\n"

    await conn.close()
    await message.reply(orders_message)


@dp.message_handler(lambda message: message.text == "Просмотреть ассортимент")
async def view_assortment(message: types.Message):
    conn = await connect_db()

    # Извлечение всех продуктов из базы данных
    products = await conn.fetch('SELECT * FROM products')
    await conn.close()

    if not products:
        await message.reply("Ассортимент пуст.")
        return

    # Формируем сообщение с ассортиментом
    assortment_message = "Ассортимент магазина:\n\n"
    for product in products:
        assortment_message += f"Название: {product['name']}\n" \
                              f"Описание: {product['description']}\n" \
                              f"Цена: {product['price']}₽\n" \
                              f"На складе: {product['stock']} шт.\n\n"

    await message.reply(assortment_message)


async def get_user(telegram_id):
    conn = await connect_db()
    user = await conn.fetchrow('SELECT * FROM users WHERE telegram_id=$1', telegram_id)
    await conn.close()
    return user


@dp.message_handler(lambda message: message.text == "Просмотреть свои заказы")
async def view_orders(message: types.Message):
    conn = await connect_db()
    user = await get_user(message.from_user.id)

    # Извлечение заказов пользователя из базы данных
    orders = await conn.fetch('SELECT * FROM orders WHERE user_id = $1', user['id'])

    if not orders:
        await message.reply("У вас нет оформленных заказов.")
        return

    orders_message = "Ваши заказы:\n\n"
    for order in orders:
        order_items = await conn.fetch('SELECT oi.quantity, p.name FROM order_items oi '
                                       'JOIN products p ON oi.product_id = p.id '
                                       'WHERE oi.order_id = $1', order['id'])

        orders_message += f"Заказ ID: {order['id']}\n" \
                          f"Дата оформления: {order['order_date']}\n" \
                          f"Статус: {order['status']}\n" \
                          f"Содержимое заказа:\n"

        if order_items:
            for item in order_items:
                orders_message += f" - {item['quantity']} шт. товара '{item['name']}'\n"
        else:
            orders_message += " - Заказ пуст.\n"

        orders_message += "\n"

    await conn.close()
    await message.reply(orders_message)


@dp.message_handler(lambda message: message.text == "Оформить заказ")
async def place_order(message: types.Message):
    await message.reply("Введите количество товара, который вы хотите заказать:")
    await Form.waiting_for_order_quantity.set()


@dp.message_handler(state=Form.waiting_for_order_quantity)
async def process_order_quantity(message: types.Message, state: FSMContext):
    quantity = message.text
    await state.update_data(quantity=quantity)  # Сохранение quantity в состоянии

    user = await get_user(message.from_user.id)
    await message.reply("Введите название продукта, который вы хотите заказать:")
    await Form.waiting_for_product_name.set()


@dp.message_handler(state=Form.waiting_for_product_name)
async def process_product_name(message: types.Message, state: FSMContext):
    product_name = message.text
    data = await state.get_data()

    # Проверка наличия количества товара перед использованием
    if 'quantity' in data:
        quantity_str = data['quantity']  # Получаем quantity как строку
        try:
            quantity = int(quantity_str)  # Преобразуем в целое число
        except ValueError:
            await message.reply("Ошибка: количество товара должно быть целым числом.")
            await state.finish()
            return
    else:
        await message.reply("Пожалуйста, сначала введите количество товара.")
        await state.finish()
        return

    conn = await connect_db()
    product = await conn.fetchrow('SELECT * FROM products WHERE name=$1', product_name)

    # Проверка наличия товара и достаточности на складе
    if product:
        if product['stock'] >= int(quantity):
            user = await get_user(message.from_user.id)
            order = await conn.fetchrow(
                'INSERT INTO orders (user_id, status) VALUES ($1, $2) RETURNING id',
                user['id'], 'Оформлен'
            )
            await conn.execute('INSERT INTO order_items (order_id, product_id, quantity) VALUES ($1, $2, $3)',
                               order['id'], product['id'], quantity)

            # Обновить количество товара на складе
            new_stock = product['stock'] - int(quantity)
            await conn.execute('UPDATE products SET stock = $1 WHERE id = $2', new_stock, product['id'])

            await message.reply(f"Заказ на {quantity} шт. товара '{product_name}' успешно оформлен!")
        else:
            await message.reply("Недостаточно товара на складе.")
    else:
        await message.reply("Товар не найден.")

    await conn.close()
    await state.finish()
    await show_main_menu(message)


@dp.message_handler(lambda message: message.text == "Добавить категорию")
async def add_category(message: types.Message):
    await message.reply("Введите название новой категории:")
    await Form.waiting_for_category_name.set()


@dp.message_handler(state=Form.waiting_for_category_name)
async def process_new_category_name(message: types.Message, state: FSMContext):
    new_category_name = message.text
    await state.update_data(new_category_name=new_category_name)

    await message.reply("Введите описание категории:")
    await Form.waiting_for_category_description.set()


@dp.message_handler(state=Form.waiting_for_category_description)
async def process_new_category_description(message: types.Message, state: FSMContext):
    category_description = message.text
    data = await state.get_data()
    new_category_name = data['new_category_name']

    conn = await connect_db()
    try:
        await conn.execute('INSERT INTO categories (name, description) VALUES ($1, $2)',
                           new_category_name, category_description)
        await message.reply(f"Категория '{new_category_name}' успешно добавлена с описанием.")
    except asyncpg.UniqueViolationError:
        await message.reply(f"Категория '{new_category_name}' уже существует.")
    finally:
        await conn.close()

    await state.finish()
    await show_main_menu(message)


@dp.message_handler(lambda message: message.text == "Удалить категорию")
async def delete_category(message: types.Message):
    await message.reply("Введите название категории, которую хотите удалить:")
    await Form.waiting_for_category_deletion.set()


@dp.message_handler(state=Form.waiting_for_category_deletion)
async def process_category_deletion(message: types.Message, state: FSMContext):
    category_name = message.text

    conn = await connect_db()
    # Проверяем, существует ли категория
    existing_category = await conn.fetchrow('SELECT * FROM categories WHERE name = $1', category_name)

    if existing_category:
        await conn.execute('DELETE FROM categories WHERE name = $1', category_name)
        await message.reply(f"Категория '{category_name}' успешно удалена.")
    else:
        await message.reply(f"Категория '{category_name}' не найдена.")

    await conn.close()
    await state.finish()
    await show_main_menu(message)


@dp.message_handler(lambda message: message.text == "Добавить продукт", state='*')
async def add_product(message: types.Message):
    await message.reply("Введите название продукта:")
    await Form.waiting_for_product_name_add.set()


@dp.message_handler(state=Form.waiting_for_product_name_add)
async def process_add_product_name(message: types.Message, state: FSMContext):
    product_name = message.text
    await state.update_data(product_name=product_name)  # Сохраняем название продукта в состоянии

    await message.reply("Введите описание продукта:")
    await Form.waiting_for_product_description.set()


@dp.message_handler(state=Form.waiting_for_product_description)
async def process_add_product_description(message: types.Message, state: FSMContext):
    product_description = message.text
    data = await state.get_data()  # Получаем сохраненные данные
    product_name = data['product_name']

    await state.update_data(product_description=product_description)  # Сохраняем описание

    await message.reply("Введите цену продукта:")
    await Form.waiting_for_product_price.set()


@dp.message_handler(state=Form.waiting_for_product_price)
async def process_add_product_price(message: types.Message, state: FSMContext):
    product_price = message.text
    data = await state.get_data()
    product_name = data['product_name']
    product_description = data['product_description']

    try:
        price = float(product_price)  # Преобразуем цену в число с плавающей точкой
        await state.update_data(product_price=price)  # Сохраняем цену

        await message.reply("Введите количество на складе:")
        await Form.waiting_for_product_stock.set()
    except ValueError:
        await message.reply("Пожалуйста, введите корректную цену.")


@dp.message_handler(state=Form.waiting_for_product_stock)
async def process_add_product_stock(message: types.Message, state: FSMContext):
    stock_quantity = message.text
    data = await state.get_data()

    product_name = data['product_name']
    product_description = data['product_description']
    product_price = data['product_price']

    try:
        stock = int(stock_quantity)  # Преобразуем количество в целое число

        conn = await connect_db()
        await conn.execute('INSERT INTO products (name, description, price, stock) VALUES ($1, $2, $3, $4)',
                           product_name, product_description, product_price, stock)
        await conn.close()

        await message.reply(f"Продукт '{product_name}' успешно добавлен!")
    except ValueError:
        await message.reply("Пожалуйста, введите корректное количество на складе.")
    except Exception as e:
        await message.reply(f"Произошла ошибка: {e}")

    await state.finish()  # Завершаем состояние
    await show_main_menu(message)


@dp.message_handler(lambda message: message.text == "Назад", state='*')
async def go_back(message: types.Message, state: FSMContext):
    await state.finish()
    await show_main_menu(message)


async def on_startup(dp):
    await create_db()


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
