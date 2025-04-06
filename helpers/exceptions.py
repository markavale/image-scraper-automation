class WindscribeNotFoundException(Exception):
    """Raised when the Windscribe CLI cannot be found."""

    pass


class WindscribeNotRunningException(Exception):
    """Raised when the Windscribe service is not running."""

    pass


class UnknownVersionException(Exception):
    """Raised when the Windscribe version cannot be found."""

    pass


class UnsupportedVersionException(Exception):
    """Raised when the Windscribe version is not supported."""

    pass


class NotLoggedInException(Exception):
    """Raised when the user is not logged in."""

    pass


class ProAccountRequiredException(Exception):
    """Raised when the user try to use a pro account feature."""

    pass


class InvalidLocationException(Exception):
    """Raised when the user try to connect to an invalid location."""

    pass


class InvalidCredentialsException(Exception):
    """Raised when the credentials are invalid."""

    pass


class InvalidUsernameException(Exception):
    """Raised when the username is invalid."""

    pass


class InvalidPasswordException(Exception):
    """Raised when the password is invalid."""

    pass