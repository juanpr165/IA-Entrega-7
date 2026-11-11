from __future__ import annotations

CRITICAL_TERMS = (
    "enviar", "publicar", "borrar", "eliminar", "pagar", "comprar", "transferir",
    "producción", "produccion", "desplegar", "deploy", "efecto secundario",
)


def is_critical_task(task: str) -> bool:
    normalized = task.casefold()
    return any(term in normalized for term in CRITICAL_TERMS)
