import { createRenderer, defineComponent, h, nextTick, type Component } from 'vue'

// A tiny in-memory Vue host for component logic; this is not browser/layout acceptance.
export interface HostNode {
  type: string
  text: string
  props: Record<string, any>
  children: HostNode[]
  parent: HostNode | null
}
function node(type: string, text = ''): HostNode {
  return { type, text, props: {}, children: [], parent: null }
}
const renderer = createRenderer<HostNode, HostNode>({
  createElement: (type) => node(type),
  createText: (text) => node('#text', text),
  createComment: (text) => node('#comment', text),
  setText: (element, text) => {
    element.text = text
  },
  setElementText: (element, text) => {
    element.text = text
    element.children = []
  },
  parentNode: (element) => element.parent,
  nextSibling: (element) => element.parent?.children[element.parent.children.indexOf(element) + 1] || null,
  patchProp: (element, key, _old, value) => {
    element.props[key] = value
  },
  insert(element, parent, anchor = null) {
    if (element.parent) element.parent.children.splice(element.parent.children.indexOf(element), 1)
    element.parent = parent
    const index = anchor ? parent.children.indexOf(anchor) : -1
    if (index < 0) parent.children.push(element)
    else parent.children.splice(index, 0, element)
  },
  remove(element) {
    if (element.parent) element.parent.children.splice(element.parent.children.indexOf(element), 1)
    element.parent = null
  },
})
const tags = [
  'el-alert',
  'el-button',
  'el-input',
  'el-select',
  'el-option',
  'el-upload',
  'el-table',
  'el-table-column',
  'el-pagination',
  'el-descriptions',
  'el-descriptions-item',
  'el-form',
  'el-form-item',
  'el-input-number',
  'el-checkbox',
  'el-empty',
  'el-tag',
  'el-radio-group',
  'el-radio-button',
  'el-icon',
  'el-dropdown',
  'el-dropdown-menu',
  'el-dropdown-item',
  'el-tooltip',
]
export function mount(
  component: Component,
  props: Record<string, unknown> = {},
  options: { tableRows?: Record<string, unknown>[] } = {},
) {
  const root = node('root')
  const app = renderer.createApp(component, props)
  for (const tag of tags) {
    app.component(
      tag,
      defineComponent({
        inheritAttrs: false,
        props: tag === 'el-upload' ? ['httpRequest'] : [],
        setup(props, { attrs, slots }) {
          return () =>
            h(tag, { ...attrs, ...props }, [
              // Scoped rows must be supplied explicitly by the test, never invented by the host.
              ...(tag === 'el-table-column'
                ? (options.tableRows || []).flatMap((row) => slots.default?.({ row }) || [])
                : slots.default?.() || []),
              ...(slots.footer?.() || []),
              ...(slots.dropdown?.() || []),
            ])
        },
      }),
    )
  }
  for (const tag of ['el-drawer', 'el-dialog']) {
    app.component(
      tag,
      defineComponent({
        inheritAttrs: false,
        setup(_, { attrs, slots }) {
          return () =>
            h(tag, attrs, attrs.modelValue ? [...(slots.default?.() || []), ...(slots.footer?.() || [])] : [])
        },
      }),
    )
  }
  app.directive('loading', {})
  app.mount(root)
  return { root, unmount: () => app.unmount() }
}
export function all(root: HostNode, predicate: (node: HostNode) => boolean): HostNode[] {
  return [...(predicate(root) ? [root] : []), ...root.children.flatMap((child) => all(child, predicate))]
}
export function text(root: HostNode): string {
  return root.type === '#comment' ? '' : root.text + root.children.map(text).join('')
}
export function button(root: HostNode, label: string): HostNode {
  const match = all(root, (element) => element.type === 'el-button' && text(element).trim() === label)[0]
  if (!match) throw new Error(`Missing button: ${label}`)
  return match
}
export async function flush() {
  // Resolve the view's API -> computed/watch -> render chain without a browser.
  for (let i = 0; i < 12; i++) {
    await Promise.resolve()
    await nextTick()
  }
}
