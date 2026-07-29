"""Validação das respostas do check-in contra o protocolo do paciente.

Função pura (sem DB/HTTP), portanto testável: recebe as perguntas do protocolo
e o dicionário de respostas estruturadas e retorna a lista de problemas. Garante
que respostas obrigatórias existam, respeitem tipo/escala/opções e que não haja
perguntas fora do protocolo.

Perguntas do tipo FREE_TEXT não entram em `structured_responses` (são o campo
`free_text`/`audio_url` do check-in) e por isso são ignoradas aqui.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import QuestionType
from app.models.protocol import ProtocolQuestion


@dataclass(frozen=True)
class ResponseError:
    code: str
    message: str

    def as_dict(self) -> dict:
        return {"code": self.code, "message": self.message}


def _to_number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip().replace(",", "."))
        except ValueError:
            return None
    return None


def _validate_numeric(q: ProtocolQuestion, value: object, errors: list[ResponseError]) -> None:
    num = _to_number(value)
    if num is None:
        errors.append(ResponseError(q.code, "esperado um número"))
        return
    if q.type is QuestionType.INTEGER and not float(num).is_integer():
        errors.append(ResponseError(q.code, "esperado um número inteiro"))
        return
    options = q.options or {}
    minimum, maximum = options.get("min"), options.get("max")
    if minimum is not None and num < minimum:
        errors.append(ResponseError(q.code, f"valor abaixo do mínimo ({minimum})"))
    if maximum is not None and num > maximum:
        errors.append(ResponseError(q.code, f"valor acima do máximo ({maximum})"))


def _validate_choice(q: ProtocolQuestion, value: object, errors: list[ResponseError]) -> None:
    choices = (q.options or {}).get("choices")
    if isinstance(value, bool):
        # BOOLEAN aceita booleano nativo além das opções textuais (sim/nao).
        if q.type is QuestionType.BOOLEAN:
            return
        value = "sim" if value else "nao"
    normalized = str(value).strip().lower()
    if choices and normalized not in choices:
        errors.append(
            ResponseError(q.code, f"valor inválido; esperado um de: {', '.join(choices)}")
        )


def validate_responses(
    questions: list[ProtocolQuestion], responses: dict
) -> list[ResponseError]:
    responses = responses or {}
    errors: list[ResponseError] = []
    answerable = [q for q in questions if q.type is not QuestionType.FREE_TEXT]

    for q in answerable:
        value = responses.get(q.code)
        if value is None:
            if q.required:
                errors.append(ResponseError(q.code, "resposta obrigatória ausente"))
            continue

        if q.type in (QuestionType.SCALE, QuestionType.INTEGER):
            _validate_numeric(q, value, errors)
        elif q.type in (QuestionType.CHOICE, QuestionType.BOOLEAN):
            _validate_choice(q, value, errors)

    # Rejeita códigos que não pertencem ao protocolo (entrada inesperada).
    allowed = {q.code for q in answerable}
    for code in responses:
        if code not in allowed:
            errors.append(ResponseError(code, "pergunta não pertence ao protocolo ativo"))

    return errors
