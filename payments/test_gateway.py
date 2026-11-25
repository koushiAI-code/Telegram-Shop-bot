

from payments.base import PaymentGateway

from database import (
    set_test_payment_result,
    get_test_payment_result
)


class TestPaymentGateway(PaymentGateway):

    def create_payment(self, order_id, amount, currency):

        return {
            "order_id": order_id,
            "amount": amount,
            "currency": currency,
            "status": "pending"
        }

    def verify_payment(self, payment_id):

        result = get_test_payment_result(payment_id)

        if result in ("not_found", "pending"):
            return {
                "payment_id": payment_id,
                "status": "pending"
            }

        if result == "invalid_payment_id":
            return {
                "payment_id": payment_id,
                "status": "error"
            }

        return {
            "payment_id": payment_id,
            "status": result
        }

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
