import { app } from "../../scripts/app.js";

const TARGETS = new Set(["AIChatCropFromJSON", "AIChatCropFromMask"]);
const ALIGNMENTS = new Set(["2", "4", "8", "16", "32", "64"]);
const PREVIEWS = new Set(["裁剪结果", "原图标框", "关闭"]);

function widget(node, name) {
    return node.widgets?.find((entry) => entry.name === name);
}

function safeInteger(value, fallback, min, max) {
    const numeric = Number(value);
    return Number.isSafeInteger(numeric) && numeric >= min && numeric <= max ? numeric : fallback;
}

function repairWidgetValues(node, saved, type) {
    // Older versions stored four separate margins; the first JSON version
    // also stored the JSON text itself before it became an input socket.
    const isJson = type === "AIChatCropFromJSON";
    if (Array.isArray(saved)) {
        const oldJson = isJson && saved.length >= 7;
        const oldMask = !isJson && saved.length >= 6;
        if (oldJson || oldMask) {
            const offset = oldJson && saved.length >= 8 && typeof saved[0] === "string" ? 1 : 0;
            const firstIndex = isJson ? offset : 0;
            if (isJson) {
                const region = widget(node, "区域序号");
                if (region) region.value = safeInteger(saved[firstIndex], 0, -1, 999);
            } else {
                const threshold = widget(node, "遮罩阈值");
                const value = Number(saved[0]);
                if (threshold && Number.isFinite(value) && value >= 0 && value <= 1) {
                    threshold.value = value;
                }
            }
            const alignment = widget(node, "对齐倍数");
            if (alignment) alignment.value = ALIGNMENTS.has(String(saved[firstIndex + 1]))
                ? String(saved[firstIndex + 1]) : "8";
            const expansion = widget(node, "裁剪扩展像素");
            if (expansion) expansion.value = safeInteger(saved[firstIndex + 2], 16, 0, 4096);
            if (isJson) {
                const ratio = widget(node, "允许宽高比不同");
                if (ratio) ratio.value = saved[firstIndex + 6] === true;
            }
        }
    }

    // Invalid widget values from an older serialized workflow must never
    // become NaN, zero alignment, or an invalid preview selection.
    if (isJson) {
        const region = widget(node, "区域序号");
        if (region) region.value = safeInteger(region.value, 0, -1, 999);
    }
    const align = widget(node, "对齐倍数");
    if (align && !ALIGNMENTS.has(String(align.value))) align.value = "8";
    const expand = widget(node, "裁剪扩展像素");
    if (expand) expand.value = safeInteger(expand.value, 16, 0, 4096);
    const preview = widget(node, "图像预览");
    if (preview && !PREVIEWS.has(preview.value)) preview.value = "裁剪结果";
    node.setDirtyCanvas?.(true, true);
}

app.registerExtension({
    name: "AIChat.CropWidgetCompatibility",
    beforeRegisterNodeDef(nodeType, nodeData) {
        if (!TARGETS.has(nodeData.name)) return;
        const oldOnConfigure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function (info) {
            const result = oldOnConfigure?.apply(this, arguments);
            repairWidgetValues(this, info?.widgets_values, nodeData.name);
            return result;
        };
    },
});
