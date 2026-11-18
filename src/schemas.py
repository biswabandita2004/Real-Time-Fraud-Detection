"""Request schema shared by the HTTP API and the Kafka worker. Strict on purpose: unknown fields are rejected."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class Txn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    txn_id: str = Field(min_length=1, max_length=64)
    ts: float = Field(gt=0, description="event time, epoch seconds (the synthetic data uses seconds from 0)")
    account_id: str = Field(min_length=1, max_length=64)
    device_id: str = Field(min_length=1, max_length=64)
    merchant_id: str = Field(default="", max_length=64)
    merchant_cat: str = Field(min_length=1, max_length=32)
    amount: float = Field(gt=0, lt=1e9)
    country: str = Field(min_length=2, max_length=2)
    channel: Literal["pos", "online", "atm"]
