FROM node:22-alpine

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ENV VITE_API_PROXY=http://api:43124

EXPOSE 43123
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "43123"]
