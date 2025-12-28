import json
from channels.generic.websocket import AsyncWebsocketConsumer

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope["user"]
        if not user.is_authenticated or not user.is_staff:
            await self.close()
            return
        self.group_name = "admin_notifications"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()


    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    # Receive notifications from the group
    async def send_notification(self, event):
        await self.send(text_data=json.dumps(event["message"]))

        self.rate_limit = 20