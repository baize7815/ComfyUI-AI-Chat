// Pure workflow migration helpers. No ComfyUI runtime dependencies here.
const MODES = new Set(["多图一起分析", "逐张批量分析"]);
export const IMAGE_INPUTS = ["image_1", "image_2", "image_3", "image_4", "image_group", "video"];

function legacyMode(saved) {
    const values = saved?.widgets_values;
    if (Array.isArray(values)) {
        // Legacy selector followed seven fixed widgets + max_token. Never
        // mistake the user's prompt text for a former mode widget.
        return values.find((value, index) => index >= 7 && MODES.has(value))
            || "多图一起分析";
    }
    if (values && typeof values === "object" && MODES.has(values["图片处理模式"])) {
        return values["图片处理模式"];
    }
    return "多图一起分析";
}

function hasLegacyFields(saved) {
    return saved?.inputs?.some((entry) => ["输入图像", "输入视频"].includes(entry.name))
        || (Array.isArray(saved?.widgets_values)
            && saved.widgets_values.some((value, index) => index >= 7 && MODES.has(value)))
        || (saved?.widgets_values && typeof saved.widgets_values === "object"
            && MODES.has(saved.widgets_values["图片处理模式"]));
}

// Keep original input objects and link IDs: only indexes and visible labels
// change. Any user-converted widget sockets are preserved after image inputs.
export function migrateAssistantNode(saved, links) {
    if (!saved || saved.type !== "MultiModalAssistant" || !hasLegacyFields(saved)) {
        return false;
    }
    const mode = legacyMode(saved);
    const originalInputs = Array.isArray(saved.inputs) ? saved.inputs : [];
    for (const entry of originalInputs) {
        if (entry.name === "输入图像") {
            entry.name = mode === "逐张批量分析" ? "image_group" : "image_1";
        } else if (entry.name === "输入视频") {
            entry.name = "video";
        }
    }
    const ordered = [];
    for (const name of IMAGE_INPUTS) {
        const matches = originalInputs.filter((entry) => entry.name === name);
        if (matches.length) ordered.push(...matches);
        else ordered.push({ name, type: name === "video" ? "VIDEO" : "IMAGE", link: null });
    }
    ordered.push(...originalInputs.filter((entry) => !IMAGE_INPUTS.includes(entry.name)));
    const indexMap = originalInputs.map((entry) => ordered.indexOf(entry));
    if (Array.isArray(links)) {
        for (const link of links) {
            if (Array.isArray(link) && String(link[3]) === String(saved.id)) {
                if (indexMap[link[4]] !== undefined) link[4] = indexMap[link[4]];
            } else if (link && !Array.isArray(link) && String(link.target_id) === String(saved.id)) {
                if (indexMap[link.target_slot] !== undefined) {
                    link.target_slot = indexMap[link.target_slot];
                }
            }
        }
    }
    saved.inputs = ordered;
    if (Array.isArray(saved.widgets_values)) {
        const index = saved.widgets_values.findIndex((value, i) => i >= 7 && MODES.has(value));
        if (index !== -1) saved.widgets_values.splice(index, 1);
    } else if (saved.widgets_values && typeof saved.widgets_values === "object") {
        delete saved.widgets_values["图片处理模式"];
    }
    return true;
}

export function migrateAssistantWorkflow(workflow) {
    let changed = 0;
    for (const node of workflow?.nodes || []) {
        if (migrateAssistantNode(node, workflow.links)) changed += 1;
    }
    return changed;
}
