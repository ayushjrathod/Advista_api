FROM python:3.10-slim

RUN useradd -m -u 1000 user
ENV PATH="/home/user/.local/bin:$PATH"

WORKDIR /code

# Copy requirements first to leverage Docker cache
COPY ./requirements.txt requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . /code

# Copy SSL certificates to /code directory
COPY ./cert.pem /code/cert.pem
COPY ./key.pem /code/key.pem

# Set permissions for SSL certificates
RUN chmod 600 /code/cert.pem /code/key.pem

# Change ownership of SSL certificates to non-root user
RUN chown user:user /code/cert.pem /code/key.pem

# Switch to non-root user
USER user

# Expose the port the app runs on
EXPOSE 7860

# Use environment variables that Hugging Face Spaces expects
ENV HOST=0.0.0.0
ENV PORT=7860
ENV SSL_CERTFILE=/code/cert.pem
ENV SSL_KEYFILE=/code/key.pem

# Command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860", "--ssl-keyfile", "/code/key.pem", "--ssl-certfile", "/code/cert.pem"]
