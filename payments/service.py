from database import (
    get_payment_by_id,
    process_payment_result,
    save_payment_transaction_id
)


class PaymentService:

    def __init__(self, gateway):

        self.gateway = gateway

    def start_payment(self, payment_id):

        payment = get_payment_by_id(payment_id)

        if isinstance(payment, str):
            return {
                "success": False,
                "error": payment
            }

        if payment["status"] != "pending":
            return {
                "success": False,
                "error": "payment_not_pending"
            }

        # جلوگیری از ایجاد مجدد تراکنشی که قبلاً ثبت شده
        if payment["transaction_id"] is not None:
            return {
                "success": True,
                "payment_id": payment_id,
                "transaction_id": payment["transaction_id"],
                "already_started": True
            }

        try:
            idempotency_key = f"shop_payment_{payment_id}"

            gateway_response = self.gateway.create_payment(
                payment,
                idempotency_key
            )

        except Exception:
            return {
                "success": False,
                "error": "gateway_connection_error",
                "payment_id": payment_id
            }

        if not isinstance(gateway_response, dict):
            return {
                "success": False,
                "error": "invalid_gateway_response"
            }

        if gateway_response.get("payment_id") != payment_id:
            return {
                "success": False,
                "error": "payment_id_mismatch"
            }

        if gateway_response.get("status") != "pending":
            return {
                "success": False,
                "error": "invalid_gateway_status"
            }

        if gateway_response.get("order_id") != payment["order_id"]:
            return {
                "success": False,
                "error": "order_id_mismatch"
            }

        if gateway_response.get("amount") != payment["amount"]:
            return {
                "success": False,
                "error": "payment_amount_mismatch"
            }

        if gateway_response.get("currency") != payment["currency"]:
            return {
                "success": False,
                "error": "payment_currency_mismatch"
            }

        transaction_id = gateway_response.get("transaction_id")

        if (
            not isinstance(transaction_id, str)
            or not transaction_id.strip()
        ):
            return {
                "success": False,
                "error": "invalid_transaction_id"
            }

        save_result = save_payment_transaction_id(
            payment_id,
            transaction_id
        )

        if save_result not in ("success", "already_saved"):
            return {
                "success": False,
                "error": save_result,
                "payment_id": payment_id
            }

        return {
            "success": True,
            "payment_id": payment_id,
            "transaction_id": transaction_id,
            "payment_url": gateway_response.get("payment_url")
        }

    def verify_payment(self, payment_id):

        payment = get_payment_by_id(payment_id)

        if isinstance(payment, str):
            return {
                "success": False,
                "error": payment
            }

        if payment["status"] != "pending":
            return {
                "success": False,
                "error": "payment_not_pending"
            }

        if payment["transaction_id"] is None:
            return {
                "success": False,
                "error": "transaction_not_started"
            }

        try:
            gateway_response = self.gateway.verify_payment(
                payment
            )

        except Exception:
            return {
                "success": False,
                "error": "gateway_connection_error",
                "payment_id": payment_id
            }

        if not isinstance(gateway_response, dict):
            return {
                "success": False,
                "error": "invalid_gateway_response"
            }

        gateway_payment_id = gateway_response.get("payment_id")

        if type(gateway_payment_id) is not int or gateway_payment_id <= 0:
            return {
                "success": False,
                "error": "invalid_gateway_payment_id"
            }

        if gateway_payment_id != payment_id:
            return {
                "success": False,
                "error": "payment_id_mismatch"
            }

        gateway_transaction_id = gateway_response.get("transaction_id")

        if (
            not isinstance(gateway_transaction_id, str)
            or not gateway_transaction_id.strip()
        ):
            return {
                "success": False,
                "error": "invalid_gateway_transaction_id"
            }

        if gateway_transaction_id != payment["transaction_id"]:
            return {
                "success": False,
                "error": "transaction_id_mismatch"
            }

        gateway_order_id = gateway_response.get("order_id")

        if type(gateway_order_id) is not int or gateway_order_id <= 0:
            return {
                "success": False,
                "error": "invalid_gateway_order_id"
            }

        if gateway_order_id != payment["order_id"]:
            return {
                "success": False,
                "error": "order_id_mismatch"
            }

        gateway_amount = gateway_response.get("amount")

        if type(gateway_amount) is not int:
            return {
                "success": False,
                "error": "invalid_gateway_amount"
            }

        if gateway_amount != payment["amount"]:
            return {
                "success": False,
                "error": "payment_amount_mismatch"
            }

        gateway_currency = gateway_response.get("currency")

        if (
            not isinstance(gateway_currency, str)
            or not gateway_currency.strip()
        ):
            return {
                "success": False,
                "error": "invalid_gateway_currency"
            }

        if gateway_currency != payment["currency"]:
            return {
                "success": False,
                "error": "payment_currency_mismatch"
            }

        result = gateway_response.get("status")

        if not isinstance(result, str):
            return {
                "success": False,
                "error": "invalid_gateway_status"
            }

        if result not in ("paid", "failed", "pending"):
            return {
                "success": False,
                "error": "invalid_gateway_status"
            }

        response = process_payment_result(
            payment_id,
            result
        )

        return {
            "success": response in (
                "success",
                "failed_and_cancelled",
                "success_product_missing",
                "still_pending",
                "payment_review"
            ),
            "payment_id": payment_id,
            "gateway_status": result,
            "processing_result": response
        }