import os
import openai
from typing import Optional
import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, Depends, Body, UploadFile
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from loguru import logger

from models.api import (
    DeleteRequest,
    DeleteResponse,
    QueryRequest,
    QueryRequest2,
    QueryResponse,
    QueryResponse2,
    UpsertRequest,
    UpsertResponse,
)
from datastore.factory import get_datastore
from services.file import get_document_from_file

from models.models import DocumentMetadata, Source,MyCustomError

bearer_scheme = HTTPBearer()
BEARER_TOKEN = os.environ.get("BEARER_TOKEN")
assert BEARER_TOKEN is not None


def validate_token(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    if credentials.scheme != "Bearer" or credentials.credentials != BEARER_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid or missing token")
    return credentials


app = FastAPI(dependencies=[Depends(validate_token)])
app.mount("/.well-known", StaticFiles(directory=".well-known"), name="static")



@app.post(
    "/upsert-file",
    response_model=UpsertResponse,
)
async def upsert_file(
    file: UploadFile = File(...),
    metadata: Optional[str] = Form(None),
    openai_api_key: Optional[str] = Form(None),
):
    try:
        metadata_obj = (
            DocumentMetadata.parse_raw(metadata)
            if metadata
            else DocumentMetadata(source=Source.file)
        )
    except:
        metadata_obj = DocumentMetadata(source=Source.file)
    if openai_api_key:
        openai.api_key = openai_api_key
    try:
        document = await get_document_from_file(file, metadata_obj)
        ids,total_token = await datastore.upsert([document])
        return UpsertResponse(ids=ids,total_token=total_token)
    except MyCustomError as e:
        raise HTTPException(status_code=400, detail=f"{e}")
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500, detail=f"{e}")


@app.post(
    "/upsert",
    response_model=UpsertResponse,
)
async def upsert(
    request: UpsertRequest = Body(...),
):
    try:
        ids,total_token = await datastore.upsert(request.documents)
        return UpsertResponse(ids=ids,total_token=total_token)
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500, detail="Internal Service Error")


@app.post(
    "/query",
    response_model=QueryResponse2,
)
async def query_main(
    request: QueryRequest2 = Body(...),
):
    if request.openai_api_key:
        openai.api_key = request.openai_api_key
    try:
        results,total_token = await datastore.query(
            request.queries,
        )
        return QueryResponse2(results=results,total_token=total_token)
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500, detail="Internal Service Error")



@app.delete(
    "/delete",
    response_model=DeleteResponse,
)
async def delete(
    request: DeleteRequest = Body(...),
):
    if not (request.ids or request.filter or request.delete_all):
        raise HTTPException(
            status_code=400,
            detail="One of ids, filter, or delete_all is required",
        )
    try:
        success = await datastore.delete(
            ids=request.ids,
            filter=request.filter,
            delete_all=request.delete_all,
        )
        return DeleteResponse(success=success)
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500, detail="Internal Service Error")


@app.on_event("startup")
async def startup():
    global datastore
    datastore = await get_datastore()


def start():
    uvicorn.run("server.main:app", host="0.0.0.0", port=8000, reload=True)
