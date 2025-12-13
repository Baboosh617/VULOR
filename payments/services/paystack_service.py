# payments/services/paystack_service.py
import os
import requests

class PaystackService:
    BASE_URL = "https://api.paystack.co"
    SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY")  # ensure loaded by Django settings/env

    @property
    def headers(self):
        return {
            "Authorization": f"Bearer {self.SECRET_KEY}",
            "Content-Type": "application/json",
        }

    def initialize_transaction(self, email, amount, reference, callback_url, metadata=None):
        """
        amount must be integer in kobo (i.e. Naira * 100)
        """
        url = f"{self.BASE_URL}/transaction/initialize"
        payload = {
            "email": email,
            "amount": int(amount),
            "reference": reference,
            "callback_url": callback_url,
        }
        if metadata:
            payload["metadata"] = metadata

        resp = requests.post(url, json=payload, headers=self.headers, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def verify_transaction(self, reference):
        url = f"{self.BASE_URL}/transaction/verify/{reference}"
        resp = requests.get(url, headers=self.headers, timeout=15)
        resp.raise_for_status()
        return resp.json()
