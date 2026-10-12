FROM python:3.12-slim

# System dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    gnupg2 \
    unixodbc \
    unixodbc-dev \
    libpq-dev \
    libssl-dev \
    libsasl2-dev \
    build-essential \
    libffi-dev \
    libxml2-dev \
    libxmlsec1-dev \
    pkg-config \
    git \
    && rm -rf /var/lib/apt/lists/*

# # Install ODBC Driver 17 for SQL Server
# RUN curl -sSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor > /etc/apt/keyrings/microsoft.gpg && \
#     echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/microsoft.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" > /etc/apt/sources.list.d/mssql-release.list && \
#     apt-get update && ACCEPT_EULA=Y apt-get install -y msodbcsql17

# Install ODBC Driver 18 for SQL Server
RUN curl -sSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor > /etc/apt/keyrings/microsoft.gpg && \
    echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/microsoft.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" > /etc/apt/sources.list.d/mssql-release.list && \
    apt-get update && ACCEPT_EULA=Y apt-get install -y \
    msodbcsql18 \
    unixodbc-dev


# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Copy project files
COPY . .

EXPOSE 5000

CMD gunicorn --bind 0.0.0.0:5000 \
    --workers "${GUNICORN_WORKERS:-3}" \
    --timeout "${GUNICORN_TIMEOUT:-300}" \
    --graceful-timeout "${GUNICORN_GRACEFUL_TIMEOUT:-60}" \
    app:app
