# payments/services/paystack_service.py

import os
import requests
from dotenv import load_dotenv

load_dotenv()  # load .env variables

class PaystackService:
    BASE_URL = "https://api.paystack.co"
    SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY")
    HEADERS = {
        "Authorization": f"Bearer {SECRET_KEY}",
        "Content-Type": "application/json",
    }

    def initialize_transaction(self, email, amount, reference, callback_url, metadata=None):
        """Initialize a Paystack transaction"""
        url = f"{self.BASE_URL}/transaction/initialize"
        payload = {
            "email": email,
            "amount": amount,
            "reference": reference,
            "callback_url": callback_url,
        }
        if metadata:
            payload["metadata"] = metadata

        response = requests.post(url, json=payload, headers=self.HEADERS)
        try:
            return response.json()
        except Exception:
            return {"status": False, "message": "Failed to parse Paystack response"}

    def verify_transaction(self, reference):
        """Verify a Paystack transaction"""
        url = f"{self.BASE_URL}/transaction/verify/{reference}"
        response = requests.get(url, headers=self.HEADERS)
        try:
            return response.json()
        except Exception:
            return {"status": False, "message": "Failed to parse Paystack response"}
