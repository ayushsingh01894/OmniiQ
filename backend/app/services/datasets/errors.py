class DatasetError(Exception):
    """A problem with the user's data that is safe to show them (never includes cell values)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
