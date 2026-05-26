FROM node:20-alpine AS build

WORKDIR /app
COPY frontend/package*.json /app/frontend/
RUN npm --prefix frontend install
COPY frontend /app/frontend
RUN npm --prefix frontend run build

FROM nginx:1.27-alpine
COPY --from=build /app/frontend/dist /usr/share/nginx/html
EXPOSE 80
