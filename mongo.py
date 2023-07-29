import os
import motor.motor_asyncio

client = motor.motor_asyncio.AsyncIOMotorClient('mongodb://os.environ.get(username):os.environ.get(mongo_pass)@46.148.230.118:27037/')
db = client.education_press_backend