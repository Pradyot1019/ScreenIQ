FROM node:22-alpine
# Not /app: our routes live in app/app/, and a project root of /app made Next.js resolve
# /app/app/app/layout.tsx as a parent of every page (500 "No QueryClient set" on /login).
WORKDIR /frontend
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
EXPOSE 3000
CMD ["npm", "run", "dev"]
