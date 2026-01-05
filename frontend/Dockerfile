# 使用阿里云镜像源
FROM registry.cn-hangzhou.aliyuncs.com/library/node:18-alpine AS build

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json /app/
RUN npm ci

COPY frontend/ /app/
RUN npm run build

# 使用阿里云镜像源
FROM registry.cn-hangzhou.aliyuncs.com/library/nginx:alpine
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]




