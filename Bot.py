from multiprocessing import context

from database import (
    create_table,
    get_product_by_id,
    get_products,
    get_all_orders,
    create_order,
    get_user_orders,
    add_product,
    update_product_info,
    update_product_price,
    update_stock,
    delete_product,
    add_image_column,
    cancel_order
)

from telegram import(
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
)

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,MessageHandler,
    filters
)

import os
import uuid
import logging
from dotenv import load_dotenv

load_dotenv()

ADMIN_ID = int(os.getenv("ADMIN_ID"))

def main_menu():
    keyboard = [
        [
            KeyboardButton("🛍 محصولات"),
            KeyboardButton("📦 سفارش‌های من")
        ],
        [
            KeyboardButton("👤 حساب کاربری"),
            KeyboardButton("☎️ پشتیبانی")
        ]
    ]

    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True
    )


def is_admin(user_id):
    return user_id == ADMIN_ID


def admin_menu():
    keyboard = [
        [
            KeyboardButton("➕ افزودن محصول"),
            KeyboardButton("✏️ ویرایش محصول")
        ],
        [
            KeyboardButton("📦 مدیریت موجودی"),
            KeyboardButton("🗑 حذف محصول")
        ],
        [
            KeyboardButton("📋 مشاهده سفارش‌ها")
        ],
        [
            KeyboardButton("🔙 بازگشت به منوی مشتری")
        ]
    ]

    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True
    )


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    user_id = update.effective_user.id

    if is_admin(user_id):
        await update.message.reply_text(
            "سلام مدیر عزیز! 👋\n"
            "به پنل مدیریت فروشگاه خوش آمدید.",
            reply_markup=admin_menu()
        )

    else:
        await update.message.reply_text(
            "سلام! به فروشگاه ما خوش آمدید. 🛍\n"
            "لطفاً یکی از گزینه‌های منو رو انتخاب کنید:",
            reply_markup=main_menu()
        )



async def menu_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    text = update.message.text or ""

    if context.user_data.get("order_step") == "quantity":

        try:
            quantity = int(text)
        except (ValueError, TypeError):
            await update.message.reply_text(
                "لطفاً تعداد رو به‌صورت عدد وارد کن:"
            )
            return

        if quantity <= 0:
            await update.message.reply_text(
               "تعداد باید بیشتر از صفر باشه. دوباره وارد کن:"
            )
            return

        product_id = context.user_data.get("pending_order_product_id")
        product = get_product_by_id(product_id)

        if product is None:
            await update.message.reply_text(
               "محصول موردنظر پیدا نشد."
            )
            context.user_data.pop("order_step", None)
            context.user_data.pop("pending_order_product_id", None)
            return

        if quantity > product[3]:
            await update.message.reply_text(
               f"موجودی کافی نیست. موجودی فعلی: {product[3]} عدد"
            )
            return

        total_price = product[2] * quantity

        context.user_data["pending_order_quantity"] = quantity
        context.user_data["order_step"] = "confirm"
        
        confirmation_id = uuid.uuid4().hex

        context.user_data["pending_confirmation_id"] = confirmation_id

        button1 = InlineKeyboardButton(
            text="✅ تأیید خرید",
            callback_data=f"confirm_{product_id}_{quantity}_{confirmation_id}"
        )

        button2 = InlineKeyboardButton(
            text="❌ انصراف",
            callback_data=f"cancel_{product_id}"
        )

        keyboard = [[button1, button2]]

        await update.message.reply_text(
           f"محصول: {product[1]}\n"
           f"تعداد: {quantity}\n"
           f"مبلغ کل: {total_price:,} تومان\n\n"
           "آیا خرید رو تأیید می‌کنی؟",
           reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return

    if context.user_data.get("admin_step") and not is_admin(update.effective_user.id):

        for key in (
            "admin_step",
            "new_product",
            "stock_product_id",
            "delete_product_id",
            "edit_product_id",
            "edit_product_name",
            "edit_product_model",
            "edit_product_price",
            "edit_product_stock",
        ):
            context.user_data.pop(key, None)

        await update.message.reply_text(
            "⛔ شما اجازه دسترسی به پنل مدیریت رو ندارید.",
            reply_markup=main_menu()
        )
        return
    
    if text in ["لغو", "❌ لغو عملیات"]:

        if is_admin(update.effective_user.id):
            context.user_data.pop("admin_step", None)
            context.user_data.pop("new_product", None)
            context.user_data.pop("stock_product_id", None)
            context.user_data.pop("delete_product_id", None)
            context.user_data.pop("edit_product_id", None)
            context.user_data.pop("edit_product_name", None)
            context.user_data.pop("edit_product_model", None)
            context.user_data.pop("edit_product_price", None)
            context.user_data.pop("edit_product_stock", None)

            await update.message.reply_text(
                "❌ عملیات لغو شد. می‌تونی از منوی مدیریت دوباره شروع کنی.",
                reply_markup=admin_menu()
            )

        else:
            await update.message.reply_text(
                "❌ عملیات لغو شد.",
                reply_markup=main_menu()
            )

        return
    
    if text == "🔙 بازگشت به منوی مشتری":
        context.user_data.pop("admin_step", None)
        context.user_data.pop("new_product", None)

        await update.message.reply_text(
           "به منوی مشتری برگشتی.",
           reply_markup=main_menu()
        )
        return

    if text in [
        "➕ افزودن محصول",
        "✏️ ویرایش محصول",
        "📦 مدیریت موجودی",
        "🗑 حذف محصول",
        "📋 مشاهده سفارش‌ها"
   ]:
        if not is_admin(update.effective_user.id):
           await update.message.reply_text(
            "⛔ شما اجازه دسترسی به پنل مدیریت رو ندارید."
           )
           return

    if text == "➕ افزودن محصول":
       context.user_data["admin_step"] = "product_name"

       keyboard = [
           [KeyboardButton("❌ لغو عملیات")]
       ]   

       reply_markup = ReplyKeyboardMarkup(
           keyboard,
           resize_keyboard=True
       )

       await update.message.reply_text(
          "نام محصول جدید رو وارد کن:",
          reply_markup=reply_markup
       )
       return

    if text == "✏️ ویرایش محصول":
       all_products = get_products()

       if not all_products:
          await update.message.reply_text(
            "هیچ محصولی برای ویرایش وجود نداره."
          )
          return
       context.user_data["admin_step"] = "edit_product_id"

       keyboard = [
           [KeyboardButton("❌ لغو عملیات")]
       ]

       reply_markup = ReplyKeyboardMarkup(
           keyboard,
           resize_keyboard=True
       )
       await update.message.reply_text(
          "شناسه محصول موردنظر را وارد کن:",
            reply_markup=reply_markup
       )
       
       message = "✏️ فهرست محصولات:\n\n"

       for product in all_products:
           message += (
              f"شناسه: {product[0]}\n"
              f"نام: {product[1]}\n"
              f"قیمت: {product[2]:,} تومان\n"
              f"موجودی: {product[3]}\n\n"
           )

       await update.message.reply_text(message)
       return

    if text == "📦 مدیریت موجودی":
       all_products = get_products()

       if not all_products:
          await update.message.reply_text(
              "هیچ محصولی برای مدیریت موجودی وجود نداره."
          )
          return

       context.user_data["admin_step"] = "stock_product_id"

       keyboard = [
          [KeyboardButton("❌ لغو عملیات")]
       ]

       reply_markup = ReplyKeyboardMarkup(
           keyboard,
           resize_keyboard=True
       )

       await update.message.reply_text("📦 فهرست محصولات:\n")

       for product in all_products:
           product_id = product[0]
           name = product[1]
           stock = product[3]
           image_file_id = product[5]

           message = (
              f"شناسه: {product_id}\n"
              f"نام: {name}\n"
              f"موجودی فعلی: {stock}"
           )

           if image_file_id:
               await update.message.reply_photo(
                  photo=image_file_id,
                  caption=message
               )
           else:
               await update.message.reply_text(message)

       await update.message.reply_text(
           "شناسه محصول موردنظر رو وارد کن:",
           reply_markup=reply_markup
       )

       return

    if context.user_data.get("admin_step") == "stock_product_id":
       try:
          product_id = int(text)
       except (ValueError, TypeError):
           await update.message.reply_text(
              "شناسه محصول باید عدد صحیح باشه. دوباره وارد کن:"
           )
           return

       product = get_product_by_id(product_id)

       if not product:
           await update.message.reply_text(
              "محصولی با این شناسه پیدا نشد. دوباره وارد کن:"
           )
           return

       context.user_data["stock_product_id"] = product_id
       context.user_data["admin_step"] = "stock_new_quantity"

       image_file_id = product[5]

       message = (
           f"محصول انتخاب شد: {product[1]}\n"
           f"موجودی فعلی: {product[3]}\n"
           "موجودی جدید رو وارد کن:"
       )

       if image_file_id:
           await update.message.reply_photo(
              photo=image_file_id,
              caption=message
           )
       else:
           await update.message.reply_text(message)

       return

    if text == "🗑 حذف محصول":
       all_products = get_products()

       keyboard = [
           [KeyboardButton("❌ لغو عملیات")]
       ]

       reply_markup = ReplyKeyboardMarkup(
           keyboard,
           resize_keyboard=True
       )

       if not all_products:
           await update.message.reply_text(
              "هیچ محصولی برای حذف وجود نداره."
           )
           return

       context.user_data["admin_step"] = "delete_product_id"

       await update.message.reply_text("🗑 فهرست محصولات:\n")

       for product in all_products:

           product_id = product[0]
           name = product[1]
           image_file_id = product[5]

           message = (
              f"شناسه: {product_id}\n"
              f"نام: {name}"
           )

           if image_file_id:
              await update.message.reply_photo(
                 photo=image_file_id,
                 caption=message
              )
           else:
              await update.message.reply_text(message)

       await update.message.reply_text(
           "شناسه محصولی که می‌خوای حذف کنی رو وارد کن:",
           reply_markup=reply_markup
       )
       return

    if context.user_data.get("admin_step") == "delete_product_id":
       try:
           product_id = int(text)
       except (ValueError, TypeError):
           await update.message.reply_text(
              "شناسه محصول باید عدد صحیح باشه. دوباره وارد کن:"
           )
           return

       product = get_product_by_id(product_id)

       if not product:
          await update.message.reply_text(
              "محصولی با این شناسه پیدا نشد. دوباره وارد کن:"
          )
          return

       context.user_data["delete_product_id"] = product_id
       context.user_data["admin_step"] = "delete_product_confirm"

       await update.message.reply_text(
           f"⚠️ محصول انتخاب‌شده: {product[1]}\n"
           "آیا مطمئنی می‌خوای این محصول رو حذف کنی؟\n"
           "برای تأیید بنویس: بله\n"
           "برای انصراف بنویس: خیر"
       )
       return

    if context.user_data.get("admin_step") == "delete_product_confirm":

       if text == "بله":
            product_id = context.user_data.get("delete_product_id")

            result = delete_product(product_id)

            context.user_data.pop("delete_product_id", None)
            context.user_data.pop("admin_step", None)

            if result == "has_orders":
                message = (
                    "⛔ این محصول سابقه سفارش دارد و امکان حذف آن وجود ندارد."
            )

            elif result == 1:
                message = "✅ محصول با موفقیت حذف شد."

            else:
                message = "❌ محصول پیدا نشد."

            await update.message.reply_text(
                message,
                reply_markup=admin_menu()
            )
            return
           

       elif text == "خیر":
           context.user_data.pop("delete_product_id", None)
           context.user_data.pop("admin_step", None)

           await update.message.reply_text(
              "❌ حذف محصول لغو شد.",
              reply_markup=admin_menu()
           )
           return

       else:
           await update.message.reply_text(
               "لطفاً فقط «بله» یا «خیر» وارد کن:"
           )
           return

    
    if text == "📋 مشاهده سفارش‌ها":
        keyboard = [
            [
                InlineKeyboardButton(
                    text="🟢 سفارش‌های فعال",
                    callback_data="admin_orders_active"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ سفارش‌های لغوشده",
                    callback_data="admin_orders_cancelled"
                )
            ]
        ]
    
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "📋 کدام سفارش‌ها را می‌خواهید مشاهده کنید؟",
            reply_markup=reply_markup
        )

        return

    
    if context.user_data.get("admin_step") == "stock_new_quantity":
       try:
           new_stock = int(text)
       except (ValueError, TypeError):
           await update.message.reply_text(
              "موجودی باید عدد صحیح باشه. دوباره وارد کن:"
           ) 
           return

       if new_stock < 0:
           await update.message.reply_text(
               "موجودی نمی‌تونه منفی باشه. دوباره وارد کن:"
           )
           return

       product_id = context.user_data.get("stock_product_id")

       result = update_stock(product_id, new_stock)

       context.user_data.pop("stock_product_id", None)
       context.user_data.pop("admin_step", None)

       if result == 1:
            message = f"✅ موجودی محصول با موفقیت به {new_stock} تغییر کرد."

       elif result == 0:
            message = "❌ محصول پیدا نشد."

       elif result == "invalid_product_id":
            message = "❌ شناسه محصول نامعتبر است."

       elif result == "invalid_stock":
            message = "❌ مقدار موجودی نامعتبر است."

       else:
            message = "❌ خطای غیرمنتظره در تغییر موجودی رخ داد."
       
       await update.message.reply_text(
           message,
           reply_markup=admin_menu()
       )
       return
    
    if context.user_data.get("admin_step") == "edit_product_id":
       try:
           product_id = int(text)
       except (ValueError, TypeError):
           await update.message.reply_text(
              "لطفاً شناسه محصول رو به‌صورت عدد وارد کن:"
           )
           return

       product = get_product_by_id(product_id)

       if not product:
           await update.message.reply_text(
              "محصولی با این شناسه پیدا نشد. دوباره وارد کن:"
           )
           return

       context.user_data["edit_product_id"] = product_id
       context.user_data["admin_step"] = "edit_product_name"

       await update.message.reply_text(
          f"محصول انتخاب شد: {product[1]}\n"
          "نام جدید محصول رو وارد کن:"
       )
       return

    if context.user_data.get("admin_step") == "edit_product_name":
       new_name = text.strip()

       if not new_name:
          await update.message.reply_text(
            "نام محصول نمی‌تونه خالی باشه. دوباره وارد کن:"
          )
          return

       context.user_data["edit_product_name"] = new_name
       context.user_data["admin_step"] = "edit_product_model"

       await update.message.reply_text(
          "مدل جدید محصول رو وارد کن:"
       )
       return
    
    if context.user_data.get("admin_step") == "edit_product_model":
       new_model = text.strip()

       context.user_data["edit_product_model"] = new_model
       context.user_data["admin_step"] = "edit_product_price"

       await update.message.reply_text(
          "قیمت جدید محصول رو به تومان وارد کن:"
       )
       return

    if context.user_data.get("admin_step") == "edit_product_price":
        try:
           new_price = int(
              text.replace(",", "").replace("٬", "").replace("،", "")
           )

           if new_price <= 0:
              raise ValueError

        except ValueError:
           await update.message.reply_text(
                "قیمت باید عدد صحیح و بزرگ‌تر از صفر باشه. دوباره وارد کن:"
           )
           return

        context.user_data["edit_product_price"] = new_price
        context.user_data["admin_step"] = "edit_product_stock"

        await update.message.reply_text(
           "موجودی جدید محصول رو وارد کن:"
        )
        return

    if context.user_data.get("admin_step") == "edit_product_stock":
       try:
           new_stock = int(text)

           if new_stock < 0:
              raise ValueError

       except ValueError:
           await update.message.reply_text(
              "موجودی باید عدد صحیح و صفر یا بیشتر باشه. دوباره وارد کن:"
           )
           return

       product_id = context.user_data.get("edit_product_id")
       new_name = context.user_data.get("edit_product_name")
       new_model = context.user_data.get("edit_product_model")
       new_price = context.user_data.get("edit_product_price")

       update_product_info(product_id, new_name, new_model)
       update_product_price(product_id, new_price)
       update_stock(product_id, new_stock)

       for key in [
          "edit_product_id",
          "edit_product_name",
          "edit_product_model",
          "edit_product_price",
          "edit_product_stock",
          "admin_step"
       ]:
          context.user_data.pop(key, None)

       await update.message.reply_text(
          "✅ اطلاعات محصول با موفقیت ویرایش شد."
       )
       return
 
    
    if context.user_data.get("admin_step") == "product_name":
       product_name = text.strip()

       if not product_name:
          await update.message.reply_text(
            "نام محصول نمی‌تونه خالی باشه. دوباره وارد کن:"
          )
          return

       context.user_data["new_product"] = {
          "name": product_name
      }

       context.user_data["admin_step"] = "product_model"

       await update.message.reply_text(
          "مدل محصول رو وارد کن:"
       )
       return

    
    if context.user_data.get("admin_step") == "product_model":
        product_model = text.strip()

        context.user_data["new_product"]["model"] = product_model
  
        context.user_data["admin_step"] = "product_image"

        keyboard = [
            [KeyboardButton("بدون عکس")]
        ]

        reply_markup = ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True
        )

        await update.message.reply_text(
            "📸 عکس محصول رو ارسال کن.\n"
            "اگر نمی‌خوای عکس اضافه کنی، روی «بدون عکس» بزن.",
            reply_markup=reply_markup
        )
        return

    if context.user_data.get("admin_step") == "product_image":

        if update.message.photo:
            image_file_id = update.message.photo[-1].file_id

            context.user_data["new_product"]["image_file_id"] = image_file_id

            context.user_data["admin_step"] = "product_price"

            await update.message.reply_text(
               "✅ عکس محصول دریافت شد.\n"
               "حالا قیمت محصول رو به تومان وارد کن:"
            )
            return

        elif text == "بدون عکس":
            context.user_data["new_product"]["image_file_id"] = None

            context.user_data["admin_step"] = "product_price"

            await update.message.reply_text(
               "قیمت محصول رو به تومان وارد کن:"
            )
            return

        else:
            await update.message.reply_text(
                "لطفاً عکس محصول رو ارسال کن یا روی «بدون عکس» بزن."
            )
            return
    
    if context.user_data.get("admin_step") == "product_price":
       try:
           product_price = int(text.replace(",", "").replace("٬", "").replace("،", ""))

           if product_price <= 0:
              raise ValueError

       except ValueError:
           await update.message.reply_text(
               "قیمت باید یک عدد صحیح و بزرگ‌تر از صفر باشد. دوباره وارد کن:"
           )
           return

       context.user_data["new_product"]["price"] = product_price

       context.user_data["admin_step"] = "product_stock"

       await update.message.reply_text(
          "تعداد موجودی محصول رو وارد کن:"
       )
       return


    if context.user_data.get("admin_step") == "product_stock":
       try:
           product_stock = int(text)

           if product_stock < 0:
              raise ValueError

       except ValueError:
           await update.message.reply_text(
              "موجودی باید یک عدد صحیح و صفر یا بیشتر باشد. دوباره وارد کن:"
           )
           return

       
       context.user_data["new_product"]["stock"] = product_stock

       new_product = context.user_data["new_product"]

       add_product(
          new_product["name"],
          new_product["model"],
          new_product["price"],
          new_product["stock"],
          new_product.get("image_file_id")
       )

       context.user_data.pop("new_product", None)
       context.user_data.pop("admin_step", None)

       await update.message.reply_text(
            "✅ محصول با موفقیت به فروشگاه اضافه شد.",
            reply_markup=admin_menu()
       )
       return



    if text == "🛍 محصولات":
        await products(update, context)

    elif text == "📦 سفارش‌های من":
        await myorders(update, context)

    elif text == "👤 حساب کاربری":
        user = update.effective_user

        await update.message.reply_text(
            f"👤 اطلاعات حساب کاربری\n\n"
            f"نام: {user.first_name}\n"
            f"شناسه کاربری: {user.id}"
        )

    elif text == "☎️ پشتیبانی":
        await update.message.reply_text(
            "☎️ بخش پشتیبانی\n\n"
            "برای ارتباط با پشتیبانی با ما در تماس باشید."
       )
        
async def products(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    products_list = get_products()

    if not products_list:
        await update.message.reply_text(
            "فعلاً محصولی برای نمایش نداریم."
        )
        return

    for product in products_list:

        product_id = product[0]
        name = product[1]
        price = product[2]
        stock = product[3]
        model = product[4]
        image_file_id = product[5]

        message = f"🛍️ {name}\n"

        if model is not None:
            message += f"مدل: {model}\n"

        message += f"قیمت: {price:,} تومان\n"

        if stock > 0:
            message += "وضعیت: موجود ✅"

            button_text = f"انتخاب {name}"

            keyboard = [[
                InlineKeyboardButton(
                    text=button_text,
                    callback_data=f"buy_{product_id}"
                )
            ]]

        else:
            message += "وضعیت: اتمام موجودی ❌"
            keyboard = []

        reply_markup = (
            InlineKeyboardMarkup(keyboard)
            if keyboard else None
        )

        if image_file_id:
            await update.message.reply_photo(
                photo=image_file_id,
                caption=message,
                reply_markup=reply_markup
            )

        else:
            await update.message.reply_text(
                message,
                reply_markup=reply_markup
            )
    
async def myorders(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    user_id = update.effective_user.id

    orders = get_user_orders(user_id)

    if not orders:
        await update.message.reply_text(
            "شما هنوز هیچ سفارشی ثبت نکرده‌اید."
        )
        return

    message = "📦 سفارش‌های قبلی شما:\n\n"

    for order in orders:
        message += (
            f"محصول: {order[0]}\n"
            f"قیمت واحد: {order[1]:,} تومان\n"
            f"تعداد: {order[2]}\n"
            f"مبلغ کل: {order[3]:,} تومان\n"
            f"تاریخ: {order[4]}\n"
            "--------------------\n"
        )

    await update.message.reply_text(message)

async def button_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
    ):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data.startswith("buy_"):
        try:
            product_id = int(data.split("_", 1)[1])
        except (ValueError, IndexError):
            await query.message.reply_text(
                "درخواست خرید نامعتبر است. ❌"
            )
            return

        product = get_product_by_id(product_id)

        if product is None:
            await query.message.reply_text(
                "محصول موردنظر پیدا نشد."
            )
            return

        if product[3] <= 0:
            await query.message.reply_text(
                "متأسفانه این محصول موجود نیست."
            )
            return

        context.user_data["pending_order_product_id"] = product_id
        context.user_data["order_step"] = "quantity"

        await query.message.reply_text(
            f"محصول انتخاب‌شده: {product[1]}\n"
            f"قیمت هر عدد: {product[2]:,} تومان\n"
            f"موجودی فعلی: {product[3]}\n\n"
            "چه تعدادی از این محصول می‌خوای؟"
        )
        return

    elif data.startswith("confirm_"):
        parts = data.split("_")

        if len(parts) != 4:
            await query.message.reply_text(
                "درخواست تأیید خرید نامعتبر است. ❌"
            )
            return

        try:
            product_id = int(parts[1])
            quantity = int(parts[2])
        except ValueError:
            await query.message.reply_text(
                "اطلاعات خرید نامعتبر است. ❌"
            )
            return

        confirmation_id = parts[3]

        if len(confirmation_id) != 32 or any(
            char not in "0123456789abcdef"
            for char in confirmation_id
        ):
            await query.message.reply_text(
                "شناسه تأیید خرید نامعتبر است. ❌"
            )
            return

        if quantity <= 0:
            await query.message.reply_text(
                "تعداد محصول نامعتبر است. ❌"
        )
            return

        pending_product_id = context.user_data.get(
           "pending_order_product_id"
        )
        pending_quantity = context.user_data.get(
           "pending_order_quantity"
        )
        pending_confirmation_id = context.user_data.get(
           "pending_confirmation_id"
        )

        if (
           product_id != pending_product_id
           or quantity != pending_quantity
           or confirmation_id != pending_confirmation_id
        ):
           await query.message.reply_text(
               "این درخواست معتبر نیست یا قبلاً پردازش شده است. ❌"
           )

           await query.edit_message_reply_markup(
               reply_markup=None
           )
           return

        user_id = query.from_user.id
        
        try:
            success = create_order(
            user_id,
            product_id,
            quantity,
            confirmation_id
        )

        except Exception:
            logging.exception("Error while creating order")
            success = "error"
        
        if success == "success":
           await query.message.reply_text(
               "خرید شما با موفقیت ثبت شد. ✅"
           )

        elif success == "duplicate":
           await query.message.reply_text(
               "این سفارش قبلاً ثبت شده است. ⚠️"
           )

        elif success == "unavailable":
           await query.message.reply_text(
               "محصول ناموجود است یا موجودی کافی نیست. ❌"
           )

        elif success == "invalid_quantity":
            await query.message.reply_text(
                "تعداد سفارش نامعتبر است. ❌"
            )

        elif success == "error":
            await query.message.reply_text(
                "هنگام ثبت سفارش خطایی رخ داد. لطفاً بعداً دوباره تلاش کنید. ❌"
            )

        context.user_data.pop("pending_order_product_id", None)
        context.user_data.pop("pending_order_quantity", None)
        context.user_data.pop("pending_confirmation_id", None)
        context.user_data.pop("order_step", None)

        await query.edit_message_reply_markup(
           reply_markup=None
        )

        return
    
    
    elif data in ("admin_orders_active", "admin_orders_cancelled"):
        if not is_admin(query.from_user.id):
            await query.message.reply_text("⛔ دسترسی غیرمجاز.")
            return


        orders = get_all_orders()

        if data == "admin_orders_active":
            selected_orders = [
                order for order in orders if order[7] == "active"
            ]
            title = "🟢 سفارش‌های فعال"

        else:
            selected_orders = [
                order for order in orders if order[7] == "cancelled"
            ]
            title = "❌ سفارش‌های لغوشده"

        if not selected_orders:
            await query.message.reply_text(
                f"{title}\n\nهیچ سفارشی در این بخش وجود ندارد."
            )
            return

        for order in selected_orders:
            (
                order_id,
                user_id,
                product_name,
                price,
                quantity,
                total_price,
                created_at,
                status
            ) = order

            message = (
                f"🆔 شناسه سفارش: {order_id}\n"
                f"👤 شناسه کاربر: {user_id}\n"
                f"📦 محصول: {product_name}\n"
                f"💰 قیمت واحد: {price:,} تومان\n"
                f"🔢 تعداد: {quantity}\n"
                f"💵 مبلغ کل: {total_price:,} تومان\n"
                f"🕒 تاریخ ثبت: {created_at}\n"
                f"📌 وضعیت سفارش: {'فعال' if status == 'active' else 'لغوشده'}"
            )

            if status == "active":
                keyboard = [[
                    InlineKeyboardButton(
                        text="❌ لغو سفارش",
                        callback_data=f"admin_cancel_order_{order_id}"
                    )
                ]]
                reply_markup = InlineKeyboardMarkup(keyboard)
            else:
                reply_markup = None

            await query.message.reply_text(
                message,
                reply_markup=reply_markup
            )

        return


    elif data.startswith("admin_cancel_order_"):
        if not is_admin(query.from_user.id):
            await query.message.reply_text("⛔ دسترسی غیرمجاز.")
            return

        try:
            order_id = int(data.rsplit("_", 1)[1])
        except (ValueError, IndexError):
            await query.message.reply_text("شناسه سفارش نامعتبر است.")
            return

        if order_id <= 0:
            await query.message.reply_text(
                "شناسه سفارش نامعتبر است."
            )
            return

        try:
            result = cancel_order(order_id)

        except Exception:
            logging.exception("Error while cancelling order")
            result = "error"

        if result == "success":
            await query.edit_message_text(
                query.message.text + "\n\n❌ وضعیت: لغوشده"
            )

        elif result == "already_cancelled":
            await query.edit_message_reply_markup(reply_markup=None)
            await query.message.reply_text("این سفارش قبلاً لغو شده است.")

        elif result == "not_found":
            await query.edit_message_reply_markup(reply_markup=None)
            await query.message.reply_text("سفارش موردنظر پیدا نشد.")

        elif result == "invalid_order_id":
            await query.message.reply_text(
                "شناسه سفارش نامعتبر است. ❌"
            )

        elif result == "product_not_found":
            await query.edit_message_reply_markup(reply_markup=None)
            await query.message.reply_text(
                "⛔ محصول این سفارش در دیتابیس پیدا نشد؛ موجودی بازنگشت."
            )

        elif result == "invalid_status":
            await query.edit_message_reply_markup(reply_markup=None)
            await query.message.reply_text(
                "⛔ وضعیت سفارش نامعتبر است؛ امکان لغو وجود ندارد."
            )

        elif result == "invalid_quantity":
            await query.edit_message_reply_markup(reply_markup=None)
            await query.message.reply_text(
                "تعداد ثبت‌شده برای این سفارش نامعتبر است. ❌"
            )

        elif result == "error":
            await query.message.reply_text(
                "هنگام لغو سفارش خطایی رخ داد. لطفاً دوباره تلاش کنید. ❌"
            )
        
        return
    
    elif data.startswith("cancel_"):

        try:
            product_id = int(data.split("_", 1)[1])
        except (ValueError, IndexError):
            await query.message.reply_text(
                "درخواست لغو خرید نامعتبر است. ❌"
            )
            return

        if (
            context.user_data.get("order_step") != "confirm"
            or context.user_data.get("pending_order_product_id") != product_id
        ):
            await query.message.reply_text(
                "این درخواست لغو معتبر نیست یا منقضی شده است. ❌"
            )
            return

        context.user_data.pop("pending_order_product_id", None)
        context.user_data.pop("pending_order_quantity", None)
        context.user_data.pop("pending_confirmation_id", None)
        context.user_data.pop("order_step", None)

        await query.message.reply_text(
            "خرید با موفقیت لغو شد. ❌"
        )

        await query.edit_message_reply_markup(
            reply_markup=None
        )

        return
    
        
def main():
    token = os.getenv("BOT_TOKEN")

    if not token:
        raise RuntimeError("BOT_TOKEN در فایل .env تنظیم نشده است.")

    create_table()

    add_image_column()

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("products", products))
    app.add_handler(CommandHandler("myorders", myorders))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(
    MessageHandler(filters.TEXT | filters.PHOTO, menu_handler))
    app.run_polling()


if __name__ == "__main__":
    main()


