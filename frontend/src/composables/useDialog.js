import { ref, reactive } from 'vue'

/**
 * CRUD 对话框状态 composable
 * @param {Object} defaultForm - 表单默认值
 */
export function useDialog(defaultForm = {}) {
  const visible = ref(false)
  const isEdit = ref(false)
  const editId = ref(null)
  const submitting = ref(false)
  const form = reactive({ ...defaultForm })

  function openCreate() {
    isEdit.value = false
    editId.value = null
    Object.assign(form, { ...defaultForm })
    visible.value = true
  }

  function openEdit(row, idField = 'id') {
    isEdit.value = true
    editId.value = row[idField]
    Object.assign(form, { ...row })
    visible.value = true
  }

  function close() {
    visible.value = false
  }

  return { visible, isEdit, editId, submitting, form, openCreate, openEdit, close }
}
