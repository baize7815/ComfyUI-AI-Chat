import { app } from "../../scripts/app.js";
import { IMAGE_INPUTS, migrateAssistantNode, migrateAssistantWorkflow } from "./assistant_legacy_helpers.js";

function repairDeferredLinks(node) {
    const targets = node.__aiChatLegacyInputLinks;
    if (!targets || !node.graph?.links) return;
    let pending = false;
    for (const [id, index] of targets) {
        const link = node.graph.links[id];
        if (!link) {
            pending = true;
            continue;
        }
        if (String(link.target_id) !== String(node.id)) continue;
        link.target_slot = index;
    }
    if (!pending) delete node.__aiChatLegacyInputLinks;
    node.setDirtyCanvas?.(true, true);
}

// Called before LiteGraph creates its links, so old slot indexes can be
// translated without losing image/video wires in saved workflow JSON.
app.registerExtension({
    name: "AIChat.AssistantInputMigration",
    beforeConfigureGraph(workflow) {
        const migrated = migrateAssistantWorkflow(workflow);
        if (migrated) console.info(`[AI Chat] 已迁移 ${migrated} 个旧版多模态助手节点的图片输入。`);
    },
    beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "MultiModalAssistant") return;
        const oldConfigure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function (saved) {
            // Fallback for workflows imported through a route that does not
            // call beforeConfigureGraph (e.g. some third-party paste tools).
            const legacy = saved?.inputs?.some((entry) =>
                entry.name === "输入图像" || entry.name === "输入视频");
            if (legacy) {
                migrateAssistantNode(saved, null);
                this.__aiChatLegacyInputLinks = new Map();
                saved.inputs.forEach((entry, slot) => {
                    if (entry.link != null) this.__aiChatLegacyInputLinks.set(String(entry.link), slot);
                });
            }
            const result = oldConfigure?.apply(this, arguments);
            if (!Array.isArray(this.inputs)) return result;
            // If an old workflow contained fewer sockets, restore all new
            // optional IMAGE ports without deleting the original wires.
            for (const name of IMAGE_INPUTS) {
                if (!this.inputs.some((entry) => entry.name === name)) {
                    this.addInput(name, name === "video" ? "VIDEO" : "IMAGE");
                }
            }
            repairDeferredLinks(this);
            this.setDirtyCanvas?.(true, true);
            return result;
        };
    },
    loadedGraphNode(node) {
        if (node.comfyClass === "MultiModalAssistant") repairDeferredLinks(node);
    },
});
