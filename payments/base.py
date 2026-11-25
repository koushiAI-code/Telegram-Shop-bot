
from abc import ABC, abstractmethod


class PaymentGateway(ABC):

    @abstractmethod
    def create_payment(self, order_id, amount, currency):
        pass

    @abstractmethod
    def verify_payment(self, payment_id):
        pass
