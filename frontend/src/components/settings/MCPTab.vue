<script setup lang="ts">
import { ref, onMounted } from 'vue'
import {
  NButton, NSpace, NPopconfirm, NTag, NTooltip, NSwitch, NEmpty,
  NModal, NForm, NFormItem, NInput, NSelect, NAlert, useMessage,
} from 'naive-ui'
import { api, type MCPServer } from '../../api/http'

const message = useMessage()
const mcpServers = ref<MCPServer[]>([])
const showMcpModal = ref(false)
const isNewMcp = ref(false)
const savingMcp = ref(false)
const togglingMcp = ref<number | null>(null)
const reconnectingMcp = ref<number | null>(null)
const mcpForm = ref({ name: '', display_name: '', transport: 'stdio' as 'stdio' | 'sse' | 'streamable-http', command: '', args: '', url: '', env: '', headers: '', enabled: true })
const mcpJsonImport = ref('')
const mcpJsonError = ref('')
const mcpTransportOptions = [
  { label: 'stdio（本地进程）', value: 'stdio' },
  { label: 'SSE（远程 Server-Sent Events）', value: 'sse' },
  { label: 'Streamable HTTP（推荐）', value: 'streamable-http' },
]

async function loadMcpServers() { try { mcpServers.value = (await api.mcpServers.list()).servers } catch (e) { console.error(e) } }

function openAddMcp() {
  isNewMcp.value = true
  mcpForm.value = { name: '', display_name: '', transport: 'stdio', command: '', args: '', url: '', env: '', headers: '', enabled: true }
  mcpJsonImport.value = ''; mcpJsonError.value = ''
  showMcpModal.value = true
}
function openEditMcp(srv: MCPServer) {
  isNewMcp.value = false
  mcpForm.value = {
    name: srv.name, display_name: srv.display_name, transport: srv.transport,
    command: srv.command || '', args: (srv.args || []).join('\n'), url: srv.url || '',
    env: srv.env && Object.keys(srv.env).length ? JSON.stringify(srv.env, null, 2) : '',
    headers: srv.headers && Object.keys(srv.headers).length ? JSON.stringify(srv.headers, null, 2) : '',
    enabled: !!srv.enabled,
  }
  mcpJsonImport.value = ''; mcpJsonError.value = ''
  showMcpModal.value = true
}

function importMcpJson() {
  mcpJsonError.value = ''; const raw = mcpJsonImport.value.trim(); if (!raw) return
  try {
    const parsed = JSON.parse(raw)
    let servers: Record<string, any> = {}
    if (parsed.mcpServers) servers = parsed.mcpServers
    else if (parsed.command || parsed.url) servers = { '': parsed }
    else servers = parsed
    const entries = Object.entries(servers)
    if (entries.length === 0) throw new Error('未找到有效的服务器配置')
    const [serverName, cfg] = entries[0] as [string, any]
    if (cfg.command) {
      mcpForm.value.transport = 'stdio'; mcpForm.value.command = cfg.command
      mcpForm.value.args = (cfg.args || []).join('\n')
      if (cfg.env) mcpForm.value.env = JSON.stringify(cfg.env, null, 2)
    } else if (cfg.url) {
      mcpForm.value.transport = cfg.transport || 'streamable-http'; mcpForm.value.url = cfg.url
      if (cfg.headers) mcpForm.value.headers = JSON.stringify(cfg.headers, null, 2)
      if (cfg.env) mcpForm.value.env = JSON.stringify(cfg.env, null, 2)
    } else throw new Error('配置中既没有 command 也没有 url')
    if (serverName && !mcpForm.value.name) { mcpForm.value.name = serverName; mcpForm.value.display_name = mcpForm.value.display_name || serverName }
    mcpJsonImport.value = ''; message.success('配置已导入，请补充名称后保存')
  } catch (e) { mcpJsonError.value = `解析失败: ${String(e)}` }
}

function parseMcpForm() {
  const args = mcpForm.value.args.trim() ? mcpForm.value.args.trim().split(/[\n\s]+/).filter(Boolean) : []
  let env: Record<string, string> = {}; if (mcpForm.value.env.trim()) { try { env = JSON.parse(mcpForm.value.env) } catch {} }
  let headers: Record<string, string> = {}; if (mcpForm.value.headers.trim()) { try { headers = JSON.parse(mcpForm.value.headers) } catch {} }
  return { args, env, headers }
}

async function saveMcp() {
  if (!mcpForm.value.name.trim() || !mcpForm.value.display_name.trim()) { message.warning('请填写服务器名称和显示名称'); return }
  if (mcpForm.value.transport === 'stdio' && !mcpForm.value.command.trim()) { message.warning('stdio 模式需要填写 command'); return }
  if ((mcpForm.value.transport === 'sse' || mcpForm.value.transport === 'streamable-http') && !mcpForm.value.url.trim()) { message.warning('远程模式需要填写服务地址'); return }
  savingMcp.value = true
  const { args, env, headers } = parseMcpForm()
  try {
    if (isNewMcp.value) {
      await api.mcpServers.create({ name: mcpForm.value.name.trim(), display_name: mcpForm.value.display_name.trim(), transport: mcpForm.value.transport, command: mcpForm.value.command.trim(), args, url: mcpForm.value.url || null, env, headers, enabled: mcpForm.value.enabled })
      message.success(`MCP 服务器「${mcpForm.value.display_name}」已添加`)
    } else {
      const srv = mcpServers.value.find(s => s.name === mcpForm.value.name)
      if (srv) {
        await api.mcpServers.update(srv.id, { display_name: mcpForm.value.display_name.trim(), transport: mcpForm.value.transport, command: mcpForm.value.command.trim(), args, url: mcpForm.value.url || null, env, headers, enabled: mcpForm.value.enabled })
        message.success(`已更新并重连「${mcpForm.value.display_name}」`)
      }
    }
    showMcpModal.value = false; await loadMcpServers()
  } catch (e) { message.error(String(e)) } finally { savingMcp.value = false }
}

async function deleteMcp(srv: MCPServer) { try { await api.mcpServers.delete(srv.id); await loadMcpServers(); message.success('已删除') } catch (e) { message.error(String(e)) } }
async function toggleMcp(srv: MCPServer) { togglingMcp.value = srv.id; try { await api.mcpServers.toggle(srv.id); await loadMcpServers() } catch (e) { message.error(String(e)) } finally { togglingMcp.value = null } }
async function reconnectMcp(srv: MCPServer) {
  reconnectingMcp.value = srv.id
  try { const res = await api.mcpServers.reconnect(srv.id); res.reconnect_ok ? message.success(`「${srv.display_name}」重连成功`) : message.error(`重连失败: ${res.error_msg || '未知错误'}`); await loadMcpServers() }
  catch (e) { message.error(String(e)) } finally { reconnectingMcp.value = null }
}
function mcpStatusType(status: string): 'success' | 'error' | 'default' { return status === 'connected' ? 'success' : status === 'error' ? 'error' : 'default' }

onMounted(loadMcpServers)
</script>

<template>
  <div class="section">
    <div class="section-header">
      <div>
        <h4 style="margin:0">MCP 服务器管理</h4>
        <p class="hint" style="margin:4px 0 0">添加 MCP 服务器后工具自动注册，支持热插拔。</p>
      </div>
      <NButton size="small" type="primary" @click="openAddMcp">+ 添加服务器</NButton>
    </div>
  </div>

  <NEmpty v-if="mcpServers.length === 0" description="暂无 MCP 服务器" style="margin: 24px 0" />
  <div v-else class="mcp-list">
    <div v-for="srv in mcpServers" :key="srv.id" class="mcp-row">
      <div class="mcp-info">
        <div class="mcp-title-row">
          <span class="mcp-name">{{ srv.display_name }}</span>
          <NTag size="tiny" :type="mcpStatusType(srv.status)">{{ srv.status === 'connected' ? `已连接 · ${srv.tools_count} 个工具` : srv.status === 'error' ? '连接错误' : '未连接' }}</NTag>
          <NTag size="tiny" type="info">{{ srv.transport }}</NTag>
        </div>
        <code class="mcp-cmd">{{ srv.transport === 'stdio' ? [srv.command, ...(srv.args || [])].filter(Boolean).join(' ') : srv.url }}</code>
        <span v-if="srv.error_msg" class="mcp-error">{{ srv.error_msg }}</span>
      </div>
      <div class="mcp-actions">
        <NTooltip><template #trigger><NSwitch :value="!!srv.enabled" :loading="togglingMcp === srv.id" size="small" @update:value="toggleMcp(srv)" /></template>{{ srv.enabled ? '点击禁用' : '点击启用' }}</NTooltip>
        <NButton size="tiny" :loading="reconnectingMcp === srv.id" @click="reconnectMcp(srv)">重连</NButton>
        <NButton size="tiny" @click="openEditMcp(srv)">编辑</NButton>
        <NPopconfirm @positive-click="deleteMcp(srv)"><template #trigger><NButton size="tiny" type="error" ghost>删除</NButton></template>删除「{{ srv.display_name }}」并断开连接？</NPopconfirm>
      </div>
    </div>
  </div>

  <!-- MCP Modal -->
  <NModal v-model:show="showMcpModal" preset="card" :title="isNewMcp ? '添加 MCP 服务器' : '编辑 MCP 服务器'" :style="{ width: '540px' }">
    <NAlert type="info" :show-icon="false" style="margin-bottom:14px;font-size:12px">粘贴 MCP 官方配置 JSON 可自动填充。</NAlert>
    <div style="margin-bottom:14px">
      <div style="display:flex;gap:8px;align-items:flex-start">
        <NInput v-model:value="mcpJsonImport" type="textarea" :autosize="{ minRows: 3, maxRows: 6 }" placeholder='粘贴 MCP JSON 配置' style="flex:1" />
        <NButton size="small" type="primary" ghost @click="importMcpJson" style="flex-shrink:0;margin-top:2px">导入</NButton>
      </div>
      <span v-if="mcpJsonError" style="font-size:11px;color:#d03050">{{ mcpJsonError }}</span>
    </div>
    <NForm label-placement="left" label-width="90">
      <NFormItem label="名称"><NInput v-model:value="mcpForm.name" :disabled="!isNewMcp" placeholder="唯一标识" /></NFormItem>
      <NFormItem label="显示名称"><NInput v-model:value="mcpForm.display_name" /></NFormItem>
      <NFormItem label="传输类型"><NSelect v-model:value="mcpForm.transport" :options="mcpTransportOptions" /></NFormItem>
      <template v-if="mcpForm.transport === 'stdio'">
        <NFormItem label="command"><NInput v-model:value="mcpForm.command" placeholder="如：npx" /></NFormItem>
        <NFormItem label="args"><NInput v-model:value="mcpForm.args" type="textarea" :autosize="{ minRows: 2, maxRows: 5 }" placeholder="每行一个参数" /></NFormItem>
      </template>
      <NFormItem v-if="mcpForm.transport === 'sse' || mcpForm.transport === 'streamable-http'" label="服务地址"><NInput v-model:value="mcpForm.url" /></NFormItem>
      <NFormItem v-if="mcpForm.transport === 'sse' || mcpForm.transport === 'streamable-http'" label="Headers"><NInput v-model:value="mcpForm.headers" type="textarea" :autosize="{ minRows: 2, maxRows: 4 }" placeholder='JSON 格式' /></NFormItem>
      <NFormItem label="env"><NInput v-model:value="mcpForm.env" type="textarea" :autosize="{ minRows: 2, maxRows: 4 }" placeholder='JSON 格式' /></NFormItem>
      <NFormItem label="连接"><NSwitch v-model:value="mcpForm.enabled" /><span style="margin-left:8px;font-size:12px;color:#999">保存后立即连接</span></NFormItem>
    </NForm>
    <template #footer>
      <NSpace justify="end">
        <NButton @click="showMcpModal = false">取消</NButton>
        <NButton type="primary" :loading="savingMcp" @click="saveMcp">{{ isNewMcp ? '添加并连接' : '保存并重连' }}</NButton>
      </NSpace>
    </template>
  </NModal>
</template>

<style scoped>
@import './settings-common.css';
</style>