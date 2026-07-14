"""Excepciones propias del extractor."""


class StoreExtractorError(Exception):
    """Error base del proyecto."""


class InputValidationError(StoreExtractorError):
    """El archivo de entrada no cumple el contrato."""


class AdapterNotFoundError(StoreExtractorError):
    """No existe un adaptador para la cadena solicitada."""


class SourceResponseError(StoreExtractorError):
    """La fuente pública devolvió una respuesta inesperada."""


class OutputValidationError(StoreExtractorError):
    """Un adaptador devolvió una fila que no cumple el contrato."""
