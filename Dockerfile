FROM python:3.12

WORKDIR /app
COPY . /app
RUN pip install -r requirements.txt
ENV FLASK_APP=main.py
CMD ["flask", "run", "--host=0.0.0.0"]