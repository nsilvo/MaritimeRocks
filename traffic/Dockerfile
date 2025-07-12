# Dockerfile - Node.js + PostgreSQL app with static frontend serving

# Use official Node.js LTS image
FROM node:18

# Create app directory inside container
WORKDIR /usr/src/app

# Copy package files first to install dependencies
COPY package*.json ./
RUN npm install

# Copy rest of the app source
COPY . .

# Ensure upload directory exists inside container
RUN mkdir -p uploads logs

# Expose the backend port
EXPOSE 3010

# Start the Node.js app
CMD [ "node", "server.js" ]
