from typing import Dict, List, Optional, Tuple
import uuid
import os
from models.models import Document, DocumentChunk, DocumentChunkMetadata
from loguru import logger
import tiktoken
import re

from services.openai import get_embeddingsTop,get_embeddings

# Global variables
tokenizer = tiktoken.get_encoding(
    "cl100k_base"
)  # The encoding scheme to use for tokenization

# Constants
CHUNK_SIZE = 200  # The target size of each text chunk in tokens
MIN_CHUNK_SIZE_CHARS = 350  # The minimum size of each text chunk in characters
MIN_CHUNK_LENGTH_TO_EMBED = 5  # Discard chunks shorter than this
EMBEDDINGS_BATCH_SIZE = int(
    os.environ.get("OPENAI_EMBEDDING_BATCH_SIZE", 128)
)  # The number of embeddings to request at a time
MAX_NUM_CHUNKS = 10000  # The maximum number of chunks to generate from a text


def get_text_chunks(text: str, chunk_token_size: Optional[int]) -> List[str]:
    """
    Split a text into chunks of ~CHUNK_SIZE tokens, based on punctuation and newline boundaries.

    Args:
        text: The text to split into chunks.
        chunk_token_size: The target size of each chunk in tokens, or None to use the default CHUNK_SIZE.

    Returns:
        A list of text chunks, each of which is a string of ~CHUNK_SIZE tokens.
    """
    # Return an empty list if the text is empty or whitespace
    if not text or text.isspace():
        return []

    # Tokenize the text
    tokens = tokenizer.encode(text, disallowed_special=())

    # Initialize an empty list of chunks
    chunks = []

    # Use the provided chunk token size or the default one
    chunk_size = chunk_token_size or CHUNK_SIZE

    # Initialize a counter for the number of chunks
    num_chunks = 0

    # Loop until all tokens are consumed
    while tokens and num_chunks < MAX_NUM_CHUNKS:
        # Take the first chunk_size tokens as a chunk
        chunk = tokens[:chunk_size]

        # Decode the chunk into text
        chunk_text = tokenizer.decode(chunk)

        # Skip the chunk if it is empty or whitespace
        if not chunk_text or chunk_text.isspace():
            # Remove the tokens corresponding to the chunk text from the remaining tokens
            tokens = tokens[len(chunk) :]
            # Continue to the next iteration of the loop
            continue

        # Find the last period or punctuation mark in the chunk
        last_punctuation = max(
            chunk_text.rfind("."),
            chunk_text.rfind("?"),
            chunk_text.rfind("!"),
            chunk_text.rfind("\n"),
        )

        # If there is a punctuation mark, and the last punctuation index is before MIN_CHUNK_SIZE_CHARS
        if last_punctuation != -1 and last_punctuation > MIN_CHUNK_SIZE_CHARS:
            # Truncate the chunk text at the punctuation mark
            chunk_text = chunk_text[: last_punctuation + 1]

        # Remove any newline characters and strip any leading or trailing whitespace
        chunk_text_to_append = chunk_text.replace("\n", " ").strip()

        if len(chunk_text_to_append) > MIN_CHUNK_LENGTH_TO_EMBED:
            # Append the chunk text to the list of chunks
            chunks.append(chunk_text_to_append)

        # Remove the tokens corresponding to the chunk text from the remaining tokens
        tokens = tokens[len(tokenizer.encode(chunk_text, disallowed_special=())) :]

        # Increment the number of chunks
        num_chunks += 1

    # Handle the remaining tokens
    if tokens:
        remaining_text = tokenizer.decode(tokens).replace("\n", " ").strip()
        if len(remaining_text) > MIN_CHUNK_LENGTH_TO_EMBED:
            chunks.append(remaining_text)

    return chunks


def create_document_chunks(
    doc: Document, chunk_token_size: Optional[int]
) -> Tuple[List[DocumentChunk], str]:
    """
    Create a list of document chunks from a document object and return the document id.

    Args:
        doc: The document object to create chunks from. It should have a text attribute and optionally an id and a metadata attribute.
        chunk_token_size: The target size of each chunk in tokens, or None to use the default CHUNK_SIZE.

    Returns:
        A tuple of (doc_chunks, doc_id), where doc_chunks is a list of document chunks, each of which is a DocumentChunk object with an id, a document_id, a text, and a metadata attribute,
        and doc_id is the id of the document object, generated if not provided. The id of each chunk is generated from the document id and a sequential number, and the metadata is copied from the document object.
    """
    # Check if the document text is empty or whitespace
    if not doc.text or doc.text.isspace():
        return [], doc.id or str(uuid.uuid4())

    # Generate a document id if not provided
    doc_id = doc.id or str(uuid.uuid4())
    logger.info(f"生成docId: {doc_id}")

    # Split the document text into chunks
    text_chunks = get_text_chunks(doc.text, chunk_token_size)

    metadata = (
        DocumentChunkMetadata(**doc.metadata.__dict__)
        if doc.metadata is not None
        else DocumentChunkMetadata()
    )

    metadata.document_id = doc_id

    # Initialize an empty list of chunks for this document
    doc_chunks = []

    # Assign each chunk a sequential number and create a DocumentChunk object
    for i, text_chunk in enumerate(text_chunks):
        chunk_id = f"{doc_id}_{i}"
        metadata.page=extract_page_number(text_chunk)
        doc_chunk = DocumentChunk(
            id=chunk_id,
            text=text_chunk,
            metadata=metadata
        )
        # Append the chunk object to the list of chunks for this document
        doc_chunks.append(doc_chunk)

    # Return the list of chunks and the document id
    return doc_chunks, doc_id


def get_document_chunks(
    documents: List[Document], chunk_token_size: Optional[int]
) -> Tuple[Dict[str, List[DocumentChunk]], int]:
    """
    Convert a list of documents into a dictionary from document id to list of document chunks.

    Args:
        documents: The list of documents to convert.
        chunk_token_size: The target size of each chunk in tokens, or None to use the default CHUNK_SIZE.

    Returns:
        A dictionary mapping each document id to a list of document chunks, each of which is a DocumentChunk object
        with text, metadata, and embedding attributes.
    """
    # Initialize an empty dictionary of lists of chunks
    chunks: Dict[str, List[DocumentChunk]] = {}
    total_tokens: int = 0
    logger.info(f"初始化对象 total_tokens: {total_tokens}")

    # Initialize an empty list of all chunks
    all_chunks: List[DocumentChunk] = []

    # 循环浏览每份文档并创建文档块
    for doc in documents:
        doc_chunks, doc_id = create_document_chunks(doc, chunk_token_size)

        # Append the chunks for this document to the list of all chunks
        all_chunks.extend(doc_chunks)

        # Add the list of chunks for this document to the dictionary with the document id as the key
        chunks[doc_id] = doc_chunks

    # 检查是否没有数据块
    logger.info(f"检查是否没有数据块")
    if not all_chunks:
        return {},0

    # 使用 get_embeddings 分批获取文档块的所有嵌入信息
    embeddings: List[List[float]] = []
    for i in range(0, len(all_chunks), EMBEDDINGS_BATCH_SIZE):
        # Get the text of the chunks in the current batch
        batch_texts = [
            chunk.text for chunk in all_chunks[i : i + EMBEDDINGS_BATCH_SIZE]
        ]
        
        # Get the embeddings for the batch texts
        #batch_embeddings2,total_usage = get_embeddings(batch_texts)
        #logger.info("向量: " + str(total_usage))
        batch_embeddings, usage = get_embeddingsTop(batch_texts)
        total_tokens += usage
        # Append the batch embeddings to the embeddings list
        embeddings.extend(batch_embeddings)

    # Update the document chunk objects with the embeddings
    for i, chunk in enumerate(all_chunks):
        # Assign the embedding from the embeddings list to the chunk object
        chunk.embedding = embeddings[i]
    logger.info("total_tokens: " + str(total_tokens))
    return chunks,total_tokens

def extract_page_number(text_chunk:str) -> int:
    page_match = re.search(r"\[\[P(\d+)\]\]", text_chunk)
    if page_match:
        page_number = int(page_match.group(1))
        return page_number
    else:
        return 1