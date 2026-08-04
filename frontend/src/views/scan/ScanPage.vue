<template>
  <div>
    <el-card shadow="never" style="margin-bottom:16px"><template #header>新建扫描任务</template>
      <el-form ref="formRef" :model="form" :rules="rules" inline label-width="90px">
        <el-form-item v-if="isAdmin" label="目标组织" prop="org_id"><el-select v-model="form.org_id" placeholder="选择分公司" style="width:180px"><el-option v-for="o in orgs" :key="o.id" :label="o.name" :value="o.id" /></el-select></el-form-item>
        <el-form-item label="扫描目标" prop="target"><el-input v-model="form.target" placeholder="192.168.1.0/24" style="width:220px" /></el-form-item>
        <el-form-item label="扫描类型"><el-select v-model="form.scan_type" style="width:130px"><el-option label="存活探测" value="ping" /><el-option label="端口扫描" value="port" /><el-option label="服务探测" value="service" /><el-option label="全面扫描" value="full" /></el-select></el-form-item>
        <el-form-item label="端口范围"><el-input v-model="form.ports" placeholder="1-1024" style="width:120px" :disabled="form.scan_type==='ping'" /></el-form-item>
        <el-form-item><el-button type="primary" :loading="submitting" @click="startScan">开始扫描</el-button></el-form-item>
      </el-form>
    </el-card>
    <el-card shadow="never">
      <template #header><el-row justify="space-between" align="middle"><span>扫描任务记录</span><el-button size="small" @click="loadTasks">刷新</el-button></el-row></template>
      <el-table v-loading="loading" :data="tasks" stripe border>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="target" label="目标" min-width="160" />
        <el-table-column prop="scan_type" label="类型" width="100" />
        <el-table-column prop="status" label="状态" width="100"><template #default="{ row }"><el-tag :type="statusMap[row.status]?.type">{{ statusMap[row.status]?.label }}</el-tag></template></el-table-column>
        <el-table-column label="进度" width="120"><template #default="{ row }"><el-progress :percentage="row.progress || 0" :status="row.status==='completed'?'success':row.status==='failed'?'exception':''" :stroke-width="6" /></template></el-table-column>
        <el-table-column prop="host_count" label="存活主机" width="90" align="center" />
        <el-table-column prop="port_count" label="开放端口" width="90" align="center" />
        <el-table-column prop="created_at" label="创建时间" width="160" />
        <el-table-column label="操作" width="160" fixed="right"><template #default="{ row }"><el-button size="small" type="primary" @click="viewResult(row)">查看结果</el-button><el-button size="small" type="danger" @click="delTask(row)">删除</el-button></template></el-table-column>
      </el-table>
    </el-card>
    <el-dialog v-model="resultDlg" title="扫描结果" width="800px">
      <div v-if="curTask"><el-descriptions :column="3" border style="margin-bottom:16px"><el-descriptions-item label="目标">{{ curTask.target }}</el-descriptions-item><el-descriptions-item label="存活主机">{{ curTask.host_count }}</el-descriptions-item></el-descriptions><el-table :data="resultHosts" border max-height="400"><el-table-column prop="ip" label="IP" width="140" /><el-table-column prop="state" label="状态" width="80" /><el-table-column label="开放端口"><template #default="{ row }"><el-tag v-for="p in row.ports" :key="p.port" size="small" style="margin:2px">{{ p.port }}/{{ p.protocol }}</el-tag></template></el-table-column></el-table></div>
    </el-dialog>
  </div>
</template>
<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { scanApi, organizationApi } from '@/api'
import { useAuthStore } from '@/stores/auth'
const authStore = useAuthStore()
const isAdmin = authStore.isAdmin
const orgs = ref([])
const loading=ref(false),submitting=ref(false),tasks=ref([]),resultDlg=ref(false),curTask=ref(null),resultHosts=ref([]),formRef=ref(null)
const form=reactive({org_id:null,target:'',scan_type:'ping',ports:'',description:''})
const rules={
  target:[{required:true,message:'请输入扫描目标'}],
  org_id: isAdmin ? [{required:true,message:'请选择目标组织'}] : [],
}
const statusMap={pending:{label:'等待中',type:'info'},running:{label:'扫描中',type:'warning'},completed:{label:'已完成',type:'success'},failed:{label:'失败',type:'danger'}}
let pollTimer=null
const isFirstLoad=ref(true)
async function loadOrgs(){try{const r=await organizationApi.all();orgs.value=r||[]}catch(e){console.error('加载组织失败',e)}}
async function loadTasks(){
  if(isFirstLoad.value){loading.value=true;isFirstLoad.value=false}
  try{const r=await scanApi.list({size:50});tasks.value=r.items||[]}catch(e){console.error('加载扫描任务失败',e)}finally{loading.value=false}
}
async function startScan(){await formRef.value.validate();submitting.value=true;try{await scanApi.start(form);ElMessage.success('扫描任务已提交，等待探针执行');loadTasks()}finally{submitting.value=false}}
async function viewResult(row){const r=await scanApi.get(row.id);curTask.value=r;resultHosts.value=r.result_json?JSON.parse(r.result_json).hosts??[]:[]; resultDlg.value=true}
async function delTask(row){await ElMessageBox.confirm('确定删除?','确认',{type:'warning'});await scanApi.delete(row.id);ElMessage.success('已删除');loadTasks()}
onMounted(()=>{if(isAdmin){loadOrgs()};loadTasks();pollTimer=setInterval(loadTasks,5000)})
onUnmounted(()=>clearInterval(pollTimer))
</script>
