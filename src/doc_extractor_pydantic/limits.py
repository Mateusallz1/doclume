"""Limites locais aplicados antes de qualquer trabalho caro sobre o documento."""

from __future__ import annotations

MULTIPART_OVERHEAD_BYTES = 64 * 1024
"""Folga para o envelope multipart em torno do arquivo enviado."""

MAX_PDF_PAGES = 20
"""Páginas aceitas em um PDF de RG/CNH."""

MAX_PREVIEW_IMAGES = 4
"""Detalhes exibidos na interface."""

MAX_PREVIEW_SCAN_PAGES = 4
"""Páginas percorridas na busca por imagens incorporadas."""

MAX_PREVIEW_CANDIDATES = 24
"""Candidatas coletadas antes de ordenar e cortar."""

MAX_PREVIEW_PIXELS = 40_000_000
"""Pixels aceitos em uma imagem incorporada, medidos sem descomprimir."""

MAX_CONTENT_STREAM_BYTES = 8 * 1024 * 1024
"""Bytes descomprimidos aceitos no content stream de uma página."""

MIN_PREVIEW_SIDE = 200
"""Menor lado aceito para uma imagem virar detalhe."""

MAX_STREAM_OPERATIONS = 10_000
"""Limite de operadores percorridos no stream de uma página para evitar bloqueio da CPU."""

MAX_CONCURRENT_EXTRACTIONS = 2
"""Análises simultâneas aceitas por este processo."""

EXTRACTION_TIMEOUT_SECONDS = 90.0
"""Tempo total aceito para a resposta do provedor, já incluindo as tentativas."""

PROVIDER_RETRIES = 1
"""Tentativa adicional para saída inválida ou falha transitória do provider."""

PROVIDER_BACKOFF_SECONDS = 1.0
"""Espera inicial antes de repetir uma falha transitória do provider."""


def upload_limit_message(max_upload_bytes: int) -> str:
    return f"O arquivo excede o limite local de {max_upload_bytes / (1024 * 1024):g} MB."
