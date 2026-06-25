# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install -r requirements.txt
# Copy project
COPY . /app/

# Collect static files (with dummy env vars since real ones are only available at runtime)
RUN SECRET_KEY=dummy DATABASE_URL=postgresql://dummy:dummy@dummy:5432/dummy python manage.py collectstatic --noinput

# Expose port 8000
EXPOSE 8000

# Run Daphne (ASGI) for Django Channels
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "b2b.asgi:application"]
