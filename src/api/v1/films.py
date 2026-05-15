from http import HTTPStatus
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from src.services.film import FilmService, get_film_service

router = APIRouter()


class Genre(BaseModel):
    """Жанр"""
    uuid: str
    name: str

    model_config = ConfigDict(from_attributes=True)


class Person(BaseModel):
    """Персона"""
    uuid: str
    full_name: str

    model_config = ConfigDict(from_attributes=True)


class Film(BaseModel):
    """Фильм"""
    uuid: str
    title: str
    imdb_rating: float
    description: str
    genre: list[Genre]
    actors: list[Person]
    writers: list[Person]
    directors: list[Person]

    model_config = ConfigDict(from_attributes=True)


class FilmShort(BaseModel):
    """Краткий формат информации о фильме"""
    uuid: str
    title: str
    imdb_rating: float

    model_config = ConfigDict(from_attributes=True)


@router.get(
    '',
    response_model=list[FilmShort],
    summary='Перечень фильмов',
    description='Перечень фильмов',
    response_description='Список фильмов'
)
async def films_list(
        sort: str = Query(default='-imdb_rating'),
        page_size: int = Query(default=50, ge=1, le=100),
        page_number: int = Query(default=1, ge=1),
        film_service: FilmService = Depends(get_film_service),
):
    """Общий список фильмов"""
    films = await film_service.get_list(
        sort=sort,
        page_size=page_size,
        page_number=page_number,
    )

    return [FilmShort.model_validate(film) for film in films]


@router.get(
    '/search',
    response_model=list[FilmShort],
    summary='Поиск фильмов',
    description='Поиск похожих по жанрам фильмов',
    response_description='Список похожих фильмов'
)
async def film_search(
        query: str = Query(..., min_length=1),
        page_size: int = Query(default=50, ge=1, le=100),
        page_number: int = Query(default=1, ge=1),
        film_service: FilmService = Depends(get_film_service),
) -> list[FilmShort]:
    """Поиск по фильмам"""
    return await film_service.search(
        query=query,
        page_size=page_size,
        page_number=page_number,
    )


@router.get('/{film_id:uuid}', response_model=Film, summary="Информация о фильме",
            description="Вывод информации о конкретном фильме",
            response_description="Информация о фильме")
async def film_details(film_id: UUID, film_service: FilmService = Depends(get_film_service)) -> Film:
    """Информация об одном фильме"""
    film = await film_service.get_by_id(film_id)
    if not film:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail='Film not found')

    return Film.model_validate(film)


@router.get(
    '/{film_id:uuid}/similar',
    response_model=list[FilmShort],
    summary='Похожие фильмы',
)
async def similar_films(
        film_id: UUID,
        page_size: int = Query(default=50, ge=1, le=100),
        page_number: int = Query(default=1, ge=1),
        film_service: FilmService = Depends(get_film_service),
):
    """Похожие по жанру"""
    return await film_service.get_similar(
        film_id=film_id,
        page_size=page_size,
        page_number=page_number,
    )
