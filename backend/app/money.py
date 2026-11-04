"""Exact decimal calculator and deterministic allocations. Never evaluates Python."""
import re
from decimal import Decimal, InvalidOperation, localcontext, ROUND_HALF_UP

MAX_MINOR = 10**12
TOKEN = re.compile(r'\s*(?:(\d+(?:[.,]\d+)?)|([+*/()%\-]))')


def calculate(expression: str) -> Decimal:
    if not expression.strip() or len(expression) > 300:
        raise ValueError('Espressione vuota o troppo lunga')
    tokens = []
    cursor = 0
    while cursor < len(expression.rstrip()):
        match = TOKEN.match(expression, cursor)
        if not match:
            raise ValueError('Carattere non consentito')
        tokens.append(match.group(1) or match.group(2))
        cursor = match.end()
    if len(tokens) > 150:
        raise ValueError('Espressione troppo complessa')
    pos = 0

    def atom():
        nonlocal pos
        if pos >= len(tokens):
            raise ValueError('Espressione incompleta')
        token = tokens[pos]
        pos += 1
        if token in ('+', '-'):
            value = atom() * (-1 if token == '-' else 1)
        elif token == '(':
            value = expr()
            if pos >= len(tokens) or tokens[pos] != ')':
                raise ValueError('Parentesi non bilanciate')
            pos += 1
        else:
            try:
                value = Decimal(token.replace(',', '.'))
            except InvalidOperation:
                raise ValueError('Numero non valido') from None
        while pos < len(tokens) and tokens[pos] == '%':
            value /= 100
            pos += 1
        return value

    def term():
        nonlocal pos
        value = atom()
        while pos < len(tokens) and tokens[pos] in ('*', '/'):
            op = tokens[pos]
            pos += 1
            rhs = atom()
            if op == '/' and rhs == 0:
                raise ValueError('Divisione per zero')
            value = value * rhs if op == '*' else value / rhs
        return value

    def expr():
        nonlocal pos
        value = term()
        while pos < len(tokens) and tokens[pos] in ('+', '-'):
            op = tokens[pos]
            pos += 1
            rhs = term()
            value = value + rhs if op == '+' else value - rhs
        return value

    try:
        with localcontext() as ctx:
            ctx.prec = 40
            result = expr()
        if pos != len(tokens) or not result.is_finite() or abs(result) > Decimal(MAX_MINOR) / 100:
            raise ValueError('Risultato non valido o fuori limite')
        return result
    except (InvalidOperation, RecursionError, OverflowError):
        raise ValueError('Espressione non valida') from None


def minor(expression: str) -> int:
    return int((calculate(expression) * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def allocate(total: int, weights: dict[str, str], tie_order: list[str] | None = None) -> dict[str, int]:
    if not 0 < total <= MAX_MINOR or not weights:
        raise ValueError('Importo o partecipanti non validi')
    with localcontext() as ctx:
        ctx.prec = 60
        try:
            values = {key: Decimal(str(value)) for key, value in weights.items()}
        except InvalidOperation:
            raise ValueError('Quote non valide') from None
        if any(not value.is_finite() or value < 0 or value > 10**12 or value.as_tuple().exponent < -8 for value in values.values()):
            raise ValueError('Pesi non validi (massimo 8 decimali)')
        denominator = sum(values.values())
        if denominator <= 0:
            raise ValueError('Somma delle quote nulla')
        exact = {key: Decimal(total) * value / denominator for key, value in values.items()}
        out = {key: int(value) for key, value in exact.items()}
        rank={key:index for index,key in enumerate(tie_order or [])}
        order = sorted(out, key=lambda key: (-(exact[key] - out[key]), rank.get(key,len(rank)), key))
        for key in order[:total - sum(out.values())]:
            out[key] += 1
        assert sum(out.values()) == total
        return out
