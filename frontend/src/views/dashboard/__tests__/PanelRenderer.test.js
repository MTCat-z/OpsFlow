import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import PanelRenderer from '../PanelRenderer.vue'

// 给 jsdom 元素一个固定非 0 尺寸，使 hasSize() 通过
const mockRect = { width: 400, height: 300, top: 0, left: 0, bottom: 300, right: 400 }
HTMLElement.prototype.getBoundingClientRect = vi.fn(() => mockRect)

const mockChart = {
  setOption: vi.fn(),
  resize: vi.fn(),
  dispose: vi.fn(),
}
const mockInit = vi.fn(() => mockChart)

vi.mock('echarts', () => ({
  __esModule: true,
  default: { init: mockInit },
  init: mockInit,
}))

const resizeObservers = []
class ResizeObserverMock {
  constructor(callback) {
    this.callback = callback
    this.observed = []
    resizeObservers.push(this)
  }
  observe(el) {
    this.observed.push(el)
  }
  disconnect() {
    this.observed = []
    const idx = resizeObservers.indexOf(this)
    if (idx > -1) resizeObservers.splice(idx, 1)
  }
}
globalThis.ResizeObserver = ResizeObserverMock

describe('PanelRenderer', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    resizeObservers.length = 0
  })

  afterEach(() => {
    resizeObservers.length = 0
  })

  it('line 图表在数据到达后初始化一次 echarts', async () => {
    mount(PanelRenderer, {
      props: {
        chartType: 'line',
        sourceType: 'zabbix_item',
        data: { series: [{ t: 1, v: 10 }], item_name: '测试项' },
      },
      attachTo: document.body,
    })
    await flushPromises()
    expect(mockInit).toHaveBeenCalledTimes(1)
    expect(mockChart.setOption).toHaveBeenCalled()
  })

  it('data.error 优先展示，不视为空数据', async () => {
    const wrapper = mount(PanelRenderer, {
      props: {
        chartType: 'line',
        sourceType: 'zabbix_item',
        data: { error: 'Zabbix 查询失败', series: [] },
      },
      attachTo: document.body,
    })
    await flushPromises()
    expect(wrapper.text()).toContain('Zabbix 查询失败')
    expect(wrapper.text()).not.toContain('暂无数据')
    expect(mockInit).not.toHaveBeenCalled()
  })

  it('空 line 数据不初始化图表，显示暂无数据', async () => {
    const wrapper = mount(PanelRenderer, {
      props: {
        chartType: 'line',
        sourceType: 'zabbix_item',
        data: { series: [] },
      },
      attachTo: document.body,
    })
    await flushPromises()
    expect(wrapper.text()).toContain('暂无数据')
    expect(mockInit).not.toHaveBeenCalled()
  })

  it('chartType 从 line 切换为 stat 时释放 echarts 实例并断开 ResizeObserver', async () => {
    const wrapper = mount(PanelRenderer, {
      props: {
        chartType: 'line',
        sourceType: 'zabbix_item',
        data: { series: [{ t: 1, v: 10 }] },
      },
      attachTo: document.body,
    })
    await flushPromises()
    expect(mockInit).toHaveBeenCalledTimes(1)
    expect(resizeObservers.length).toBe(1)

    await wrapper.setProps({ chartType: 'stat', sourceType: 'iperf_recent', data: { values: {} } })
    await flushPromises()

    expect(mockChart.dispose).toHaveBeenCalledTimes(1)
    expect(resizeObservers.length).toBe(0)
  })

  it('chartType 从 stat 切回 line 时能重新渲染', async () => {
    const wrapper = mount(PanelRenderer, {
      props: {
        chartType: 'stat',
        sourceType: 'iperf_recent',
        data: { values: { bandwidth_mbps: 100 } },
      },
      attachTo: document.body,
    })
    await flushPromises()
    expect(mockInit).not.toHaveBeenCalled()

    await wrapper.setProps({
      chartType: 'line',
      sourceType: 'zabbix_item',
      data: { series: [{ t: 1, v: 10 }] },
    })
    await nextTick()
    await flushPromises()
    expect(mockInit).toHaveBeenCalledTimes(1)
  })

  it('line 图表触发 resize 时不会重复初始化多个实例', async () => {
    mount(PanelRenderer, {
      props: {
        chartType: 'line',
        sourceType: 'zabbix_item',
        data: { series: [{ t: 1, v: 10 }] },
      },
      attachTo: document.body,
    })
    await flushPromises()

    const ro = resizeObservers[0]
    expect(ro).toBeDefined()
    // 模拟 layout transition 中连续触发多次 ResizeObserver 回调
    ro.callback()
    ro.callback()
    ro.callback()
    await flushPromises()

    // 已初始化完成，后续 resize 只应触发 resize()，不应重复 init()
    expect(mockInit).toHaveBeenCalledTimes(1)
    expect(mockChart.resize).toHaveBeenCalledTimes(3)
  })
})
