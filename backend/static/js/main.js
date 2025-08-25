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
