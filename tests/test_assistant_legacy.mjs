// Run with: node tests/test_assistant_legacy.mjs
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

// Import the pure helper as ESM even if the host has no package.json.
const source = readFileSync(new URL("../web/assistant_legacy_helpers.js", import.meta.url));
const { migrateAssistantWorkflow, migrateAssistantNode, IMAGE_INPUTS } =
    await import(`data:text/javascript;base64,${source.toString("base64")}`);

function oldWorkflow(mode) {
    return {
        nodes: [{
            id: 8,
            type: "MultiModalAssistant",
            inputs: [
                { name: "输入图像", type: "IMAGE", link: 100 },
                { name: "输入视频", type: "VIDEO", link: 101 },
                { name: "最大token", type: "INT", link: 102 },
            ],
            // Seven required widgets, max token, legacy selector, two buttons.
            widgets_values: ["OpenRouter", "test", "", "默认", "system", "prompt", 1,
                             8192, mode, null, null],
        }],
        links: [
            [100, 11, 0, 8, 0, "IMAGE"],
            [101, 12, 0, 8, 1, "VIDEO"],
            [102, 13, 0, 8, 2, "INT"],
        ],
    };
}

for (const [mode, target] of [
    ["多图一起分析", "image_1"],
    ["逐张批量分析", "image_group"],
]) {
    const wf = oldWorkflow(mode);
    assert.equal(migrateAssistantWorkflow(wf), 1);
    const node = wf.nodes[0];
    assert.deepEqual(node.inputs.slice(0, 6).map((x) => x.name), IMAGE_INPUTS);
    assert.equal(node.inputs.find((entry) => entry.name === target)?.link, 100);
    assert.equal(node.inputs[5].link, 101);
    assert.equal(node.inputs[6].name, "最大token");
    assert.equal(node.inputs[6].link, 102);
    assert.equal(wf.links[0][4], IMAGE_INPUTS.indexOf(target));
    assert.equal(wf.links[1][4], 5);
    assert.equal(wf.links[2][4], 6);
    assert.equal(node.widgets_values[7], 8192);
    assert.equal(node.widgets_values[8], null);
    assert.ok(!node.widgets_values.includes(mode));
    assert.equal(migrateAssistantWorkflow(wf), 0);
}

const brandNew = { nodes: [{
    type: "MultiModalAssistant", id: 5,
    inputs: [{ name: "image_3", type: "IMAGE", link: 300 }],
    widgets_values: ["OpenRouter", "test", "", "默认", "system", "prompt", 1, 8192],
}], links: [[300, 2, 0, 5, 0, "IMAGE"]] };
assert.equal(migrateAssistantWorkflow(brandNew), 0);
assert.equal(brandNew.links[0][4], 0);
assert.equal(brandNew.nodes[0].inputs.length, 1);

const promptWithModeWords = { nodes: [{
    type: "MultiModalAssistant", id: 6,
    inputs: [{ name: "image_2", type: "IMAGE", link: null }],
    widgets_values: ["OpenRouter", "test", "", "默认", "system",
                     "逐张批量分析", 1, 8192],
}], links: [] };
assert.equal(migrateAssistantWorkflow(promptWithModeWords), 0);
assert.equal(promptWithModeWords.nodes[0].widgets_values[5], "逐张批量分析");

const legacyPromptWithModeWords = oldWorkflow("多图一起分析");
legacyPromptWithModeWords.nodes[0].widgets_values[5] = "逐张批量分析";
assert.equal(migrateAssistantWorkflow(legacyPromptWithModeWords), 1);
assert.equal(legacyPromptWithModeWords.nodes[0].widgets_values[5], "逐张批量分析");
assert.equal(legacyPromptWithModeWords.nodes[0].inputs[0].name, "image_1");

const noVideo = oldWorkflow("多图一起分析");
noVideo.nodes[0].inputs = [{ name: "输入图像", type: "IMAGE", link: 100 }];
noVideo.links = [{ id: 100, origin_id: 11, origin_slot: 0,
                   target_id: 8, target_slot: 0, type: "IMAGE" }];
assert.equal(migrateAssistantNode(noVideo.nodes[0], noVideo.links), true);
assert.equal(noVideo.links[0].target_slot, 0);
assert.equal(noVideo.nodes[0].inputs[0].name, "image_1");

console.log("Assistant legacy workflow migration: passed.");
