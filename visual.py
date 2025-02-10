import threading
import os
from telebot import TeleBot

def send_product_media(bot, chat_id, product_name, media_path, media_type="photo", delete_after=120):
    """
    Envoie une image ou une vidéo avec une légende et la supprime après `delete_after` secondes.
    
    :param bot: Instance du bot Telegram
    :param chat_id: ID du chat où envoyer le média
    :param product_name: Nom du produit pour la légende
    :param media_path: Chemin du fichier média
    :param media_type: "photo" pour une image, "video" pour une vidéo
    :param delete_after: Durée avant suppression en secondes (120s = 2min par défaut)
    """
    if not os.path.exists(media_path):
        bot.send_message(chat_id, f"❌ {media_type.capitalize()} non disponible.")
        return

    with open(media_path, "rb") as media:
        if media_type == "photo":
            sent_message = bot.send_photo(chat_id, media, caption=f"📷 {product_name}")
        elif media_type == "video":
            sent_message = bot.send_video(chat_id, media, caption=f"🎥 {product_name}")
        else:
            bot.send_message(chat_id, "❌ Type de média non supporté.")
            return

    # Timer pour suppression après `delete_after` secondes
    threading.Timer(delete_after, delete_message, args=[bot, chat_id, sent_message.message_id]).start()


def delete_message(bot, chat_id, message_id):
    """
    Supprime un message après un délai.
    """
    try:
        bot.delete_message(chat_id, message_id)
        print(f"✅ Message {message_id} supprimé dans le chat {chat_id}.")
    except Exception as e:
        print(f"❌ Erreur lors de la suppression du message {message_id} : {e}")
