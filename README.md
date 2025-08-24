# Emby 自动标签工具

这是一个用于 Emby 的辅助工具，它通过接收 Emby 的 Webhook 通知，根据用户自定义的规则，自动为电影和剧集添加标签。

## 更新日志

<details>
<summary>点击展开/折叠</summary>

- **v1.0.0 (2025-08-24)**
  - 项目初始化。

</details>

## 核心功能

- **Webhook 驱动的自动化**: 通过 Emby Webhook 实时响应媒体库更新。
- **基于规则的标签生成**: 可视化创建和管理标签规则。
- **灵活的标签写入**: 支持合并和覆盖两种模式，并提供预览。
- **全面的 Web 管理面板**: 轻松完成所有配置、规则设定和功能测试。
- **TMDB 集成**: 利用 The Movie Database (TMDB) 的数据来丰富媒体信息。
- **Docker 支持**：易于通过 Docker 和 Docker Compose 进行部署。

## 快速开始

## Docker Compose 示例

```yaml
version: '3.8'

services:
  backend:
    image: pipi20xx/emby-auto-tags:latest
    container_name: emby-auto-tags
    ports:
      - "6005:8000"
    volumes:
      - ./config:/app/config
    restart: always
    network_mode: bridge
```

webhook通知选择类型为JSON
![alt text](img/image.png)
## 技术栈

- **后端**: Python (FastAPI)
- **部署**: Docker
