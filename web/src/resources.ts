import { toRaw } from 'vue'

export interface Option {
  label: string
  value: string
}
export interface Field {
  key: string
  label: string
  type?:
    | 'text'
    | 'textarea'
    | 'number'
    | 'money'
    | 'select'
    | 'relation'
    | 'tags'
    | 'datetime'
    | 'image'
    | 'variants'
    | 'password'
  required?: boolean
  options?: Option[]
  resource?: string
  multiple?: boolean
  min?: number
  max?: number
  default?: unknown
  precision?: number
  operationsOnly?: boolean
}
export interface Column {
  key: string
  label: string
  width?: number
  type?: 'status' | 'date' | 'money' | 'image'
}
export interface Resource {
  title: string
  singular: string
  group: string
  fields: Field[]
  columns: Column[]
  idEditable?: boolean
}
const text = (key: string, label: string, required = false): Field => ({ key, label, required })
const area = (key: string, label: string, required = false): Field => ({
  key,
  label,
  type: 'textarea',
  required,
})
const rel = (key: string, label: string, resource: string, required = false, multiple = false): Field => ({
  key,
  label,
  type: 'relation',
  resource,
  required,
  multiple,
})
const num = (key: string, label: string, min = 0, value: number | null = 0, max?: number): Field => ({
  key,
  label,
  type: 'number',
  min,
  max,
  default: value,
})
const dates: Field[] = [
  { key: 'start_at', label: '开始时间', type: 'datetime', required: true },
  { key: 'end_at', label: '结束时间', type: 'datetime', required: true },
]
const statusColumn: Column = { key: 'status', label: '状态', type: 'status', width: 110 }
const image = (key = 'image_url', label = '展示图片'): Field => ({ key, label, type: 'image' })

export const statusOptions: Option[] = [
  { label: '草稿', value: 'draft' },
  { label: '已审核', value: 'reviewed' },
  { label: '已发布', value: 'published' },
  { label: '已停用', value: 'disabled' },
]
export const statusLabels: Record<string, string> = {
  draft: '草稿',
  reviewed: '已审核',
  published: '已发布',
  disabled: '已停用',
  active: '正常',
  pending: '待审核',
  approved: '已通过',
  rejected: '已驳回',
  confirmed: '已确认',
  used: '已核销',
  redeemed: '已核销',
  claimed: '待核销',
  available: '待核销',
  expired: '已过期',
  success: '成功',
  failed: '失败',
  unavailable: '不可用',
  needs_confirmation: '待确认',
}
export const resources: Record<string, Resource> = {
  characters: {
    title: '东巴字典',
    singular: '词条',
    group: '内容中心',
    idEditable: true,
    columns: [
      { key: 'image_url', label: '字形', type: 'image', width: 74 },
      { key: 'cn_name', label: '中文释义' },
      { key: 'source_no', label: '原资料编号', width: 120 },
      { key: 'category_l1', label: '一级分类' },
      { key: 'source_ref', label: '资料来源' },
      statusColumn,
    ],
    fields: [
      text('id', '词条编号', true),
      text('cn_name', '中文释义', true),
      num('source_no', '原资料编号', 0, null),
      { key: 'alias', label: '别名', type: 'tags' },
      text('category_l1', '一级分类', true),
      text('category_l2', '二级分类'),
      area('culture_summary', '文化摘要', true),
      area('culture_detail', '文化故事'),
      text('source_ref', '资料来源', true),
      image(),
      text('audio_url', '读音音频地址'),
      { key: 'tags', label: '主题标签', type: 'tags' },
      { key: 'keywords', label: '检索关键词', type: 'tags' },
      { key: 'commercial_tags', label: '商业标签', type: 'tags' },
      { key: 'variants', label: '同字异形', type: 'variants' },
    ],
  },
  merchants: {
    title: '商户管理',
    singular: '商户',
    group: '商户与地图',
    columns: [
      { key: 'name', label: '门店名称' },
      { key: 'address', label: '地址' },
      { key: 'phone', label: '联系电话', width: 150 },
      statusColumn,
    ],
    fields: [
      text('name', '门店名称', true),
      area('description', '门店简介'),
      text('address', '门店地址', true),
      num('latitude', '纬度（GCJ-02）', -90, null, 90),
      num('longitude', '经度（GCJ-02）', -180, null, 180),
      text('phone', '联系电话'),
      text('opening_hours', '营业时间'),
      image(),
      { key: 'tags', label: '主题标签', type: 'tags' },
      rel('character_ids', '关联东巴字', 'characters', false, true),
      { ...num('merchant_quality', '商户质量评分', 0, 0.5, 1), precision: 2, operationsOnly: true },
      { ...num('operation_weight', '运营推荐评分', 0, 0.5, 1), precision: 2, operationsOnly: true },
    ],
  },
  pois: {
    title: '文化地图点位',
    singular: '点位',
    group: '商户与地图',
    columns: [
      { key: 'name', label: '点位名称' },
      { key: 'poi_type', label: '类型', width: 130 },
      { key: 'latitude', label: '纬度', width: 120 },
      { key: 'longitude', label: '经度', width: 120 },
      statusColumn,
    ],
    fields: [
      text('name', '点位名称', true),
      area('description', '简介'),
      {
        key: 'poi_type',
        label: '点位类型',
        type: 'select',
        required: true,
        default: 'culture',
        options: [
          { label: '文化场所', value: 'culture' },
          { label: '景点', value: 'attraction' },
          { label: '门店', value: 'merchant' },
        ],
      },
      { ...num('latitude', '纬度（GCJ-02）', -90, null, 90), required: true },
      { ...num('longitude', '经度（GCJ-02）', -180, null, 180), required: true },
      rel('merchant_id', '关联商户', 'merchants'),
      rel('character_ids', '关联东巴字', 'characters', false, true),
    ],
  },
  products: {
    title: '商品管理',
    singular: '商品',
    group: '商户与地图',
    columns: [
      { key: 'image_url', label: '图片', type: 'image', width: 74 },
      { key: 'name', label: '商品名称' },
      { key: 'merchant_id', label: '所属商户' },
      { key: 'price', label: '价格', type: 'money', width: 110 },
      statusColumn,
    ],
    fields: [
      rel('merchant_id', '所属商户', 'merchants', true),
      text('name', '商品名称', true),
      { key: 'price', label: '价格（元）', type: 'money', min: 0, default: 0, required: true },
      area('description', '商品简介'),
      image(),
      rel('character_ids', '关联东巴字', 'characters', false, true),
    ],
  },
  coupons: {
    title: '优惠券',
    singular: '优惠券',
    group: '运营活动',
    columns: [
      { key: 'title', label: '优惠券名称' },
      { key: 'stock', label: '总库存', width: 100 },
      { key: 'claimed_count', label: '已领取', width: 100 },
      { key: 'end_at', label: '有效期至', type: 'date', width: 180 },
      statusColumn,
    ],
    fields: [
      rel('merchant_id', '所属商户', 'merchants', true),
      text('title', '优惠券名称', true),
      area('rule', '领取及使用规则', true),
      num('stock', '总库存', 0),
      num('per_user_limit', '每人限领', 1, 1),
      ...dates,
    ],
  },
  activities: {
    title: '体验活动',
    singular: '活动',
    group: '运营活动',
    columns: [
      { key: 'name', label: '活动名称' },
      { key: 'merchant_id', label: '所属商户' },
      { key: 'capacity', label: '人数限制', width: 110 },
      { key: 'start_at', label: '开始时间', type: 'date', width: 180 },
      statusColumn,
    ],
    fields: [
      rel('merchant_id', '所属商户', 'merchants', true),
      text('name', '活动名称', true),
      area('description', '活动与预约说明', true),
      ...dates,
      num('capacity', '人数限制', 1, 20),
    ],
  },
  quests: {
    title: '寻迹路线',
    singular: '路线',
    group: '寻迹任务',
    columns: [
      { key: 'name', label: '路线名称' },
      { key: 'area', label: '所在区域' },
      { key: 'start_at', label: '开始时间', type: 'date', width: 180 },
      statusColumn,
    ],
    fields: [
      text('name', '路线名称', true),
      text('area', '所在区域', true),
      area('description', '路线说明'),
      ...dates,
      rel('reward_coupon_id', '完成奖励', 'coupons'),
    ],
  },
  'quest-nodes': {
    title: '任务节点',
    singular: '节点',
    group: '寻迹任务',
    columns: [
      { key: 'name', label: '节点名称' },
      { key: 'quest_id', label: '所属路线' },
      { key: 'condition', label: '完成条件', width: 120 },
      { key: 'sequence', label: '顺序', width: 90 },
      statusColumn,
    ],
    fields: [
      rel('quest_id', '所属路线', 'quests', true),
      text('name', '节点名称', true),
      num('sequence', '节点顺序', 1, 1),
      {
        key: 'condition',
        label: '完成条件',
        type: 'select',
        default: 'recognition',
        required: true,
        options: [
          { label: '识别东巴字', value: 'recognition' },
          { label: '扫码', value: 'qr' },
          { label: '到达地点', value: 'geofence' },
          { label: '优惠券核销', value: 'coupon' },
          { label: '人工确认', value: 'manual' },
        ],
      },
      rel('character_id', '目标东巴字', 'characters'),
      rel('merchant_id', '目标商户', 'merchants'),
      rel('poi_id', '目标点位', 'pois'),
      num('radius_m', '打卡半径（米）', 10, 100, 1000),
      text('qr_token', '扫码口令'),
    ],
  },
  users: {
    title: '账号与权限',
    singular: '账号',
    group: '系统管理',
    columns: [
      { key: 'username', label: '登录账号' },
      { key: 'display_name', label: '显示名称' },
      { key: 'role', label: '角色', width: 120 },
      { key: 'merchant_id', label: '关联商户' },
      statusColumn,
    ],
    fields: [
      text('username', '登录账号', true),
      text('display_name', '显示名称', true),
      { key: 'password', label: '密码', type: 'password' },
      {
        key: 'role',
        label: '角色',
        type: 'select',
        required: true,
        default: 'operator',
        options: [
          { label: '运营人员', value: 'operator' },
          { label: '商户', value: 'merchant' },
          { label: '管理员', value: 'admin' },
        ],
      },
      rel('merchant_id', '关联商户', 'merchants'),
    ],
  },
}

export function initialForm(resource: Resource, row?: Record<string, any>): Record<string, any> {
  const value: Record<string, any> = {}
  for (const field of resource.fields) {
    if (field.key === 'password') {
      value.password = ''
      continue
    }
    value[field.key] = structuredClone(
      toRaw(
        row && Object.hasOwn(row, field.key)
          ? row[field.key]
          : field.default !== undefined
            ? field.default
            : field.multiple || field.type === 'tags' || field.type === 'variants'
              ? []
              : field.type === 'number' || field.type === 'money'
                ? 0
                : '',
      ),
    )
  }
  return value
}
export function payloadFor(
  resource: Resource,
  form: Record<string, any>,
  merchant: boolean,
  editing: boolean,
): Record<string, any> {
  const output: Record<string, any> = {}
  for (const field of resource.fields) {
    if (
      (merchant &&
        (field.key === 'merchant_id' ||
          field.key === 'character_ids' ||
          field.key === 'tags' ||
          field.operationsOnly)) ||
      (editing && field.key === 'id')
    )
      continue
    const value = form[field.key]
    if (['latitude', 'longitude', 'source_no'].includes(field.key) && value == null) {
      output[field.key] = null
      continue
    }
    if (field.key === 'password' && !value && editing) continue
    output[field.key] =
      ((field.type === 'relation' && !field.multiple) || field.key === 'qr_token') && !value ? null : value
  }
  return output
}
