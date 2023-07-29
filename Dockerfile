# syntax=docker/dockerfile:1
FROM python:3.10
WORKDIR /education_press

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt
