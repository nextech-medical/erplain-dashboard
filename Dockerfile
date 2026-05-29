FROM python:3.9-slim
WORKDIR /app
RUN pip install streamlit psycopg2-binary
COPY check_db.py .
EXPOSE 8080
CMD ["streamlit", "run", "check_db.py", "--server.port=8080", "--server.address=0.0.0.0"]
