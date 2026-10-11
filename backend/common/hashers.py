"""Password hashing tuned for a small, CPU-throttled deployment.

Django 5.0's default Argon2 parameters (memory_cost=102400 KiB ≈ 100 MB,
time_cost=2, parallelism=8) are sized for beefy servers. On a free
PythonAnywhere worker (~1/10 of a core, hard memory ceiling) a single
hash can stall for many seconds or spike memory — enough that a login or
registration request appears to hang forever in the browser.

This hasher keeps Argon2id (memory-hard, GPU-resistant) but with lean
parameters: ~16 MB, two passes, single lane. It stays the "default" so
`set_password` / `make_password` (including the security-answer hash)
use it automatically, while the stock Argon2 entry remains in
PASSWORD_HASHERS so existing 100 MB hashes still verify.
"""
from django.contrib.auth.hashers import Argon2PasswordHasher


class FastArgon2PasswordHasher(Argon2PasswordHasher):
    """Argon2id with 16 MB memory instead of the default 100 MB."""

    time_cost = 2
    memory_cost = 16384  # KiB (16 MB)
    parallelism = 1
