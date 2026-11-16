import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const TARGET_NODES = new Set(["MultiModalAssistant", "GoogleNanoNode"]);
const MANUAL_MODEL = "手动填写";
let profileCache = [];
let profilesLoaded = false;

async function requestJson(path, options = {}) {
    const method = (options.method || "GET").toUpperCase();
    const requestOptions = {
        ...options,
        cache: "no-store",
        headers: {
            ...(method === "GET" ? {} : { "Content-Type": "application/json" }),
            ...(options.headers || {}),
        },
    };
    let response;
    try {
        response = await api.fetchApi(path, requestOptions);
    } catch (_error) {
        // A second GET through the native fetch API can work on hosted
        // ComfyUI deployments whose frontend fetch wrapper is unavailable.
        // Never retry mutations: save/delete/clear-key must execute at most once.
        if (method === "GET" && typeof api.apiURL === "function") {
            try {
                response = await fetch(api.apiURL(path), {
                    ...requestOptions,
                    credentials: "same-origin",
                });
            } catch (_fallbackError) {
                // The path is safe to reveal; API credentials never appear here.
            }
        }
        if (!response) {
            throw new Error(`无法连接 ComfyUI 服务商接口（${path}）。请确认 ComfyUI 正在运行、插件已加载，并检查云端代理是否允许访问 /ai_chat/ 路径。`);
        }
    }
    let body = {};
    try {
        body = await response.json();
    } catch (_error) {
        body = {};
    }
    if (!response.ok) {
        const reason = body.error || `请求失败（HTTP ${response.status}）`;
        throw new Error(`${reason} [${path}]${response.status === 404 ? "；请重启 ComfyUI 并确认插件的配置接口已成功注册。" : ""}`);
    }
    return body;
}

async function loadProfiles() {
    const body = await requestJson("/ai_chat/profiles");
    if (!Array.isArray(body.profiles)) {
        throw new Error("服务商接口返回的配置列表无效，未覆盖现有缓存。");
    }
    profileCache = body.profiles;
    profilesLoaded = true;
    return profileCache;
}

function findWidget(node, name) {
    return node.widgets?.find((widget) => widget.name === name);
}

function updateCombo(widget, values, preferredValue = "") {
    if (!widget) return;
    const normalized = [...new Set(values.filter(Boolean))];
    widget.options ||= {};
    widget.options.values = normalized;
    if (preferredValue && normalized.includes(preferredValue)) {
        widget.value = preferredValue;
    } else if (!normalized.includes(widget.value)) {
        widget.value = normalized[0] || "";
    }
}

function modelValues(profile) {
    const values = Array.isArray(profile?.models) ? [...profile.models] : [];
    if (profile?.default_model) values.unshift(profile.default_model);
    values.push(MANUAL_MODEL);
    return [...new Set(values)];
}

async function syncAllNodes() {
    const profiles = profilesLoaded ? profileCache : await loadProfiles();
    const names = profiles.length ? profiles.map((profile) => profile.name) : ["请先配置服务商"];
    for (const node of app.graph?._nodes || []) {
        if (!TARGET_NODES.has(node.__aiChatNodeType)) continue;
        const providerWidget = findWidget(node, "服务商配置");
        const previousProvider = providerWidget?.value;
        const sameProvider = names.includes(previousProvider);
        updateCombo(providerWidget, names, providerWidget?.value);
        const profile = profiles.find((item) => item.name === providerWidget?.value) || profiles[0];
        const modelWidget = findWidget(node, "选择模型");
        const values = modelValues(profile);
        if (sameProvider && profile && modelWidget?.value && !values.includes(modelWidget.value)) {
            values.unshift(modelWidget.value);
        }
        const preferredModel = sameProvider && profile ? modelWidget?.value : profile?.default_model;
        updateCombo(modelWidget, values, preferredModel);
        node.setDirtyCanvas?.(true, true);
    }
}

async function refreshNodeModels(node, forceRefresh) {
    const providerWidget = findWidget(node, "服务商配置");
    const profileName = providerWidget?.value;
    if (!profileName) throw new Error("请先选择服务商配置。");

    await loadProfiles();
    if (!profileCache.some((entry) => entry.name === profileName)) {
        throw new Error("当前服务商配置已不存在，请先在管理服务商中保存配置。");
    }

    if (forceRefresh) {
        await requestJson("/ai_chat/models/refresh", {
            method: "POST",
            body: JSON.stringify({ name: profileName }),
        });
    }
    await loadProfiles();
    const profile = profileCache.find((item) => item.name === profileName);
    const modelWidget = findWidget(node, "选择模型");
    const values = modelValues(profile);
    if (forceRefresh && modelWidget?.value && !values.includes(modelWidget.value)) {
        values.unshift(modelWidget.value);
    }
    const preferredModel = forceRefresh ? modelWidget?.value : profile?.default_model;
    updateCombo(modelWidget, values, preferredModel);
    node.setDirtyCanvas?.(true, true);
}

function makeElement(tag, attributes = {}, text = "") {
    const element = document.createElement(tag);
    for (const [key, value] of Object.entries(attributes)) {
        if (key === "className") element.className = value;
        else if (key === "type") element.type = value;
        else element.setAttribute(key, value);
    }
    if (text) element.textContent = text;
    return element;
}

function ensureStyles() {
    if (document.getElementById("ai-chat-provider-style")) return;
    const style = makeElement("style", { id: "ai-chat-provider-style" });
    style.textContent = `
        .ai-chat-modal-backdrop { position: fixed; inset: 0; z-index: 10050; display: grid; place-items: center; background: rgba(0,0,0,.62); }
        .ai-chat-modal { width: min(560px, calc(100vw - 32px)); max-height: calc(100vh - 32px); overflow: auto; color: #ececf1; background: #202124; border: 1px solid #4b4d52; border-radius: 12px; box-shadow: 0 24px 80px rgba(0,0,0,.5); font: 14px/1.45 system-ui, sans-serif; }
        .ai-chat-modal header, .ai-chat-modal footer { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 16px 18px; border-bottom: 1px solid #3a3b40; }
        .ai-chat-modal footer { border-top: 1px solid #3a3b40; border-bottom: 0; justify-content: flex-end; }
        .ai-chat-modal h2 { margin: 0; font-size: 18px; }
        .ai-chat-modal main { display: grid; gap: 14px; padding: 18px; }
        .ai-chat-field { display: grid; gap: 6px; }
        .ai-chat-field label { color: #c8c9ce; font-weight: 600; }
        .ai-chat-field input, .ai-chat-field select { box-sizing: border-box; width: 100%; padding: 9px 10px; color: #f5f5f7; background: #151619; border: 1px solid #555861; border-radius: 7px; }
        .ai-chat-field input[readonly] { color: #aeb0b7; background: #292a2f; cursor: not-allowed; }
        .ai-chat-inline { display: flex; align-items: center; gap: 8px; }
        .ai-chat-inline input:not([type=checkbox]) { min-width: 0; flex: 1; }
        .ai-chat-inline input[type=checkbox] { width: auto; }
        .ai-chat-inline .ai-chat-button { flex: none; white-space: nowrap; }
        .ai-chat-button { padding: 8px 12px; color: #f5f5f7; background: #34363c; border: 1px solid #5b5e67; border-radius: 7px; cursor: pointer; }
        .ai-chat-button:hover { background: #41444b; }
        .ai-chat-button:disabled { opacity: .45; cursor: not-allowed; }
        .ai-chat-icon-button { display: grid; place-items: center; width: 40px; height: 40px; padding: 8px; }
        .ai-chat-icon-button svg { width: 20px; height: 20px; fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
        .ai-chat-primary { background: #3767d6; border-color: #4b7ced; }
        .ai-chat-danger { margin-right: auto; color: #ffb9b9; }
        .ai-chat-warning { display: none; padding: 9px 10px; color: #ffd18b; background: #4a3418; border-radius: 7px; }
        .ai-chat-status { min-height: 20px; color: #aeb7c5; }
        .ai-chat-status.error { color: #ff9a9a; }
        .ai-chat-help { color: #aeb7c5; font-size: 13px; }
    `;
    document.head.appendChild(style);
}

async function confirmAction(title, message) {
    const dialog = app.extensionManager?.dialog;
    if (dialog?.confirm) return dialog.confirm({ title, message });
    return typeof window.confirm === "function" ? window.confirm(message) : false;
}

function showAlert(message) {
    const toast = app.extensionManager?.toast;
    if (toast?.addAlert) toast.addAlert(message);
    else console.error(`[AI Chat] ${message}`);
}

async function openProfileManager(sourceNode) {
    ensureStyles();
    const existingModal = document.getElementById("ai-chat-provider-modal");
    if (existingModal) {
        existingModal.querySelector("select")?.focus();
        return;
    }
    const backdrop = makeElement("div", {
        id: "ai-chat-provider-modal",
        className: "ai-chat-modal-backdrop",
    });
    const modal = makeElement("section", {
        className: "ai-chat-modal",
        role: "dialog",
        "aria-modal": "true",
        "aria-labelledby": "ai-chat-provider-title",
    });
    const header = makeElement("header");
    header.append(makeElement("h2", { id: "ai-chat-provider-title" }, "AI Chat 服务商配置"));
    const closeButton = makeElement("button", { className: "ai-chat-button", type: "button" }, "关闭");
    header.append(closeButton);

    const main = makeElement("main");
    const profileSelect = makeElement("select");
    const nameInput = makeElement("input", { maxlength: "80", placeholder: "例如：OpenRouter" });
    const baseUrlInput = makeElement("input", { placeholder: "https://example.com/v1", spellcheck: "false" });
    const apiKeyInput = makeElement("input", {
        type: "password",
        placeholder: "已保存的密钥不会回显",
        autocomplete: "new-password",
        "aria-label": "API Key",
    });
    const modelInput = makeElement("input", { placeholder: "可留空，刷新模型后再选择", spellcheck: "false" });
    const allowHttpInput = makeElement("input", { type: "checkbox" });
    const warning = makeElement("div", { className: "ai-chat-warning" }, "HTTP 会以明文传输 API Key，仅在你信任的网络中使用。 ");
    const status = makeElement("div", { className: "ai-chat-status", role: "status" });

    function field(label, control) {
        const wrapper = makeElement("div", { className: "ai-chat-field" });
        wrapper.append(makeElement("label", {}, label), control);
        return wrapper;
    }
    const selectRow = makeElement("div", { className: "ai-chat-inline" });
    const reloadButton = makeElement("button", {
        className: "ai-chat-button", type: "button",
        title: "重新从 ComfyUI 服务端读取配置",
    }, "重新读取");
    selectRow.append(profileSelect, reloadButton);
    main.append(field("已有配置", selectRow));
    const newButton = makeElement("button", { className: "ai-chat-button", type: "button" }, "新建配置");
    main.append(newButton, field("配置名称", nameInput), field("Base URL", baseUrlInput));

    const keyRow = makeElement("div", { className: "ai-chat-inline" });
    keyRow.append(apiKeyInput);
    const revealButton = makeElement("button", { className: "ai-chat-button ai-chat-icon-button", type: "button", title: "显示输入的 Key", "aria-label": "显示输入的 Key" });
    const clearKeyButton = makeElement("button", { className: "ai-chat-button ai-chat-icon-button", type: "button", title: "清除已保存的 Key", "aria-label": "清除已保存的 Key" });
    const eyeIcon = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/></svg>';
    const eyeOffIcon = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 3l18 18M10.6 6.1A12.6 12.6 0 0 1 12 6c6.5 0 10 6 10 6a15 15 0 0 1-3 3.4M6.2 6.9A15 15 0 0 0 2 12s3.5 6 10 6a12 12 0 0 0 4-.7M9.9 9.9a3 3 0 0 0 4.2 4.2"/></svg>';
    revealButton.innerHTML = eyeIcon;
    clearKeyButton.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13M10 11v5M14 11v5"/></svg>';
    keyRow.append(revealButton, clearKeyButton);
    const modelRow = makeElement("div", { className: "ai-chat-inline" });
    const refreshButton = makeElement("button", { className: "ai-chat-button", type: "button" }, "检测");
    modelRow.append(modelInput, refreshButton);
    main.append(field("API Key", keyRow), field("默认模型", modelRow));
    const httpRow = makeElement("div", { className: "ai-chat-inline" });
    httpRow.append(allowHttpInput, makeElement("span", {}, "允许 HTTP"));
    main.append(httpRow, warning, status);

    const footer = makeElement("footer");
    const deleteButton = makeElement("button", { className: "ai-chat-button ai-chat-danger", type: "button" }, "删除配置");
    const saveButton = makeElement("button", { className: "ai-chat-button ai-chat-primary", type: "button" }, "保存");
    footer.append(deleteButton, saveButton);
    modal.append(header, main, footer);
    backdrop.append(modal);
    document.body.append(backdrop);

    const setStatus = (message, error = false) => {
        status.textContent = message;
        status.classList.toggle("error", error);
    };
    const updateWarning = () => {
        warning.style.display = baseUrlInput.value.trim().toLowerCase().startsWith("http://") ? "block" : "none";
    };
    const previousFocus = document.activeElement;
    const close = () => {
        backdrop.remove();
        previousFocus?.focus?.();
    };

    function fill(profile) {
        nameInput.value = profile?.name || "";
        nameInput.readOnly = Boolean(profile);
        baseUrlInput.value = profile?.base_url || "";
        apiKeyInput.value = "";
        apiKeyInput.placeholder = profile?.has_api_key ? "******** 已保存；留空则保持不变" : "请输入 API Key";
        clearKeyButton.disabled = !profile?.has_api_key;
        modelInput.value = profile?.default_model || "";
        allowHttpInput.checked = Boolean(profile?.allow_http);
        deleteButton.disabled = !profile;
        updateWarning();
    }

    function renderSelect(preferredName = "") {
        profileSelect.replaceChildren();
        if (profileCache.length === 0) {
            profileSelect.append(makeElement("option", { value: "" }, "暂无已保存配置"));
        }
        for (const profile of profileCache) {
            const option = makeElement("option", { value: profile.name }, profile.name);
            profileSelect.append(option);
        }
        if (preferredName && profileCache.some((profile) => profile.name === preferredName)) {
            profileSelect.value = preferredName;
        }
        fill(profileCache.find((profile) => profile.name === profileSelect.value));
    }

    async function reloadProfiles(preferredName = "") {
        setStatus("正在读取服务端配置……");
        reloadButton.disabled = true;
        try {
            await loadProfiles();
            renderSelect(preferredName);
            await syncAllNodes();
            setStatus(profileCache.length
                ? `已读取 ${profileCache.length} 个服务商配置；真实 API Key 不会返回浏览器。`
                : "当前没有保存的服务商配置，可以新建。");
            return true;
        } catch (error) {
            setStatus(`${error.message}。配置仍可能保存在服务器上，请勿把空白列表误认为已删除。`, true);
            return false;
        } finally {
            reloadButton.disabled = false;
        }
    }
    profileSelect.addEventListener("change", () => fill(profileCache.find((profile) => profile.name === profileSelect.value)));
    reloadButton.addEventListener("click", () => reloadProfiles(profileSelect.value));
    baseUrlInput.addEventListener("input", updateWarning);
    closeButton.addEventListener("click", close);
    backdrop.addEventListener("click", (event) => { if (event.target === backdrop) close(); });
    backdrop.addEventListener("keydown", (event) => {
        if (event.key === "Escape") close();
    });
    revealButton.addEventListener("click", () => {
        apiKeyInput.type = apiKeyInput.type === "password" ? "text" : "password";
        const label = apiKeyInput.type === "password" ? "显示输入的 Key" : "隐藏输入的 Key";
        revealButton.innerHTML = apiKeyInput.type === "password" ? eyeIcon : eyeOffIcon;
        revealButton.title = label;
        revealButton.setAttribute("aria-label", label);
    });
    clearKeyButton.addEventListener("click", async () => {
        const name = profileSelect.value;
        if (!name || !(await confirmAction("清除 API Key", `确认清除服务商“${name}”保存的 Key？旧版备份中的 Key 不会被删除。`))) return;
        setStatus("正在清除 Key……");
        try {
            const body = await requestJson("/ai_chat/profiles/clear-key", {
                method: "POST",
                body: JSON.stringify({ name }),
            });
            const index = profileCache.findIndex((profile) => profile.name === name);
            if (index >= 0) profileCache[index] = body.profile;
            if (profileSelect.value === name) {
                apiKeyInput.value = "";
                apiKeyInput.placeholder = "请输入 API Key";
                clearKeyButton.disabled = true;
            }
            setStatus(`已清除“${name}”在当前 providers.json 中的 Key。历史备份和旧 config.json 不会自动删除。`);
        } catch (error) {
            setStatus(error.message, true);
        }
    });
    newButton.addEventListener("click", () => {
        profileSelect.value = "";
        fill(null);
        nameInput.focus();
    });

    saveButton.addEventListener("click", async () => {
        setStatus("正在保存……");
        try {
            const body = await requestJson("/ai_chat/profiles", {
                method: "POST",
                body: JSON.stringify({
                    name: nameInput.value,
                    base_url: baseUrlInput.value,
                    api_key: apiKeyInput.value,
                    default_model: modelInput.value,
                    allow_http: allowHttpInput.checked,
                }),
            });
            let detectionMessage = "";
            if (body.profile.has_api_key) {
                try {
                    const detected = await requestJson("/ai_chat/models/refresh", {
                        method: "POST",
                        body: JSON.stringify({ name: body.profile.name }),
                    });
                    detectionMessage = `，自动检测到 ${detected.models.length} 个模型`;
                } catch (error) {
                    detectionMessage = `；模型自动检测失败：${error.message}，仍可手动填写`;
                }
            }
            await loadProfiles();
            renderSelect(body.profile.name);
            await syncAllNodes();
            setStatus(`已保存${detectionMessage}。API Key 只保存在 ComfyUI 服务端。`);
        } catch (error) {
            setStatus(error.message, true);
        }
    });

    deleteButton.addEventListener("click", async () => {
        const name = profileSelect.value;
        if (!name || !(await confirmAction("删除服务商配置", `确认删除“${name}”及当前文件中的 API Key？最后一个配置也可以删除；历史备份与旧 config.json 不会自动删除。`))) return;
        setStatus("正在删除……");
        try {
            await requestJson("/ai_chat/profiles/delete", {
                method: "POST",
                body: JSON.stringify({ name }),
            });
            await loadProfiles();
            renderSelect();
            await syncAllNodes();
            setStatus("已删除当前服务端配置。历史备份和旧 config.json 需要自行检查。");
        } catch (error) {
            setStatus(error.message, true);
        }
    });

    refreshButton.addEventListener("click", async () => {
        const name = profileSelect.value;
        if (!name) return setStatus("请先保存或选择一个配置。", true);
        const profile = profileCache.find((item) => item.name === name);
        if (!profile || apiKeyInput.value || baseUrlInput.value.trim().replace(/\/+$/, "") !== profile.base_url || allowHttpInput.checked !== Boolean(profile.allow_http)) {
            return setStatus("请先保存修改后的 Base URL、API Key 或 HTTP 设置，再检测模型。", true);
        }
        const requestedModel = modelInput.value.trim();
        refreshButton.disabled = true;
        setStatus("正在请求 /models……");
        try {
            const body = await requestJson("/ai_chat/models/refresh", {
                method: "POST",
                body: JSON.stringify({ name }),
            });
            await loadProfiles();
            await syncAllNodes();
            if (!requestedModel) {
                setStatus(`检测到 ${body.models.length} 个模型，已更新节点的模型列表。`);
            } else if (body.models.includes(requestedModel)) {
                setStatus(`检测到 ${body.models.length} 个模型，列表包含“${requestedModel}”。`);
            } else {
                setStatus(`检测到 ${body.models.length} 个模型，列表未包含“${requestedModel}”；仍可尝试手动使用。`);
            }
        } catch (error) {
            setStatus(`${error.message}；仍可手动填写模型。`, true);
        } finally {
            refreshButton.disabled = false;
        }
    });

    renderSelect();
    await reloadProfiles(findWidget(sourceNode, "服务商配置")?.value || "");
    profileSelect.focus();
}

app.registerExtension({
    name: "AIChat.ProviderProfiles",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (!TARGET_NODES.has(nodeData.name)) return;
        const originalCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const result = originalCreated?.apply(this, arguments);
            this.__aiChatNodeType = nodeData.name;
            if (nodeData.name === "MultiModalAssistant") {
                // Keep the widget for old workflow serialization while hiding it from the node.
                const temperatureWidget = findWidget(this, "随机度");
                if (temperatureWidget) {
                    temperatureWidget.type = "hidden";
                    temperatureWidget.computeSize = () => [0, -4];
                }
            }
            const providerWidget = findWidget(this, "服务商配置");
            if (providerWidget) {
                const originalCallback = providerWidget.callback;
                const node = this;
                providerWidget.callback = function (...args) {
                    originalCallback?.apply(this, args);
                    refreshNodeModels(node, false).catch((error) => console.warn("[AI Chat]", error));
                };
            }
            this.addWidget("button", "管理服务商", null, () => openProfileManager(this));
            this.addWidget("button", "刷新模型", null, async () => {
                try {
                    await refreshNodeModels(this, true);
                } catch (error) {
                    showAlert(`模型刷新失败：${error.message}`);
                }
            });
            loadProfiles().then(syncAllNodes).catch((error) => console.warn("[AI Chat]", error));
            return result;
        };
    },
});
