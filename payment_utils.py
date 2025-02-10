import random
import os
import requests
import qrcode
from datetime import datetime
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from bitcoinlib.keys import Key

# On stocke le canal privé ici, si besoin
PRIVATE_CHANNEL_ID = -1002410522101

# Dictionnaire pour stocker toutes les commandes
orders = {}

def generate_order_id():
    now = datetime.now()
    return f"ORD-{now.strftime('%Y%m%d-%H%M%S')}-{random.randint(1000, 9999)}"

def generate_btc_wallet():
    key = Key()
    private_key = key.wif()
    btc_address = key.address()
    return private_key, btc_address

def generate_qr_code(address):
    qr = qrcode.make(address)
    qr_file_path = f"{address}.png"
    qr.save(qr_file_path)
    return qr_file_path

def get_current_btc_price_in_chf():
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": "bitcoin",
        "vs_currencies": "chf"
    }
    try:
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        return float(data["bitcoin"]["chf"])
    except Exception as e:
        print(f"Erreur lors de la récupération du prix BTC : {e}")
        # En cas d’erreur, vous pouvez décider de renvoyer None,
        # une valeur par défaut, ou gérer différemment
        return None

def confirm_order(bot, call, user_id, user_cart):
    cart = user_cart.get(user_id, [])
    if not cart:
        bot.answer_callback_query(call.id, "Votre panier est vide.", show_alert=True)
        return

    order_id = generate_order_id()
    private_key, btc_address = generate_btc_wallet()

    total_fiat = 0.0
    for item in cart:
        try:
            cleaned_price = float(str(item["price"]).replace("-", "").replace(",", "."))
            total_fiat += cleaned_price * item["quantity"]
        except:
            pass

    # Récupération du prix actuel du BTC
    current_btc_price_chf = get_current_btc_price_in_chf()
    if current_btc_price_chf is None:
        # Ici vous pouvez gérer ce cas (ex. envoyer un message d'erreur à l'utilisateur)
        bot.answer_callback_query(
            call.id,
            "Impossible de récupérer le prix BTC pour le moment, réessayez plus tard.",
            show_alert=True
        )
        return

    # Conversion fiat -> BTC en se basant sur le cours actuel
    total_btc = 0.0
    if total_fiat > 0:
        total_btc = round(total_fiat / current_btc_price_chf, 6)

    # On stocke la commande
    orders[order_id] = {
        "user_id": user_id,
        "cart": cart,
        "btc_address": btc_address,
        "private_key": private_key,
        "total_btc": total_btc,
        "status": "pending",
        "delivery_mode": None,
        "delivery_info": {},
        "shipping_message_id": call.message.message_id
    }

    # Proposer le mode de livraison
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("🚚 Livraison", callback_data=f"delivery_mode|{order_id}|livraison"),
        InlineKeyboardButton("🏠 Click & Collect", callback_data=f"delivery_mode|{order_id}|collect")
    )

    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=(
            "Sélectionnez votre mode de livraison :\n\n"
            f"**Total à payer estimé : {total_fiat:.2f} CHF**\n"
            f"(~{total_btc} BTC)"
        ),
        parse_mode="Markdown",
        reply_markup=keyboard
    )

def accept_order(bot, call, order_id):
    bot.answer_callback_query(call.id)
    order = orders.get(order_id)
    if not order:
        bot.answer_callback_query(call.id, "Commande introuvable.", show_alert=True)
        return
    
    # Démo, pas forcément utilisé
    bot.send_message(call.message.chat.id, f"Commande {order_id} acceptée (WIP).")

def pay_order(bot, call, order_id):
    order = orders.get(order_id)
    if not order:
        bot.answer_callback_query(call.id, "Commande introuvable.", show_alert=True)
        return

    btc_address = order["btc_address"]
    bot.send_message(
        call.message.chat.id,
        f"💳 Voici l'adresse Bitcoin : {btc_address}",
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("📷 QR Code", callback_data=f"qr_code|{order_id}")
        ),
    )

def send_qr_code(bot, call, btc_address):
    qr_file_path = generate_qr_code(btc_address)
    with open(qr_file_path, "rb") as qr_file:
        bot.send_photo(call.message.chat.id, qr_file, caption="📷 QR Code pour paiement")
    os.remove(qr_file_path)

def cancel_shipment(bot, call, order_id):
    order = orders.get(order_id)
    if not order:
        bot.answer_callback_query(call.id, "Commande introuvable.", show_alert=True)
        return

    order["status"] = "paid"
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"❌ Envoi annulé pour la commande {order_id}. Statut remis à 'paid'.",
        reply_markup=None,
    )


# -----------------------------#
#   Collecte infos de livraison
# -----------------------------#

def collect_shipping_info(bot, message, order_id, step):
    order = orders.get(order_id)
    if not order:
        bot.send_message(message.chat.id, "Erreur : commande introuvable.")
        return

    # On stocke le message_id de la réponse de l'utilisateur
    if "temp_messages" not in order:
        order["temp_messages"] = []
    order["temp_messages"].append(message.message_id)

    # On enregistre la valeur saisie
    order["delivery_info"][step] = message.text.strip()

    if step == "nom":
        sent_msg = bot.send_message(message.chat.id, "Veuillez entrer votre prénom :")
        order["temp_messages"].append(sent_msg.message_id)
        bot.register_next_step_handler(sent_msg, lambda msg: collect_shipping_info(bot, msg, order_id, "prenom"))

    elif step == "prenom":
        sent_msg = bot.send_message(message.chat.id, "Veuillez entrer votre rue et numéro :")
        order["temp_messages"].append(sent_msg.message_id)
        bot.register_next_step_handler(sent_msg, lambda msg: collect_shipping_info(bot, msg, order_id, "adresse"))

    elif step == "adresse":
        sent_msg = bot.send_message(message.chat.id, "Veuillez entrer votre code postal :")
        order["temp_messages"].append(sent_msg.message_id)
        bot.register_next_step_handler(sent_msg, lambda msg: collect_shipping_info(bot, msg, order_id, "code_postal"))

    elif step == "code_postal":
        sent_msg = bot.send_message(message.chat.id, "Veuillez entrer votre ville :")
        order["temp_messages"].append(sent_msg.message_id)
        bot.register_next_step_handler(sent_msg, lambda msg: collect_shipping_info(bot, msg, order_id, "ville"))

    elif step == "ville":
        sent_msg = bot.send_message(message.chat.id, "Veuillez entrer votre pays :")
        order["temp_messages"].append(sent_msg.message_id)
        bot.register_next_step_handler(sent_msg, lambda msg: collect_shipping_info(bot, msg, order_id, "pays"))

    elif step == "pays":
        # Supprimer tous les messages d'étapes
        for m_id in order["temp_messages"]:
            try:
                bot.delete_message(chat_id=order["user_id"], message_id=m_id)
            except Exception as e:
                print(f"Erreur lors de la suppression du message {m_id}: {e}")

        order["temp_messages"].clear()

        cart_text = "\n".join(
            f"- {item['product']} ({item['weight']}): {item['quantity']}x {item['price']}"
            for item in order["cart"]
        )
        delivery_text = (
            f"Nom : {order['delivery_info']['nom']}\n"
            f"Prénom : {order['delivery_info']['prenom']}\n"
            f"Adresse : {order['delivery_info']['adresse']}\n"
            f"Code postal : {order['delivery_info']['code_postal']}\n"
            f"Ville : {order['delivery_info']['ville']}\n"
            f"Pays : {order['delivery_info']['pays']}"
        )

        try:
            bot.edit_message_text(
                chat_id=order["user_id"],
                message_id=order["shipping_message_id"],
                text=(
                    f"📦 Voici un récapitulatif de votre commande :\n\n{cart_text}\n\n"
                    "Mode de livraison : Livraison\n\n"
                    f"{delivery_text}\n\n"
                    "Veuillez confirmer votre commande."
                ),
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup().add(
                    InlineKeyboardButton("✅ Confirmer la commande", callback_data=f"confirm_order|{order_id}")
                )
            )
        except Exception as e:
            print(f"Erreur lors de l'édition du message principal: {e}")

        update_private_channel_with_delivery(bot, order_id)


def update_private_channel_with_delivery(bot, order_id):
    order = orders.get(order_id)
    if not order:
        return

    delivery_mode = order.get("delivery_mode", "")
    info = order.get("delivery_info", {})
    if delivery_mode == "livraison":
        delivery_text = (
            f"Mode de livraison : Livraison\n"
            f"Nom : {info.get('nom','N/A')}\n"
            f"Prénom : {info.get('prenom','N/A')}\n"
            f"Adresse : {info.get('adresse','N/A')}\n"
            f"Code Postal : {info.get('code_postal','N/A')}\n"
            f"Ville : {info.get('ville','N/A')}\n"
            f"Pays : {info.get('pays','N/A')}"
        )
    else:
        delivery_text = "Mode de livraison : Click & Collect"

    try:
        bot.send_message(
            PRIVATE_CHANNEL_ID,
            f"📦 Mise à jour de la commande {order_id}.\n\n{delivery_text}"
        )
    except Exception as e:
        print(f"Impossible d'envoyer la mise à jour au canal privé : {e}")

# utils/payment_utils.py

...

# On suppose que vos variables "orders" et "PRIVATE_CHANNEL_ID" sont déjà définies ici.

def admin_confirm_order_callback(bot, call):
    """Traite la logique de confirmation d'une commande par l'admin."""
    _, order_id = call.data.split("|")
    order = orders.get(order_id)

    if not order:
        bot.answer_callback_query(call.id, "Commande introuvable.", show_alert=True)
        return

    order["status"] = "confirmed"

    user_chat_id = order["user_id"]
    msg_id_to_edit = order.get("confirmation_message_id")

    cart_text = "\n".join(
        f"- {item['product']} ({item['weight']}): {item['quantity']}x {item['price']}"
        for item in order["cart"]
    )

    if order["delivery_mode"] == "livraison":
        d = order["delivery_info"]
        delivery_text = (
            f"Mode de livraison : {order['delivery_mode']}\n"
            f"Nom : {d.get('nom','N/A')}\n"
            f"Prénom : {d.get('prenom','N/A')}\n"
            f"Adresse : {d.get('adresse','N/A')}\n"
            f"Code postal : {d.get('code_postal','N/A')}\n"
            f"Ville : {d.get('ville','N/A')}\n"
            f"Pays : {d.get('pays','N/A')}\n"
        )
    else:
        delivery_text = "Mode de livraison : Click & Collect"

    # Éditer le message utilisateur (si on a un msg_id)
    if msg_id_to_edit:
        try:
            bot.edit_message_text(
                chat_id=user_chat_id,
                message_id=msg_id_to_edit,
                text=(
                    f"✅ Votre commande {order_id} a été confirmée par notre équipe !\n\n"
                    f"📦 **Détails de la commande :**\n{cart_text}\n\n"
                    f"📍 **Adresse de livraison :**\n{delivery_text}\n\n"
                    f"💳 **Paiement requis :**\n"
                    f"Adresse Bitcoin : {order['btc_address']}\n"
                    f"Montant total : {order['total_btc']} BTC\n\n"
                    "Cliquez sur le bouton ci-dessous pour voir le QR Code de paiement."
                ),
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup().add(
                    InlineKeyboardButton("📷 Voir QR Code", callback_data=f"qr_code|{order_id}")
                )
            )
        except Exception as e:
            print(f"Erreur lors de l'édition du message chez l'utilisateur: {e}")
            bot.send_message(
                chat_id=user_chat_id,
                text="✅ Votre commande a été confirmée, mais l'édition du message a échoué."
            )
    else:
        # Sinon, on envoie simplement un nouveau message
        bot.send_message(
            chat_id=user_chat_id,
            text=(
                f"✅ Votre commande {order_id} a été confirmée par notre équipe !\n\n"
                f"📦 Détails :\n{cart_text}"
            ),
            parse_mode="Markdown"
        )

    # Mise à jour du message dans le canal privé
    try:
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=(
                f"✅ La commande {order_id} a été confirmée par l'administrateur.\n\n"
                f"**Commande ID :** {order_id}\n\n"
                f"📦 **Détails :**\n{cart_text}\n\n"
                f"📍 **Infos livraison :**\n{delivery_text}\n"
                f"💳 **Adresse Bitcoin :** {order['btc_address']}\n"
                f"🔑 **Clé privée :** {order['private_key']}\n"
                f"💰 **Montant total :** {order['total_btc']} BTC\n\n"
                f"**Statut :** Paiement en attente."
            ),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(row_width=2).add(
                InlineKeyboardButton("⏳ Vérifier paiement", callback_data=f"check_payment|{order_id}"),
                InlineKeyboardButton("✅ Forcer paiement", callback_data=f"mark_as_paid|{order_id}"),
                InlineKeyboardButton("❌ Annuler la commande", callback_data=f"cancel_order|{order_id}")
            )
        )
    except Exception as e:
        print(f"Erreur lors de l'édition du message privé admin : {e}")

    bot.answer_callback_query(call.id, "Commande confirmée.")
