from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import threading
import time
user_cart = {}

def add_to_cart(bot, call, products):
    """Ajoute un produit au panier et affiche une confirmation."""
    _, product_key, weight, encoded_farm_name, encoded_subcategory, encoded_category = call.data.split("|")
    farm_name = encoded_farm_name.replace("%20", " ")
    subcategory = encoded_subcategory.replace("%20", " ")
    category = encoded_category.replace("%20", " ")

    user_id = call.message.chat.id
    product_data = products[category][subcategory][farm_name].get(product_key)

    if product_data:
        price = product_data["prix"].get(weight)
        if price:
            if user_id not in user_cart:
                user_cart[user_id] = []
            for item in user_cart[user_id]:
                if item["product"] == product_data["nom"] and item["weight"] == weight:
                    item["quantity"] += 1
                    bot.edit_message_text(
                        chat_id=call.message.chat.id,
                        message_id=call.message.message_id,
                        text=(
                            f"✅ Quantité mise à jour pour **{product_data['nom']} ({weight})**.\n"
                            f"Nouvelle quantité : {item['quantity']}."
                        ),
                        parse_mode="Markdown"
                    )
                    return
            user_cart[user_id].append({
                "product": product_data["nom"],
                "weight": weight,
                "quantity": 1,
                "price": price
            })
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"✅ Vous avez ajouté **{product_data['nom']} ({weight})** au panier pour {price}.",
                parse_mode="Markdown"
            )

            # Programmer la suppression dans 5 secondes (par exemple)
            delay = 5
            def delete_after_delay():
                time.sleep(delay)
                try:
                    bot.delete_message(call.message.chat.id, call.message.message_id)
                except Exception as e:
                    print(f"Erreur lors de la suppression du message : {e}")

            threading.Thread(target=delete_after_delay).start()

def view_cart(bot, call):
    """Affiche le panier avec une liste claire et le total."""
    user_id = call.message.chat.id
    cart = user_cart.get(user_id, [])

    if not cart:
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="🛒 Votre panier est vide.",
            reply_markup=InlineKeyboardMarkup().add(
                InlineKeyboardButton("⬅️ Retour au menu principal", callback_data="start")
            )
        )
        return

    cart_text = "🛒 **Votre panier :**\n"
    total = 0.0
    for index, item in enumerate(cart):
        try:
            cleaned_price = float(str(item["price"]).replace("-", "").replace(",", "."))
            line_total = cleaned_price * item["quantity"]
            total += line_total
            cart_text += (
                f"{index + 1}. {item['product']} ({item['weight']}) "
                f"- {item['quantity']}x {item['price']}.- = {line_total:.2f}.-\n"
            )
        except ValueError:
            bot.send_message(
                call.message.chat.id,
                f"Erreur de format de prix pour {item['product']} ({item['weight']})."
            )
            continue

    cart_text += f"\n**Total : {total:.2f}.-**"

    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("✏️ Modifier le panier", callback_data="edit_cart"),
        InlineKeyboardButton("✅ Commander et payer", callback_data="checkout"),
        InlineKeyboardButton("⬅️ Retour au menu principal", callback_data="start")
    )

    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=cart_text,
        parse_mode="Markdown",
        reply_markup=keyboard
    )

def edit_cart_item(bot, call, products):
    user_id = call.message.chat.id
    cart = user_cart.get(user_id, [])

    if not cart:
        bot.send_message(user_id, "Votre panier est vide.")
        return

    bot.send_message(
        user_id,
        "Veuillez entrer le **numéro de l'article** que vous souhaitez modifier (ex : 1).",
        parse_mode="Markdown"
    )

    @bot.message_handler(func=lambda message: message.chat.id == user_id and message.text.isdigit())
    def handle_edit_selection(message):
        index = int(message.text) - 1
        if index < 0 or index >= len(cart):
            bot.send_message(user_id, "Numéro invalide. Réessayez.")
            return

        item = cart[index]
        show_edit_options(bot, message, item, index, products)

def show_edit_options(bot, message, item, index, products):
    product_name = item["product"]
    product_weight = item["weight"]
    product_data = None

    for category, subcategories in products.items():
        for subcategory, farms in subcategories.items():
            for farm_name, farm_products in farms.items():
                for product_key, product_details in farm_products.items():
                    if product_details["nom"] == product_name:
                        product_data = product_details
                        break

    if not product_data:
        bot.send_message(message.chat.id, "Produit introuvable pour modification.")
        return

    keyboard = InlineKeyboardMarkup()
    for weight, price in product_data["prix"].items():
        keyboard.add(InlineKeyboardButton(f"{weight} - {price}", callback_data=f"update_cart|{index}|{weight}|{price}"))

    bot.send_message(
        message.chat.id,
        f"Modifier **{product_name} ({product_weight})**.\nChoisissez un nouveau poids et prix :",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

def delete_cart_item(bot, call):
    user_id = call.message.chat.id
    cart = user_cart.get(user_id, [])

    item_index = int(call.data.split("|")[1])
    if item_index >= len(cart):
        bot.send_message(user_id, "Article introuvable.")
        return

    removed_item = cart.pop(item_index)
    bot.send_message(
        user_id,
        f"L'article **{removed_item['product']} ({removed_item['weight']})** a été supprimé du panier.",
        parse_mode="Markdown"
    )
    view_cart(bot, call)

def update_cart_handler(bot, call):
    bot.answer_callback_query(call.id)
    _, index, new_weight, new_price = call.data.split("|")
    index = int(index)
    user_id = call.message.chat.id

    cart = user_cart.get(user_id, [])
    if index < 0 or index >= len(cart):
        bot.send_message(user_id, "Article introuvable.")
        return

    cart[index]["weight"] = new_weight
    cart[index]["price"] = new_price

    view_cart(bot, call)
