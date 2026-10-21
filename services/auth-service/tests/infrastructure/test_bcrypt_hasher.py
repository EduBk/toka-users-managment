from infrastructure.security.bcrypt_hasher import BcryptPasswordHasher


def test_hash_is_not_the_plain_password() -> None:
    hasher = BcryptPasswordHasher()

    password_hash = hasher.hash("secret")

    assert password_hash != "secret"
    assert password_hash.startswith("$2")


def test_verify_accepts_the_right_password() -> None:
    hasher = BcryptPasswordHasher()
    password_hash = hasher.hash("secret")

    assert hasher.verify("secret", password_hash) is True


def test_verify_rejects_a_wrong_password() -> None:
    hasher = BcryptPasswordHasher()
    password_hash = hasher.hash("secret")

    assert hasher.verify("wrong", password_hash) is False
