"""
Utilidades compartidas para scripts de migración.
"""
from ulid import ULID


def generate_id() -> str:
    """
    Genera un nuevo ID usando ULID.

    ULID (Universally Unique Lexicographically Sortable Identifier):
    - 128 bits como UUID pero ordenable cronológicamente
    - Formato: 26 caracteres en base32 (ej: 01ARZ3NDEKTSV4RRFFQ69G5FAV)
    - Componentes: timestamp (48 bits) + random (80 bits)

    Returns:
        str: ULID en formato string lowercase
    """
    return str(ULID()).lower()
