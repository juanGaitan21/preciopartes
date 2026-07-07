FROM node:22-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

ARG VITE_API_URL=https://api.versacode.com.co
ARG VITE_APP_OWNER=Juan David Gaitan
ARG VITE_APP_PHONE=+573045384661
ARG VITE_APP_CONTACT=juandavid092415@hotmail.com
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_APP_OWNER=$VITE_APP_OWNER
ENV VITE_APP_PHONE=$VITE_APP_PHONE
ENV VITE_APP_CONTACT=$VITE_APP_CONTACT

RUN npm run build

FROM nginx:alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
