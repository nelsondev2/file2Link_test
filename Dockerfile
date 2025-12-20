FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements
COPY requirements.txt .

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código fuente
COPY . .

# Crear directorio de almacenamiento
RUN mkdir -p storage && chmod 700 storage

# Hacer ejecutable el script de inicio
RUN chmod +x start.sh

# Puerto expuesto
EXPOSE 8080

# Comando de inicio
CMD ["./start.sh"]