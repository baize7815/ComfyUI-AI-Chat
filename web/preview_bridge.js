import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

// Registration tokens belong to the current ComfyUI server process.
let serverGeneration = 0;
api.addEventListener("reconnected", () => { serverGeneration += 1; });

function parseImageReference(text) {
    if (typeof text !== "string" || !text) return null;
    const suffix = /\s*\[(input|output|temp)\]\s*$/i.exec(text);
    const path = (suffix ? text.slice(0, suffix.index) : text).replaceAll("\\", "/");
    const slash = path.lastIndexOf("/");
    return {
        filename: path.slice(slash + 1),
        subfolder: slash < 0 ? "" : path.slice(0, slash),
        type: suffix ? suffix[1].toLowerCase() : "input",
    };
}

function widgetPath(item) {
    const sub = item.subfolder ? item.subfolder + "/" : "";
    return `${sub}${item.filename} [${item.type || "temp"}]`;
}

function bindBridge(node) {
    const widget = node.widgets?.find((w) => w.name === "image");
    if (!widget || node.__aiChatPreviewBound) return;
    node.__aiChatPreviewBound = true;
    node.imgs = [new Image()];
    node.imageIndex = 0;
    let registration;

    const onAdded = node.onAdded;
    node.onAdded = function (...args) {
        const result = onAdded?.apply(this, args);
        if (!widget.value) widget.value = `$aichat-${node.id}-0`;
        return result;
    };

    // This returns a transient token for the API prompt without changing
    // the file path saved in the editor's native workflow widget.
    widget.serializeValue = async function () {
        const value = widget.value || `$aichat-${node.id}-0`;
        if (!registration || registration.value !== value
            || registration.generation !== serverGeneration) {
            const task = { value, generation: serverGeneration, id: null };
            registration = task;
            task.promise = (async () => {
                if (value.startsWith("$aichat-")) return value;
                const item = parseImageReference(value);
                if (!item?.filename) throw new Error("AI Chat 桥接预览：无可用图片。");
                const response = await api.fetchApi("/ai_chat/preview_bridge/register", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ node_id: String(node.id), image: item }),
                    cache: "no-store",
                });
                if (!response.ok) {
                    throw new Error(`AI Chat 桥接预览：图片登记失败（${response.status}）`);
                }
                const data = await response.json();
                if (!data?.id) throw new Error("AI Chat 桥接预览：登记返回无效 ID。");
                return data.id;
            })().then(id => {
                task.id = id;
                return id;
            }).catch(err => {
                if (registration === task) registration = undefined;
                throw err;
            });
        }
        return registration.promise;
    };

    const onExecuted = node.onExecuted;
    node.onExecuted = function (message, ...args) {
        const result = onExecuted?.call(this, message, ...args);
        const item = message?.images?.[0];
        if (item && registration?.id
            && message?.source_image?.[0] === registration.id
            && registration.generation === serverGeneration
            && widget.value === registration.value) {
            widget.value = widgetPath(item);
            registration.value = widget.value;
            registration.id = null;
            node.properties.image = widget.value;
        }
        return result;
    };
}

async function restoreBridge(node) {
    const widget = node.widgets?.find((w) => w.name === "image");
    if (!widget?.value) return;
    const value = widget.value;
    let item = parseImageReference(value);
    if (value.startsWith("$aichat-")) {
        const response = await api.fetchApi(
            `/ai_chat/preview_bridge/lookup?${new URLSearchParams({ id: value })}`,
            { cache: "no-store" });
        if (!response.ok) return;
        item = await response.json();
    }
    if (!item?.filename || widget.value !== value || !node.graph) return;
    const image = new Image();
    image.src = api.apiURL(`/view?${new URLSearchParams(item)}`);
    node.images = [item];
    node.imgs = [image];
    node.graph.setDirtyCanvas(true);
}

app.registerExtension({
    name: "AIChat.PreviewBridge",
    beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "AIChatPreviewBridge") return;
        const original = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function (...args) {
            const result = original?.apply(this, args);
            bindBridge(this);
            return result;
        };
    },
    loadedGraphNode(node) {
        if (node.comfyClass === "AIChatPreviewBridge") {
            restoreBridge(node).catch((error) => console.warn("AI Chat bridge restore:", error));
        }
    },
});
