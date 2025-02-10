from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import threading
import time


def create_main_menu(products):
    """Génère le menu principal."""
    keyboard = InlineKeyboardMarkup(row_width=2)
    for category in products.keys():
        encoded_category = category.replace(" ", "%20")
        keyboard.add(InlineKeyboardButton(category, callback_data=f"category|{encoded_category}"))
    keyboard.add(
        InlineKeyboardButton("🛒 Voir le panier", callback_data="view_cart"),
    )
    return keyboard

def handle_main_menu(bot, call, products):
    """Affiche les sous-catégories d'une catégorie."""
    _, encoded_category = call.data.split("|")
    category = encoded_category.replace("%20", " ")

    keyboard = InlineKeyboardMarkup(row_width=2)
    for subcategory in products[category]:
        encoded_subcategory = subcategory.replace(" ", "%20")
        keyboard.add(
            InlineKeyboardButton(
                subcategory,
                callback_data=f"subcategory|{encoded_subcategory}|{encoded_category}"
            )
        )
    keyboard.add(InlineKeyboardButton("⬅️ Retour au menu principal", callback_data="start"))
    bot.edit_message_text(
        f"Sélectionnez une sous-catégorie dans {category} :",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=keyboard
    )

def handle_subcategory_selection(bot, call, products):
    """Affiche les fermes d'une sous-catégorie."""
    _, encoded_subcategory, encoded_category = call.data.split("|")
    subcategory = encoded_subcategory.replace("%20", " ")
    category = encoded_category.replace("%20", " ")

    keyboard = InlineKeyboardMarkup(row_width=2)
    for farm_key in products[category][subcategory]:
        encoded_farm_key = farm_key.replace(" ", "%20")
        keyboard.add(
            InlineKeyboardButton(
                farm_key,
                callback_data=f"farm|{encoded_farm_key}|{encoded_subcategory}|{encoded_category}"
            )
        )
    keyboard.add(InlineKeyboardButton("⬅️ Retour à la catégorie", callback_data=f"category|{encoded_category}"))
    keyboard.add(InlineKeyboardButton("⬅️ Retour au menu principal", callback_data="start"))
    bot.edit_message_text(
        f"Sélectionnez une ferme dans {subcategory} :",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=keyboard
    )

def handle_farm_selection(bot, call, products):
    """Affiche les produits d'une ferme."""
    _, encoded_farm_name, encoded_subcategory, encoded_category = call.data.split("|")
    farm_name = encoded_farm_name.replace("%20", " ")
    subcategory = encoded_subcategory.replace("%20", " ")
    category = encoded_category.replace("%20", " ")

    keyboard = InlineKeyboardMarkup(row_width=1)
    for product_key, product_data in products[category][subcategory][farm_name].items():
        if isinstance(product_data, dict) and "nom" in product_data:
            keyboard.add(
                InlineKeyboardButton(
                    product_data["nom"],
                    callback_data=f"product|{product_key}|{encoded_farm_name}|{encoded_subcategory}|{encoded_category}"
                )
            )

    keyboard.add(InlineKeyboardButton("⬅️ Retour à la sous-catégorie", callback_data=f"subcategory|{encoded_subcategory}|{encoded_category}"))
    keyboard.add(InlineKeyboardButton("⬅️ Retour au menu principal", callback_data="start"))
    bot.edit_message_text(
        f"Produits disponibles dans la ferme {farm_name} :",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=keyboard
    )

def handle_product_selection(bot, call, products):
    """
    1. Si le message actuel ressemble à "Choisissez une option...", on suppose qu'on revient
       de la liste de prix => on édite ce même message.
    2. Sinon, on envoie un nouveau message (cas "première fois depuis la ferme").
    """

    _, product_key, encoded_farm_name, encoded_subcategory, encoded_category = call.data.split("|")
    farm_name = encoded_farm_name.replace("%20", " ")
    subcategory = encoded_subcategory.replace("%20", " ")
    category = encoded_category.replace("%20", " ")

    print(f"DEBUG: Catégorie = {category}, Sous-catégorie = {subcategory}, Ferme = {farm_name}, Produit = {product_key}")

    if category not in products or \
       subcategory not in products[category] or \
       farm_name not in products[category][subcategory] or \
       product_key not in products[category][subcategory][farm_name]:
        bot.answer_callback_query(call.id, "Produit introuvable.", show_alert=True)
        return

    product_data = products[category][subcategory][farm_name][product_key]
    if not product_data:
        bot.answer_callback_query(call.id, "Produit introuvable.", show_alert=True)
        return

    # -- Construire le texte de la fiche --
    details = (
        f"**{product_data['nom']}**\n"
        f"Type : {product_data['type']}\n"
        f"Provenance : {product_data['provenance']}\n"
        f"Terpènes : {product_data['terpenes']}\n"
        f"Goût : {product_data['gout']}\n"
        f"Note : {product_data['note']}/10\n"
        f"Prix : {', '.join([f'{k}: {v}' for k, v in product_data['prix'].items()])}\n"
        f"Disponibilité : {product_data.get('disponibilite', 'Non spécifié')}"
    )

    # -- Construire le clavier --
    callback_data = f"add_options|{product_key}|{encoded_farm_name}|{encoded_subcategory}|{encoded_category}"
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("➕ Ajouter au panier", callback_data=callback_data))

    if "image_path" in product_data:
        callback_data_image = f"view_image|{product_key}|{encoded_farm_name}|{encoded_subcategory}|{encoded_category}"
        keyboard.add(InlineKeyboardButton("📷 Voir l'image", callback_data=callback_data_image))

    # -- Vérifier d'où on vient --
    current_msg_text = call.message.text or ""

    if "Choisissez une option" in current_msg_text:
        # On suppose qu'on revient depuis la liste de prix
        # => On ÉDITE le message actuel
        try:
            sent_msg = bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=details,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
        except Exception as e:
            print(f"[DEBUG] Échec edit_message_text dans handle_product_selection : {e}")
            # Fallback : on envoie un nouveau message
            sent_msg = bot.send_message(
                chat_id=call.message.chat.id,
                text=details,
                parse_mode="Markdown",
                reply_markup=keyboard
            )

    else:
        # Première fois => on envoie un NOUVEAU message
        sent_msg = bot.send_message(
            chat_id=call.message.chat.id,
            text=details,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )

    # -- Timer de suppression (60 secondes) --
    def delete_message_after_delay(bot_instance, chat_id, msg_id, delay=60):
        time.sleep(delay)
        try:
            bot_instance.delete_message(chat_id, msg_id)
        except Exception as exc:
            print(f"Erreur lors de la suppression du message {msg_id} : {exc}")

    threading.Thread(
        target=delete_message_after_delay,
        args=(bot, sent_msg.chat.id, sent_msg.message_id, 60)
    ).start()

def handle_add_options(bot, call, products):
    """Affiche la liste des prix pour ajouter le produit au panier."""
    bot.answer_callback_query(call.id)
    _, product_key, encoded_farm_name, encoded_subcategory, encoded_category = call.data.split("|")
    farm_name = encoded_farm_name.replace("%20", " ")
    subcategory = encoded_subcategory.replace("%20", " ")
    category = encoded_category.replace("%20", " ")

    product_data = products[category][subcategory][farm_name].get(product_key)
    if product_data:
        keyboard = InlineKeyboardMarkup()
        for weight, price in product_data["prix"].items():
            keyboard.add(
                InlineKeyboardButton(
                    f"{weight} - {price}",
                    callback_data=(
                        f"add|{product_key}|{weight}|{encoded_farm_name}|"
                        f"{encoded_subcategory}|{encoded_category}"
                    )
                )
            )
        # Bouton "Retour au produit" -> renvoie au même handler que pour product|
        keyboard.add(
            InlineKeyboardButton(
                "⬅️ Retour au produit",
                callback_data=f"product|{product_key}|{encoded_farm_name}|{encoded_subcategory}|{encoded_category}"
            )
        )

        try:
            msg = bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"Choisissez une option pour ajouter **{product_data['nom']}** au panier :",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
        except Exception as e:
            # Au cas où l'on ne peut pas éditer (message introuvable par ex.)
            print(f"[DEBUG] Impossible d'éditer : {e}")
            msg = bot.send_message(
                call.message.chat.id,
                f"Choisissez une option pour ajouter **{product_data['nom']}** au panier :",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )

        # Timer de suppression (60s)
        def delete_message_after_delay(chat_id, message_id, delay=60):
            time.sleep(delay)
            try:
                bot.delete_message(chat_id, message_id)
            except Exception as e:
                print(f"Impossible de supprimer le message {message_id} : {e}")

        threading.Thread(
            target=delete_message_after_delay,
            args=(msg.chat.id, msg.message_id, 60)
        ).start()

    else:
        bot.answer_callback_query(call.id, "Produit introuvable.")
