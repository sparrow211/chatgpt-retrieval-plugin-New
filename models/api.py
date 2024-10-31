from models.models import (
    Document,
    DocumentMetadataFilter,
    Query,
    QueryResult,
)
from pydantic import BaseModel
from typing import List, Optional


class UpsertRequest(BaseModel):
    documents: List[Document]


class UpsertResponse(BaseModel):
    ids: List[str]
    total_token: int


class QueryRequest(BaseModel):
    queries: List[Query]

class QueryRequest2(BaseModel):
    queries: List[Query]
    openai_api_key: Optional[str] = None

class QueryResponse(BaseModel):
    results: List[QueryResult]

class QueryResponse2(BaseModel):
    results: List[QueryResult]
    total_token: int

class DeleteRequest(BaseModel):
    ids: Optional[List[str]] = None
    filter: Optional[DocumentMetadataFilter] = None
    delete_all: Optional[bool] = False


class DeleteResponse(BaseModel):
    success: bool
