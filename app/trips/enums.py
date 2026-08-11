from enum import StrEnum


class TripStatus(StrEnum):
    """Status da viagem."""

    PLANNING = "planning"
    ONGOING = "ongoing"
    CLOSED = "closed"


class TripCategory(StrEnum):
    """Categorias fixas para gastos de viagem."""

    HOTEL = "hotel"
    TRANSPORT = "transport"
    TOUR = "tour"
    MEAL = "meal"
    SHOPPING = "shopping"
    LEISURE = "leisure"
    OTHER = "other"


class PaymentMethod(StrEnum):
    """Forma de pagamento de um gasto da viagem."""

    CASH = "cash"
    CARD = "card"
    TRANSFER = "transfer"
    OTHER = "other"
