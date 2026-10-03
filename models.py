class BankAccount:
    def __init__(self, account_id, customer_name, account_type, balance, is_active=True):
        self.account_id = account_id
        self.customer_name = customer_name
        self.account_type = account_type
        self.balance = balance
        self.is_active = is_active

    def to_dict(self):
        return {
            "account_id": self.account_id,
            "customer_name": self.customer_name,
            "account_type": self.account_type,
            "balance": str(self.balance),
            "is_active": self.is_active,
        }
