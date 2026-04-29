<script setup lang="ts">
import { NDrawer, NDrawerContent, NTabs, NTabPane } from 'naive-ui'
import { useSettingsStore } from '../stores/settings'
import ModelTab from './settings/ModelTab.vue'
import ParamsTab from './settings/ParamsTab.vue'
import ProviderTab from './settings/ProviderTab.vue'
import ToolsTab from './settings/ToolsTab.vue'
import MCPTab from './settings/MCPTab.vue'
import SkillsTab from './settings/SkillsTab.vue'
import TemplatesTab from './settings/TemplatesTab.vue'

const settings = useSettingsStore()
</script>

<template>
  <NDrawer
    :show="settings.showSettings"
    @update:show="settings.showSettings = $event"
    :width="580"
    placement="right"
  >
    <NDrawerContent :native-scrollbar="false" title="系统设置">
      <NTabs type="line" animated>
        <NTabPane name="model" tab="🤖 模型">
          <ModelTab />
        </NTabPane>
        <NTabPane name="params" tab="⚙️ 参数">
          <ParamsTab />
        </NTabPane>
        <NTabPane name="providers" tab="🔑 服务商">
          <ProviderTab />
        </NTabPane>
        <NTabPane name="tools" tab="🔧 工具">
          <ToolsTab />
        </NTabPane>
        <NTabPane name="mcp" tab="🔌 MCP">
          <MCPTab />
        </NTabPane>
        <NTabPane name="skills" tab="⚡ 技能">
          <SkillsTab />
        </NTabPane>
        <NTabPane name="templates" tab="📋 模板">
          <TemplatesTab />
        </NTabPane>
      </NTabs>
    </NDrawerContent>
  </NDrawer>
</template>