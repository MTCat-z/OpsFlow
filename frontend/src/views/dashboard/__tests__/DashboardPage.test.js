import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

// mock element-plus 消息框，避免依赖真实 DOM 弹层
vi.mock('element-plus', async () => {
  const actual = await vi.importActual('element-plus')
  return {
    ...actual,
    ElMessageBox: {
      confirm: vi.fn(() => Promise.resolve()),
    },
    ElMessage: {
      success: vi.fn(),
      error: vi.fn(),
      warning: vi.fn(),
    },
  }
})

const mockListPanels = vi.fn()
const mockInitDefaults = vi.fn()
const mockDeletePanel = vi.fn()
const mockGetPanelData = vi.fn()

vi.mock('@/api', () => ({
  dashboardApi: {
    listPanels: (...args) => mockListPanels(...args),
    initDefaults: (...args) => mockInitDefaults(...args),
    deletePanel: (...args) => mockDeletePanel(...args),
    getPanelData: (...args) => mockGetPanelData(...args),
    createPanel: vi.fn(),
    updatePanel: vi.fn(),
    saveLayout: vi.fn(),
  },
  organizationApi: {
    all: vi.fn(() => Promise.resolve([])),
  },
  zabbixApi: {
    orgHosts: vi.fn(() => Promise.resolve({ items: [] })),
    orgItems: vi.fn(() => Promise.resolve({ items: [] })),
  },
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    isAdmin: false,
    orgId: 1,
    user: { role: 'user', org_id: 1 },
  }),
}))

describe('DashboardPage initDefaults 修复验证', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockListPanels.mockResolvedValue({ items: [] })
    mockGetPanelData.mockResolvedValue({ empty: true })
  })

  it('initDefaults 部分删除失败后仍刷新面板列表，避免 UI 与后端状态不一致', async () => {
    const { default: DashboardPage } = await import('../DashboardPage.vue')

    const panels = [
      { id: 1, title: 'P1', grid_position: { x: 0, y: 0, w: 6, h: 4 }, source_type: 'iperf_recent', chart_type: 'stat', source_config: {} },
      { id: 2, title: 'P2', grid_position: { x: 6, y: 0, w: 6, h: 4 }, source_type: 'iperf_recent', chart_type: 'stat', source_config: {} },
      { id: 3, title: 'P3', grid_position: { x: 0, y: 4, w: 6, h: 4 }, source_type: 'iperf_recent', chart_type: 'stat', source_config: {} },
    ]

    mockListPanels.mockResolvedValue({ items: panels })

    mockDeletePanel.mockImplementation((id) => {
      if (id === 2) return Promise.reject(new Error('network error'))
      return Promise.resolve()
    })

    const wrapper = mount(DashboardPage, {
      global: {
        components: {
          'grid-layout': { template: '<div><slot /></div>' },
          'grid-item': { props: ['i'], template: '<div><slot /></div>' },
        },
        stubs: {
          PanelRenderer: true,
          ElSelect: true,
          ElOption: true,
          ElTag: true,
          ElSwitch: true,
          ElButton: true,
          ElDialog: true,
          ElForm: true,
          ElFormItem: true,
          ElInput: true,
          ElSlider: true,
          ElEmpty: true,
          ElCard: true,
          ElTable: true,
          ElTableColumn: true,
        },
      },
    })

    await flushPromises()

    // onMounted 调用了 loadPanels（第1次）
    expect(mockListPanels).toHaveBeenCalledTimes(1)

    // 调用 initDefaults
    await wrapper.vm.initDefaults()
    await flushPromises()

    // 循环中第2个删除失败，异常被外层 catch 捕获后循环中断，只调用了2次
    expect(mockDeletePanel).toHaveBeenCalledTimes(2)
    expect(mockDeletePanel).toHaveBeenNthCalledWith(1, 1)
    expect(mockDeletePanel).toHaveBeenNthCalledWith(2, 2)

    // 关键断言：即使删除失败，finally 中 listPanels 仍被再次调用以同步真实状态
    expect(mockListPanels).toHaveBeenCalledTimes(2)
  })
})
