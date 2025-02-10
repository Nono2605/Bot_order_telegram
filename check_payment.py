import requests
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

BLOCKCYPHER_API_BASE = "https://api.blockcypher.com/v1/btc/main"

def check_btc_transaction(address, min_confirmations=1):
    """
    Vérifie les transactions entrantes pour une adresse Bitcoin via BlockCypher.
    :param address: Adresse Bitcoin à vérifier.
    :param min_confirmations: Nombre minimum de confirmations requises.
    :return: Détails de la transaction (dict).
    """
    url = f"{BLOCKCYPHER_API_BASE}/addrs/{address}/full"
    
    # DEBUG : Afficher l’URL complète
    print(f"[DEBUG] Check BTC Transaction - URL: {url}")

    response = requests.get(url)

    # DEBUG : Afficher le code de statut et la réponse brute
    print(f"[DEBUG] Response Status Code: {response.status_code}")
    print(f"[DEBUG] Response Text: {response.text}")

    if response.status_code != 200:
        raise Exception(f"Erreur API BlockCypher : {response.text}")

    transactions = response.json().get("txs", [])

    # DEBUG : Afficher la liste des transactions
    print(f"[DEBUG] Transactions: {transactions}")

    for tx in transactions:
        confirmations = tx.get("confirmations", 0)
        # DEBUG : Afficher le nombre de confirmations pour chaque tx
        print(f"[DEBUG] TX hash = {tx.get('hash')} | confirmations = {confirmations}")

        if confirmations >= min_confirmations:
            value = sum(
                output["value"]
                for output in tx["outputs"]
                if address in output.get("addresses", [])
            )
            # DEBUG : Afficher la valeur totale calculée pour cette transaction
            print(f"[DEBUG] Transaction confirmée ! Hash: {tx['hash']} | Value BTC: {value / 1e8}")
            return {
                "confirmed": True,
                "transaction_hash": tx["hash"],
                "value": value / 1e8,  # Convertir satoshis en BTC
            }

    # DEBUG : Aucun TX confirmé
    print("[DEBUG] Aucune transaction confirmée pour cette adresse.")
    return {"confirmed": False, "transaction_hash": None, "value": 0.0}


def process_payment(order_id, bot, orders, PRIVATE_CHANNEL_ID):
    order = orders.get(order_id)
    if not order:
        return "❌ Commande introuvable."

    btc_address = order.get("btc_address")
    if not btc_address:
        return "❌ Aucune adresse Bitcoin associée à cette commande."

    try:
        result = check_btc_transaction(btc_address)
        if result["confirmed"]:
            order["status"] = "paid"
            order["transaction_hash"] = result["transaction_hash"]

            # Notifier l'utilisateur
            bot.send_message(
                order["user_id"],
                f"✅ Paiement reçu pour la commande {order_id} !\n\n"
                f"Montant : {result['value']} BTC\n"
                f"Hash de transaction : `{result['transaction_hash']}`",
                parse_mode="Markdown",
            )

            # Mettre à jour le message admin
            if "admin_message_id" in order:
                try:
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

                    bot.edit_message_text(
                        chat_id=PRIVATE_CHANNEL_ID,
                        message_id=order["admin_message_id"],
                        text=(
                            f"💰 **Paiement confirmé** pour la commande {order_id} !\n\n"
                            f"📦 **Détails :**\n{cart_text}\n\n"
                            f"📍 **Infos livraison :**\n{delivery_text}\n"
                            f"💳 **Adresse Bitcoin :** {order['btc_address']}\n"
                            f"🔑 **Clé privée :** {order['private_key']}\n"
                            f"💰 **Montant total :** {result['value']} BTC\n\n"
                            f"Hash : `{result['transaction_hash']}`\n\n"
                            "Prochaine étape : Expédition ou Annulation ?"
                        ),
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup(row_width=2).add(
                            InlineKeyboardButton("🚚 Envoyer", callback_data=f"shipment_sent|{order_id}"),
                            InlineKeyboardButton("❌ Annuler la commande", callback_data=f"cancel_order|{order_id}")
                        )
                    )
                except Exception as e:
                    print(f"Impossible d'éditer le message admin : {e}")

            return "✅ Paiement confirmé !"
        else:
            # Ici, si `confirmed` est False
            return "❌ Paiement non détecté ou pas encore confirmé."
    except Exception as e:
        return f"❌ Erreur lors de la vérification du paiement : {e}"