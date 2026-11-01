from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

# argon2-cffi defaults to Argon2id with RFC 9106 low-memory parameters
_hasher = PasswordHasher()

MIN_PASSWORD_LENGTH = 10
MAX_PASSWORD_LENGTH = 128

# Used to equalize timing when the username does not exist
_DUMMY_HASH = _hasher.hash("dummy-password-for-timing")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def validate_new_password(password: str, username: str | None = None) -> str | None:
    """Return a Persian error message, or None if the password is acceptable."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"رمز عبور باید حداقل {MIN_PASSWORD_LENGTH} کاراکتر باشد."
    if len(password) > MAX_PASSWORD_LENGTH:
        return f"رمز عبور نباید بیش از {MAX_PASSWORD_LENGTH} کاراکتر باشد."
    if username and password.strip().lower() == username.strip().lower():
        return "رمز عبور نباید با نام کاربری یکسان باشد."
    return None
