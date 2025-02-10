import telebot
from utils.visual import (
    send_product_media,
)
from menu.products import products
from utils.cart_utils import (
    user_cart,
    add_to_cart,
    view_cart,
    edit_cart_item,
    delete_cart_item,
    update_cart_handler,
)
from utils.menu_utils import (
    create_main_menu,
    handle_main_menu,
    handle_subcategory_selection,
    handle_farm_selection,
    handle_product_selection,
    handle_add_options,
)
from utils.payment_utils import (
    confirm_order,
    accept_order,
    pay_order,
    send_qr_code,
    cancel_shipment,
    admin_confirm_order_callback,
    collect_shipping_info,
    orders,
)
from utils.check_payment import (
    process_payment,
    
)
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# Mettez l'ID de votre canal privé ici
PRIVATE_CHANNEL_ID = -1002452065791

bot = telebot.TeleBot("6264711973:AAEid4hVhHm15WrN-7LLzSOl_v69dBk-XTw")


def escape_markdown(text, version=2):
    """Escape special characters for Markdown/MarkdownV2."""
    if not isinstance(text, str):
        text = str(text)
    escape_chars = r"_*[]()~>#+-=|{}.!"
    if version == 2:
        escape_chars += r"\\"
    return "".join(f"\\{char}" if char in escape_chars else char for char in text)

# -------------------------#
#         COMMANDES        #
# -------------------------#

@bot.message_handler(commands=["start"])
def send_welcome(message):
    bot.reply_to(
        message,
        "Bienvenue ! Sélectionnez une catégorie de produits :",
        reply_markup=create_main_menu(products),
    )

# -------------------------#
#       MENUS & PANIER     #
# -------------------------#

@bot.callback_query_handler(func=lambda call: call.data.startswith("category|"))
def category_handler(call):
    handle_main_menu(bot, call, products)

@bot.callback_query_handler(func=lambda call: call.data.startswith("subcategory|"))
def subcategory_handler(call):
    handle_subcategory_selection(bot, call, products)

@bot.callback_query_handler(func=lambda call: call.data.startswith("farm|"))
def farm_handler(call):
    handle_farm_selection(bot, call, products)

@bot.callback_query_handler(func=lambda call: call.data.startswith("product|"))
def product_handler(call):
    handle_product_selection(bot, call, products)

@bot.callback_query_handler(func=lambda call: call.data.startswith("add_options|"))
def add_options_handler(call):
    handle_add_options(bot, call, products)

@bot.callback_query_handler(func=lambda call: call.data.startswith("add|"))
def add_to_cart_handler(call):
    add_to_cart(bot, call, products)

@bot.callback_query_handler(func=lambda call: call.data == "view_cart")
def view_cart_handler(call):
    view_cart(bot, call)

@bot.callback_query_handler(func=lambda call: call.data == "edit_cart")
def edit_cart_handler(call):
    edit_cart_item(bot, call, products)

@bot.callback_query_handler(func=lambda call: call.data.startswith("update_cart|"))
def update_cart_handler_callback(call):
    update_cart_handler(bot, call)

@bot.callback_query_handler(func=lambda call: call.data.startswith("delete|"))
def delete_cart_handler(call):
    delete_cart_item(bot, call)

# -------------------------#
#   VALIDATION & PAIEMENT  #
# -------------------------#

@bot.callback_query_handler(func=lambda call: call.data == "checkout")
def checkout_handler(call):
    confirm_order(bot, call, call.message.chat.id, user_cart)

@bot.callback_query_handler(func=lambda call: call.data.startswith("accept_order|"))
def accept_order_handler(call):
    order_id = call.data.split("|")[1]
    accept_order(bot, call, order_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("pay|"))
def pay_order_handler(call):
    order_id = call.data.split("|")[1]
    pay_order(bot, call, order_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("qr_code|"))
def qr_code_handler(call):
    order_id = call.data.split("|")[1]
    order = orders.get(order_id)
    if order:
        send_qr_code(bot, call, order["btc_address"])

@bot.callback_query_handler(func=lambda call: call.data.startswith("check_payment|"))
def handle_check_payment(call):
    bot.answer_callback_query(call.id)
    _, order_id = call.data.split("|")

    # Vérifier le paiement en appelant `process_payment()`
    result_message = process_payment(order_id, bot, orders, PRIVATE_CHANNEL_ID)

    # Envoyer le résultat à l'utilisateur
    bot.send_message(call.message.chat.id, result_message)

# -------------------------#
#  EXPÉDITION & ANNULATION #
# -------------------------#

@bot.callback_query_handler(func=lambda call: call.data.startswith("cancel_shipment|"))
def cancel_shipment_handler(call):
    order_id = call.data.split("|")[1]
    cancel_shipment(bot, call, order_id)


# -------------------------#
#    GESTION IMAGES/VIDE0  #
# -------------------------#

@bot.callback_query_handler(func=lambda call: call.data.startswith("view_image|") or call.data.startswith("view_video|"))
def handle_media_request(call):
    """
    Gère les demandes d'affichage des images et vidéos des produits.
    """
    data_parts = call.data.split("|")
    
    # Détecter si c'est une image ou une vidéo
    if call.data.startswith("view_image|"):
        media_type = "photo"
        media_key = "image_path"
        media_label = "📷 Image"
    elif call.data.startswith("view_video|"):
        media_type = "video"
        media_key = "video_path"
        media_label = "🎥 Vidéo"
    else:
        bot.answer_callback_query(call.id, "❌ Type de média non reconnu.", show_alert=True)
        return

    product_key, encoded_farm_name, encoded_subcategory, encoded_category = data_parts[1:]

    farm_name = encoded_farm_name.replace("%20", " ")
    subcategory = encoded_subcategory.replace("%20", " ")
    category = encoded_category.replace("%20", " ")

    product_data = products.get(category, {}).get(subcategory, {}).get(farm_name, {}).get(product_key)

    if not product_data:
        bot.answer_callback_query(call.id, "❌ Produit introuvable.", show_alert=True)
        return

    # Vérifier que le média existe
    if media_key in product_data and product_data[media_key]:
        delete_after = 120  # 2 minutes
        send_product_media(bot, call.message.chat.id, product_data["nom"], product_data[media_key], media_type, delete_after)
    else:
        bot.answer_callback_query(call.id, f"{media_label} non disponible.", show_alert=True)

# -------------------------#
#        AUTRES HANDLERS   #
# -------------------------#

@bot.callback_query_handler(func=lambda call: call.data == "start")
def restart_bot(call):
    bot.edit_message_text(
        text="Bienvenue ! Sélectionnez une catégorie de produits :",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=create_main_menu(products),
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("delivery_mode|"))
def handle_delivery_mode(call):
    bot.answer_callback_query(call.id)
    _, order_id, delivery_mode = call.data.split("|")
    order = orders.get(order_id)

    if not order:
        bot.send_message(call.message.chat.id, "Commande introuvable.")
        return

    order["delivery_mode"] = delivery_mode

    if delivery_mode == "livraison":
        # On édite le message principal pour dire qu'on va commencer la collecte d'infos
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=order["shipping_message_id"],
            text=(
                "🚚 Vous avez choisi **Livraison**.\n\n"
                "Nous allons vous poser quelques questions pour la livraison.\n"
                "Veuillez répondre dans le chat. Une fois vos informations complètes, "
                "nous mettrons à jour ce même message pour récapituler la commande."
            ),
            parse_mode="Markdown"
        )
        # On démarre la première question :
        sent_msg = bot.send_message(
            chat_id=order["user_id"], 
            text="Veuillez entrer votre nom :"
        )
        # IMPORTANT : on initialise la liste temp_messages
        order["temp_messages"] = []
        order["temp_messages"].append(sent_msg.message_id)

        bot.register_next_step_handler(sent_msg, lambda m: collect_shipping_info(bot, m, order_id, "nom"))
    
    else:
        # Click & Collect -> on édite immédiatement pour afficher la confirmation
        cart_text = "\n".join(
            f"- {item['product']} ({item['weight']}): {item['quantity']}x {item['price']}"
            for item in order["cart"]
        )
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=order["shipping_message_id"],
            text=(
                f"📦 Voici un récapitulatif de votre commande :\n\n"
                f"{cart_text}\n\n"
                "Mode de livraison : Click & Collect.\n\n"
                "Veuillez confirmer votre commande."
            ),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup().add(
                InlineKeyboardButton("✅ Confirmer la commande", callback_data=f"confirm_order|{order_id}")
            ),
        )

@bot.callback_query_handler(func=lambda call: call.data.startswith("confirm_order|"))
def confirm_order_final(call):
    bot.answer_callback_query(call.id)
    _, order_id = call.data.split("|")
    order = orders.get(order_id)

    if not order:
        bot.send_message(call.message.chat.id, "❌ Commande introuvable.")
        return

    order["status"] = "waiting_admin_validation"

    cart_text = "\n".join(
        f"- {item['product']} ({item['weight']}): {item['quantity']}x {item['price']}"
        for item in order["cart"]
    )
    if order["delivery_mode"] == "livraison":
        d = order["delivery_info"]
        delivery_text = (
            f"Mode de livraison : Livraison\n"
            f"Nom : {d.get('nom','N/A')}\n"
            f"Prénom : {d.get('prenom','N/A')}\n"
            f"Adresse : {d.get('adresse','N/A')}\n"
            f"Code postal : {d.get('code_postal','N/A')}\n"
            f"Ville : {d.get('ville','N/A')}\n"
            f"Pays : {d.get('pays','N/A')}\n"
        )
    else:
        delivery_text = "Mode de livraison : Click & Collect"

    # Éditer le message de l'utilisateur pour "En attente de validation"
    try:
        bot.edit_message_text(
            chat_id=order["user_id"],
            message_id=order["shipping_message_id"],
            text=(
                f"✅ Votre commande {order_id} a été soumise et est en attente de validation.\n\n"
                f"📦 Détails de la commande :\n{cart_text}\n\n"
                f"{delivery_text}\n"
                "🕒 Statut : En attente de validation."
            ),
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"Erreur lors de l'édition du message: {e}")

    # On associe shipping_message_id à confirmation_message_id (pour admin_confirm_order)
    order["confirmation_message_id"] = order["shipping_message_id"]

    # Envoi dans le canal privé
    admin_message = bot.send_message(
        PRIVATE_CHANNEL_ID,
        text=(
            f"Nouvelle commande en attente de validation !\n\n"
            f"**Commande ID :** {order_id}\n\n"
            f"📦 **Détails :**\n{cart_text}\n\n"
            f"📍 **Infos livraison :**\n{delivery_text}\n"
            f"💳 **Adresse Bitcoin :** {order['btc_address']}\n"
            f"🔑 **Clé privée :** {order['private_key']}\n"
            f"💰 **Montant total :** {order['total_btc']} BTC\n\n"
            "Confirmez-vous cette commande ?"
        ),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(row_width=2).add(
            InlineKeyboardButton("✅ Confirmer", callback_data=f"admin_confirm_order|{order_id}"),
            InlineKeyboardButton("❌ Rejeter", callback_data=f"admin_reject_order|{order_id}")
        )
    )
    order["admin_message_id"] = admin_message.message_id

@bot.callback_query_handler(func=lambda call: call.data.startswith("mark_as_paid|"))
def mark_as_paid_handler(call):
    order_id = call.data.split("|")[1]
    order = orders.get(order_id)

    if not order:
        bot.answer_callback_query(call.id, "Commande introuvable.", show_alert=True)
        return

    cart_text = "\n".join(
        f"- {item['product']} ({item['weight']}): {item['quantity']}x {item['price']}"
        for item in order["cart"]
    )
    if order["delivery_mode"] == "livraison":
        delivery_text = (
            f"Mode de livraison : {order['delivery_mode']}\n"
            f"Nom : {order['delivery_info'].get('nom', 'N/A')}\n"
            f"Prénom : {order['delivery_info'].get('prenom', 'N/A')}\n"
            f"Adresse : {order['delivery_info'].get('adresse', 'N/A')}\n"
            f"Code postal : {order['delivery_info'].get('code_postal', 'N/A')}\n"
            f"Ville : {order['delivery_info'].get('ville', 'N/A')}\n"
            f"Pays : {order['delivery_info'].get('pays', 'N/A')}"
        )
    else:
        delivery_text = "Mode de livraison : Click & Collect"

    order["status"] = "paid"

    # Notifier l'utilisateur
    bot.send_message(
        order["user_id"],
        f"✅ Votre paiement pour la commande {order_id} a été reçu !\n\n"
        f"Merci pour votre confiance. Votre commande sera bientôt expédiée ! 🚚",
    )

    # Mettre à jour dans le canal privé
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=(
            f"✅ La commande {order_id} a été marquée comme payée !\n\n"
            f"📦 **Détails de la commande :**\n{cart_text}\n\n"
            f"📍 **Adresse de livraison :**\n{delivery_text}\n\n"
            f"💳 Adresse Bitcoin : {order['btc_address']}\n"
            f"🔑 Clé privée : {order['private_key']}\n\n"
            "📦 **Statut : En attente d'expédition.** 🕒"
        ),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("🚚 Colis envoyé", callback_data=f"shipment_sent|{order_id}"),
            InlineKeyboardButton("❌ Annuler la commande", callback_data=f"cancel_order|{order_id}")
        ),
    )
    bot.answer_callback_query(call.id, "Commande marquée comme payée.")

@bot.callback_query_handler(func=lambda call: call.data.startswith("cancel_order|"))
def cancel_order_handler(call):
    order_id = call.data.split("|")[1]
    order = orders.get(order_id)

    if not order:
        bot.answer_callback_query(call.id, "Commande introuvable.", show_alert=True)
        return

    cart_text = "\n".join(
        f"- {item['product']} ({item['weight']}): {item['quantity']}x {item['price']}"
        for item in order["cart"]
    )

    if order["delivery_mode"] == "livraison":
        delivery_text = (
            f"Mode de livraison : {order['delivery_mode']}\n"
            f"Nom : {order['delivery_info'].get('nom', 'N/A')}\n"
            f"Prénom : {order['delivery_info'].get('prenom', 'N/A')}\n"
            f"Adresse : {order['delivery_info'].get('adresse', 'N/A')}\n"
            f"Code postal : {order['delivery_info'].get('code_postal', 'N/A')}\n"
            f"Ville : {order['delivery_info'].get('ville', 'N/A')}\n"
            f"Pays : {order['delivery_info'].get('pays', 'N/A')}"
        )
    else:
        delivery_text = "Mode de livraison : Click & Collect"

    # Supprimer la commande
    orders.pop(order_id, None)

    # Mise à jour dans le canal privé
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=(
            f"❌ La commande {order_id} a été annulée.\n\n"
            f"📦 **Détails de la commande :**\n{cart_text}\n\n"
            f"📍 **Adresse de livraison :**\n{delivery_text}\n\n"
            f"💳 Adresse Bitcoin : {order['btc_address']}\n"
            f"🔑 Clé privée : {order['private_key']}\n\n"
            "❌ **Statut : Commande annulée.**"
        ),
        parse_mode="Markdown",
    )
    bot.answer_callback_query(call.id, "Commande annulée.")


@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_confirm_order|"))
def admin_confirm_order(call):
    """
    Gère la commande 'admin_confirm_order|...' en délégant la logique
    à la fonction du fichier utils/payment_utils.py
    """
    admin_confirm_order_callback(bot, call)

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_reject_order|"))
def admin_reject_order(call):
    """Handles admin rejection of an order."""
    _, order_id = call.data.split("|")
    order = orders.get(order_id)

    if not order:
        bot.answer_callback_query(call.id, "Commande introuvable.", show_alert=True)
        return

    # On peut afficher un récap avant de rejeter, etc.
    orders.pop(order_id, None)

    bot.send_message(
        chat_id=order["user_id"],
        text=f"❌ Votre commande {order_id} a été rejetée. Merci de nous contacter pour plus d'informations."
    )

    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"❌ La commande {order_id} a été rejetée par l'administrateur.",
        parse_mode="Markdown"
    )

    bot.answer_callback_query(call.id, "Commande rejetée.")

# -------------------------#
#   SHIPMENT SENT HANDLER
# -------------------------#

@bot.callback_query_handler(func=lambda call: call.data.startswith("shipment_sent|"))
def shipment_sent_handler(call):
    order_id = call.data.split("|")[1]
    order = orders.get(order_id)

    if not order:
        bot.answer_callback_query(call.id, "Commande introuvable.", show_alert=True)
        return

    order["status"] = "shipped"
    user_id = order["user_id"]

    # Réinitialiser le panier de l'utilisateur
    user_cart[user_id] = []  # Vider le panier
    print(f"DEBUG: Panier utilisateur {user_id} après expédition : {user_cart[user_id]}")

    # Supprimer la commande après expédition si nécessaire
    del orders[order_id]
    print(f"DEBUG: Commande {order_id} supprimée.")

    # Notifier l'utilisateur que sa commande a été expédiée
    bot.send_message(
        user_id,
        f"📦 Bonjour, votre commande {order_id} a été expédiée ! 🚚"
    )
    bot.send_message(
        user_id,
        f"Pour passer une nouvelle commande : /start"
    )
    # Générer les détails
    cart_text = "\n".join(
        f"- {item['product']} ({item['weight']}): {item['quantity']}x {item['price']}"
        for item in order["cart"]
    ) or "Aucun article dans cette commande."

    if order["delivery_mode"] == "livraison":
        delivery_text = (
            f"Mode de livraison : {order['delivery_mode']}\n"
            f"Nom : {order['delivery_info'].get('nom', 'N/A')}\n"
            f"Prénom : {order['delivery_info'].get('prenom', 'N/A')}\n"
            f"Adresse : {order['delivery_info'].get('adresse', 'N/A')}\n"
            f"Code postal : {order['delivery_info'].get('code_postal', 'N/A')}\n"
            f"Ville : {order['delivery_info'].get('ville', 'N/A')}\n"
            f"Pays : {order['delivery_info'].get('pays', 'N/A')}"
        )
    else:
        delivery_text = "Mode de livraison : Click & Collect"

    # Mettre à jour le message canal privé
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=(
            f"✅ La commande {order_id} a été marquée comme expédiée !\n\n"
            f"📍 **Adresse de livraison :**\n{delivery_text}\n\n"
            f"💳 Adresse Bitcoin : {order['btc_address']}\n"
            f"🔑 Clé privée : {order['private_key']}\n\n"
            f"👤 **Utilisateur :** {user_id}\n"
            "📦 **Statut : Colis envoyé** ✅"
        ),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("✅ Envoi confirmé", callback_data="disabled")
        ),
    )

    # Confirmer l'action auprès de l'administrateur
    bot.answer_callback_query(call.id, "Colis marqué comme expédié.")

if __name__ == "__main__":
    print("Le bot démarre...")
    bot.polling(none_stop=True, interval=0)
