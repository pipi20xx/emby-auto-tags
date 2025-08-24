from fastapi import APIRouter, HTTPException, Body, BackgroundTasks, Request
from typing import Dict, Any, Literal
from services import config_service, tmdb_service, rule_service, emby_service
from core import config as core_config # 导入 core.config 并重命名以避免与 config_service 冲突
from fastapi.responses import HTMLResponse, RedirectResponse
import uuid
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/")
async def root():
    """
    根路由，重定向到管理页面。
    """
    return RedirectResponse(url="/api/manage")

async def _run_tag_all_media_task(task_id: str, mode: Literal['merge', 'overwrite'], task_manager: Dict[str, Any]):
    """
    实际执行打标签任务的后台函数。
    """
    try:
        task_manager[task_id]["status"] = "running"
        logger.info(f"任务 {task_id}: 开始对所有媒体进行打标签操作 (模式: {mode})...")
        result = await emby_service.tag_all_media_items(mode=mode)
        task_manager[task_id].update(result)
        task_manager[task_id]["status"] = "completed"
        logger.info(f"任务 {task_id}: 打标签任务完成。结果: {result}")
    except Exception as e:
        task_manager[task_id]["status"] = "failed"
        task_manager[task_id]["error"] = str(e)
        logger.error(f"任务 {task_id}: 打标签任务失败: {e}")

@router.post("/tag_all_media")
async def tag_all_media(
    request: Request,
    background_tasks: BackgroundTasks,
    mode: Literal['merge', 'overwrite'] = Body('merge', embed=True)
):
    """
    触发对所有 Emby 媒体库中的电影和剧集进行打标签操作。
    操作将在后台执行。
    """
    task_id = str(uuid.uuid4())
    task_manager = request.app.state.task_manager
    task_manager[task_id] = {
        "task_id": task_id,
        "status": "pending",
        "mode": mode,
        "processed_count": 0,
        "updated_count": 0,
        "failed_count": 0,
        "start_time": core_config.get_current_time()
    }
    
    logger.info(f"收到请求：启动后台打标签任务 {task_id} (模式: {mode})...")
    background_tasks.add_task(_run_tag_all_media_task, task_id, mode, task_manager)
    return {"message": "打标签任务已在后台启动。", "task_id": task_id}

@router.get("/tag_all_media/status/{task_id}")
async def get_tag_all_media_status(request: Request, task_id: str):
    """
    获取指定打标签任务的当前状态。
    """
    task_manager = request.app.state.task_manager
    task_status = task_manager.get(task_id)
    if not task_status:
        raise HTTPException(status_code=404, detail="Task not found.")
    return task_status

@router.post("/webhook/{token}")
async def receive_webhook(token: str, payload: Dict[Any, Any] = Body(...)):
    """
    接收 Emby Webhook 通知，验证 token 并打印完整的 JSON 数据用于调试。
    """
    # 1. 验证 Token 和启用状态
    webhook_config = config_service.get_config().get('WEBHOOK', {})
    is_enabled = webhook_config.get('enabled', 'false').lower() == 'true'
    secret_token = webhook_config.get('secret_token')

    if not is_enabled:
        print("Webhook 接收器当前已禁用，忽略请求。")
        raise HTTPException(status_code=403, detail="Webhook receiver is disabled.")

    if not secret_token or token != secret_token:
        print(f"收到无效的 Webhook token: {token}")
        raise HTTPException(status_code=401, detail="Invalid webhook token.")

    # 2. 导入 json 模块并处理数据
    import json
    
    print("--- 收到有效的 Webhook 请求 ---")
    try:
        pretty_payload = json.dumps(payload, indent=2, ensure_ascii=False)
        print(pretty_payload)
    except Exception as e:
        print(f"无法格式化为 JSON，打印原始数据: {e}")
        print(payload)
    print("--- Webhook 请求结束 ---")
    
    # 3. 检查自动化是否启用
    automation_enabled = webhook_config.get('automation_enabled', 'false').lower() == 'true'
    if not automation_enabled:
        print("Webhook 自动化处理当前已禁用，仅记录数据。")
        return {"status": "received", "message": "Webhook received, but automation is disabled."}

    # 4. 开始自动化处理
    print("--- 开始自动化处理 ---")
    try:
        # 提取关键信息
        item = payload.get('Item', {})
        if not item:
            print("Webhook payload 中缺少 'Item' 信息，跳过处理。")
            return {"status": "skipped", "message": "Missing 'Item' in payload."}

        tmdb_id = item.get('ProviderIds', {}).get('Tmdb')
        item_type = item.get('Type')  # "Movie" or "Series"
        item_id = item.get('Id')  # Emby Item ID

        if not all([tmdb_id, item_type, item_id]):
            print(f"缺少关键信息 (TMDB ID, Item Type, or Item ID)，跳过处理。TMDB_ID: {tmdb_id}, Type: {item_type}, ItemID: {item_id}")
            return {"status": "skipped", "message": "Missing key information."}
        
        print(f"提取信息成功: Emby ID='{item_id}', TMDB ID='{tmdb_id}', Type='{item_type}'")

        # 转换媒体类型以用于 TMDB API
        media_type_tmdb = 'movie' if item_type == 'Movie' else 'tv' if item_type == 'Series' else None
        if not media_type_tmdb:
            print(f"不支持的媒体类型: {item_type}，跳过处理。")
            return {"status": "skipped", "message": f"Unsupported media type: {item_type}"}

        # 1. 从 TMDB 获取详细信息
        print(f"正在从 TMDB 获取 '{tmdb_id}' ({media_type_tmdb}) 的详细信息...")
        details = tmdb_service.get_tmdb_details(tmdb_id, media_type_tmdb)
        if not details:
            print("无法从 TMDB 获取信息。")
            raise Exception("Failed to get TMDB details.")

        # 2. 根据规则生成标签
        genre_ids = [genre['id'] for genre in details.get('genres', [])]
        countries = [country['iso_3166_1'] for country in details.get('production_countries', [])]
        print(f"提取的 TMDB 信息: Genres={genre_ids}, Countries={countries}")
        
        generated_tags = rule_service.generate_tags(countries, genre_ids)
        print(f"根据规则生成的标签: {generated_tags}")

        if not generated_tags:
            print("未生成任何标签，处理结束。")
            return {"status": "success", "message": "No tags generated."}

        # 3. 更新 Emby 项目的元数据
        write_mode = webhook_config.get('write_mode', 'merge')
        print(f"准备以 '{write_mode}' 模式向 Emby 项目 '{item_id}' 写入标签: {generated_tags}")
        
        success = emby_service.update_item_metadata(
            item_id=item_id,
            tags_to_set=generated_tags,
            mode=write_mode
        )

        if success:
            print("成功更新 Emby 项目的标签。")
            return {"status": "success", "message": f"Tags {generated_tags} applied successfully."}
        else:
            print("更新 Emby 项目的标签失败。")
            raise Exception("Failed to update Emby item.")

    except Exception as e:
        print(f"自动化处理过程中发生错误: {e}")
        # 即使内部处理失败，也应向 Emby Webhook 返回 200 OK，避免 Emby 重试。
        return {"status": "error", "message": "An error occurred during processing.", "detail": str(e)}
    finally:
        print("--- 自动化处理结束 ---")

@router.get("/manage", response_class=HTMLResponse)
async def management_page():
    """
    提供一个功能完善的前端管理和测试页面。
    """
    return """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Emby 自动标签 - 管理面板</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; line-height: 1.6; color: #333; max-width: 960px; margin: 20px auto; padding: 0 20px; background-color: #f4f4f4; }
        h1, h2 { color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }
        .container { background: #fff; padding: 25px; border-radius: 8px; box-shadow: 0 2px 15px rgba(0,0,0,0.1); margin-bottom: 25px; }
        label { display: block; margin-bottom: 8px; font-weight: bold; }
        input[type="text"], input[type="password"], select { width: 100%; padding: 10px; margin-bottom: 15px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
        button { background-color: #3498db; color: white; padding: 10px 15px; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; transition: background-color 0.3s; }
        button:hover { background-color: #2980b9; }
        pre { background-color: #2d2d2d; color: #f8f8f2; padding: 15px; border-radius: 4px; white-space: pre-wrap; word-wrap: break-word; }
        .result { border: 1px solid #ddd; padding: 15px; margin-top: 15px; border-radius: 4px; background-color: #f9f9f9; }
        .hidden { display: none; }
        .spinner { border: 4px solid #f3f3f3; border-top: 4px solid #3498db; border-radius: 50%; width: 20px; height: 20px; animation: spin 1s linear infinite; display: inline-block; margin-left: 10px; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        
        /* Modal styles */
        .modal { position: fixed; z-index: 100; left: 0; top: 0; width: 100%; height: 100%; overflow: auto; background-color: rgba(0,0,0,0.5); }
        .modal-content { background-color: #fefefe; margin: 10% auto; padding: 20px; border: 1px solid #888; width: 80%; max-width: 500px; border-radius: 8px; position: relative; }
        .close-btn { color: #aaa; float: right; font-size: 28px; font-weight: bold; cursor: pointer; }
        .close-btn:hover, .close-btn:focus { color: black; text-decoration: none; }

        /* Table styles */
        #rules-table { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
        #rules-table th, #rules-table td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        #rules-table th { background-color: #f2f2f2; color: #333; }
        #rules-table tr:nth-child(even) { background-color: #f9f9f9; }
        #rules-table .actions-cell button { margin-right: 5px; padding: 5px 10px; font-size: 14px; }
        
        /* Checkbox container styles */
        .checkbox-container { display: flex; flex-wrap: wrap; max-height: 150px; overflow-y: auto; border: 1px solid #ddd; padding: 10px; border-radius: 4px; margin-bottom: 15px; }
        .checkbox-container label { width: 33%; margin-bottom: 5px; font-weight: normal; }
        .checkbox-container input { margin-right: 5px; }
    </style>
</head>
<body>
    <h1>Emby 自动标签 - 管理面板</h1>

    <!-- Webhook 管理 -->
    <div class="container">
        <h2>Emby Webhook 自动化</h2>
        <div id="webhook-settings">
            <div style="margin-bottom: 15px;">
                <label style="display: flex; align-items: center; font-weight: normal;">
                    <input type="checkbox" id="webhook-enabled" style="width: auto; margin-right: 10px;">
                    <strong>启用 Emby Webhook 接收器 (主开关)</strong>
                </label>
            </div>
            <div style="margin-bottom: 15px;">
                <label style="display: flex; align-items: center; font-weight: normal;">
                    <input type="checkbox" id="automation-enabled" style="width: auto; margin-right: 10px;">
                    <strong>启用自动化处理 (处理接收到的数据)</strong>
                </label>
            </div>
            <div style="margin-bottom: 15px;">
                <label style="font-weight: bold;">自动化写入模式:</label>
                <div style="padding-left: 10px;">
                    <label style="display: inline-block; margin-right: 20px; font-weight: normal;"><input type="radio" name="webhook-write-mode" value="merge"> 合并现有标签</label>
                    <label style="display: inline-block; font-weight: normal;"><input type="radio" name="webhook-write-mode" value="overwrite"> 覆盖所有标签</label>
                </div>
            </div>
            <div>
                <label for="webhook-token">安全密钥 (Token):</label>
                <input type="text" id="webhook-token" readonly>
            </div>
            <div>
                <label for="webhook-url">Webhook URL (自动生成):</label>
                <div style="display: flex;">
                    <input type="text" id="webhook-url" readonly style="flex-grow: 1; margin-right: 10px;">
                    <button id="copy-webhook-url-btn" style="flex-shrink: 0;">复制</button>
                </div>
            </div>
        </div>
        <div id="webhook-result" class="result hidden"></div>
    </div>

    <!-- 配置管理 -->
    <div class="container">
        <h2>配置管理</h2>
        <form id="config-form">
            <!-- 配置项将由JS动态填充 -->
        </form>
        <button id="save-config-btn">保存配置</button>
        <div id="config-result" class="result hidden"></div>
    </div>

    <!-- TMDB 测试 -->
    <div class="container">
        <h2>TMDB 信息获取测试</h2>
        <form id="tmdb-form">
            <label for="tmdb-id">TMDB ID:</label>
            <input type="text" id="tmdb-id" placeholder="例如: 550 (搏击俱乐部)" required>
            <label for="tmdb-type">媒体类型:</label>
            <select id="tmdb-type">
                <option value="movie">电影</option>
                <option value="tv">电视剧</option>
            </select>
            <button type="submit">获取信息</button>
        </form>
        <div id="tmdb-result" class="result hidden"></div>
    </div>

    <!-- 规则管理 -->
    <div class="container">
        <h2>标签规则管理</h2>
        <table id="rules-table">
            <thead>
                <tr>
                    <th>规则名称</th>
                    <th>生成的标签</th>
                    <th>国家/地区</th>
                    <th>类型</th>
                    <th>作用于</th>
                    <th>操作</th>
                </tr>
            </thead>
            <tbody id="rules-table-body">
                <!-- 规则将由JS动态填充 -->
            </tbody>
        </table>
        <br>
        <button id="add-rule-btn">添加新规则</button>
        <hr>
        <button id="save-rules-btn">保存所有规则</button>
        <div id="rules-result" class="result hidden"></div>
    </div>

    <!-- Emby 写入测试 -->
    <div class="container">
        <h2>Emby 标签写入测试</h2>
        <form id="emby-form">
            <label for="emby-tmdb-id">TMDB ID:</label>
            <input type="text" id="emby-tmdb-id" placeholder="输入 Emby 库中存在的 TMDB ID" required>
            
            <label for="emby-media-type">媒体类型:</label>
            <select id="emby-media-type" style="margin-bottom: 15px;">
                <option value="Movie">电影</option>
                <option value="Series">剧集</option>
            </select>

            <label for="emby-tags">要写入的标签 (英文逗号分隔):</label>
            <input type="text" id="emby-tags" placeholder="例如: 测试标签1,测试标签2" required>
            
            <label>写入模式:</label>
            <div style="margin-bottom: 15px;">
                <label style="display: inline-block; margin-right: 20px; font-weight: normal;"><input type="radio" name="emby-write-mode" value="merge" checked> 合并现有标签</label>
                <label style="display: inline-block; font-weight: normal;"><input type="radio" name="emby-write-mode" value="overwrite"> 覆盖所有标签</label>
            </div>

            <button type="button" id="emby-test-btn">测试写入 (预览)</button>
            <button type="button" id="emby-write-btn" style="background-color: #c0392b;">确认写入</button>
        </form>
        <div id="emby-result" class="result hidden"></div>
    </div>

    <!-- 清除所有标签 -->
    <div class="container">
        <h2>清除所有 Emby 媒体库标签</h2>
        <p style="color: red; font-weight: bold;">警告: 此操作将清除 Emby 媒体库中所有电影和剧集的标签，不可撤销！</p>
        <button type="button" id="clear-all-tags-btn" style="background-color: #e74c3c;">确认清除所有标签</button>
        <div id="clear-all-tags-result" class="result hidden"></div>
    </div>

    <!-- 一键打标签 -->
    <div class="container">
        <h2>一键为所有媒体打标签</h2>
        <p>此功能将遍历 Emby 媒体库中所有电影和剧集，根据已配置的规则自动生成并应用标签。</p>
        <div style="margin-bottom: 15px;">
            <label style="font-weight: bold;">写入模式:</label>
            <div style="padding-left: 10px;">
                <label style="display: inline-block; margin-right: 20px; font-weight: normal;"><input type="radio" name="tag-all-media-mode" value="merge" checked> 合并现有标签</label>
                <label style="display: inline-block; font-weight: normal;"><input type="radio" name="tag-all-media-mode" value="overwrite"> 覆盖所有标签</label>
            </div>
        </div>
        <button type="button" id="tag-all-media-btn" style="background-color: #27ae60;">开始一键打标签</button>
        <div id="tag-all-media-result" class="result hidden"></div>
    </div>

    <!-- 整合测试 -->
    <div class="container">
        <h2>整合流程测试</h2>
        <form id="full-flow-form">
            <label for="full-flow-tmdb-id">TMDB ID:</label>
            <input type="text" id="full-flow-tmdb-id" placeholder="例如: 550" required>
            <label for="full-flow-media-type">媒体类型:</label>
            <select id="full-flow-media-type">
                <option value="movie">电影</option>
                <option value="tv">电视剧</option>
            </select>
            <button type="submit">获取信息并预览标签</button>
        </form>
        <div id="full-flow-result" class="result hidden"></div>
    </div>

    <!-- 规则编辑/添加 Modal -->
    <div id="rule-modal" class="modal hidden">
        <div class="modal-content">
            <span class="close-btn">&times;</span>
            <h3 id="modal-title">添加新规则</h3>
            <form id="rule-form">
                <input type="hidden" id="rule-index">
                <label for="rule-name">规则名称:</label>
                <input type="text" id="rule-name" required>
                <label for="rule-tag">生成的标签:</label>
                <input type="text" id="rule-tag" required>
                <label>国家/地区:</label>
                <div id="rule-countries-container" class="checkbox-container"></div>
                <label>类型:</label>
                <div id="rule-genres-container" class="checkbox-container"></div>
                <label for="rule-item-type">作用于:</label>
                <select id="rule-item-type">
                    <option value="all">全部</option>
                    <option value="movie">电影</option>
                    <option value="series">剧集</option>
                </select>
                <button type="submit">保存规则</button>
            </form>
        </div>
    </div>

<script>
document.addEventListener('DOMContentLoaded', function() {
    const apiPrefix = '/api';
    let dataMaps = { countries: {}, genres: {} };

    // --- 通用函数 ---
    function showResult(element, message, isError = false) {
        element.innerHTML = message;
        element.style.color = isError ? 'red' : 'green';
        element.classList.remove('hidden');
    }

    function showLoading(button, show = true) {
        if (show) {
            button.disabled = true;
            button.innerHTML += ' <div class="spinner"></div>';
        } else {
            button.disabled = false;
            const spinner = button.querySelector('.spinner');
            if (spinner) spinner.remove();
        }
    }

    // --- 配置管理 ---
    const configForm = document.getElementById('config-form');
    const saveConfigBtn = document.getElementById('save-config-btn');
    const configResult = document.getElementById('config-result');

    // --- Webhook 管理 ---
    const webhookEnabledCheckbox = document.getElementById('webhook-enabled');
    const automationEnabledCheckbox = document.getElementById('automation-enabled');
    const webhookWriteModeRadios = document.querySelectorAll('input[name="webhook-write-mode"]');
    const webhookTokenInput = document.getElementById('webhook-token');
    const webhookUrlInput = document.getElementById('webhook-url');
    const copyWebhookUrlBtn = document.getElementById('copy-webhook-url-btn');
    const webhookResult = document.getElementById('webhook-result');
    let currentFullConfig = {};

    function updateWebhookUI(config) {
        const webhookConfig = config.WEBHOOK || {};
        const isEnabled = webhookConfig.enabled === 'true';
        const automationEnabled = webhookConfig.automation_enabled === 'true';
        const writeMode = webhookConfig.write_mode || 'merge';
        const token = webhookConfig.secret_token || '';

        webhookEnabledCheckbox.checked = isEnabled;
        automationEnabledCheckbox.checked = automationEnabled;
        document.querySelector(`input[name="webhook-write-mode"][value="${writeMode}"]`).checked = true;
        webhookTokenInput.value = token;
        
        if (token) {
            // 使用 window.location.origin 来动态构建基础 URL
            const baseUrl = window.location.origin;
            webhookUrlInput.value = `${baseUrl}${apiPrefix}/webhook/${token}`;
        } else {
            webhookUrlInput.value = '保存配置后自动生成';
        }
    }

    copyWebhookUrlBtn.addEventListener('click', () => {
        webhookUrlInput.select();
        document.execCommand('copy');
        showResult(webhookResult, 'URL 已复制到剪贴板！');
        setTimeout(() => webhookResult.classList.add('hidden'), 2000);
    });

    async function saveWebhookSwitch(key, value) {
        if (currentFullConfig.WEBHOOK) {
            currentFullConfig.WEBHOOK[key] = value.toString();
            
            try {
                const response = await fetch(`${apiPrefix}/config`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(currentFullConfig)
                });
                const result = await response.json();
                if (!response.ok) throw new Error(result.detail || '保存失败');
                const statusText = key === 'enabled' ? '接收器' : '自动化处理';
                showResult(webhookResult, `${statusText}状态已更新为: ${value ? '启用' : '禁用'}`);
            } catch (error) {
                showResult(webhookResult, `错误: ${error.message}`, true);
            }
        }
    }

    webhookEnabledCheckbox.addEventListener('change', () => {
        saveWebhookSwitch('enabled', webhookEnabledCheckbox.checked);
    });

    automationEnabledCheckbox.addEventListener('change', () => {
        saveWebhookSwitch('automation_enabled', automationEnabledCheckbox.checked);
    });

    webhookWriteModeRadios.forEach(radio => {
        radio.addEventListener('change', () => {
            if (radio.checked) {
                saveWebhookSwitch('write_mode', radio.value);
            }
        });
    });

    async function loadConfig() {
        try {
            const response = await fetch(`${apiPrefix}/config`);
            if (!response.ok) throw new Error('无法加载配置');
            const config = await response.json();
            currentFullConfig = config; // 存储完整配置
            
            // 更新 Webhook UI
            updateWebhookUI(config);

            configForm.innerHTML = '';
            const sectionNames = {
                "DEFAULT": "通用设置",
                "EMBY": "Emby 设置",
                "TMDB": "TMDB 设置",
                "PROXY": "代理设置"
            };
            const keyNames = {
                "project_name": "项目名称",
                "server_url": "服务器地址",
                "api_key": "API 密钥",
                "user_id": "用户 ID (可选)",
                "http_proxy": "HTTP 代理地址"
            };

            const defaultConfig = config['DEFAULT'] || {};
            
            for (const section in config) {
                if (section === 'WEBHOOK') continue; // 不在通用表单中显示 WEBHOOK 部分
                const fieldset = document.createElement('fieldset');
                const legend = document.createElement('legend');
                legend.textContent = sectionNames[section] || `[${section}]`;
                fieldset.appendChild(legend);

                for (const key in config[section]) {
                    // 避免在其他 section 重复显示 DEFAULT 中的项
                    if (section !== 'DEFAULT' && key in defaultConfig) {
                        continue;
                    }
                    const label = document.createElement('label');
                    label.textContent = `${keyNames[key] || key}:`;
                    const input = document.createElement('input');
                    // 按照要求，所有字段都使用 text 类型以明文显示
                    input.type = 'text';
                    input.name = `${section}.${key}`;
                    input.value = config[section][key];
                    label.appendChild(input);
                    fieldset.appendChild(label);
                }
                configForm.appendChild(fieldset);
            }
        } catch (error) {
            showResult(configResult, `错误: ${error.message}`, true);
        }
    }

    saveConfigBtn.addEventListener('click', async () => {
        const formData = new FormData(configForm);
        const configData = {};
        for (const [key, value] of formData.entries()) {
            const [section, option] = key.split('.');
            if (!configData[section]) {
                configData[section] = {};
            }
            configData[section][option] = value;
        }
        
        showLoading(saveConfigBtn);
        try {
            const response = await fetch(`${apiPrefix}/config`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(configData)
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.detail || '保存失败');
            showResult(configResult, "配置保存成功！部分设置可能需要重启服务才能生效。");
            // 重新加载以显示新值（特别是密码字段）
            setTimeout(loadConfig, 1000);
        } catch (error) {
            showResult(configResult, `错误: ${error.message}`, true);
        } finally {
            showLoading(saveConfigBtn, false);
        }
    });

    // --- TMDB 测试 ---
    const tmdbForm = document.getElementById('tmdb-form');
    const tmdbResult = document.getElementById('tmdb-result');

    tmdbForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const tmdbId = document.getElementById('tmdb-id').value;
        const mediaType = document.getElementById('tmdb-type').value;
        const button = tmdbForm.querySelector('button');
        
        showLoading(button);
        tmdbResult.classList.add('hidden');
        try {
            const response = await fetch(`${apiPrefix}/test/tmdb`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ tmdb_id: tmdbId, media_type: mediaType })
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.detail || '获取信息失败');
            
            const rawDetailsJson = JSON.stringify(result.raw_details, null, 2);
            const extracted = result.extracted_info;

            const genresText = extracted.genres.map(g => `${g.name} (ID: ${g.id})`).join(', ') || '无';
            const countriesText = extracted.countries.map(c => `${c.name} (Code: ${c.iso_3166_1})`).join(', ') || '无';

            tmdbResult.innerHTML = `
                <h4>提取的信息</h4>
                <p><strong>类型:</strong> ${genresText}</p>
                <p><strong>地区:</strong> ${countriesText}</p>
                <hr>
                <h4>原始数据</h4>
                <pre>${rawDetailsJson}</pre>
            `;
            tmdbResult.classList.remove('hidden');
        } catch (error) {
            tmdbResult.innerHTML = `<p style="color:red;">错误: ${error.message}</p>`;
            tmdbResult.classList.remove('hidden');
        } finally {
            showLoading(button, false);
        }
    });

    // --- 规则管理 ---
    const rulesTableBody = document.getElementById('rules-table-body');
    const addRuleBtn = document.getElementById('add-rule-btn');
    const saveRulesBtn = document.getElementById('save-rules-btn');
    const rulesResult = document.getElementById('rules-result');
    const ruleModal = document.getElementById('rule-modal');
    const ruleForm = document.getElementById('rule-form');
    const modalTitle = document.getElementById('modal-title');
    const closeModalBtn = ruleModal.querySelector('.close-btn');

    let currentRules = [];

    function populateCheckboxes() {
        const countriesContainer = document.getElementById('rule-countries-container');
        const genresContainer = document.getElementById('rule-genres-container');
        countriesContainer.innerHTML = '';
        genresContainer.innerHTML = '';

        for (const [code, name] of Object.entries(dataMaps.countries).sort((a, b) => a[1].localeCompare(b[1], 'zh-CN'))) {
            countriesContainer.innerHTML += `
                <label><input type="checkbox" name="countries" value="${code}"> ${name}</label>
            `;
        }

        for (const [id, name] of Object.entries(dataMaps.genres).sort((a, b) => a[1].localeCompare(b[1], 'zh-CN'))) {
            genresContainer.innerHTML += `
                <label><input type="checkbox" name="genres" value="${id}"> ${name}</label>
            `;
        }
    }

    function renderRules() {
        rulesTableBody.innerHTML = '';
        if (!currentRules) return;
        currentRules.forEach((rule, index) => {
            const countryNames = (rule.conditions.countries || []).map(code => dataMaps.countries[code] || code).join(', ');
            const genreNames = (rule.conditions.genre_ids || []).map(id => dataMaps.genres[id] || id).join(', ');

            const itemTypeDisplay = {
                "movie": "电影",
                "series": "剧集",
                "all": "全部"
            }[rule.item_type] || "全部"; // Display name for item_type

            const row = rulesTableBody.insertRow();
            row.innerHTML = `
                <td>${rule.name || ''}</td>
                <td>${rule.tag || ''}</td>
                <td>${countryNames}</td>
                <td>${genreNames}</td>
                <td>${itemTypeDisplay}</td>
                <td class="actions-cell">
                    <button class="edit-rule-btn" data-index="${index}">编辑</button>
                    <button class="delete-rule-btn" data-index="${index}">删除</button>
                </td>
            `;
        });

        // Re-attach event listeners
        document.querySelectorAll('.delete-rule-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const indexToDelete = parseInt(e.target.dataset.index, 10);
                if (confirm(`确定要删除规则 "${currentRules[indexToDelete].name}" 吗?`)) {
                    currentRules.splice(indexToDelete, 1);
                    renderRules();
                }
            });
        });

        document.querySelectorAll('.edit-rule-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const indexToEdit = parseInt(e.target.dataset.index, 10);
                openModal(indexToEdit);
            });
        });
    }

    function openModal(index = null) {
        ruleForm.reset();
        if (index !== null) {
            // Edit mode
            modalTitle.textContent = '编辑规则';
            const rule = currentRules[index];
            document.getElementById('rule-index').value = index;
            document.getElementById('rule-name').value = rule.name;
            document.getElementById('rule-tag').value = rule.tag;
            
            // Check selected countries
            (rule.conditions.countries || []).forEach(code => {
                const checkbox = ruleForm.querySelector(`input[name="countries"][value="${code}"]`);
                if (checkbox) checkbox.checked = true;
            });

            // Check selected genres
            (rule.conditions.genre_ids || []).forEach(id => {
                const checkbox = ruleForm.querySelector(`input[name="genres"][value="${id}"]`);
                if (checkbox) checkbox.checked = true;
            });

            // Set item_type
            document.getElementById('rule-item-type').value = rule.item_type || 'all';

        } else {
            // Add mode
            modalTitle.textContent = '添加新规则';
            document.getElementById('rule-index').value = '';
            document.getElementById('rule-item-type').value = 'all'; // Default for new rules
        }
        ruleModal.classList.remove('hidden');
    }

    function closeModal() {
        ruleModal.classList.add('hidden');
    }

    async function loadInitialData() {
        try {
            // Load data maps first
            const mapsResponse = await fetch(`${apiPrefix}/data/maps`);
            if (!mapsResponse.ok) throw new Error('无法加载数据映射');
            dataMaps = await mapsResponse.json();
            populateCheckboxes();

            // Then load rules
            const rulesResponse = await fetch(`${apiPrefix}/rules`);
            if (!rulesResponse.ok) throw new Error('无法加载规则');
            currentRules = await rulesResponse.json();
            renderRules();
        } catch (error) {
            showResult(rulesResult, `错误: ${error.message}`, true);
        }
    }

    addRuleBtn.addEventListener('click', () => {
        openModal();
    });

    closeModalBtn.addEventListener('click', closeModal);
    window.addEventListener('click', (event) => {
        if (event.target == ruleModal) {
            closeModal();
        }
    });

    ruleForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const index = document.getElementById('rule-index').value;
        const name = document.getElementById('rule-name').value;
        const tag = document.getElementById('rule-tag').value;
        
        const selectedCountries = Array.from(ruleForm.querySelectorAll('input[name="countries"]:checked')).map(cb => cb.value);
        const selectedGenreIds = Array.from(ruleForm.querySelectorAll('input[name="genres"]:checked')).map(cb => parseInt(cb.value, 10));
        const itemType = document.getElementById('rule-item-type').value;

        const newRule = { name, tag, conditions: { countries: selectedCountries, genre_ids: selectedGenreIds }, item_type: itemType };

        if (index) {
            // Update existing rule
            currentRules[parseInt(index, 10)] = newRule;
        } else {
            // Add new rule
            currentRules.push(newRule);
        }
        renderRules();
        closeModal();
    });

    saveRulesBtn.addEventListener('click', async () => {
        showLoading(saveRulesBtn);
        try {
            const response = await fetch(`${apiPrefix}/rules`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(currentRules) // Just save the current state
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.detail || '保存规则失败');
            showResult(rulesResult, result.message);
        } catch (error) {
            showResult(rulesResult, `错误: ${error.message}`, true);
        } finally {
            showLoading(saveRulesBtn, false);
        }
    });


    // --- Emby 写入测试 ---
    const embyForm = document.getElementById('emby-form');
    const embyResult = document.getElementById('emby-result');
    const embyTestBtn = document.getElementById('emby-test-btn');
    const embyWriteBtn = document.getElementById('emby-write-btn');

    async function handleEmbyWrite(isTest) {
        const tmdbId = document.getElementById('emby-tmdb-id').value;
        const mediaType = document.getElementById('emby-media-type').value;
        const tags = document.getElementById('emby-tags').value.split(',').map(tag => tag.trim()).filter(Boolean);
        const mode = document.querySelector('input[name="emby-write-mode"]:checked').value;
        const button = isTest ? embyTestBtn : embyWriteBtn;

        if (!tmdbId || tags.length === 0) {
            alert('请输入 TMDB ID 和至少一个标签。');
            return;
        }
        
        if (!isTest) {
            if (!confirm(`确定要以 [${mode === 'merge' ? '合并' : '覆盖'}] 模式，将标签写入到 TMDB ID 为 ${tmdbId} 的项目吗？此操作不可撤销。`)) {
                return;
            }
        }

        showLoading(button);
        embyResult.classList.add('hidden');
        try {
            const response = await fetch(`${apiPrefix}/test/emby`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    tmdb_id: tmdbId,
                    media_type: mediaType,
                    tags: tags,
                    mode: mode,
                    is_test: isTest 
                })
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.detail || '操作失败');

            let resultHtml = `<h4>操作结果: ${result.action === 'preview' ? '预览' : '写入'} (${result.mode === 'merge' ? '合并模式' : '覆盖模式'})</h4>`;
            resultHtml += `<p>找到 ${result.found_items_count} 个匹配项目。</p>`;
            
            if (result.updated_items_count > 0) {
                resultHtml += `<p style="color: green;">成功处理 ${result.updated_items_count} 个项目:</p><ul>`;
                result.updated_items.forEach(item => {
                    resultHtml += `<li><strong>${item.name}</strong> (ID: ${item.id})</li>`;
                    if (isTest) {
                        resultHtml += `<ul>
                            <li>原始标签: ${item.original_tags.join(', ') || '<em>无</em>'}</li>
                            <li>最终标签: ${item.final_tags.join(', ') || '<em>无</em>'}</li>
                        </ul>`;
                    }
                });
                resultHtml += `</ul>`;
            }

            if (result.failed_items_count > 0) {
                resultHtml += `<p style="color: red;">处理失败 ${result.failed_items_count} 个项目:</p><ul>`;
                result.failed_items.forEach(item => {
                    resultHtml += `<li><strong>${item.name}</strong> (ID: ${item.id})</li>`;
                });
                resultHtml += `</ul>`;
            }
            
            embyResult.innerHTML = resultHtml;
            embyResult.classList.remove('hidden');

        } catch (error) {
            embyResult.innerHTML = `<p style="color:red;">错误: ${error.message}</p>`;
            embyResult.classList.remove('hidden');
        } finally {
            showLoading(button, false);
        }
    }

    embyTestBtn.addEventListener('click', () => handleEmbyWrite(true));
    embyWriteBtn.addEventListener('click', () => handleEmbyWrite(false));

    // --- 清除所有标签功能 ---
    const clearAllTagsBtn = document.getElementById('clear-all-tags-btn');
    const clearAllTagsResult = document.getElementById('clear-all-tags-result');

    clearAllTagsBtn.addEventListener('click', async () => {
        if (!confirm("您确定要清除 Emby 媒体库中所有电影和剧集的标签吗？此操作不可撤销！")) {
            return;
        }

        showLoading(clearAllTagsBtn);
        clearAllTagsResult.classList.add('hidden');
        try {
            const response = await fetch(`${apiPrefix}/test/clear-all-tags`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.detail || '清除失败');

            showResult(clearAllTagsResult, `
                <h4>清除结果:</h4>
                <p style="color: green;">${result.message}</p>
                <p>成功清除: ${result.cleared_count} 个项目</p>
                <p>清除失败: ${result.failed_count} 个项目</p>
            `);
        } catch (error) {
            showResult(clearAllTagsResult, `错误: ${error.message}`, true);
        } finally {
            showLoading(clearAllTagsBtn, false);
        }
    });

    // --- 一键打标签功能 ---
    const tagAllMediaBtn = document.getElementById('tag-all-media-btn');
    const tagAllMediaResult = document.getElementById('tag-all-media-result');
    const tagAllMediaModeRadios = document.querySelectorAll('input[name="tag-all-media-mode"]');

    let currentTagAllMediaTaskId = null;
    let tagAllMediaPollingInterval = null;

    async function pollTagAllMediaStatus(taskId) {
        if (!taskId) return;

        try {
            const response = await fetch(`${apiPrefix}/tag_all_media/status/${taskId}`);
            const result = await response.json();

            if (!response.ok) {
                showResult(tagAllMediaResult, `错误: 无法获取任务状态 - ${result.detail || '未知错误'}`, true);
                clearInterval(tagAllMediaPollingInterval);
                showLoading(tagAllMediaBtn, false);
                return;
            }

            let statusMessage = `
                <h4>任务状态: ${result.status}</h4>
                <p>模式: ${result.mode === 'merge' ? '合并' : '覆盖'}</p>
                <p>已处理项目: ${result.processed_count}</p>
                <p>已更新项目: ${result.updated_count}</p>
                <p>失败项目: ${result.failed_count}</p>
            `;

            if (result.status === 'completed') {
                statusMessage += `<p style="color: green; font-weight: bold;">打标签任务已完成！</p>`;
                clearInterval(tagAllMediaPollingInterval);
                showLoading(tagAllMediaBtn, false);
            } else if (result.status === 'failed') {
                statusMessage += `<p style="color: red; font-weight: bold;">打标签任务失败: ${result.error || '未知错误'}</p>`;
                clearInterval(tagAllMediaPollingInterval);
                showLoading(tagAllMediaBtn, false);
            } else {
                statusMessage += `<p>任务正在进行中...</p>`;
            }
            showResult(tagAllMediaResult, statusMessage);

        } catch (error) {
            showResult(tagAllMediaResult, `错误: 轮询任务状态失败 - ${error.message}`, true);
            clearInterval(tagAllMediaPollingInterval);
            showLoading(tagAllMediaBtn, false);
        }
    }

    tagAllMediaBtn.addEventListener('click', async () => {
        const mode = document.querySelector('input[name="tag-all-media-mode"]:checked').value;
        if (!confirm(`您确定要以 [${mode === 'merge' ? '合并' : '覆盖'}] 模式，对所有 Emby 媒体库中的电影和剧集进行打标签操作吗？此操作将在后台执行，并在页面上显示进度。`)) {
            return;
        }

        showLoading(tagAllMediaBtn);
        tagAllMediaResult.classList.add('hidden');
        
        // 清除之前的轮询
        if (tagAllMediaPollingInterval) {
            clearInterval(tagAllMediaPollingInterval);
        }

        try {
            const response = await fetch(`${apiPrefix}/tag_all_media`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ mode: mode })
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.detail || '启动任务失败');

            currentTagAllMediaTaskId = result.task_id;
            showResult(tagAllMediaResult, `
                <h4>任务启动成功:</h4>
                <p style="color: green;">打标签任务已在后台启动，任务ID: <code>${currentTagAllMediaTaskId}</code></p>
                <p>正在获取任务进度...</p>
            `);

            // 启动轮询
            tagAllMediaPollingInterval = setInterval(() => pollTagAllMediaStatus(currentTagAllMediaTaskId), 3000); // 每3秒轮询一次
            pollTagAllMediaStatus(currentTagAllMediaTaskId); // 立即执行一次
            
        } catch (error) {
            showResult(tagAllMediaResult, `错误: ${error.message}`, true);
            showLoading(tagAllMediaBtn, false);
        }
    });

    // --- 整合测试 ---
    const fullFlowForm = document.getElementById('full-flow-form');
    const fullFlowResult = document.getElementById('full-flow-result');

    fullFlowForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const tmdbId = document.getElementById('full-flow-tmdb-id').value;
        const mediaType = document.getElementById('full-flow-media-type').value;
        const button = fullFlowForm.querySelector('button');

        showLoading(button);
        fullFlowResult.classList.add('hidden');
        try {
            const response = await fetch(`${apiPrefix}/test/full-flow-preview`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ tmdb_id: tmdbId, media_type: mediaType })
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.detail || '操作失败');

            let resultHtml = `<h4>预览结果 (TMDB ID: ${result.tmdb_id})</h4>`;
            
            // TMDB Info
            resultHtml += `
                <p><strong>标题:</strong> ${result.tmdb_details.title} (${result.tmdb_details.release_date})</p>
                <p><strong>类型:</strong> ${result.tmdb_details.genres.join(', ')}</p>
                <p><strong>地区:</strong> ${result.tmdb_details.countries.join(', ')}</p>
            `;

            // Generated Tags
            const generatedTagsString = result.generated_tags.join(', ');
            resultHtml += `<p><strong>根据规则生成的标签:</strong> <code id="generated-tags-code">${generatedTagsString}</code></p>`;

            // Emby Items
            if (result.emby_items_found.length > 0) {
                resultHtml += `<p><strong>在 Emby 中找到 ${result.emby_items_found.length} 个匹配项目:</strong></p><ul>`;
                result.emby_items_found.forEach(item => {
                    resultHtml += `<li>${item.name} (ID: ${item.id})<br><em>当前标签: ${item.original_tags.join(', ') || '无'}</em></li>`;
                });
                resultHtml += `</ul>`;

                // Add action buttons
                resultHtml += `
                    <hr>
                    <p><strong>执行操作:</strong></p>
                    <p>使用上面生成的标签，对找到的 Emby 项目进行写入操作。</p>
                    <button id="full-flow-merge-btn" class="action-btn" data-tmdb-id="${result.tmdb_id}" data-media-type="${result.media_type}" data-tags='${JSON.stringify(result.generated_tags)}'>合并写入</button>
                    <button id="full-flow-overwrite-btn" class="action-btn" style="background-color: #e74c3c;" data-tmdb-id="${result.tmdb_id}" data-media-type="${result.media_type}" data-tags='${JSON.stringify(result.generated_tags)}'>覆盖写入</button>
                `;
            } else {
                resultHtml += `<p style="color: orange;"><strong>在 Emby 中未找到匹配的项目。</strong></p>`;
            }

            fullFlowResult.innerHTML = resultHtml;
            fullFlowResult.classList.remove('hidden');

        } catch (error) {
            fullFlowResult.innerHTML = `<p style="color:red;">错误: ${error.message}</p>`;
            fullFlowResult.classList.remove('hidden');
        } finally {
            showLoading(button, false);
        }
    });

    // Event delegation for action buttons
    fullFlowResult.addEventListener('click', async (e) => {
        if (e.target.classList.contains('action-btn')) {
            const button = e.target;
            const tmdbId = button.dataset.tmdbId;
            const mediaType = button.dataset.mediaType;
            const tags = JSON.parse(button.dataset.tags);
            const mode = button.id.includes('merge') ? 'merge' : 'overwrite';

            // Populate and use the existing Emby Write Test form
            document.getElementById('emby-tmdb-id').value = tmdbId;
            document.getElementById('emby-media-type').value = mediaType;
            document.getElementById('emby-tags').value = tags.join(', ');
            document.querySelector(`input[name="emby-write-mode"][value="${mode}"]`).checked = true;
            
            // Scroll to the form and trigger the write action
            const embyFormContainer = document.getElementById('emby-form').parentElement;
            embyFormContainer.scrollIntoView({ behavior: 'smooth' });
            embyFormContainer.style.border = '2px solid #3498db';
            setTimeout(() => { embyFormContainer.style.border = 'none'; }, 2000);

            if (confirm(`将使用自动生成的标签对 TMDB ID ${tmdbId} 进行 [${mode}] 操作，是否继续？`)) {
                handleEmbyWrite(false); // false for actual write
            }
        }
    });

    // --- 初始化 ---
    loadConfig();
    loadInitialData();
});
</script>
</body>
</html>
    """
