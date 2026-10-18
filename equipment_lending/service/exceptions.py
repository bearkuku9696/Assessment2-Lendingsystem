class ValidationError(ValueError):
    pass


class AccessDeniedError(PermissionError):
    pass
