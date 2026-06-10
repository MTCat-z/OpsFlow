<template>
  <div>
    <el-card shadow="never">
      <el-tabs v-model="activeTab">
        <!-- Ping -->
        <el-tab-pane label="Ping 测试" name="ping">
          <el-form :model="pingForm" inline label-width="90px" style="margin-bottom:16px">
            <el-form-item label="目标主机"><el-input v-model="pingForm.host" placeholder="192.168.1.1" style="width:220px" /></el-form-item>
            <el-form-item label="发送次数"><el-input-number v-model="pingForm.count" :min="1" :max="100" style="width:120px" /></el-form-item>
            <el-form-item label="超时(秒)"><el-input-number v-model="pingForm.timeout" :min="1" :max="30" style="width:100px" /></el-form-item>
            <el-form-item><el-button type="primary" :loading="pingLoading" @click="doPing">执行</el-button></el-form-item>
          </el-form>
          <div v-if="pingResult">
            <el-row v-if="pingResult.stats" :gutter="16" style="margin-bottom:16px">
              <el-col :span="6"><el-statistic title="发送" :value="pingResult.stats.sent ?? '-'" /></el-col>
              <el-col :span="6"><el-statistic title="接收" :value="pingResult.stats.received ?? '-'" /></el-col>
              <el-col :span="6"><el-statistic title="丢包率" :value="pingResult.stats.loss_percent ?? '-'" suffix="%" /></el-col>
              <el-col :span="6"><el-statistic title="平均延迟" :value="pingResult.stats.avg_rtt ?? '-'" suffix="ms" /></el-col>
            </el-row>
            <pre class="output-block">{{ pingResult.output }}</pre>
          </div>
        </el-tab-pane>

        <!-- Traceroute -->
        <el-tab-pane label="路由追踪" name="traceroute">
          <el-form :model="traceForm" inline label-width="90px" style="margin-bottom:16px">
            <el-form-item label="目标主机"><el-input v-model="traceForm.host" placeholder="192.168.1.1" style="width:220px" /></el-form-item>
            <el-form-item label="最大跳数"><el-input-number v-model="traceForm.max_hops" :min="1" :max="64" style="width:120px" /></el-form-item>
            <el-form-item><el-button type="primary" :loading="traceLoading" @click="doTrace">执行</el-button></el-form-item>
          </el-form>
          <div v-if="traceResult">
            <el-table v-if="traceResult.hops.length" :data="traceResult.hops" border stripe max-height="400" style="margin-bottom:16px">
              <el-table-column prop="hop" label="跳" width="60" align="center" />
              <el-table-column prop="hostname" label="主机名" min-width="160" />
              <el-table-column prop="ip" label="IP" width="140" />
              <el-table-column label="RTT1" width="90" align="center"><template #default="{ row }">{{ row.rtt1 != null ? row.rtt1 + 'ms' : '*' }}</template></el-table-column>
              <el-table-column label="RTT2" width="90" align="center"><template #default="{ row }">{{ row.rtt2 != null ? row.rtt2 + 'ms' : '*' }}</template></el-table-column>
              <el-table-column label="RTT3" width="90" align="center"><template #default="{ row }">{{ row.rtt3 != null ? row.rtt3 + 'ms' : '*' }}</template></el-table-column>
            </el-table>
            <pre class="output-block">{{ traceResult.output }}</pre>
          </div>
        </el-tab-pane>

        <!-- DNS -->
        <el-tab-pane label="DNS 查询" name="dns">
          <el-form :model="dnsForm" inline label-width="90px" style="margin-bottom:16px">
            <el-form-item label="域名"><el-input v-model="dnsForm.domain" placeholder="example.com" style="width:220px" /></el-form-item>
            <el-form-item label="记录类型">
              <el-select v-model="dnsForm.record_type" style="width:110px">
                <el-option v-for="t in ['A','AAAA','MX','NS','CNAME','TXT','SOA','PTR','SRV','CAA']" :key="t" :label="t" :value="t" />
              </el-select>
            </el-form-item>
            <el-form-item label="DNS 服务器"><el-input v-model="dnsForm.dns_server" placeholder="可选" style="width:160px" /></el-form-item>
            <el-form-item><el-button type="primary" :loading="dnsLoading" @click="doDns">查询</el-button></el-form-item>
          </el-form>
          <div v-if="dnsResult">
            <el-table v-if="dnsResult.records.length" :data="dnsResult.records" border stripe max-height="300" style="margin-bottom:16px">
              <el-table-column prop="type" label="类型" width="80" />
              <el-table-column prop="value" label="值" min-width="300" />
              <el-table-column prop="ttl" label="TTL" width="80" align="center" />
            </el-table>
            <pre v-if="dnsResult.output" class="output-block">{{ dnsResult.output }}</pre>
          </div>
        </el-tab-pane>

        <!-- Port Check -->
        <el-tab-pane label="端口检测" name="port">
          <el-form :model="portForm" inline label-width="90px" style="margin-bottom:16px">
            <el-form-item label="目标主机"><el-input v-model="portForm.host" placeholder="192.168.1.1" style="width:200px" /></el-form-item>
            <el-form-item label="端口号"><el-input-number v-model="portForm.port" :min="1" :max="65535" style="width:130px" /></el-form-item>
            <el-form-item label="协议">
              <el-select v-model="portForm.protocol" style="width:90px">
                <el-option label="TCP" value="tcp" /><el-option label="UDP" value="udp" />
              </el-select>
            </el-form-item>
            <el-form-item><el-button type="primary" :loading="portLoading" @click="doPort">检测</el-button></el-form-item>
          </el-form>
          <div v-if="portResult">
            <el-descriptions :column="3" border style="margin-bottom:16px">
              <el-descriptions-item label="状态">
                <el-tag :type="portResult.open === true ? 'success' : portResult.open === false ? 'danger' : 'warning'">
                  {{ portResult.open === true ? '开放' : portResult.open === false ? '关闭' : '未知' }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="延迟">{{ portResult.latency_ms != null ? portResult.latency_ms + 'ms' : '-' }}</el-descriptions-item>
              <el-descriptions-item v-if="portResult.banner" label="Banner">{{ portResult.banner }}</el-descriptions-item>
            </el-descriptions>
            <pre class="output-block">{{ portResult.output }}</pre>
          </div>
        </el-tab-pane>

        <!-- MTR -->
        <el-tab-pane label="MTR 综合追踪" name="mtr">
          <el-form :model="mtrForm" inline label-width="90px" style="margin-bottom:16px">
            <el-form-item label="目标主机"><el-input v-model="mtrForm.host" placeholder="192.168.1.1" style="width:220px" /></el-form-item>
            <el-form-item label="测试轮数"><el-input-number v-model="mtrForm.count" :min="1" :max="100" style="width:120px" /></el-form-item>
            <el-form-item><el-button type="primary" :loading="mtrLoading" @click="doMtr">执行</el-button></el-form-item>
          </el-form>
          <div v-if="mtrResult">
            <el-table v-if="mtrResult.hops.length" :data="mtrResult.hops" border stripe max-height="400" style="margin-bottom:16px">
              <el-table-column prop="hop" label="#" width="50" align="center" />
              <el-table-column prop="host" label="主机" min-width="140" />
              <el-table-column label="丢包%" width="80" align="center">
                <template #default="{ row }"><span :style="{ color: row.loss_percent > 0 ? '#e6a23c' : '#67c23a' }">{{ row.loss_percent }}%</span></template>
              </el-table-column>
              <el-table-column prop="sent" label="发送" width="60" align="center" />
              <el-table-column prop="avg" label="Avg(ms)" width="90" align="center" />
              <el-table-column prop="best" label="Best(ms)" width="90" align="center" />
              <el-table-column prop="worst" label="Worst(ms)" width="90" align="center" />
              <el-table-column prop="stdev" label="StDev" width="80" align="center" />
            </el-table>
            <pre class="output-block">{{ mtrResult.output }}</pre>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>
<script setup>
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { diagApi } from '@/api'

const activeTab = ref('ping')

// --- Ping ---
const pingLoading = ref(false), pingResult = ref(null)
const pingForm = reactive({ host: '', count: 4, timeout: 5 })
async function doPing() {
  if (!pingForm.host) return ElMessage.warning('请输入目标主机')
  pingLoading.value = true; pingResult.value = null
  try { pingResult.value = await diagApi.ping(pingForm) } finally { pingLoading.value = false }
}

// --- Traceroute ---
const traceLoading = ref(false), traceResult = ref(null)
const traceForm = reactive({ host: '', max_hops: 30 })
async function doTrace() {
  if (!traceForm.host) return ElMessage.warning('请输入目标主机')
  traceLoading.value = true; traceResult.value = null
  try { traceResult.value = await diagApi.traceroute(traceForm) } finally { traceLoading.value = false }
}

// --- DNS ---
const dnsLoading = ref(false), dnsResult = ref(null)
const dnsForm = reactive({ domain: '', record_type: 'A', dns_server: '' })
async function doDns() {
  if (!dnsForm.domain) return ElMessage.warning('请输入域名')
  dnsLoading.value = true; dnsResult.value = null
  try { dnsResult.value = await diagApi.dns(dnsForm) } finally { dnsLoading.value = false }
}

// --- Port ---
const portLoading = ref(false), portResult = ref(null)
const portForm = reactive({ host: '', port: 80, protocol: 'tcp' })
async function doPort() {
  if (!portForm.host) return ElMessage.warning('请输入目标主机')
  portLoading.value = true; portResult.value = null
  try { portResult.value = await diagApi.port(portForm) } finally { portLoading.value = false }
}

// --- MTR ---
const mtrLoading = ref(false), mtrResult = ref(null)
const mtrForm = reactive({ host: '', count: 10 })
async function doMtr() {
  if (!mtrForm.host) return ElMessage.warning('请输入目标主机')
  mtrLoading.value = true; mtrResult.value = null
  try { mtrResult.value = await diagApi.mtr(mtrForm) } finally { mtrLoading.value = false }
}
</script>
<style scoped>
.output-block {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 16px;
  border-radius: 6px;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 13px;
  line-height: 1.5;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 400px;
  overflow-y: auto;
}
</style>
