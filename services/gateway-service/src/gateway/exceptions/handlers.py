class GatewayBaseError(Exception):
    """Error base del gateway de mensajería."""


class SNSPublishError(GatewayBaseError):
    """Error al publicar un mensaje en SNS."""


class DynamoDBError(GatewayBaseError):
    """Error al interactuar con DynamoDB."""


class TransactionNotFoundError(GatewayBaseError):
    """La transacción solicitada no existe."""


class TransactionValidationError(GatewayBaseError):
    """Los datos de la transacción no son válidos."""
