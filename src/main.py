from contextlib import asynccontextmanager

from elasticsearch import AsyncElasticsearch, ConnectionError, ConnectionTimeout
from fastapi import FastAPI
from fastapi.responses import ORJSONResponse
from redis.asyncio import Redis

from src.api.v1 import films
from src.core.config import settings
from src.core.exceptions import elastic_exception_handler
from src.db import elastic
from src.db import redis


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis.redis = Redis(host=settings.redis_host, port=settings.redis_port)
    elastic.es = AsyncElasticsearch(hosts=[f'http://{settings.elastic_host}:{settings.elastic_port}'])

    yield

    await redis.redis.close()
    await elastic.es.close()


app = FastAPI(
    lifespan=lifespan,
    description="Информация о фильмах",
    version="1.0.0",
    title=settings.project_name,
    docs_url='/api/openapi',
    openapi_url='/api/openapi.json',
    default_response_class=ORJSONResponse,
)

app.include_router(films.router, prefix='/api/v1/films', tags=['films'])

app.add_exception_handler(
    ConnectionError,
    elastic_exception_handler,
)

app.add_exception_handler(
    ConnectionTimeout,
    elastic_exception_handler,
)
