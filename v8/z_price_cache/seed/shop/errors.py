class ShopError(Exception):
    pass


class UnknownProduct(ShopError):
    def __init__(self, sku):
        super().__init__(f"unknown product: {sku}")
        self.sku = sku


class UnknownCustomer(ShopError):
    def __init__(self, cid):
        super().__init__(f"unknown customer: {cid}")
        self.cid = cid
