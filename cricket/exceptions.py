class AuctionBaseException(Exception):
    """Base class for all auction related exceptions."""
    pass


class AuctionValidationException(AuctionBaseException):
    """Raised when general business validation fails."""
    pass


class AuctionBudgetException(AuctionBaseException):
    """Raised when team budget rules are violated."""
    pass


class AuctionStageException(AuctionBaseException):
    """Raised when invalid stage transition occurs."""
    pass