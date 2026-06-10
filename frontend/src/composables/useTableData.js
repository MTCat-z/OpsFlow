import { ref, reactive } from 'vue'

/**
 * 表格数据加载 composable
 * @param {Function} fetchFn - API 函数 (params) => Promise<{ items, total }>
 * @param {Object} defaultQuery - 默认查询参数
 */
export function useTableData(fetchFn, defaultQuery = {}) {
  const loading = ref(false)
  const tableData = ref([])
  const total = ref(0)
  const query = reactive({
    page: 1,
    size: 20,
    keyword: '',
    ...defaultQuery,
  })

  async function loadData() {
    loading.value = true
    try {
      const r = await fetchFn(query)
      tableData.value = r.items || []
      total.value = r.total || 0
    } finally {
      loading.value = false
    }
  }

  function resetQuery() {
    Object.assign(query, { page: 1, keyword: '', ...defaultQuery })
    loadData()
  }

  return { loading, tableData, total, query, loadData, resetQuery }
}
