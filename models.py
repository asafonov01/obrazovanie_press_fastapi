import time
import typing
from datetime import datetime

from pydantic import BaseModel, Field, EmailStr
from bson import ObjectId
from typing import Optional, List


class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid objectid")
        return ObjectId(v)

    @classmethod
    def __modify_schema__(cls, field_schema):
        field_schema.update(type="string")


class UserModel(BaseModel):
    uuid: str = Field(...)
    email: str = Field(...)
    name: str = Field(...)
    surname: str = Field(...)
    patronymic: str = Field(...)
    birthday: str = Field(...)
    phone_number: Optional[str] = Field(...)
    is_banned: bool = Field(False)
    permissions: int = Field(0)
    registration_date: int = Field(default=0)
    username: str = Field()
    avatar: str | None = Field(default=None)

    subscriptions: list = Field(default=[])

    show_first_name: Optional[bool] = Field(default=False)
    show_surname: Optional[bool] = Field(default=False)
    show_email: Optional[bool] = Field(default=False)
    show_phone: Optional[bool] = Field(default=False)
    hide_profile: Optional[bool] = Field(default=False)

    notify_new_comment: Optional[bool] = Field(default=False)
    notify_new_like: Optional[bool] = Field(default=False)
    notify_new_subscriber: Optional[bool] = Field(default=False)
    notify_new_offers: Optional[bool] = Field(default=False)

    about_text: str | None = Field(default=None)
    screen_name: str | None = Field(default=None)

    def __init__(self, *args, **kwargs):
        if 'username' not in kwargs.keys():
            kwargs['username'] = f"{kwargs.get('name') or 'Некто'} {kwargs.get('surname') or 'Некто'}"

        kwargs['avatar'] = 'https://api.obrazovanie.press/images/' + kwargs.get('image_name') if kwargs.get('image_name') else 'https://www.ktoeos.org/wp-content/uploads/2021/11/default-avatar.png'

        super().__init__(**kwargs)

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        schema_extra = {
            "example": {
                "uuid": "c7870ed4-747f-4c61-b327-e32fed095e64",
                "email": "jdoe@example.com",
                "name": "Test",
                "surname": "Bot",
                "patronymic": "Botovich",
                "birthday": "01.01.2000",
                "phone_number": "88005553535",
                "is_banned": False,
                "permissions": 0
            }
        }


class Subscription(BaseModel):
    to_uuid: str = Field(...)
    avatar: str | None = Field(...)
    username: str = Field(...)
    date: int = Field(...)
    subscriptions_num: int = Field(...)
    subscribers_num: int = Field(...)

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        schema_extra = {
            "example": {
                "uuid": "c7870ed4-747f-4c61-b327-e32fed095e64",
                "avatar": None,
                "username": "testbot",
                "date": int(time.time()),
                "subscriptions_num": 0,
                "subscribers_num": 0
            }
        }


class Notification(BaseModel):
    avatar: str | None = Field(...)
    text: str = Field(...)
    date: int = Field(...)
    user_name: str

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        schema_extra = {
            "example": {
                "uuid": "c7870ed4-747f-4c61-b327-e32fed095e64",
                "user_name": "admin",
                "avatar": None,
                "text": "Тестовое уведомление",
                "date": int(time.time())
            }
        }


class SignUpUserModel(BaseModel):
    email: str = Field(...)
    name: str = Field(...)
    surname: str = Field(...)
    patronymic: str = Field(...)
    password: str = Field(...)
    birthday: str = Field(...)
    phone_number: Optional[str] = Field(...)

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
        schema_extra = {
            "example": {
                "email": "jdoe@example.com",
                "name": "Test",
                "surname": "Bot",
                "patronymic": "Botovich",
                "password": "123",
                "birthday": "01.01.2000",
                "phone_number": "88005553535"
            }
        }

class EditUserModel(BaseModel):
    email: Optional[str] = Field(default=None)
    name: Optional[str] = Field(default=None)
    surname: Optional[str] = Field(default=None)
    patronymic: Optional[str] = Field(default=None)
    password: Optional[str] = Field(default=None)
    birthday: Optional[str] = Field(default=None)
    phone_number: Optional[str] = Field(default=None)

    show_first_name: Optional[bool] = Field(default=False)
    show_surname: Optional[bool] = Field(default=False)
    show_email: Optional[bool] = Field(default=False)
    show_phone: Optional[bool] = Field(default=False)
    hide_profile: Optional[bool] = Field(default=False)

    notify_new_comment: Optional[bool] = Field(default=False)
    notify_new_like: Optional[bool] = Field(default=False)
    notify_new_subscriber: Optional[bool] = Field(default=False)
    notify_new_offers: Optional[bool] = Field(default=False)

    about_text: str | None = Field(default=None)
    screen_name: str | None = Field(default=None)


    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
        schema_extra = {
            "example": {
                "email": "jdoe@example.com",
                "name": "Test",
                "surname": "Bot",
                "patronymic": "Botovich",
                "password": "123",
                "birthday": "01.01.2000",
                "phone_number": "88005553535"
            }
        }


class LoginUserModel(BaseModel):
    email: str = Field(...)
    password: str = Field(...)

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
        schema_extra = {
            "example": {
                "email": "jdoe@example.com",
                "password": "123",
            }
        }


class PostModel(BaseModel):
    uuid: str = Field(...)
    author: UserModel = Field(...)
    category_ids: List[int] = Field(default=[])
    tags: typing.List[str] = Field(default=[])
    comments_disabled: bool = Field(default=False)

    title: str = Field(...)
    text: str = Field(...)
    source: str = Field(...)
    image_name: Optional[str] = Field(...)
    moderated: bool = Field(False)
    likes: int = Field(0)
    views: int = Field(0)
    is_liked: bool = Field(False)
    comments: int = Field(0)
    publication_time: int = Field(0)

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        schema_extra = {
            "example": {
                "posts": [
                    {
                        "uuid": "b45580b6-0e71-453a-bb9b-88cf1004f3dd",
                        "author": {
                            "uuid": "ae4a4f7c-86a4-4ad6-a70b-9b1b7537a201",
                            "email": "jdoeeee@example.com",
                            "name": "Test",
                            "surname": "Bot",
                            "patronymic": "Botovich",
                            "birthday": "01.01.2000",
                            "phone_number": "88005553535",
                            "is_banned": False,
                            "permissions": 1,
                            "registration_date": 1662667062,
                            "username": "Test Bot",
                            "subscriptions": []
                        },
                        "category_id": 1,
                        "title": "Раст топ!",
                        "text": "Раст был признан лучшим языком программирования! лопата",
                        "source": "Это все знают ",
                        "image_name": "J1GfQ-lloN8i4voY4PYp7UZb4SvMebgw2AFAoJkSga7-BNzIyM7wr10MmdlqdlX-xZt7dS1rAmu1gh9-lILnAbJ2.jpeg_b45580b6-0e71-453a-bb9b-88cf1004f3dd.jpg",
                        "moderated": False,
                        "likes": 0,
                        "views": 0,
                        "is_liked": False,
                        "comments": 0
                    }, ]}
        }


class CommentModel(BaseModel):
    uuid: str = Field(...)
    post_uuid: str = Field(...)
    author: UserModel = Field(...)
    text: str = Field(...)
    time: datetime = Field(...)
    likes: int = Field(...)
    is_liked: bool = Field(...)
    liked_by: List[str] = Field(...)

    reply: List[typing.Any] = Field(...)
    class Config:

        schema_extra = {
        "example": {
            "posts": [
                {
                    "uuid": "b45580b6-0e71-453a-bb9b-88cf1004f3dd",
                    "author": {
                        "uuid": "ae4a4f7c-86a4-4ad6-a70b-9b1b7537a201",
                        "email": "jdoeeee@example.com",
                        "name": "Test",
                        "surname": "Bot",
                        "patronymic": "Botovich",
                        "birthday": "01.01.2000",
                        "phone_number": "88005553535",
                        "is_banned": False,
                        "permissions": 1,
                        "registration_date": 1662667062,
                        "username": "Test Bot",
                        "subscriptions": []
                    },
                    "category_id": 1,
                    "title": "Раст топ!",
                    "text": "Раст был признан лучшим языком программирования! лопата",
                    "source": "Это все знают ",
                    "image_name": "J1GfQ-lloN8i4voY4PYp7UZb4SvMebgw2AFAoJkSga7-BNzIyM7wr10MmdlqdlX-xZt7dS1rAmu1gh9-lILnAbJ2.jpeg_b45580b6-0e71-453a-bb9b-88cf1004f3dd.jpg",
                    "moderated": False,
                    "likes": 0,
                    "views": 0,
                    "is_liked": False,
                    "comments": 0
                }, ]}
    }


class PostUUID(BaseModel):
    post_uuid: str = Field(...)

    class Config:
        allow_population_by_field_name = True
        schema_extra = {
            "example": {
                "post_uuid": "c7870ed4-747f-4c61-b327-e32fed095e64",
            }
        }


class CommentUUID(BaseModel):
    comment_uuid: str = Field(...)

    class Config:
        allow_population_by_field_name = True
        schema_extra = {
            "example": {
                "comment_uuid": "c7870ed4-747f-4c61-b327-e32fed095e64",
            }
        }
