# Emby 自动标签工具

这是一个用于 Emby 的辅助工具，它通过接收 Emby 的 Webhook 通知，根据用户自定义的规则，自动为电影和剧集添加标签。

## 更新日志

<details>
<summary>点击展开/折叠</summary>

- **v1.0.3 (2025-08-24)**
  - **新增功能**: TMDB 请求限流功能。
    - 增加了对 TMDB API 请求的限流，默认每秒1次。
    - 限流周期可在配置页面设置，支持小数（如0.3秒、0.5秒），设置为0表示不限制。
  - **依赖更新**: 添加了 `ratelimit` 和 `backoff` 库。
- **v1.0.2 (2025-08-24)**
  - **新增功能**: 添加了“一键为所有媒体打标签”功能。
    - 在 Web 管理面板中新增了“一键为所有媒体打标签”区域，允许用户选择写入模式（合并/覆盖）并触发对所有电影和剧集进行打标签操作。
    - 任务在后台异步执行，前端页面通过轮询API实时显示任务进度（已处理、已更新、失败数量）。
  - **改进**: 优化了后台任务的日志记录，将 `print` 语句替换为 `logging` 模块。
  - **修复**: 修复了 `AttributeError: module 'services.config_service' has no attribute 'get_current_time'` 错误。
- **v1.0.1 (2025-08-24)**
  - **新增功能**: 添加了“清除所有 Emby 媒体库标签”功能。
    - 在 Web 管理面板中新增了“清除所有 Emby 媒体库标签”按钮，允许用户一键清除所有电影和剧集的标签。
    - 此操作不可撤销，请谨慎使用。
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
