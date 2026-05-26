FROM python:3.9-slim

WORKDIR /workspace

# Copie des fichiers
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expose le port (8080 est standard sur AI Deploy)
EXPOSE 8080

# Lance l'application
CMD streamlit run app.py --server.port=8080 --server.address=0.0.0.0