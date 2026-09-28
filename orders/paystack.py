import requests
from django.conf import settings

class PaystackAPI:
    def __init__(self):
        self.secret_key = settings.PAYSTACK_SECRET_KEY
        self.base_url = 'https://api.paystack.co'

    def initialize_transaction(self, email, amount, order_id, callback_url, metadata=None):
        """Tells Paystack an order is about to happen and requests a checkout URL."""
        url = f"{self.base_url}/transaction/initialize"
        headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json"
        }
        
        # Default to product if no specific metadata is provided
        if metadata is None:
            metadata = {"order_id": order_id, "type": "product"}
            
        data = {
            "email": email,
            "amount": int(amount * 100),
            "metadata": metadata,
            "callback_url": callback_url
        }
        
        response = requests.post(url, headers=headers, json=data)
        return response.json()

    def verify_transaction(self, reference):
        """Asks Paystack to confirm if a specific transaction was actually paid."""
        url = f"{self.base_url}/transaction/verify/{reference}"
        headers = {
            "Authorization": f"Bearer {self.secret_key}",
        }
        response = requests.get(url, headers=headers)
        return response.json()

    def create_transfer_recipient(self, name, account_number, bank_code):
        """Registers a vendor's bank account with Paystack to receive funds."""
        url = "https://api.paystack.co/transferrecipient"
        payload = {
            "type": "nuban",
            "name": name,
            "account_number": account_number,
            "bank_code": bank_code,
            "currency": "NGN"
        }
        response = requests.post(url, headers=self.headers, json=payload)
        return response.json()

    def initiate_transfer(self, amount_in_naira, recipient_code, reference, reason="Vendor Payout"):
        """Wires money from your Paystack balance to the registered recipient."""
        url = "https://api.paystack.co/transfer"
        # Paystack requires outbound transfers to be in Kobo (multiply by 100)
        amount_in_kobo = int(float(amount_in_naira) * 100)
        
        payload = {
            "source": "balance",
            "amount": amount_in_kobo,
            "recipient": recipient_code,
            "reason": reason,
            "reference": reference
        }
        response = requests.post(url, headers=self.headers, json=payload)
        return response.json()