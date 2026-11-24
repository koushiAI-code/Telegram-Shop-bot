from pathlib import Path
import sqlite3


DB_PATH = Path(__file__).resolve().parent / "shop.db"


def connect_db():
    connection = sqlite3.connect(
        DB_PATH,
        timeout=10
    )

    connection.execute("PRAGMA foreign_keys = ON")

    return connection

def create_table():
    connection = connect_db()

    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price INTEGER NOT NULL,
            stock INTEGER NOT NULL,
            model TEXT
        )
    """)

    connection.commit()
    connection.close()
    create_orders_table()  # Create the orders table when creating the products table

def add_image_column():
    connection = connect_db()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            ALTER TABLE products
            ADD COLUMN image_file_id TEXT
        """)
        connection.commit()

    except sqlite3.OperationalError:
        pass

    connection.close()

def add_description_column():
    connection = connect_db()

    try:
        cursor = connection.cursor()

        cursor.execute("PRAGMA table_info(products)")
        columns = [column[1] for column in cursor.fetchall()]

        if "description" not in columns:
            cursor.execute("""
                ALTER TABLE products
                ADD COLUMN description TEXT
            """)

            connection.commit()

    finally:
        connection.close()

def create_orders_table():
    connection = connect_db()
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            price INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            total_price INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        PRAGMA table_info(orders)
    """)

    columns = [column[1] for column in cursor.fetchall()]

    if "status" not in columns:
        cursor.execute("""
            ALTER TABLE orders
            ADD COLUMN status TEXT NOT NULL DEFAULT 'active'
        """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS processed_confirmations (
            confirmation_id TEXT PRIMARY KEY
        )
    """)

    connection.commit()
    connection.close()



def add_product(
    name,
    model,
    price,
    stock,
    image_file_id=None,
    description=None
):
    connection = connect_db()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO products (
                name,
                model,
                price,
                stock,
                image_file_id,
                description
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                model,
                price,
                stock,
                image_file_id,
                description
            )
        )

        connection.commit()

    finally:
        connection.close()

def get_products():
    connection = connect_db()
    cursor = connection.cursor()

    cursor.execute("SELECT * FROM products")

    products = cursor.fetchall()

    connection.close()

    return products


def get_available_products():
    connection = connect_db()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT * FROM products
        WHERE stock > 0
    """)

    products = cursor.fetchall()

    connection.close()

    return products


def update_stock(product_id, new_stock):

    if type(product_id) is not int or product_id <= 0:
        return "invalid_product_id"

    if type(new_stock) is not int or new_stock < 0:
        return "invalid_stock"

    connection = connect_db()

    try:
        cursor = connection.cursor()

        cursor.execute("BEGIN IMMEDIATE")

        cursor.execute("""
            UPDATE products
            SET stock = ?
            WHERE id = ?
        """, (new_stock, product_id))

        updated = cursor.rowcount

        connection.commit()

        return updated

    except sqlite3.Error:
        connection.rollback()
        raise

    finally:
        connection.close()


def get_product_by_id(product_id):
    connection = connect_db()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT * FROM products
        WHERE id = ?
    """, (product_id,))

    product = cursor.fetchone()

    connection.close()

    return product

def delete_product(product_id):
    if type(product_id) is not int or product_id <= 0:
        return "invalid_product_id"

    connection = connect_db()

    try:
        cursor = connection.cursor()

        cursor.execute("BEGIN IMMEDIATE")

        cursor.execute("""
            SELECT id
            FROM orders
            WHERE product_id = ?
            LIMIT 1
        """, (product_id,))

        order = cursor.fetchone()

        if order:
            connection.rollback()
            return "has_orders"

        cursor.execute("""
            DELETE FROM products
            WHERE id = ?
        """, (product_id,))

        deleted = cursor.rowcount

        connection.commit()

        return deleted

    except sqlite3.Error:
        connection.rollback()
        raise

    finally:
        connection.close()

def update_product_price(product_id, new_price):
    if type(product_id) is not int or product_id <= 0:
        return "invalid_product_id"

    if type(new_price) is not int or new_price < 0:
        return "invalid_price"

    connection = connect_db()

    try:
        cursor = connection.cursor()

        cursor.execute("BEGIN IMMEDIATE")

        cursor.execute("""
            UPDATE products
            SET price = ?
            WHERE id = ?
        """, (new_price, product_id))

        updated = cursor.rowcount

        connection.commit()

        return updated

    except sqlite3.Error:
        connection.rollback()
        raise

    finally:
        connection.close()
        

def update_product_info(product_id, new_name, new_model, new_description):
    if type(product_id) is not int or product_id <= 0:
        return "invalid_product_id"

    if not isinstance(new_name, str) or not new_name.strip():
        return "invalid_name"

    if not isinstance(new_model, str) or not new_model.strip():
        return "invalid_model"


    connection = connect_db()

    try:
        cursor = connection.cursor()

        cursor.execute("BEGIN IMMEDIATE")

        cursor.execute("""
            UPDATE products
            SET name = ?, model = ?, description = ?
            WHERE id = ?
        """, (
            new_name.strip(),
            new_model.strip(),
            new_description.strip() if new_description is not None else None,
            product_id
        ))

        updated = cursor.rowcount

        connection.commit()

        return updated

    except sqlite3.Error:
        connection.rollback()
        raise

    finally:
        connection.close()

def create_order(user_id, product_id, quantity, confirmation_id):

    if type(user_id) is not int or user_id <= 0:
        return "invalid_user_id"

    if type(product_id) is not int or product_id <= 0:
        return "invalid_product_id"

    if type(quantity) is not int or quantity <= 0:
        return "invalid_quantity"

    if (
        not isinstance(confirmation_id, str)
        or len(confirmation_id) != 32
        or any(char not in "0123456789abcdef" for char in confirmation_id)
    ):
        return "invalid_confirmation_id"

    connection = connect_db()

    try:
        cursor = connection.cursor()

        cursor.execute("BEGIN IMMEDIATE")

        try:
            cursor.execute("""
                INSERT INTO processed_confirmations (confirmation_id)
                VALUES (?)
            """, (confirmation_id,))

        except sqlite3.IntegrityError:
            connection.rollback()
            return "duplicate"

        cursor.execute("""
            SELECT name, price, stock
            FROM products
            WHERE id = ?
        """, (product_id,))

        product = cursor.fetchone()

        if product is None:
            connection.rollback()
            return "unavailable"

        product_name, price, stock = product

        if stock < quantity:
            connection.rollback()
            return "unavailable"

        cursor.execute("""
            INSERT INTO orders (
                user_id,
                product_id,
                product_name,
                price,
                quantity,
                total_price
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            product_id,
            product_name,
            price,
            quantity,
            price * quantity
        ))

        cursor.execute("""
            UPDATE products
            SET stock = ?
            WHERE id = ?
        """, (stock - quantity, product_id))

        connection.commit()
        return "success"

    except sqlite3.Error:
        connection.rollback()
        raise

    finally:
        connection.close()


def cancel_order(order_id, user_id=None):

    if type(order_id) is not int or order_id <= 0:
        return "invalid_order_id"

    if user_id is not None:
        if type(user_id) is not int or user_id <= 0:
            return "invalid_user_id"

    connection = connect_db()

    try:
        cursor = connection.cursor()

        cursor.execute("BEGIN IMMEDIATE")

        cursor.execute("""
            SELECT product_id, quantity, status, user_id
            FROM orders
            WHERE id = ?
        """, (order_id,))

        order = cursor.fetchone()

        if order is None:
            connection.rollback()
            return "not_found"

        product_id, quantity, status, order_user_id = order

        if user_id is not None and order_user_id != user_id:
            connection.rollback()
            return "unauthorized"

        if not isinstance(quantity, int) or quantity <= 0:
            connection.rollback()
            return "invalid_quantity"

        if status == "cancelled":
            connection.rollback()
            return "already_cancelled"

        if status != "active":
            connection.rollback()
            return "invalid_status"

        # تلاش برای بازگرداندن موجودی محصول
        cursor.execute("""
            UPDATE products
            SET stock = stock + ?
            WHERE id = ?
        """, (quantity, product_id))

        product_missing = cursor.rowcount == 0

        # در هر دو حالت، سفارش لغو می‌شود
        cursor.execute("""
            UPDATE orders
            SET status = 'cancelled'
            WHERE id = ? AND status = 'active'
        """, (order_id,))

        if cursor.rowcount != 1:
            connection.rollback()
            return "error"

        connection.commit()

        if product_missing:
            return "success_product_missing"

        return "success"

    except sqlite3.Error:
        connection.rollback()
        raise

    finally:
        connection.close()


def get_user_orders(user_id, status=None):
    connection = connect_db()

    try:
        cursor = connection.cursor()

        if status is None:
            cursor.execute("""
                SELECT id, product_name, price, quantity,
                       total_price, created_at, status
                FROM orders
                WHERE user_id = ?
                ORDER BY id DESC
            """, (user_id,))

        else:
            cursor.execute("""
                SELECT id, product_name, price, quantity,
                       total_price, created_at, status
                FROM orders
                WHERE user_id = ? AND status = ?
                ORDER BY id DESC
            """, (user_id, status))

        return cursor.fetchall()

    finally:
        connection.close()



def get_all_orders():
        connection = connect_db()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT id, user_id, product_name, price, quantity,
                total_price, created_at, status
            FROM orders
            ORDER BY id DESC
        """)

        orders = cursor.fetchall()
        connection.close()

        return orders

def test_orders_table():
    connection = connect_db()
    cursor = connection.cursor()

    cursor.execute("PRAGMA table_info(orders)")
    columns = cursor.fetchall()

    for column in columns:
        print(column[1])

    connection.close()


    connection = connect_db()
    cursor = connection.cursor()

    cursor.execute("SELECT * FROM orders")
    print(cursor.fetchall())

    cursor.execute("SELECT * FROM products")
    print(cursor.fetchall())

    connection.close()    