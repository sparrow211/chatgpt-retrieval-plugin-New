from typing import List,Tuple
import openai
import os
from loguru import logger

from tenacity import retry, wait_random_exponential, stop_after_attempt

EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-large")


@retry(wait=wait_random_exponential(min=1, max=20), stop=stop_after_attempt(3))
def get_embeddings(texts: List[str]) -> Tuple[List[List[float]], int]:
    """
    Embed texts using OpenAI's ada model.

    Args:
        texts: The list of texts to embed.

    Returns:
        A list of embeddings, each of which is a list of floats.

    Raises:
        Exception: If the OpenAI API call fails.
    """
    # Call the OpenAI API to get the embeddings
    # NOTE: Azure Open AI requires deployment id
    deployment = os.environ.get("OPENAI_EMBEDDINGMODEL_DEPLOYMENTID")

    response = {}
    if deployment is None:
        response = openai.Embedding.create(input=texts, model=EMBEDDING_MODEL)
    else:
        response = openai.Embedding.create(input=texts, deployment_id=deployment)

    # Extract the embedding data from the response
    data = response["data"]  # type: ignore
    
    # Extract the total usage from the response
    total_usage = response["usage"]["total_tokens"]  # type: ignore
    logger.info("请求AI向量api_base: " +openai.api_base)

    # Return the embeddings as a list of lists of floats and total usage
    return [result["embedding"] for result in data], total_usage

@retry(wait=wait_random_exponential(min=1, max=20), stop=stop_after_attempt(3))
def get_embeddingsTop(texts: List[str]) -> Tuple[List[List[float]], int]:
    """
    Embed texts using OpenAI's ada model.

    Args:
        texts: The list of texts to embed.

    Returns:
        A list of embeddings, each of which is a list of floats.

    Raises:
        Exception: If the OpenAI API call fails.
    """
    # Call the OpenAI API to get the embeddings
    # NOTE: Azure Open AI requires deployment id
    deployment = os.environ.get("OPENAI_EMBEDDINGMODEL_DEPLOYMENTID")
    response = {}
    try:
        if deployment == None:
            response = openai.Embedding.create(input=texts, model=EMBEDDING_MODEL)
        else:
            response = openai.Embedding.create(input=texts, deployment_id=deployment)
    except Exception as e:
        logger.info("请求AI向量api_base: " +openai.api_base)
        logger.error("请求AI向量错误: " +str(e))
        raise e

    # Extract the embedding data from the response
    data = response["data"]  # type: ignore
    # Extract the usage count from the response
    usage = int(response["usage"]["total_tokens"])

    # Return the embeddings as a list of lists of floats
    #return [result["embedding"] for result in data]
    return [result["embedding"] for result in data], usage

@retry(wait=wait_random_exponential(min=1, max=20), stop=stop_after_attempt(3))
def get_chat_completion(
    messages,
    model="gpt-4o-mini",  # use "gpt-4" for better results
    deployment_id = None
):
    """
    Generate a chat completion using OpenAI's chat completion API.

    Args:
        messages: The list of messages in the chat history.
        model: The name of the model to use for the completion. Default is gpt-3.5-turbo, which is a fast, cheap and versatile model. Use gpt-4 for higher quality but slower results.

    Returns:
        A string containing the chat completion.

    Raises:
        Exception: If the OpenAI API call fails.
    """
    # call the OpenAI chat completion API with the given messages
    # Note: Azure Open AI requires deployment id
    response = {}
    if deployment_id == None:
        response = openai.ChatCompletion.create(
            model=model,
            messages=messages,
        )
    else:
        response = openai.ChatCompletion.create(
            deployment_id = deployment_id,
            messages=messages,
        )


    choices = response["choices"]  # type: ignore
    completion = choices[0].message.content.strip()
    logger.info(f"Completion: {completion}")
    return completion
