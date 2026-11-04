from datetime import date
from .exchange import CURRENCIES
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class PreferencesIn(Strict):
    theme: Literal['light','dark']


class GateIn(Strict):
    key: str = Field(min_length=1, max_length=256)


class Credentials(Strict):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)
    code: str = Field(default='', max_length=100)

    @field_validator('email')
    @classmethod
    def email_valid(cls, value):
        value = value.strip().lower()
        if value.count('@') != 1 or not all(value.split('@')) or any(c.isspace() for c in value):
            raise ValueError('Email non valida')
        return value


class Register(Credentials):
    name: str = Field(min_length=1, max_length=100)
    invite: str = Field(default='', max_length=100)

    @field_validator('name')
    @classmethod
    def name_valid(cls, value):
        if not value.strip():
            raise ValueError('Nome obbligatorio')
        return value.strip()

    @field_validator('password')
    @classmethod
    def strong(cls, value):
        if len(value) < 12:
            raise ValueError('Usa almeno 12 caratteri')
        return value


class GroupIn(Strict):
    name: str = Field(min_length=1, max_length=100)
    currency: str = 'EUR'

    @field_validator('currency')
    @classmethod
    def supported_currency(cls,value):
        if value not in CURRENCIES:raise ValueError('Valuta non supportata')
        return value


class ParticipantIn(Strict):
    name: str = Field(min_length=1, max_length=100)
    email: str | None = Field(default=None, max_length=254)
    role: Literal['admin', 'member', 'viewer'] = 'member'


class ItemIn(Strict):
    title: str = Field(default='', max_length=200)
    amount: str = Field(min_length=1, max_length=300)
    mode: Literal['equal', 'percent', 'exact', 'weight', 'quantity'] = 'equal'
    shares: dict[str, str] = Field(min_length=1, max_length=200)
    payers: dict[str, str] | None = Field(default=None, min_length=1, max_length=200)


class ExchangeContext(Strict):
    base:str=Field(min_length=3,max_length=3)
    quote:str=Field(min_length=3,max_length=3)
    rate:str=Field(min_length=1,max_length=40)
    source:str=Field(min_length=1,max_length=150)
    date:date


class ExpenseIn(Strict):
    allocation_order:list[str]|None=Field(default=None,min_length=1,max_length=200)
    exchange_context:ExchangeContext|None=None
    tags: list[str] = Field(default_factory=list,max_length=20)
    remember_expressions: bool = False

    @field_validator("tags")
    @classmethod
    def valid_tags(cls, values):
        result=[]
        for value in values:
            value=value.strip()
            if not value or len(value)>40: raise ValueError("Tag da 1 a 40 caratteri")
            if value.casefold() not in {v.casefold() for v in result}: result.append(value)
        return result

    currency: str | None = Field(default=None,max_length=3)
    exchange_rate: str | None = Field(default=None,max_length=40)
    exchange_token: str | None = Field(default=None,max_length=2000)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default='', max_length=4000)
    date: date
    category: str = Field(default='Altro', max_length=60)
    payers: dict[str, str] = Field(default_factory=dict, max_length=200)
    items: list[ItemIn] = Field(min_length=1, max_length=100)
    audience: list[str] | None = Field(default=None, min_length=1, max_length=200)


class CodeIn(Strict):
    code: str = Field(min_length=6, max_length=100)


class ExpressionIn(Strict):
    expression: str = Field(min_length=1, max_length=300)
