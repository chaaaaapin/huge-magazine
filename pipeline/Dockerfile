FROM node:20-slim

# Install Python + git + curl
RUN apt-get update && apt-get install -y \
    python3 python3-pip python3-venv \
    git curl \
    && rm -rf /var/lib/apt/lists/*

# Install wrangler globally
RUN npm install -g wrangler

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Install Node deps for the Astro site
COPY site/package*.json site/
RUN cd site && npm install

# Copy everything
COPY . .

# Configure git
RUN git config --global user.email "pipeline@hugemagazine.com" && \
    git config --global user.name "HUGE Pipeline"

CMD ["python3", "pipeline/publish.py", "--scheduler"]
