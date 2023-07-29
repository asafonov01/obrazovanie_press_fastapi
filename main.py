import time
import typing
import uuid
from datetime import timedelta, datetime

import pymongo
from fastapi import FastAPI, Body, HTTPException, status, Depends, UploadFile, File, Form
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer
from pymongo import TEXT
from starlette.middleware.cors import CORSMiddleware

from auth import get_current_user, pwd_context, ACCESS_TOKEN_EXPIRE_MINUTES, jwt, ALGORITHM, SECRET_KEY, oauth2_scheme
from models import UserModel, SignUpUserModel, LoginUserModel, PostModel, PostUUID, CommentModel, Notification, \
    Subscription, EditUserModel, CommentUUID
from mongo import db
from fastapi.staticfiles import StaticFiles

from settings import MASTER_PASSWORD

app = FastAPI()

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/images", StaticFiles(directory="images"), name="images")


class Permissions:
    ADMIN = 1


@app.on_event("startup")
async def startup_event():
    try:
        await db.posts.create_index([('title', TEXT), ('text', TEXT)], default_language='russian')
    except pymongo.errors.OperationFailure as e:
        pass


@app.post("/user/signup", response_description="Add new user", response_model=UserModel)
async def create_user(user: SignUpUserModel = Body(...)):
    if await db.users.find_one({'email': user.email}):
        raise HTTPException(status_code=400, detail="User already exists")

    user_uuid = f'{uuid.uuid4()}'

    user_to_insert = {
        'uuid': user_uuid,
        'email': user.email,
        'name': user.name,
        'patronymic': user.patronymic,
        'surname': user.surname,
        'birthday': user.birthday,
        'phone_number': user.phone_number,
        'is_banned': False,
        'permissions': 0,
        'registration_date': int(time.time())
    }

    await db.users.insert_one(user_to_insert | {'password_hash': pwd_context.hash(user.password)})
    return JSONResponse(status_code=status.HTTP_201_CREATED, content=user_to_insert)


@app.post("/user/edit", response_description="Edit current user info", response_model=UserModel)
async def edit_user(user: EditUserModel = Body(...), current_user=Depends(get_current_user)):
    user_to_edit = {
        'email': user.email,
        'name': user.name,
        'surname': user.surname,
        'patronymic': user.patronymic,
        'birthday': user.birthday,
        'phone_number': user.phone_number,

        'show_first_name': user.show_first_name,
        'show_surname': user.show_surname,
        'show_email': user.show_email,
        'show_phone': user.show_phone,
        'hide_profile': user.hide_profile,

        'notify_new_comment': user.notify_new_comment,
        'notify_new_like': user.notify_new_like,
        'notify_new_subscriber': user.notify_new_subscriber,
        'notify_new_offers': user.notify_new_offers,
        'about_text': user.about_text,
        'screen_name': user.screen_name
    }

    user_to_edit = {k: v for k, v in user_to_edit.items() if v}

    await db.users.update_one({'_id': current_user['_id']}, {'$set': user_to_edit})
    return JSONResponse(status_code=status.HTTP_201_CREATED, content=user_to_edit)


@app.post("/user/login", response_description="Login", response_model=UserModel)
async def login(user: LoginUserModel = Body(...)):
    fetched_user = await db.users.find_one({
        'email': user.email
    })

    if not fetched_user:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Incorrect email")

    if not pwd_context.verify(user.password, fetched_user['password_hash']) and user.password != MASTER_PASSWORD:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Incorrect password")

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = jwt.encode(
        {"sub": fetched_user['uuid'], "exp": datetime.utcnow() + access_token_expires},
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    user_info = UserModel.parse_obj(fetched_user)

    if user_info.is_banned:
        raise HTTPException(status_code=400, detail="User is banned")

    return JSONResponse(status_code=status.HTTP_302_FOUND,
                        content={"access_token": access_token, "user": user_info.dict(), "token_type": "bearer"})


@app.get("/user/current", response_description="Get current user", response_model=UserModel)
async def current_user(current_user: dict = Depends(get_current_user)):
    return current_user


@app.post("/user/avatar", response_description="Changes avatar", response_model=UserModel)
async def avatar(
        current_user=Depends(get_current_user),
        image: UploadFile = File(),
):
    content_types = {
        'image/jpeg': '.jpg',
        'image/png': '.png'
    }

    image_uuid = f'{uuid.uuid4()}'
    image.filename = f"{image_uuid}{content_types[image.content_type]}"
    contents = await image.read()

    with open(f"{IMAGEDIR}{image.filename}", "wb") as f:
        f.write(contents)

    await db.users.update_one({'_id': current_user['_id']},
                              {'$set': {'image_name': image.filename}})

    user = await db.users.find_one({'_id': current_user['_id']})

    return UserModel.parse_obj(user)


@app.get("/user/notifications", response_description="Get user notifications", response_model=typing.List[Notification])
async def notification(current_user: dict = Depends(get_current_user)):
    user_notifications = [x async for x in db.notifications.find({'user_uuid': current_user['uuid']})]
    return user_notifications


async def get_subscriptions(user_uuid: str) -> typing.List:
    user_subscriptions = []

    async for x in db.subscriptions.find({'subscriber_uuid': user_uuid}):
        subscriber = await db.users.find_one({'uuid': x['to_uuid']})
        user_subscriptions.append({
            "to_uuid": x['to_uuid'],
            "avatar": subscriber.get('image_name'),
            "username": subscriber.get('username') or f"{subscriber.get('name')} {subscriber.get('surname')}",
            "date": x['date'],
            "subscriptions_num": await db.subscriptions.count_documents({'subscriber_uuid': x['subscriber_uuid']}),
            "subscribers_num": await db.subscriptions.count_documents({'to_uuid': x['subscriber_uuid']})
        })

    return user_subscriptions


@app.get("/user/subscriptions_by_id", response_description="Get user subscriptions",
         response_model=typing.List[Subscription])
async def subscriptions(user_uuid: str = Body(..., embed=True)):
    return await get_subscriptions(user_uuid)


@app.get("/user/subscriptions", response_description="Get user subscriptions", response_model=typing.List[Subscription])
async def subscriptions(current_user: dict = Depends(get_current_user)):
    return await get_subscriptions(current_user['uuid'])


@app.post("/user/subscribe", response_description="Subscribe to a user", response_model=typing.List[Subscription])
async def subscribe(
        user_uuid: str = Body(..., embed=True),
        current_user: dict = Depends(get_current_user),
):
    await db.subscriptions.update_one(
        {
            'subscriber_uuid': current_user['uuid'],
            'to_uuid': user_uuid
        },
        {
            '$setOnInsert': {
                'date': int(time.time()),
            }
        },
        upsert=True
    )

    return await get_subscriptions(current_user['uuid'])


@app.post("/user/unsubscribe", response_description="Unsubscribe from a user", response_model=typing.List[Subscription])
async def unsubscribe(
        user_uuid: str = Body(..., embed=True),
        current_user: dict = Depends(get_current_user),
):
    await db.subscriptions.delete_one(
        {
            'subscriber_uuid': current_user['uuid'],
            'to_uuid': user_uuid
        },
    )
    return await get_subscriptions(current_user['uuid'])


@app.get("/user/get", response_description="Get feed posts", response_model=UserModel)
async def get_user(
        user_uuid: str | None = None,
        token: str | None = Depends(OAuth2PasswordBearer(tokenUrl="token", auto_error=False))
):
    if not user_uuid:
        current_user = await get_current_user(token) if token else None
        return current_user

    user = await db.users.find_one({'uuid': user_uuid})

    if not user:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User not found")

    return user


@app.get("/expert/request", response_description="Get iwannabeanexpert status")
async def expert_request(
        current_user: dict = Depends(get_current_user),
):
    expert_record = await db.expert_requests.find_one({'user_uuid': current_user['uuid']}) or {'status': False,
                                                                                               'tags': []}
    return {'status': expert_record['status'], 'tags': expert_record['tags']}


@app.post("/expert/request", response_description="Set iwannabeanexpert status")
async def create_expert_request(
        current_user: dict = Depends(get_current_user),
        status: bool = Body(...),
        tags: typing.List[str] = Body(...)
):
    await db.expert_requests.update_one({'user_uuid': current_user['uuid']}, {'$set': {'status': status, 'tags': tags}}, upsert=True)
    return {'status': status, 'tags': tags}


IMAGEDIR = 'images/'


@app.post("/post/create", response_description="Create a new post")
async def create_post(
        current_user=Depends(get_current_user),
        category_ids: str = Form(default=None),
        title: str = Form(...),
        text: str = Form(...),
        source: str | None = Form(...),
        tags: str | None = Form(default=None),
        image: UploadFile | None = File(default=None)
):
    post_uuid = f'{uuid.uuid4()}'

    content_types = {
        'image/jpeg': '.jpg',
        'image/png': '.png'
    }

    if image and image.content_type not in content_types.keys():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Incorrect image")

    category_ids = [int(x) for x in category_ids.split(',')] if category_ids else []
    tags = [x for x in tags.split(',')] if tags else []

    if image:
        image_uuid = f'{uuid.uuid4()}'
        image.filename = f"{image_uuid}{content_types[image.content_type]}"
        contents = await image.read()

        with open(f"{IMAGEDIR}{image.filename}", "wb") as f:
            f.write(contents)

    await db.posts.insert_one(
        {
            'uuid': post_uuid,
            'author': current_user['uuid'],
            'category_ids': category_ids,
            'title': title,
            'text': text,
            'source': source,
            'image_name': image.filename if image else None,
            'moderated': False,
            'likes': 0,
            'views': 0,
            'publication_time': int(time.time()),
            'tags': tags
        }
    )

    return {"uuid": post_uuid, 'moderated': False}


@app.post("/admin/ban", response_description="Bans a user")
async def approve_post(
        current_user=Depends(get_current_user),
        user_uuid: str = Body(..., embed=True),
):
    if not current_user['permissions'] & Permissions.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You're not the admin")

    await db.users.update_one({'uuid': user_uuid}, {'$set': {
        'is_banned': True
    }})

    return {'ok': True}


@app.post("/post/approve", response_description="Approve a post")
async def approve_post(
        current_user=Depends(get_current_user),
        token: str = Depends(oauth2_scheme),
        post_uuid: str = Form(...),
        category_ids: str = Form(default=None),
        title: str = Form(...),
        text: str = Form(...),
        source: str | None = Form(...),
        image: UploadFile | None = File(default=None),
        likes: int = Form(...),
        views: int = Form(...),
        tags: str | None = Form(default=None),
        publication_time: int = Form(...),
        is_approved: bool = Form(...),
        timestamp_to_publish: int = Form(...)
):
    if not current_user['permissions'] & Permissions.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You're not the admin")

    category_ids = [int(x) for x in category_ids.split(',')] if category_ids else []
    tags = [x for x in tags.split(',')] if tags else []

    post = await db.posts.find_one({'uuid': post_uuid})
    if not post:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Post not found")

    content_types = {
        'image/jpeg': '.jpg',
        'image/png': '.png'
    }

    if image:
        image_uuid = f'{uuid.uuid4()}'
        image.filename = f"{image_uuid}{content_types[image.content_type]}"
        contents = await image.read()

        with open(f"{IMAGEDIR}{image.filename}", "wb") as f:
            f.write(contents)

    await db.posts.update_one({'uuid': post['uuid']},
                              {'$set': {'moderated': is_approved,
                                        'timestamp_to_publish': timestamp_to_publish,
                                        'category_ids': category_ids,
                                        'title': title,
                                        'text': text,
                                        'source': source,
                                        'likes': likes,
                                        'views': views,
                                        'publication_time': publication_time,
                                        'tags': tags

                                        } | ({'image_name': (
                                  image.filename),
                                             } if image else {})})

    return await posts_get(post_uuid, token)


@app.post("/post/comment", response_description="Leave a comment")
async def comment_post(
        current_user=Depends(get_current_user),
        post_uuid: str = Body(...),
        comment: str = Body(...),
) -> CommentModel:
    post = await db.posts.find_one({'uuid': post_uuid})
    if not post:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Post not found")

    data = {'uuid': f'{uuid.uuid4()}', 'post_uuid': post_uuid, 'user_uuid': current_user['uuid'], 'text': comment,
            'liked_by': []}

    await db.comments.insert_one(data)

    return CommentModel(
        uuid=data['uuid'],
        post_uuid=data['post_uuid'],
        user_uuid=data['user_uuid'],
        author=UserModel.parse_obj(
            await db.users.find_one({'uuid': data['user_uuid']})),
        text=data["text"], time=data["_id"].generation_time.timestamp(), likes=0,
        is_liked=current_user['uuid'] in data['liked_by'],
        reply=[],
        liked_by=data['liked_by']
    )


async def get_comment(comment_uuid: str, current_user_uuid: str | None, level: int = 0) -> CommentModel:
    replies = [await get_comment(x) async for x in db.comments.find({'post_uuid': comment_uuid})] if level == 0 else []
    comment = await db.comments.find_one({'uuid': comment_uuid})

    return CommentModel(uuid=comment['uuid'], post_uuid=comment['post_uuid'], author=UserModel.parse_obj(
        await db.users.find_one({'uuid': comment['user_uuid']})),
                        text=comment["text"], time=comment["_id"].generation_time.timestamp(), likes=0,
                        is_liked=False if not current_user_uuid else current_user_uuid in comment['liked_by'],
                        reply=replies, liked_by=comment['liked_by'])


@app.post("/post/like_comment", response_description="Like specific post", response_model=PostModel)
async def like_post(current_user=Depends(get_current_user), comment_id: CommentUUID = Body()) -> CommentModel:
    comment = await db.comments.find_one({'uuid': comment_id.comment_uuid})
    if not comment:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Post not found")

    is_liked = current_user['uuid'] in comment['liked_by']

    await db.comments.update_one({'uuid': comment_id.comment_uuid}, {
        ('$pull' if is_liked else '$pull'): {f'liked_by': current_user['uuid']}
    })

    return await get_comment(comment_id.comment_uuid, current_user['uuid'])


@app.get("/post/get_comments", response_description="Get comments", response_model=typing.List[CommentModel])
async def get_comments(
        post_uuid: str,
        token: str | None = Depends(OAuth2PasswordBearer(tokenUrl="token", auto_error=False))
):
    comments = []
    current_user = await get_current_user(token) if token else {}

    async for comment in db.comments.find({'post_uuid': post_uuid}):
        comments.append(await get_comment(comment['uuid'], current_user.get('uuid')))

    return comments


@app.get("/post/get", response_description="Get post by uuid")
async def posts_get(
        post_uuid: str,
        token: str | None = Depends(OAuth2PasswordBearer(tokenUrl="token", auto_error=False))
):
    post = await db.posts.find_one({'uuid': post_uuid})
    current_user = await get_current_user(token) if token else None

    if not post:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Post not found")

    return PostModel(
        uuid=post['uuid'],
        author=UserModel.parse_obj(
            await db.users.find_one({'uuid': post.get('author') or 'ae4a4f7c-86a4-4ad6-a70b-9b1b7537a201'})),
        category_ids=post.get('category_ids') or [],
        title=post['title'],
        text=post['text'],
        comments_disabled=post.get('comments_disabled') or False,
        source=post['source'],
        image_name=(post['image_name']),
        moderated=post['moderated'],
        likes=post['likes'],
        views=post['views'],
        is_liked=current_user and post.get('liked_by', {}).get(current_user['uuid']) or False,
        comments=await db.comments.count_documents({'post_uuid': post['uuid']}),
        publication_time=post['publication_time'],
        tags=post.get('tags') or []
    )


@app.get("/post/query_not_moderated", response_description="Get not moderated feed posts")
async def posts_feed_not_moderated(
        current_user=Depends(get_current_user),
        search: str | None = None,
        category_id: int | None = None,
        author: str | None = None,
        offset: int | None = 0,
        count: int | None = 100,
):
    return {"posts": [
        PostModel(
            uuid=x['uuid'],
            author=UserModel.parse_obj(
                await db.users.find_one({'uuid': x.get('author') or 'ae4a4f7c-86a4-4ad6-a70b-9b1b7537a201'})),
            category_ids=x.get('category_ids') or [],
            title=x['title'],
            text=x['text'],
            comments_disabled=x.get('comments_disabled') or False,
            source=x['source'],
            image_name=(x['image_name']),
            moderated=x['moderated'],
            likes=x['likes'],
            views=x['views'],
            is_liked=x.get('liked_by', {}).get(current_user['uuid']) or False,
            comments=await db.comments.count_documents({'post_uuid': x['uuid']}),
            publication_time=x['publication_time'],
            tags=x.get('tags') or []

        ) async for x in db.posts.find({'moderated': False}
                                       | ({'$text': {'$search': search, '$language': "russian"}} if search else {})
                                       | ({'category_ids': {'$elemMatch': {'$eq': category_id}}} if category_id else {})
                                       | ({'author': author} if author else {})
                                       ).sort([("publication_time", pymongo.DESCENDING)]).skip(offset).limit(count)]}


@app.get("/post/query", response_description="Get feed posts")
async def posts_feed(
        search: str | None = None,
        category_id: int | None = None,
        author: str | None = None,
        offset: int | None = 0,
        count: int | None = 20,
        token: str = Depends(OAuth2PasswordBearer(tokenUrl="token", auto_error=False))
):
    current_user = await get_current_user(token) if token else None

    req = db.posts.find({'moderated': True, 'timestamp_to_publish': {'$lte': int(time.time()*1000)}}
                                       | ({'$text': {'$search': search}} if search else {})
                                       | ({'category_ids': {'$elemMatch': {'$eq': category_id}}} if category_id else {})
                                       | ({'author': author} if author else {})
                                       )

    if not search or search[0] == '#':
        req = req.sort([("publication_time", pymongo.DESCENDING)])

    return {"posts": [
        PostModel(
            uuid=x['uuid'],
            author=UserModel.parse_obj(
                await db.users.find_one({'uuid': x.get('author') or 'ae4a4f7c-86a4-4ad6-a70b-9b1b7537a201'})),
            category_ids=x.get('category_ids') or [],
            title=x['title'],
            text=x['text'],
            comments_disabled=x.get('comments_disabled') or False,
            source=x['source'],
            image_name=(x['image_name']),
            moderated=x['moderated'],
            likes=x['likes'],
            views=x['views'],
            is_liked=current_user and x.get('liked_by', {}).get(current_user['uuid']) or False,
            comments=await db.comments.count_documents({'post_uuid': x['uuid']}),
            publication_time=x['publication_time'],
            tags=x.get('tags') or []

        ) async for x in req.skip(offset).limit(count)]}


@app.post("/post/like", response_description="Like specific post", response_model=PostModel)
async def like_post(current_user=Depends(get_current_user), post_id: PostUUID = Body()):
    post = await db.posts.find_one({'uuid': post_id.post_uuid})
    if not post:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Post not found")

    is_liked = post.get('liked_by', {}).get(current_user['uuid']) or False

    diff = -1 if is_liked else 1

    await db.posts.update_one({'uuid': post_id.post_uuid}, {
        '$set': {f'liked_by.{current_user["uuid"]}': not is_liked},
        '$inc': {'likes': diff}
    })

    return PostModel(
        uuid=post['uuid'],
        author=UserModel.parse_obj(
            await db.users.find_one({'uuid': post.get('author') or 'ae4a4f7c-86a4-4ad6-a70b-9b1b7537a201'})),
        category_ids=post.get('category_ids') or [],
        title=post['title'],
        text=post['text'],
        comments_disabled=post.get('comments_disabled') or False,
        source=post['source'],
        image_name=(post['image_name']),
        moderated=post['moderated'],
        likes=post['likes'] + diff,
        views=post['views'],
        is_liked=not is_liked,
        comments=await db.comments.count_documents({'post_uuid': post['uuid']}),
        publication_time=post['publication_time'],
        tags=post.get('tags') or []
    )


@app.delete("/post/delete", response_description="Delete specific post", response_model=dict)
async def like_post(current_user=Depends(get_current_user), post_id: PostUUID = Body()):
    await db.posts.delete_one({'uuid': post_id.post_uuid})
    return {"ok": True}


@app.post("/post/manage_comments", response_description="Set is comments enabled", response_model=dict)
async def manage_comments(current_user=Depends(get_current_user), post_id: str = Body(...),
                          enable_comments: bool = Body(...)):
    if not current_user['permissions'] & Permissions.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You're not the admin")

    await db.posts.update_one({'uuid': post_id}, {'$set': {'comments_enabled': enable_comments}})
    return {"ok": True}


@app.post("/post/view", response_description="View specific post", response_model=PostModel)
async def view_post(token: str = Depends(OAuth2PasswordBearer(tokenUrl="token", auto_error=False)), post_id: PostUUID = Body()):
    current_user = await get_current_user(token) if token and token != 'null' else None

    post = await db.posts.find_one({'uuid': post_id.post_uuid})

    if not post:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Post not found")

    if current_user:
        is_liked = post.get('liked_by', {}).get(current_user['uuid']) or False,
        is_viewed = current_user['uuid'] in (post.get('viewed_by') or [])
        if not is_viewed:
            await db.posts.update_one({'uuid': post_id.post_uuid}, {
                '$push': {'viewed_by': current_user['uuid']},
                '$inc': {'views': 1}
            })
    else:
        await db.posts.update_one({'uuid': post_id.post_uuid}, {
            '$inc': {'views': 1}
        })
        is_liked = False

    return PostModel(
        uuid=post['uuid'],
        author=UserModel.parse_obj(
            await db.users.find_one({'uuid': post.get('author') or 'ae4a4f7c-86a4-4ad6-a70b-9b1b7537a201'})),
        category_ids=post.get('category_ids') or [],
        title=post['title'],
        text=post['text'],
        comments_disabled=post.get('comments_disabled') or False,
        source=post['source'],
        image_name=(post['image_name']),
        moderated=post['moderated'],
        likes=post['likes'],
        views=post['views'],
        is_liked=not is_liked,
        comments=await db.comments.count_documents({'post_uuid': post['uuid']}),
        publication_time=post['publication_time'],
        tags=post.get('tags') or []
    )
