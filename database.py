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

    try:
        cursor = connection.cursor()

        # جدول سفارش‌ها
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                product_name TEXT NOT NULL,
                price INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                total_price INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT NOT NULL DEFAULT 'active'
            )
        """)

        # بررسی ستون‌های موجود برای مهاجرت امن
        cursor.execute("PRAGMA table_info(orders)")
        columns = [column[1] for column in cursor.fetchall()]

        new_columns = {
            "status": "TEXT NOT NULL DEFAULT 'active'",
            "unit_price_rial": "INTEGER NOT NULL DEFAULT 0",
            "total_amount": "INTEGER NOT NULL DEFAULT 0",
            "currency": "TEXT NOT NULL DEFAULT 'IRR'",
            "expires_at": "TEXT",
            "stock_released": "INTEGER NOT NULL DEFAULT 0"
        }

        for column_name, column_type in new_columns.items():
            if column_name not in columns:
                cursor.execute(
                    f"ALTER TABLE orders ADD COLUMN "
                    f"{column_name} {column_type}"
                )

        # جلوگیری از ثبت تأیید سفارش تکراری
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processed_confirmations (
                confirmation_id TEXT PRIMARY KEY
            )
        """)

        # جدول تلاش‌های پرداخت
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                amount INTEGER NOT NULL CHECK(amount > 0),
                currency TEXT NOT NULL,
                gateway TEXT NOT NULL,
                transaction_id TEXT UNIQUE,
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK(status IN (
                        'pending',
                        'paid',
                        'failed',
                        'cancelled',
                        'refund_pending',
                        'refunded'
                    )),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                verified_at TEXT,
                last_checked_at TEXT,
                next_check_at TEXT,
                verification_attempts INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(order_id) REFERENCES orders(id)
            )
        """)

        # هر سفارش می‌تواند چند تلاش پرداخت داشته باشد
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_payments_order_id
            ON payments(order_id)
        """)


        # ذخیره نتیجه شبیه‌سازی پرداخت‌های آزمایشی
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS test_payment_results (
                payment_id INTEGER PRIMARY KEY,
                simulated_status TEXT NOT NULL
                    CHECK(simulated_status IN (
                        'paid',
                        'failed',
                        'pending'
                    )),
                updated_at TEXT NOT NULL,
                FOREIGN KEY(payment_id) REFERENCES payments(id)
            )
        """)

        # تاریخچه رویدادهای پرداخت
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS payment_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                payment_id INTEGER,
                event_type TEXT NOT NULL,
                gateway_event_id TEXT,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(order_id) REFERENCES orders(id),
                FOREIGN KEY(payment_id) REFERENCES payments(id)
            )
        """)

        # جلوگیری از پردازش دوباره یک رویداد درگاه
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
            idx_payment_logs_gateway_event
            ON payment_logs(gateway_event_id)
            WHERE gateway_event_id IS NOT NULL
        """)

        connection.commit()

    except sqlite3.Error:
        connection.rollback()
        raise

    finally:
        connection.close()


def set_test_payment_result(payment_id, result):

    from datetime import datetime, timezone

    if type(payment_id) is not int or payment_id <= 0:
        return "invalid_payment_id"

    if result not in ("paid", "failed", "pending"):
        return "invalid_result"

    connection = connect_db()

    try:
        cursor = connection.cursor()

        cursor.execute("BEGIN IMMEDIATE")

        cursor.execute("""
            SELECT gateway, status
            FROM payments
            WHERE id = ?
        """, (payment_id,))

        payment = cursor.fetchone()

        if payment is None:
            connection.rollback()
            return "payment_not_found"

        gateway, payment_status = payment

        if gateway != "test":
            connection.rollback()
            return "not_test_payment"

        if payment_status != "pending":
            connection.rollback()
            return "payment_already_processed"

        updated_at = datetime.now(timezone.utc).isoformat()

        cursor.execute("""
            INSERT INTO test_payment_results (
                payment_id,
                simulated_status,
                updated_at
            )
            VALUES (?, ?, ?)
            ON CONFLICT(payment_id)
            DO UPDATE SET
                simulated_status = excluded.simulated_status,
                updated_at = excluded.updated_at
        """, (
            payment_id,
            result,
            updated_at
        ))

        connection.commit()
        return "success"

    except sqlite3.Error:
        connection.rollback()
        raise

    finally:
        connection.close()


def get_test_payment_result(payment_id):

    if type(payment_id) is not int or payment_id <= 0:
        return "invalid_payment_id"

    connection = connect_db()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            SELECT simulated_status
            FROM test_payment_results
            WHERE payment_id = ?
        """, (payment_id,))

        result = cursor.fetchone()

        if result is None:
            return "not_found"

        return result[0]

    finally:
        connection.close()

def process_payment_result(
    payment_id,
    result,
    gateway_event_id=None
):

    from datetime import datetime, timezone, timedelta

    if type(payment_id) is not int or payment_id <= 0:
        return "invalid_payment_id"

    if result not in ("paid", "failed", "pending"):
        return "invalid_result"

    if gateway_event_id is not None:
        if (
            not isinstance(gateway_event_id, str)
            or not gateway_event_id.strip()
            or len(gateway_event_id) > 255
        ):
            return "invalid_event_id"

    connection = connect_db()

    try:
        cursor = connection.cursor()

        cursor.execute("BEGIN IMMEDIATE")

        now = datetime.now(timezone.utc)
        now_text = now.isoformat()

        # بررسی تکراری نبودن رویداد درگاه
        if gateway_event_id is not None:

            cursor.execute("""
                SELECT id
                FROM payment_logs
                WHERE gateway_event_id = ?
            """, (gateway_event_id,))

            if cursor.fetchone() is not None:
                connection.rollback()
                return "duplicate_event"

        # دریافت اطلاعات پرداخت و سفارش
        cursor.execute("""
            SELECT
                p.order_id,
                p.status,
                o.status,
                o.expires_at,
                o.product_id,
                o.quantity,
                o.stock_released,
                p.verification_attempts
            FROM payments p
            JOIN orders o ON o.id = p.order_id
            WHERE p.id = ?
        """, (payment_id,))

        payment = cursor.fetchone()

        if payment is None:
            connection.rollback()
            return "payment_not_found"

        (
            order_id,
            payment_status,
            order_status,
            expires_at,
            product_id,
            quantity,
            stock_released,
            verification_attempts
        ) = payment

        # جلوگیری از پردازش دوباره پرداخت
        if payment_status != "pending":
            connection.rollback()
            return "already_processed"

        
        # نتیجه نامشخص
        if result == "pending":

            new_attempts = verification_attempts + 1

            backoff_minutes = {
                1: 1,
                2: 2,
                3: 5,
                4: 10
            }

            delay = backoff_minutes.get(new_attempts)

            # اگر هنوز فرصت بررسی مجدد وجود دارد
            if delay is not None:

                next_check = (
                    now + timedelta(minutes=delay)
                ).isoformat()

                cursor.execute("""
                    UPDATE payments
                    SET
                        last_checked_at = ?,
                        next_check_at = ?,
                        verification_attempts = ?
                    WHERE id = ? AND status = 'pending'
                """, (
                    now_text,
                    next_check,
                    new_attempts,
                    payment_id
                ))

                event_type = "payment_pending"

                details = (
                    f"Payment still pending. "
                    f"Next verification in {delay} minutes."
                )

            # پس از چهار نوبت بررسی مجدد، ارجاع به مدیر
            else:

                cursor.execute("""
                    UPDATE payments
                    SET
                        last_checked_at = ?,
                        next_check_at = NULL,
                        verification_attempts = ?
                    WHERE id = ? AND status = 'pending'
                """, (
                    now_text,
                    new_attempts,
                    payment_id
                ))

                cursor.execute("""
                    UPDATE orders
                    SET status = 'payment_review'
                    WHERE id = ?
                """, (order_id,))

                event_type = "payment_needs_admin_review"

                details = (
                    "Payment remains uncertain after "
                    "all verification retries. "
                    "Admin review required."
                )

            cursor.execute("""
                INSERT INTO payment_logs (
                    order_id,
                    payment_id,
                    event_type,
                    gateway_event_id,
                    details
                )
                VALUES (?, ?, ?, ?, ?)
            """, (
                order_id,
                payment_id,
                event_type,
                gateway_event_id,
                details
            ))

            connection.commit()

            if delay is not None:
                return "still_pending"

            return "payment_review"
        
        # پردازش پرداخت موفق
        if result == "paid":

            # فقط سفارش‌های پرداختی جدید مجاز هستند
            if order_status not in (
                "pending_payment",
                "payment_review",
                "cancelled"
            ):
                connection.rollback()
                return "invalid_order_status"

            is_on_time = False

            # فعال‌سازی فقط در صورتی مجاز است که:
            # سفارش در انتظار پرداخت باشد،
            # موجودی هنوز آزاد نشده باشد،
            # و مهلت پرداخت تمام نشده باشد.
            if (
                order_status == "pending_payment"
                and stock_released == 0
                and expires_at
            ):

                try:
                    expiry_time = datetime.fromisoformat(
                        expires_at
                    )

                    if expiry_time.tzinfo is None:
                        expiry_time = expiry_time.replace(
                            tzinfo=timezone.utc
                        )

                    is_on_time = now < expiry_time

                except ValueError:
                    is_on_time = False

            new_order_status = (
                "active" if is_on_time else "payment_review"
            )

            cursor.execute("""
                UPDATE payments
                SET
                    status = 'paid',
                    verified_at = ?,
                    last_checked_at = ?,
                    next_check_at = NULL
                WHERE id = ? AND status = 'pending'
            """, (
                now_text,
                now_text,
                payment_id
            ))

            if cursor.rowcount != 1:
                connection.rollback()
                return "error"

            cursor.execute("""
                UPDATE orders
                SET status = ?
                WHERE id = ?
            """, (new_order_status, order_id))

            event_type = (
                "payment_verified"
                if is_on_time
                else "late_payment_detected"
            )

            details = (
                "Payment verified successfully"
                if is_on_time
                else (
                    "Payment succeeded but order requires "
                    "admin review. Stock was not reactivated."
                )
            )

            cursor.execute("""
                INSERT INTO payment_logs (
                    order_id,
                    payment_id,
                    event_type,
                    gateway_event_id,
                    details
                )
                VALUES (?, ?, ?, ?, ?)
            """, (
                order_id,
                payment_id,
                event_type,
                gateway_event_id,
                details
            ))

            connection.commit()

            if is_on_time:
                return "success"

            return "payment_review"

        # پردازش پرداخت ناموفق
        if result == "failed":

            if order_status not in (
                "pending_payment",
                "payment_review",
                "cancelled"
            ):
                connection.rollback()
                return "invalid_order_status"

            cursor.execute("""
                UPDATE payments
                SET
                    status = 'failed',
                    verified_at = ?,
                    last_checked_at = ?,
                    next_check_at = NULL
                WHERE id = ? AND status = 'pending'
            """, (
                now_text,
                now_text,
                payment_id
            ))

            if cursor.rowcount != 1:
                connection.rollback()
                return "error"

            product_missing = False

            # آزادسازی موجودی فقط یک بار
            if stock_released == 0:

                cursor.execute("""
                    UPDATE products
                    SET stock = stock + ?
                    WHERE id = ?
                """, (quantity, product_id))

                product_missing = cursor.rowcount == 0

            cursor.execute("""
                UPDATE orders
                SET
                    status = 'cancelled',
                    stock_released = 1
                WHERE id = ?
            """, (order_id,))

            cursor.execute("""
                INSERT INTO payment_logs (
                    order_id,
                    payment_id,
                    event_type,
                    gateway_event_id,
                    details
                )
                VALUES (?, ?, ?, ?, ?)
            """, (
                order_id,
                payment_id,
                "payment_failed",
                gateway_event_id,
                "Payment definitively failed; order cancelled"
            ))

            connection.commit()

            if product_missing:
                return "success_product_missing"

            return "failed_and_cancelled"

    except sqlite3.Error:
        connection.rollback()
        raise

    finally:
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

    from datetime import datetime, timedelta, timezone

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

        # جلوگیری از ثبت سفارش تکراری
        try:
            cursor.execute("""
                INSERT INTO processed_confirmations (confirmation_id)
                VALUES (?)
            """, (confirmation_id,))

        except sqlite3.IntegrityError:
            connection.rollback()
            return "duplicate"

        # دریافت اطلاعات محصول
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

        if price <= 0:
            connection.rollback()
            return "invalid_price"

        # محاسبه مبلغ‌ها
        total_price = price * quantity
        unit_price_rial = price * 10
        total_amount = total_price * 10

        # تعیین مهلت ۱۵ دقیقه‌ای پرداخت
        now = datetime.now(timezone.utc)
        expires_at = (
            now + timedelta(minutes=15)
        ).isoformat()

        # ثبت سفارش در انتظار پرداخت
        cursor.execute("""
            INSERT INTO orders (
                user_id,
                product_id,
                product_name,
                price,
                quantity,
                total_price,
                status,
                unit_price_rial,
                total_amount,
                currency,
                expires_at,
                stock_released
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            product_id,
            product_name,
            price,
            quantity,
            total_price,
            "pending_payment",
            unit_price_rial,
            total_amount,
            "IRR",
            expires_at,
            0
        ))

        order_id = cursor.lastrowid

        # رزرو موجودی محصول
        cursor.execute("""
            UPDATE products
            SET stock = stock - ?
            WHERE id = ? AND stock >= ?
        """, (quantity, product_id, quantity))

        if cursor.rowcount != 1:
            connection.rollback()
            return "unavailable"

        # ایجاد تلاش پرداخت آزمایشی
        cursor.execute("""
            INSERT INTO payments (
                order_id,
                amount,
                currency,
                gateway,
                status
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            order_id,
            total_amount,
            "IRR",
            "test",
            "pending"
        ))

        connection.commit()
        return ("payment_pending", order_id)

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
            SELECT
                product_id,
                quantity,
                status,
                user_id,
                stock_released
            FROM orders
            WHERE id = ?
        """, (order_id,))

        order = cursor.fetchone()

        if order is None:
            connection.rollback()
            return "not_found"

        (
            product_id,
            quantity,
            status,
            order_user_id,
            stock_released
        ) = order

        # بررسی مالکیت سفارش
        if user_id is not None and order_user_id != user_id:
            connection.rollback()
            return "unauthorized"

        if not isinstance(quantity, int) or quantity <= 0:
            connection.rollback()
            return "invalid_quantity"

        if status == "cancelled":
            connection.rollback()
            return "already_cancelled"

        # سفارش نیازمند بررسی را نمی‌توان عادی لغو کرد
        if status == "payment_review":
            connection.rollback()
            return "payment_review"

        # بررسی وضعیت پرداخت سفارش
        cursor.execute("""
            SELECT status
            FROM payments
            WHERE order_id = ?
            ORDER BY id DESC
            LIMIT 1
        """, (order_id,))

        payment = cursor.fetchone()

        # سفارش‌های قدیمی ممکن است رکورد پرداخت نداشته باشند
        if payment is None:

            if status == "pending_payment":
                connection.rollback()
                return "payment_not_found"

            if status != "active":
                connection.rollback()
                return "invalid_status"

        else:

            payment_status = payment[0]

            if status == "pending_payment":

                if payment_status in (
                    "paid",
                    "refund_pending",
                    "refunded"
                ):
                    connection.rollback()
                    return "payment_already_paid"

                if payment_status == "pending":
                    connection.rollback()
                    return "payment_uncertain"

                if payment_status not in ("failed", "cancelled"):
                    connection.rollback()
                    return "invalid_payment_status"

            elif status == "active":

                if payment_status in ("paid", "refund_pending"):
                    connection.rollback()
                    return "payment_already_paid"

                if payment_status == "refunded":
                    connection.rollback()
                    return "payment_refunded"

                if payment_status == "pending":
                    connection.rollback()
                    return "payment_uncertain"

                if payment_status in ("failed", "cancelled"):
                    connection.rollback()
                    return "invalid_payment_order_state"

                connection.rollback()
                return "invalid_payment_status"

            else:
                connection.rollback()
                return "invalid_status"
            
        # آزادسازی موجودی فقط در صورت آزاد نشدن قبلی
        product_missing = False

        if stock_released == 0:

            cursor.execute("""
                UPDATE products
                SET stock = stock + ?
                WHERE id = ?
            """, (quantity, product_id))

            product_missing = cursor.rowcount == 0

        # ثبت نهایی لغو سفارش
        cursor.execute("""
            UPDATE orders
            SET
                status = 'cancelled',
                stock_released = 1
            WHERE id = ?
            AND status = ?
            AND stock_released = ?
        """, (
            order_id,
            status,
            stock_released
        ))

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

        elif status == "active":
            cursor.execute("""
                SELECT id, product_name, price, quantity,
                       total_price, created_at, status
                FROM orders
                WHERE user_id = ?
                AND status IN ('active', 'pending_payment')
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

    try:
        cursor = connection.cursor()

        cursor.execute("""
            SELECT id, user_id, product_name, price, quantity,
                   total_price, created_at, status
            FROM orders
            ORDER BY id DESC
        """)

        return cursor.fetchall()

    finally:
        connection.close()


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