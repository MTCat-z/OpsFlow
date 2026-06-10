import { ref } from 'vue'

/**
 * 拓扑图 G6 渲染 composable
 * 封装 G6 动态导入、图实例管理、节点/边数据转换、事件绑定和布局切换
 */

// 节点颜色映射
const COLOR_MAP = {
  router: '#f56c6c',
  switch: '#e6a23c',
  server: '#409eff',
  firewall: '#909399',
  ap: '#67c23a',
  endpoint: '#909399',
  unknown: '#c0c4cc',
}

/** 将后端节点转为 G6 节点数据 */
function nodeToG6(n) {
  const color = COLOR_MAP[n.device_type] || '#c0c4cc'
  const style = {
    labelText: `${n.name}\n${n.ip_address || ''}`.trim(),
    labelFill: '#333',
    labelFontSize: 11,
    labelPlacement: 'bottom',
    labelOffsetY: 8,
    fill: color,
    stroke: '#333',
    lineWidth: 1,
    size: 36,
  }
  if (n.position_x && n.position_x !== 0) style.x = n.position_x
  if (n.position_y && n.position_y !== 0) style.y = n.position_y
  return { id: `node-${n.id}`, data: { _raw: n }, style, type: 'circle' }
}

/** 将后端边转为 G6 边数据 */
function edgeToG6(e) {
  return {
    id: `edge-${e.id}`,
    source: `node-${e.source_node_id}`,
    target: `node-${e.target_node_id}`,
    data: { _raw: e },
    style: {
      stroke: e.style === 'dashed' ? '#aaa' : '#666',
      lineDash: e.style === 'dashed' ? [5, 3] : undefined,
      lineWidth: 1.5,
    },
  }
}

/** 根据布局类型生成 G6 layout 配置 */
function getLayoutConfig(layoutType) {
  if (layoutType === 'dagre') return { type: 'dagre', rankdir: 'TB', nodesep: 40, ranksep: 60 }
  if (layoutType === 'force') return { type: 'd3-force', linkDistance: 120, nodeSize: 40 }
  return { type: 'circular', radius: 200 }
}

/**
 * useTopologyGraph composable
 * @param {Object} options
 * @param {Function} options.onNodeClick - 点击节点回调(rawNode)
 * @param {Function} options.onEdgeClick - 点击边回调(rawEdge)
 * @param {Function} options.onCanvasClick - 点击画布回调
 * @param {Function} options.onNodeDragEnd - 拖拽结束回调(rawNode, position)
 */
export function useTopologyGraph({ onNodeClick, onEdgeClick, onCanvasClick, onNodeDragEnd } = {}) {
  const graphDom = ref(null)
  let graph = null

  async function renderGraph(nodes, edges, layoutType) {
    if (!graphDom.value) return

    const w = graphDom.value.clientWidth
    const h = graphDom.value.clientHeight || 540
    if (w <= 0) {
      console.warn('拓扑图容器宽度为 0，跳过渲染')
      return
    }

    // 动态导入 G6
    let G6
    try {
      G6 = await import('@antv/g6')
    } catch (_e) {
      graphDom.value.innerHTML =
        '<div style="padding:40px;text-align:center;color:#999">请安装 @antv/g6 依赖: <code>npm install @antv/g6</code></div>'
      return
    }

    if (graph) {
      graph.destroy()
      graph = null
    }

    const g6Nodes = nodes.map(nodeToG6)
    const g6Edges = edges.map(edgeToG6)

    if (!g6Nodes.length) {
      graphDom.value.innerHTML =
        '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#999;font-size:14px">暂无拓扑数据，请添加节点或执行自动发现</div>'
      return
    }

    try {
      graph = new G6.Graph({
        container: graphDom.value,
        width: w,
        height: Math.max(500, h),
        autoFit: 'view',
        padding: 40,
        data: { nodes: g6Nodes, edges: g6Edges },
        layout: getLayoutConfig(layoutType || 'dagre'),
        behaviors: ['drag-canvas', 'zoom-canvas', 'drag-element', 'click-select'],
        animation: false,
      })

      await graph.render()

      // 事件绑定
      graph.on('node:click', (evt) => {
        const id = evt.target?.id
        if (!id) return
        const nodeData = graph.getNodeData(id)
        onNodeClick?.(nodeData?.data?._raw || null)
      })
      graph.on('edge:click', (evt) => {
        const id = evt.target?.id
        if (!id) return
        const edgeData = graph.getEdgeData(id)
        onEdgeClick?.(edgeData?.data?._raw || null)
      })
      graph.on('canvas:click', () => {
        onCanvasClick?.()
      })
      graph.on('node:dragend', async (evt) => {
        const id = evt.target?.id
        if (!id) return
        const nodeData = graph.getNodeData(id)
        if (nodeData?.data?._raw) {
          const pos = graph.getNodePosition(id)
          onNodeDragEnd?.(nodeData.data._raw, { position_x: pos[0], position_y: pos[1] })
        }
      })
    } catch (e) {
      console.error('G6 渲染失败', e)
      graphDom.value.innerHTML = `<div style="padding:40px;text-align:center;color:#f56c6c">拓扑图渲染失败: ${e.message || e}</div>`
    }
  }

  function resize() {
    if (graph) {
      try {
        graph.resize(graphDom.value?.clientWidth, Math.max(500, graphDom.value?.clientHeight || 540))
      } catch (_e) {
        /* ignore */
      }
    }
  }

  function destroy() {
    if (graph) {
      graph.destroy()
      graph = null
    }
  }

  return { graphDom, renderGraph, resize, destroy }
}
