<template>
  <el-dialog
    v-model="visible"
    title="批量导入宽带合同"
    width="500px"
    :close-on-click-modal="false"
  >
    <el-alert type="info" :closable="false" style="margin-bottom:16px">
      <template #title>
        请先<a href="#" style="color:#409eff" @click.prevent="$emit('downloadTemplate')">下载模板</a>，按格式填写后上传 Excel 文件
      </template>
    </el-alert>
    <el-upload
      ref="uploadRef"
      :auto-upload="false"
      :show-file-list="true"
      :limit="1"
      accept=".xlsx,.xls"
      @change="onFileChange"
    >
      <template #trigger>
        <el-button type="primary">选择文件</el-button>
      </template>
      <span style="margin-left:12px;font-size:13px;color:#999">仅支持 .xlsx 格式</span>
    </el-upload>
    <div v-if="importResult" style="margin-top:16px">
      <el-alert :title="importResult.message" :type="importResult.errors?.length ? 'warning' : 'success'" :closable="false" />
      <div v-if="importResult.errors?.length" style="margin-top:8px;max-height:200px;overflow:auto">
        <p v-for="(e,i) in importResult.errors" :key="i" style="font-size:13px;color:#e6a23c;margin:2px 0">{{ e }}</p>
      </div>
    </div>
    <template #footer>
      <el-button @click="close">关闭</el-button>
      <el-button type="primary" :loading="importing" :disabled="!selectedFile" @click="doImport">开始导入</el-button>
    </template>
  </el-dialog>
</template>
<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { broadbandApi } from '@/api'

const emit = defineEmits(['downloadTemplate', 'imported'])
const visible = ref(false)
const importing = ref(false)
const selectedFile = ref(null)
const importResult = ref(null)

function open() {
  selectedFile.value = null
  importResult.value = null
  visible.value = true
}
function onFileChange(uploadFile) {
  selectedFile.value = uploadFile.raw
  importResult.value = null
}
async function doImport() {
  if (!selectedFile.value) return ElMessage.warning('请先选择文件')
  importing.value = true
  try {
    const r = await broadbandApi.importExcel(selectedFile.value)
    importResult.value = r
    if (r.imported > 0) {
      ElMessage.success(`成功导入 ${r.imported} 条记录`)
      emit('imported')
    }
  } catch (_e) {
    ElMessage.error('导入失败，请检查文件格式')
  } finally { importing.value = false }
}
function close() {
  visible.value = false
  importResult.value = null
}
defineExpose({ open })
</script>
