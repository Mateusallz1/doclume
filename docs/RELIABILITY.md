# Confiabilidade

## Operação esperada

- Host local: `127.0.0.1`.
- Porta padrão: `8788`.
- Configuração: `.env` carregado pelo comando do Uvicorn.
- Entradas: PDF, JPG, JPEG e PNG até 15 MB.
- Resultado: sempre sujeito à revisão humana.

## Dependências críticas

1. O servidor FastAPI precisa estar ativo.
2. O provider configurado precisa aceitar entrada multimodal e estar autenticado.
3. A rede externa precisa estar disponível para providers remotos.
4. A resposta precisa obedecer ao modelo `DocumentExtraction`.

## Falhas conhecidas

- Provider indisponível, quota excedida ou timeout resulta em erro genérico HTTP
  502 para o navegador.
- O piloto não possui limite de páginas, rate limit ou fila de concorrência.
- O retry do agente pode repetir uma chamada quando a saída não é válida.
- A extração de imagens incorporadas é uma melhoria de prévia; se falhar, o PDF
  não impede a análise, e a interface informa que não há detalhe ampliado.
- A camada gratuita do provider pode apresentar variação de latência e políticas
  próprias de uso de dados.

Esses limites devem ser tratados antes de qualquer uso multiusuário ou produção.
