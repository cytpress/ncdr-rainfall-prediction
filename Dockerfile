FROM oven/bun:latest

WORKDIR /app

# Copy package files and install
COPY package.json bun.lockb* ./
RUN bun install

# Copy all application code
COPY . .

# Expose the port
EXPOSE 8000

# Run the app
CMD ["bun", "run", "index.ts"]
