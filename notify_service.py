from typing import Optional
from logservice import systemlogger

class NotifyService:
    def init(self):
        self.client = None  # Se inyecta desde TelegramBot

    def set_client(self, client):
        self.client = client

    async def notifyuser(self, userid: int, text: str, disable_preview: bool = True):
        if not self.client:
            systemlogger.warning(f"No se pudo notificar a {userid}: cliente no inicializado")
            return
        try:
            await self.client.send_message(
                chatid=userid,
                text=text,
                disablewebpagepreview=disablepreview
            )
        except Exception as e:
            systemlogger.error(f"Error enviando notificación a {userid}: {e}")

notify_service = NotifyService()