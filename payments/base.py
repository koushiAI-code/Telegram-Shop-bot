from abc import ABC, abstractmethod


class PaymentGateway(ABC):

    @abstractmethod
    def create_payment(self, payment, idempotency_key):
        pass

    @abstractmethod
    def verify_payment(self, payment):
        pass