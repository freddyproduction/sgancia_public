from decimal import Decimal
import pytest
from hypothesis import given, strategies as st
from app.money import calculate, minor, allocate


@pytest.mark.parametrize('expression,expected', [('12,50 + 8,90 + 4,20',2560), ('(10+5)*2',3000), ('100 * 20%',2000), ('1/3',33), ('0.005',1), ('-1,005',-101)])
def test_calculator(expression, expected):
    assert minor(expression) == expected


@pytest.mark.parametrize('expression', ['__import__("os")', '1/0', '2**4', '(1+2', '1..2', 'NaN', '9'*301, '2(3)', ''])
def test_unsafe_and_invalid(expression):
    with pytest.raises(ValueError): calculate(expression)


def test_rounding_stable():
    assert allocate(100, {'c':'1','a':'1','b':'1'}) == {'c':33,'a':34,'b':33}


@given(st.integers(1,10**12), st.lists(st.integers(0,100000), min_size=1, max_size=50).filter(lambda v: sum(v)>0))
def test_conservation(total, values):
    weights = {str(i):str(v) for i,v in enumerate(values)}
    result = allocate(total, weights)
    assert sum(result.values()) == total
    assert all(v>=0 for v in result.values())
    assert result == allocate(total, dict(reversed(list(weights.items()))))
