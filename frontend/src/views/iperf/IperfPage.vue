<template>
  <div>
    <el-card shadow="never" style="margin-bottom:16px"><template #header>新建 Iperf3 测速任务</template>
      <el-form ref="formRef" :model="form" :rules="rules" inline label-width="90px">
        <el-form-item v-if="isAdmin" label="目标组织" prop="org_id"><el-select v-model="form.org_id" placeholder="选择分公司" style="width:180px"><el-option v-for="o in orgs" :key="o.id" :label="o.name" :value="o.id" /></el-select></el-form-item>
        <el-form-item label="测速目标"><el-select v-model="form.target_type" style="width:120px" @change="onTargetTypeChange"><el-option label="中心服务器" value="central" /><el-option label="分公司探针" value="probe" /><el-option label="手动输入" value="manual" /></el-select></el-form-item>
        <el-form-item v-if="form.target_type==='probe'" label="选择探针"><el-select v-model="form.selected_probe" placeholder="选择在线探针" style="width:180px" @change="onProbeSelect"><el-option v-for="t in onlineProbeTargets" :key="t.org_id" :label="t.name+' ('+t.host+')'" :value="t.host" :disabled="!t.online" /></el-select></el-form-item>
        <el-form-item v-if="form.target_type!=='probe'" label="服务端IP" prop="server_host"><el-input v-model="form.server_host" :placeholder="form.target_type==='central'?'自动填充':'192.168.1.100'" :disabled="form.target_type==='central'" style="width:180px" /></el-form-item>
        <el-form-item label="端口"><el-input-number v-model="form.server_port" :min="1" :max="65535" style="width:120px" /></el-form-item>
        <el-form-item label="协议"><el-select v-model="form.protocol" style="width:90px"><el-option label="TCP" value="tcp" /><el-option label="UDP" value="udp" /></el-select></el-form-item>
        <el-form-item label="时长(秒)"><el-input-number v-model="form.duration" :min="3" :max="300" style="width:100px" /></el-form-item>
        <el-form-item><el-button type="primary" :loading="submitting" @click="startIperf">开始测速</el-button></el-form-item>
      </el-form>
    </el-card>
    <el-card shadow="never">
      <template #header><el-row justify="space-between" align="middle"><span>测速任务记录</span><el-button size="small" @click="loadTasks">刷新</el-button></el-row></template>
      <el-table v-loading="loading" :data="tasks" stripe border>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="server_host" label="服务端" min-width="130" />
        <el-table-column prop="protocol" label="协议" width="70" />
        <el-table-column prop="status" label="状态" width="100"><template #default="{ row }"><el-tag :type="statusMap[row.status]?.type">{{ statusMap[row.status]?.label }}</el-tag></template></el-table-column>
        <el-table-column label="带宽" width="110"><template #default="{ row }">{{ row.bandwidth_mbps!=null?row.bandwidth_mbps+' Mbps':'-' }}</template></el-table-column>
        <el-table-column label="抖动/丢包" width="120"><template #default="{ row }">{{ row.jitter_ms!=null?row.jitter_ms+'ms / '+row.lost_percent+'%':'-' }}</template></el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="160" />
        <el-table-column label="操作" width="160" fixed="right"><template #default="{ row }"><el-button size="small" type="primary" @click="viewResult(row)">图表</el-button><el-button size="small" type="danger" @click="delTask(row)">删除</el-button></template></el-table-column>
      </el-table>
    </el-card>
    <el-dialog v-model="resultDlg" title="测速结果" width="860px">
      <div v-if="curTask">
        <el-row :gutter="16" style="margin-bottom:16px"><el-col :span="6"><el-statistic title="带宽" :value="curTask.bandwidth_mbps??0" suffix="Mbps" /></el-col><el-col v-if="curTask.protocol==='udp'" :span="6"><el-statistic title="抖动" :value="curTask.jitter_ms??0" suffix="ms" /></el-col><el-col v-if="curTask.protocol==='udp'" :span="6"><el-statistic title="丢包率" :value="curTask.lost_percent??0" suffix="%" /></el-col></el-row>
        <div ref="chartDom" style="height:300px"></div>
      </div>
    </el-dialog>
  </div>
</template>
<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { iperfApi, organizationApi } from '@/api'
import { useAuthStore } from '@/stores/auth'
const authStore = useAuthStore()
const isAdmin = authStore.isAdmin
const orgs = ref([])
const iperfTargets = ref([])
const onlineProbeTargets = computed(() => iperfTargets.value.filter(t => t.type === 'probe'))
const centralTarget = computed(() => iperfTargets.value.find(t => t.type === 'central'))
const loading=ref(false),submitting=ref(false),tasks=ref([]),resultDlg=ref(false),curTask=ref(null),chartDom=ref(null),formRef=ref(null)
let chartInstance=null,pollTimer=null
const isFirstLoad=ref(true)
const form=reactive({org_id:null,target_type:'central',selected_probe:null,server_host:'',server_port:5201,protocol:'tcp',duration:10,parallel:1,reverse:false})
const rules={
  server_host:[{required:true,message:'请输入服务端IP'}],
  org_id: isAdmin ? [{required:true,message:'请选择目标组织'}] : [],
}
const statusMap={pending:{label:'等待中',type:'info'},running:{label:'测速中',type:'warning'},completed:{label:'已完成',type:'success'},failed:{label:'失败',type:'danger'}}
async function loadOrgs(){try{const r=await organizationApi.all();orgs.value=r||[]}catch(e){console.error('加载组织失败',e)}}
async function loadTargets(){try{const r=await iperfApi.targets();iperfTargets.value=r.targets||[]}catch(e){console.error('加载测速目标失败',e)}}
function onTargetTypeChange(v){
  if(v==='central'&&centralTarget.value){form.server_host=centralTarget.value.host;form.server_port=centralTarget.value.port}
  else if(v==='probe'){form.server_host='';form.selected_probe=null}
  else{form.server_host=''}
}
function onProbeSelect(host){form.server_host=host}
async function loadTasks(){if(isFirstLoad.value){loading.value=true;isFirstLoad.value=false};try{const r=await iperfApi.list({size:50});tasks.value=r.items}finally{loading.value=false}}
async function startIperf(){await formRef.value.validate();submitting.value=true;try{await iperfApi.start(form);ElMessage.success('测速任务已提交，等待探针执行');loadTasks()}finally{submitting.value=false}}
async function viewResult(row){const r=await iperfApi.get(row.id);curTask.value=r;resultDlg.value=true;await nextTick();renderChart(r)}
async function renderChart(task){if(!chartDom.value)return;const echarts=await import('echarts');if(!chartInstance)chartInstance=echarts.init(chartDom.value);let intervals=[];if(task.result_json){try{const d=JSON.parse(task.result_json);intervals=(d.intervals??[]).map((iv,i)=>({t:i+1,bw:((iv.sum?.bits_per_second??0)/1e6).toFixed(2)}))}catch{ /* parse optional */ }}chartInstance.setOption({tooltip:{trigger:'axis'},xAxis:{type:'category',data:intervals.map(i=>i.t),name:'时间(s)'},yAxis:{type:'value',name:'Mbps'},series:[{name:'带宽',type:'line',data:intervals.map(i=>i.bw),smooth:true,areaStyle:{opacity:0.1}}]})}
async function delTask(row){await ElMessageBox.confirm('确定删除?','确认',{type:'warning'});await iperfApi.delete(row.id);ElMessage.success('已删除');loadTasks()}
onMounted(()=>{if(isAdmin){loadOrgs()};loadTargets();onTargetTypeChange('central');loadTasks();pollTimer=setInterval(loadTasks,5000)})
onUnmounted(()=>{clearInterval(pollTimer);chartInstance?.dispose()})
</script>
