import json
from functools import lru_cache
from typing import Optional
from uuid import UUID

from elasticsearch import AsyncElasticsearch, NotFoundError
from fastapi import Depends
from redis.asyncio import Redis

from src.db.elastic import get_elastic
from src.db.redis import get_redis
from src.models.film import Film

FILM_CACHE_EXPIRE_IN_SECONDS = 60 * 5


class FilmService:
    """Сервис фильмов"""

    def __init__(self, redis: Redis, elastic: AsyncElasticsearch):
        self.redis = redis
        self.elastic = elastic

    # Функции для кеширования
    async def _get_cache(self, key: str) -> Optional[list[Film]]:
        data = await self.redis.get(key)
        if not data:
            return None
        return [Film.model_validate(item) for item in json.loads(data)]

    async def _set_cache(self, key: str, value: list[Film]):
        await self.redis.set(
            key,
            json.dumps([f.model_dump() for f in value]),
            ex=FILM_CACHE_EXPIRE_IN_SECONDS,
        )

    # Получение фильма по id
    async def get_by_id(self, film_id: UUID) -> Optional[Film]:
        film = await self._film_from_cache(film_id)
        if not film:
            film = await self._get_film_from_elastic(film_id)
            if not film:
                return None
            await self._put_film_to_cache(film)
        return film

    async def _get_film_from_elastic(self, film_id: UUID) -> Optional[Film]:
        try:
            doc = await self.elastic.get(index='movies', id=str(film_id))
        except NotFoundError:
            return None
        return Film.model_validate(doc['_source'])

    async def _film_from_cache(self, film_id: UUID) -> Optional[Film]:
        data = await self.redis.get(str(film_id))
        if not data:
            return None
        return Film.model_validate_json(data)

    async def _put_film_to_cache(self, film: Film):
        await self.redis.set(
            str(film.uuid),
            film.model_dump_json(),
            ex=FILM_CACHE_EXPIRE_IN_SECONDS,
        )

    # Получение списка фильмов
    async def get_list(self, sort: str, page_size: int, page_number: int) -> list[Film]:
        cache_key = f"films:list:{sort}:{page_size}:{page_number}"

        cached = await self._get_cache(cache_key)
        if cached:
            return cached

        sort_field = sort.removeprefix('-')
        sort_order = 'desc' if sort.startswith('-') else 'asc'

        response = await self.elastic.search(
            index='movies',
            sort=[{sort_field: {'order': sort_order}}],
            from_=(page_number - 1) * page_size,
            size=page_size,
        )

        films = [Film.model_validate(hit['_source']) for hit in response['hits']['hits']]

        await self._set_cache(cache_key, films)
        return films

    # Поиск по фильмам
    async def search(self, query: str, page_size: int, page_number: int) -> list[Film]:
        cache_key = f"films:search:{query}:{page_size}:{page_number}"

        cached = await self._get_cache(cache_key)
        if cached:
            return cached

        body = {
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": [
                        "title^3",
                        "description",
                        "actors_names",
                        "writers_names",
                        "directors_names",
                    ],
                    "fuzziness": "auto"
                }
            },
            "from": (page_number - 1) * page_size,
            "size": page_size,
        }

        response = await self.elastic.search(index="movies", body=body)

        films = [Film.model_validate(hit["_source"]) for hit in response["hits"]["hits"]]

        await self._set_cache(cache_key, films)
        return films

    # Поиск похожих по жанру
    async def get_similar(self, film_id: UUID, page_size: int, page_number: int) -> list[Film]:
        cache_key = f"films:similar:{film_id}:{page_size}:{page_number}"

        cached = await self._get_cache(cache_key)
        if cached:
            return cached

        film = await self._get_film_from_elastic(film_id)
        if not film:
            return []

        genre_ids = [g.uuid for g in film.genre]

        body = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "nested": {
                                "path": "genre",
                                "query": {
                                    "terms": {
                                        "genre.uuid": genre_ids
                                    }
                                }
                            }
                        }
                    ],
                    "must_not": [
                        {"term": {"uuid": str(film_id)}}
                    ]
                }
            },
            "from": (page_number - 1) * page_size,
            "size": page_size,
            "sort": [{"imdb_rating": {"order": "desc"}}]
        }

        response = await self.elastic.search(index="movies", body=body)

        films = [Film.model_validate(hit["_source"]) for hit in response["hits"]["hits"]]

        await self._set_cache(cache_key, films)
        return films


@lru_cache()
def get_film_service(
        redis: Redis = Depends(get_redis),
        elastic: AsyncElasticsearch = Depends(get_elastic),
) -> FilmService:
    return FilmService(redis, elastic)
