# This file should be placed inside your new 'frontend_src' directory.

# Stage 1: Build the Next.js application
FROM node:22-alpine AS builder
WORKDIR /app

# Copy dependency files and install them
COPY package.json package-lock.json* ./
RUN npm install

# Copy the rest of the application source code
COPY . .

# Build for production
RUN npm run build

# Stage 2: Create the production image
FROM node:22-alpine
WORKDIR /app

# Copy only the necessary build artifacts from the builder stage
# This creates a smaller, more secure final image.
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json

EXPOSE 3001

# The standard command to start a Next.js production server
CMD ["npm", "start"]
