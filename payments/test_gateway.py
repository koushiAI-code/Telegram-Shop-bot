from payments.base import PaymentGateway

from database import (
    set_test_payment_result,
    get_test_payment_result
)


class TestPaymentGateway(PaymentGateway):

    def __init__(self):
        self.created_payments = {}

    def create_payment(self, payment, idempotency_key):

        if idempotency_key in self.created_payments:
            return self.created_payments[idempotency_key]

        response = {
            "payment_id": payment["id"],
            "order_id": payment["order_id"],
            "amount": payment["amount"],
            "currency": payment["currency"],
            "transaction_id": f"test_{payment['id']}",
            "payment_url": None,
            "idempotency_key": idempotency_key,
            "status": "pending"
        }

        self.created_payments[idempotency_key] = response

        return response
    
    def verify_payment(self, payment):

        payment_id = payment["id"]

        result = get_test_payment_result(payment_id)

        if result in ("not_found", "pending"):
            result = "pending"
        elif result == "invalid_payment_id":
            result = "error"

        response = {
            "payment_id": payment_id,
            "order_id": payment["order_id"],
            "amount": payment["amount"],
            "currency": payment["currency"],
            "transaction_id": payment["transaction_id"],
            "status": result
        }

        return response

    def simulate_result(self, payment_id, result):

        response = set_test_payment_result(
            payment_id,
            result
        )

        if response != "success":
            return {
                "success": False,
                "error": response
            }

        return {
            "success": True,
            "payment_id": payment_id,
            "status": result
        }